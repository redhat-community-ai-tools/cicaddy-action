"""Local tools for dependency impact analysis on pull requests.

These tools collect dependency context for AI-assisted impact assessment:
- Dependency diffs via GitHub Dependency Review API
- Usage analysis via Go toolchain
- Upstream changelogs via GitHub Releases API
- Security advisories via GitHub Global Advisories API
- Vulnerability reachability via govulncheck
"""

import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from cicaddy.tools import tool

from cicaddy_github.validation import validate_git_ref

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"

# Timeout constants (seconds)
_GITHUB_API_TIMEOUT = 30
_GO_TOOLCHAIN_TIMEOUT = 60
_GOVULNCHECK_TIMEOUT = 300

# Go module names: alphanumeric, dots, hyphens, underscores, slashes, tildes, plus
# Must not contain whitespace, shell metacharacters, or control characters.
_SAFE_MODULE_NAME = re.compile(
    r"^[a-zA-Z0-9._/\-~+@]+$"
)

# GitHub repository format: owner/repo
_REPO_FORMAT = re.compile(r"^[\w.-]+/[\w.-]+$")


def _get_working_dir() -> str:
    """Get the git working directory from environment or default."""
    return os.getenv(
        "LOCAL_TOOLS_WORKING_DIR",
        os.getenv("GITHUB_WORKSPACE", os.getcwd()),
    )


def _github_api_get(path: str, headers: dict[str, str]) -> bytes:
    """Make a GET request to the GitHub API.

    All URLs are constructed from the trusted _GITHUB_API base.
    """
    url = f"{_GITHUB_API}{path}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(  # nosec B310
        req, timeout=_GITHUB_API_TIMEOUT
    ) as resp:
        return resp.read()


def _github_api_post(
    path: str, headers: dict[str, str], payload: bytes
) -> bytes:
    """Make a POST request to the GitHub API."""
    url = f"{_GITHUB_API}{path}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(  # nosec B310
        req, timeout=_GITHUB_API_TIMEOUT
    ) as resp:
        return resp.read()


def _get_github_api_headers() -> dict[str, str]:
    """Get headers for GitHub API requests."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _validate_repository(repository: str) -> str | None:
    """Validate GITHUB_REPOSITORY format (owner/repo).

    Returns an error message if invalid, None if valid.
    """
    if not repository:
        return "Error: GITHUB_REPOSITORY environment variable not set."
    if not _REPO_FORMAT.match(repository):
        return (
            f"Error: Invalid GITHUB_REPOSITORY format: {repository!r}. "
            "Expected owner/repo."
        )
    return None


@tool
def get_dependency_diff(base_ref: str, head_ref: str) -> str:
    """Get structured dependency changes between two refs via GitHub API.

    Returns JSON with changed dependencies including package names, versions,
    ecosystems, and inline vulnerability data.

    Args:
        base_ref: Base ref (branch, tag, or SHA) for comparison.
        head_ref: Head ref (branch, tag, or SHA) for comparison.
    """
    validate_git_ref(base_ref, "base_ref")
    validate_git_ref(head_ref, "head_ref")

    repository = os.getenv("GITHUB_REPOSITORY", "")
    error = _validate_repository(repository)
    if error:
        return error

    path = (
        f"/repos/{repository}/dependency-graph"
        f"/compare/{base_ref}...{head_ref}"
    )
    headers = _get_github_api_headers()

    try:
        raw = _github_api_get(path, headers)
        data = json.loads(raw.decode())

        changes = []
        for dep in data:
            change = {
                "change_type": dep.get("change_type"),
                "ecosystem": dep.get("ecosystem"),
                "name": dep.get("name"),
                "version": dep.get("version"),
                "package_url": dep.get("package_url"),
                "source_repository_url": dep.get(
                    "source_repository_url"
                ),
                "license": dep.get("license"),
                "vulnerabilities": dep.get("vulnerabilities", []),
            }
            changes.append(change)

        return json.dumps(changes, indent=2)
    except urllib.error.HTTPError as e:
        return (
            f"Error fetching dependency diff: HTTP {e.code} - {e.reason}"
        )
    except Exception as e:
        logger.warning("Failed to fetch dependency diff: %s", e)
        return f"Error fetching dependency diff: {e}"


@tool
def get_dependency_usage(module_name: str) -> str:
    """Check if a Go module is actually used in the project.

    Runs ``go mod why -m`` and ``go mod graph`` to determine if the module
    is needed and show the import chain.

    Args:
        module_name: Go module path (e.g. 'golang.org/x/net').
    """
    if not module_name or not isinstance(module_name, str):
        return "Error: module_name must be a non-empty string."

    # Validate against allowlist: Go module names are alphanumeric with
    # dots, hyphens, underscores, slashes, tildes, plus, and @.
    # This rejects whitespace, newlines, shell metacharacters, and
    # control characters.
    if not _SAFE_MODULE_NAME.match(module_name):
        return f"Error: Invalid module name: {module_name!r}"

    working_dir = _get_working_dir()

    go_mod_path = os.path.join(working_dir, "go.mod")
    if not os.path.isfile(go_mod_path):
        return (
            "Error: No go.mod found in working directory. "
            "Not a Go project."
        )

    results: dict[str, str] = {}

    # go mod why -m
    try:
        proc = subprocess.run(
            ["go", "mod", "why", "-m", module_name],
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=_GO_TOOLCHAIN_TIMEOUT,
        )
        results["go_mod_why"] = (
            proc.stdout.strip() or proc.stderr.strip()
        )
    except subprocess.TimeoutExpired:
        results["go_mod_why"] = "Timed out running go mod why"
    except FileNotFoundError:
        results["go_mod_why"] = "Go toolchain not available"

    # go mod graph — find what depends on this module
    try:
        proc = subprocess.run(
            ["go", "mod", "graph"],
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=_GO_TOOLCHAIN_TIMEOUT,
        )
        if proc.returncode == 0:
            relevant = [
                line
                for line in proc.stdout.splitlines()
                if module_name in line
            ]
            results["dependency_graph"] = (
                "\n".join(relevant[:20]) if relevant else "Not in graph"
            )
        else:
            results["dependency_graph"] = proc.stderr.strip()
    except subprocess.TimeoutExpired:
        results["dependency_graph"] = "Timed out running go mod graph"
    except FileNotFoundError:
        results["dependency_graph"] = "Go toolchain not available"

    return json.dumps(results, indent=2)


@tool
def get_upstream_changelog(
    repo_url: str, old_version: str, new_version: str
) -> str:
    """Fetch release notes between two versions of an upstream dependency.

    Tries GitHub Releases API first, falls back to auto-generated notes,
    then commit comparison.

    Args:
        repo_url: GitHub repository URL (e.g. 'https://github.com/o/r').
        old_version: Previous version tag (e.g. 'v1.0.0').
        new_version: New version tag (e.g. 'v1.1.0').
    """
    if not repo_url or not old_version or not new_version:
        return (
            "Error: repo_url, old_version, and new_version are required."
        )

    owner_repo = _extract_owner_repo(repo_url)
    if not owner_repo:
        return (
            "Error: Could not parse GitHub owner/repo from URL: "
            f"{repo_url}"
        )

    headers = _get_github_api_headers()

    # Strategy 1: GitHub release for new version
    release_body = _fetch_release_notes(owner_repo, new_version, headers)
    if release_body:
        return json.dumps(
            {
                "source": "github_release",
                "version": new_version,
                "body": release_body,
            },
            indent=2,
        )

    # Strategy 2: Auto-generated release notes
    auto_notes = _fetch_generated_notes(
        owner_repo, old_version, new_version, headers
    )
    if auto_notes:
        return json.dumps(
            {
                "source": "auto_generated",
                "from": old_version,
                "to": new_version,
                "body": auto_notes,
            },
            indent=2,
        )

    # Strategy 3: Commit comparison
    path = (
        f"/repos/{owner_repo}"
        f"/compare/{old_version}...{new_version}"
    )
    try:
        raw = _github_api_get(path, headers)
        data = json.loads(raw.decode())
        commits = [
            c.get("commit", {}).get("message", "").split("\n")[0]
            for c in data.get("commits", [])[:30]
        ]
        return json.dumps(
            {
                "source": "commit_comparison",
                "from": old_version,
                "to": new_version,
                "total_commits": data.get("total_commits", 0),
                "commit_messages": commits,
            },
            indent=2,
        )
    except Exception as e:
        logger.warning(
            "Failed to fetch changelog for %s: %s", owner_repo, e
        )
        return (
            f"Error: Could not fetch changelog for {owner_repo}: {e}"
        )


def _extract_owner_repo(url: str) -> str | None:
    """Extract 'owner/repo' from a GitHub URL."""
    m = re.search(
        r"github\.com/([^/]+/[^/]+?)(?:\.git)?/?$", url
    )
    if m:
        return m.group(1)
    if re.match(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$", url):
        return url
    return None


def _fetch_release_notes(
    owner_repo: str, tag: str, headers: dict[str, str]
) -> str | None:
    """Fetch release notes for a specific tag."""
    tags_to_try = [tag]
    if not tag.startswith("v"):
        tags_to_try.append(f"v{tag}")
    else:
        tags_to_try.append(tag[1:])

    for t in tags_to_try:
        path = f"/repos/{owner_repo}/releases/tags/{t}"
        try:
            raw = _github_api_get(path, headers)
            data = json.loads(raw.decode())
            body = data.get("body")
            if body:
                return body
        except urllib.error.HTTPError as e:
            logger.debug(
                "No release for tag %s (HTTP %s)", t, e.code
            )
        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse release notes for tag %s: %s", t, e
            )
        except Exception as e:
            logger.warning(
                "Unexpected error fetching release for tag %s: %s",
                t,
                e,
            )
    return None


def _fetch_generated_notes(
    owner_repo: str,
    old_tag: str,
    new_tag: str,
    headers: dict[str, str],
) -> str | None:
    """Fetch auto-generated release notes between two tags."""
    path = f"/repos/{owner_repo}/releases/generate-notes"
    payload = json.dumps(
        {"tag_name": new_tag, "previous_tag_name": old_tag}
    ).encode()
    try:
        raw = _github_api_post(path, headers, payload)
        data = json.loads(raw.decode())
        return data.get("body")
    except urllib.error.HTTPError as e:
        logger.debug(
            "Failed to generate notes for %s..%s (HTTP %s)",
            old_tag,
            new_tag,
            e.code,
        )
    except Exception as e:
        logger.warning(
            "Unexpected error generating notes for %s..%s: %s",
            old_tag,
            new_tag,
            e,
        )
    return None


@tool
def get_security_advisories(
    ecosystem: str, package_name: str, version: str = ""
) -> str:
    """Query GitHub Global Security Advisories for a specific package.

    Returns known vulnerabilities with GHSA IDs, CVSS scores, severity,
    and patched version information.

    Args:
        ecosystem: Package ecosystem (e.g. 'go', 'npm', 'pip').
        package_name: Package name (e.g. 'golang.org/x/net').
        version: Optional specific version to check (e.g. '0.17.0').
    """
    if not ecosystem or not package_name:
        return "Error: ecosystem and package_name are required."

    params: dict[str, str] = {
        "ecosystem": ecosystem,
        "per_page": "10",
        "type": "reviewed",
    }
    if version:
        params["affects"] = f"{package_name}@{version}"
    else:
        params["affects"] = package_name

    path = f"/advisories?{urllib.parse.urlencode(params)}"
    headers = _get_github_api_headers()

    try:
        raw = _github_api_get(path, headers)
        data = json.loads(raw.decode())

        advisories = []
        for adv in data:
            advisory = {
                "ghsa_id": adv.get("ghsa_id"),
                "cve_id": adv.get("cve_id"),
                "summary": adv.get("summary"),
                "severity": adv.get("severity"),
                "cvss_score": (
                    adv.get("cvss", {}).get("score")
                    if adv.get("cvss")
                    else None
                ),
                "published_at": adv.get("published_at"),
                "html_url": adv.get("html_url"),
                "vulnerabilities": [
                    {
                        "package": v.get("package", {}).get("name"),
                        "vulnerable_version_range": v.get(
                            "vulnerable_version_range"
                        ),
                        "patched_versions": v.get("patched_versions"),
                    }
                    for v in adv.get("vulnerabilities", [])
                ],
            }
            advisories.append(advisory)

        if not advisories:
            return json.dumps({
                "status": "clean",
                "message": (
                    f"No advisories found for {package_name}"
                ),
            })

        return json.dumps(advisories, indent=2)
    except urllib.error.HTTPError as e:
        return (
            f"Error querying advisories: HTTP {e.code} - {e.reason}"
        )
    except Exception as e:
        logger.warning("Failed to query advisories: %s", e)
        return f"Error querying advisories: {e}"


@tool
def run_govulncheck() -> str:
    """Run govulncheck for reachability analysis of known vulnerabilities.

    Returns structured vulnerability data showing whether vulnerable
    functions are actually called in the codebase. Only runs if govulncheck
    is installed.
    """
    working_dir = _get_working_dir()

    if not shutil.which("govulncheck"):
        return json.dumps({
            "status": "skipped",
            "reason": (
                "govulncheck not installed. Install with: "
                "go install golang.org/x/vuln/cmd/govulncheck@latest"
            ),
        })

    go_mod_path = os.path.join(working_dir, "go.mod")
    if not os.path.isfile(go_mod_path):
        return json.dumps({
            "status": "skipped",
            "reason": "No go.mod found in working directory.",
        })

    try:
        result = subprocess.run(
            ["govulncheck", "-json", "./..."],
            capture_output=True,
            text=True,
            cwd=working_dir,
            timeout=_GOVULNCHECK_TIMEOUT,
        )

        # govulncheck exit codes:
        #   0 = no vulnerabilities found
        #   3 = vulnerabilities found (not an error)
        #   other = tool error
        # See: https://pkg.go.dev/golang.org/x/vuln/cmd/govulncheck
        if result.returncode not in (0, 3):
            return json.dumps({
                "status": "error",
                "stderr": result.stderr.strip()[:2000],
            })

        return json.dumps({
            "status": "completed",
            "output": result.stdout.strip()[:10000],
        })
    except subprocess.TimeoutExpired:
        return json.dumps({
            "status": "error",
            "reason": (
                f"govulncheck timed out after "
                f"{_GOVULNCHECK_TIMEOUT // 60} minutes"
            ),
        })
    except Exception as e:
        logger.warning("govulncheck failed: %s", e)
        return json.dumps({
            "status": "error",
            "reason": str(e),
        })


def get_all_dep_review_tools() -> list:
    """Return all dependency review tools for registration."""
    return [
        get_dependency_diff,
        get_dependency_usage,
        get_upstream_changelog,
        get_security_advisories,
        run_govulncheck,
    ]
