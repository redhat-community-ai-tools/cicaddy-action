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
  anthropic-vertex)
    ;;  # handled below
  gemini-vertex)
    ;;  # handled below
  *)
    echo "ERROR: Unknown ai_provider '${AI_PROVIDER}'. Supported: gemini, openai, claude, anthropic, anthropic-vertex, gemini-vertex"
    exit 3
    ;;
esac

# Validate API key for non-vertex providers
if [[ "${AI_PROVIDER}" != *-vertex && -z "${INPUT_AI_API_KEY}" ]]; then
  echo "ERROR: ai_api_key is required for provider '${AI_PROVIDER}'"
  exit 3
fi

# Export shared Vertex AI env vars
if [[ -n "${INPUT_GOOGLE_CLOUD_PROJECT}" ]]; then
  export GOOGLE_CLOUD_PROJECT="${INPUT_GOOGLE_CLOUD_PROJECT}"
fi
if [[ -n "${INPUT_GOOGLE_CLOUD_LOCATION}" ]]; then
  export GOOGLE_CLOUD_LOCATION="${INPUT_GOOGLE_CLOUD_LOCATION}"
fi

# Handle gemini-vertex provider setup
if [[ "${AI_PROVIDER}" == "gemini-vertex" ]]; then
  if [[ -z "${GOOGLE_CLOUD_PROJECT}" ]]; then
    echo "ERROR: ai_provider 'gemini-vertex' requires google_cloud_project input"
    exit 3
  fi
  if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
    echo "WARNING: GOOGLE_APPLICATION_CREDENTIALS not set. Use google-github-actions/auth before this step."
  fi
fi

# Handle anthropic-vertex provider setup
if [[ "${AI_PROVIDER}" == "anthropic-vertex" ]]; then
  export ANTHROPIC_VERTEX_PROJECT_ID="${INPUT_VERTEX_PROJECT_ID:-$GOOGLE_CLOUD_PROJECT}"
  export CLOUD_ML_REGION="${INPUT_CLOUD_ML_REGION:-${GOOGLE_CLOUD_LOCATION:-global}}"
  if [[ -z "${ANTHROPIC_VERTEX_PROJECT_ID}" && -z "${GOOGLE_CLOUD_PROJECT}" ]]; then
    echo "ERROR: ai_provider 'anthropic-vertex' requires vertex_project_id or google_cloud_project input"
    exit 3
  fi
  if [[ -z "${GOOGLE_APPLICATION_CREDENTIALS}" ]]; then
    echo "WARNING: GOOGLE_APPLICATION_CREDENTIALS not set. Use google-github-actions/auth before this step."
  fi
fi

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
  _ws_path="$(_to_abs "${INPUT_TASK_FILE}")"
  if [[ -f "${_ws_path}" ]]; then
    export AI_TASK_FILE="${_ws_path}"
  elif [[ -f "/app/${INPUT_TASK_FILE}" ]]; then
    # Fall back to bundled task files shipped with the action
    export AI_TASK_FILE="/app/${INPUT_TASK_FILE}"
  else
    export AI_TASK_FILE="${_ws_path}"
  fi
fi
export AI_TASK_PROMPT="${INPUT_TASK_PROMPT}"
if [[ -n "${INPUT_REPORT_TEMPLATE}" ]]; then
  export REPORT_TEMPLATE="$(_to_abs "${INPUT_REPORT_TEMPLATE}")"
fi
export MCP_SERVERS_CONFIG="${INPUT_MCP_SERVERS_CONFIG:-[]}"
export SLACK_WEBHOOK_URL="${INPUT_SLACK_WEBHOOK_URL}"
export GITHUB_TOKEN="${INPUT_GITHUB_TOKEN:-$GITHUB_TOKEN}"
export POST_PR_COMMENT="${INPUT_POST_PR_COMMENT:-false}"
export SUBMIT_REVIEW="${INPUT_SUBMIT_REVIEW:-false}"
export RUN_GOVULNCHECK="${INPUT_RUN_GOVULNCHECK:-false}"
export DEP_REVIEW_SEVERITY_THRESHOLD="${INPUT_DEP_REVIEW_SEVERITY_THRESHOLD:-minor}"
export DELEGATION_MODE="${INPUT_DELEGATION_MODE:-none}"
export MAX_SUB_AGENTS="${INPUT_MAX_SUB_AGENTS:-3}"

# Validate MAX_SUB_AGENTS is a number
if [[ -n "${MAX_SUB_AGENTS}" ]] && ! [[ "${MAX_SUB_AGENTS}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: max_sub_agents must be a number (1-10), got: '${MAX_SUB_AGENTS}'"
  exit 3
fi

# Extract PR number from GITHUB_REF (e.g. refs/pull/123/merge -> 123)
if [[ "${GITHUB_REF}" =~ ^refs/pull/([0-9]+)/ ]]; then
  export GITHUB_PR_NUMBER="${BASH_REMATCH[1]}"
elif [[ -n "${GITHUB_EVENT_PATH}" && -f "${GITHUB_EVENT_PATH}" ]]; then
  # For pull_request_target, GITHUB_REF is the base branch, not refs/pull/N/merge.
  # Extract PR number from the event payload JSON instead.
  PR_NUM=$(python3 -c "import json,sys; e=json.load(open(sys.argv[1])); print(e.get('pull_request',{}).get('number',''))" "${GITHUB_EVENT_PATH}" 2>/dev/null || true)
  if [[ -n "${PR_NUM}" ]]; then
    export GITHUB_PR_NUMBER="${PR_NUM}"
  fi
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
