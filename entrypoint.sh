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

export AI_TASK_FILE="${INPUT_TASK_FILE}"
export AI_TASK_PROMPT="${INPUT_TASK_PROMPT}"
export REPORT_TEMPLATE="${INPUT_REPORT_TEMPLATE}"
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

# Run cicaddy
cicaddy run
