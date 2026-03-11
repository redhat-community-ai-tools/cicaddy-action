#!/bin/bash
set -e

# GitHub Actions sets inputs as INPUT_<UPPERCASED_NAME> env vars.
# Input names use underscores (e.g. ai_provider -> INPUT_AI_PROVIDER).

export AI_PROVIDER="${INPUT_AI_PROVIDER}"
export AI_MODEL="${INPUT_AI_MODEL}"

# Map API key to provider-specific env var
case "${AI_PROVIDER}" in
  gemini)  export GEMINI_API_KEY="${INPUT_AI_API_KEY}" ;;
  openai)  export OPENAI_API_KEY="${INPUT_AI_API_KEY}" ;;
  claude|anthropic) export ANTHROPIC_API_KEY="${INPUT_AI_API_KEY}" ;;
esac

# Resolve file paths to absolute before cd into .cicaddy/ subdirectory.
# Rejects absolute paths and parent directory traversal to prevent
# reading files outside the workspace.
WORKSPACE="${GITHUB_WORKSPACE:-$(pwd)}"

_to_abs() {
  local path="$1"
  [[ -z "$path" ]] && return
  if [[ "$path" == /* ]]; then
    echo "ERROR: Absolute paths not allowed: $path" >&2
    exit 1
  fi
  local full_path="${WORKSPACE}/${path}"
  # Resolve symlinks and .. components, then verify the result is under WORKSPACE
  if [[ "$(realpath -m "$full_path")" != "${WORKSPACE}"* ]]; then
    echo "ERROR: Path traversal detected: $path" >&2
    exit 1
  fi
  echo "$full_path"
}

if [[ -n "${INPUT_TASK_FILE}" ]]; then
  export AI_TASK_FILE="$(_to_abs "${INPUT_TASK_FILE}")"
fi
export AI_TASK_PROMPT="${INPUT_TASK_PROMPT}"
if [[ -n "${INPUT_REPORT_TEMPLATE}" ]]; then
  export REPORT_TEMPLATE="$(_to_abs "${INPUT_REPORT_TEMPLATE}")"
fi
export MCP_SERVERS_CONFIG="${INPUT_MCP_SERVERS_CONFIG:-[]}"
export SLACK_WEBHOOK_URL="${INPUT_SLACK_WEBHOOK_URL}"
export GITHUB_TOKEN="${INPUT_GITHUB_TOKEN:-$GITHUB_TOKEN}"
export POST_PR_COMMENT="${INPUT_POST_PR_COMMENT:-false}"

# Extract PR number from GITHUB_REF (e.g. refs/pull/123/merge -> 123)
if [[ "${GITHUB_REF}" =~ ^refs/pull/([0-9]+)/ ]]; then
  export GITHUB_PR_NUMBER="${BASH_REMATCH[1]}"
fi

# Enable local tools (git operations) and set working directory
export ENABLE_LOCAL_TOOLS=true
export LOCAL_TOOLS_WORKING_DIR="${GITHUB_WORKSPACE:-$(pwd)}"
export GIT_WORKING_DIRECTORY="${GITHUB_WORKSPACE:-$(pwd)}"

# Cicaddy saves reports/logs to "../" relative to cwd.
# GitHub Actions sets workdir to /github/workspace (not writable parent).
# Create a subdirectory so "../" resolves back to the workspace.
CICADDY_RUN_DIR="${GITHUB_WORKSPACE:-.}/.cicaddy"
mkdir -p "${CICADDY_RUN_DIR}"
cd "${CICADDY_RUN_DIR}"

# Run cicaddy
cicaddy run
