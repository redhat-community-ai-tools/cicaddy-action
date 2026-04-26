# AI Provider Configuration

cicaddy-action supports multiple AI providers. This guide covers provider-specific setup.

## Gemini (API Key)

```yaml
- uses: redhat-community-ai-tools/cicaddy-action@main
  with:
    ai_provider: gemini
    ai_model: gemini-3-flash-preview
    ai_api_key: ${{ secrets.GEMINI_API_KEY }}
```

## OpenAI

```yaml
- uses: redhat-community-ai-tools/cicaddy-action@main
  with:
    ai_provider: openai
    ai_model: gpt-4.5
    ai_api_key: ${{ secrets.OPENAI_API_KEY }}
```

## Claude (Anthropic API)

```yaml
- uses: redhat-community-ai-tools/cicaddy-action@main
  with:
    ai_provider: claude
    ai_model: claude-sonnet-4-6
    ai_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Vertex AI (GCP) — Claude & Gemini

Use Google Cloud Workload Identity Federation (WIF) for keyless authentication.
WIF eliminates static service account keys — GitHub mints a short-lived OIDC token
per workflow run, and GCP exchanges it for temporary credentials scoped to that job.

### Parameters

The examples below use these placeholders. Set them as GitHub
[repository variables](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables)
(`vars.*`) so every workflow can reference them:

| Placeholder | GitHub variable | How to obtain | Example |
|-------------|-----------------|---------------|---------|
| `GCP_PROJECT_ID` | `vars.GCP_PROJECT_ID` | `gcloud config get project` | `my-ai-project` |
| `GCP_PROJECT_NUM` | `vars.GCP_PROJECT_NUM` | `gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)'` | `123456789012` |
| `GCP_WIF_PROVIDER` | `vars.GCP_WIF_PROVIDER` | Full provider resource name (see setup below) | `projects/123456789012/locations/global/workloadIdentityPools/github-pool/providers/github-provider` |
| `GCP_SERVICE_ACCOUNT` | `vars.GCP_SERVICE_ACCOUNT` | SA email with Vertex AI permissions | `cicaddy@my-ai-project.iam.gserviceaccount.com` |
| `GH_ORG` | — | GitHub org or user that owns the repo | `my-org` |
| `GH_REPO` | — | Repository name | `my-repo` |
| `GH_OWNER_ID` | — | `gh api orgs/YOUR_ORG --jq '.id'` (only needed for org-wide condition) | `12345678` |

### Prerequisites

**One-time GCP setup** — create a Workload Identity Pool and OIDC provider:

```bash
# Set these for your environment
export GCP_PROJECT_ID="my-ai-project"
export GCP_PROJECT_NUM="$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')"
export GH_ORG="my-org"
export GH_REPO="my-repo"

# 1. Create a workload identity pool
gcloud iam workload-identity-pools create "github-pool" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool"

# 2. Create an OIDC provider linked to GitHub Actions
#    The attribute condition restricts which repositories can authenticate.
#    Use a per-repository condition (recommended) or per-org condition.
#
#    Per-repository (recommended — only YOUR_ORG/YOUR_REPO can authenticate):
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="${GCP_PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner_id=assertion.repository_owner_id" \
  --attribute-condition="assertion.repository=='${GH_ORG}/${GH_REPO}'"

#    Per-org alternative (any repo in the org can authenticate):
#    --attribute-condition="assertion.repository_owner_id=='${GH_OWNER_ID}'"

# 3. Allow the pool to impersonate a service account (per-repository scope)
gcloud iam service-accounts add-iam-policy-binding \
  "cicaddy@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --project="${GCP_PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${GCP_PROJECT_NUM}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${GH_ORG}/${GH_REPO}"
```

The service account needs `roles/aiplatform.user` to invoke Vertex AI models.

> **Security**: Both the provider attribute condition (step 2) and the IAM
> binding (step 3) should be scoped to the specific repository, not just the
> organization. An org-wide condition lets any repo in the org mint tokens
> and impersonate the service account. Use `repository_owner_id` (numeric,
> immutable) if you do need org-level access — never use `repository_owner`
> (name string, can be re-registered after deletion).

### Claude via Vertex AI

```yaml
name: PR Review (Claude on Vertex AI)

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  id-token: write       # Required for Workload Identity Federation
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: anthropic-vertex
          ai_model: claude-sonnet-4-6
          vertex_project_id: ${{ vars.GCP_PROJECT_ID }}
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
```

### Gemini via Vertex AI

```yaml
name: PR Review (Gemini on Vertex AI)

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  id-token: write
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - uses: google-github-actions/auth@v3
        with:
          workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
          service_account: ${{ vars.GCP_SERVICE_ACCOUNT }}

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: gemini-vertex
          ai_model: gemini-3-flash-preview
          google_cloud_project: ${{ vars.GCP_PROJECT_ID }}
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
```

> **Note**: `google_cloud_project` is required for `gemini-vertex`. The
> `google-github-actions/auth` step sets `GOOGLE_APPLICATION_CREDENTIALS`
> automatically. No `ai_api_key` is needed.

### Fallback: Service Account Key

If WIF is not available (e.g., restricted GCP environments without a Workload
Identity Pool), you can use a service account JSON key as a fallback:

```yaml
- uses: google-github-actions/auth@v3
  with:
    credentials_json: ${{ secrets.GCP_SA_KEY }}

- uses: redhat-community-ai-tools/cicaddy-action@main
  with:
    ai_provider: anthropic-vertex
    ai_model: claude-sonnet-4-6
    vertex_project_id: ${{ vars.GCP_PROJECT_ID }}
```

The `google-github-actions/auth` action sets `GOOGLE_APPLICATION_CREDENTIALS`
automatically in both WIF and SA key modes — never write keys to disk manually
or echo them in scripts.

> **Prefer WIF over service account keys.** SA keys are long-lived secrets
> that can leak and require manual rotation. WIF tokens are short-lived
> (~1 hour), scoped to the specific workflow run, and leave no secrets to manage.

### Authentication Method Comparison

| | WIF (recommended) | SA Key (fallback) | API Key |
|-|--------------------|-------------------|---------|
| Secrets to manage | None | JSON key in GitHub secret | API key in GitHub secret |
| Token lifetime | ~1 hour (auto-issued) | Until key is revoked | Until key is revoked |
| Rotation | Automatic | Manual (every 90 days) | Manual |
| Blast radius | Single workflow run | Unlimited until revoked | Unlimited until revoked |
| Audit trail | Per-job OIDC claims | SA-level logging | Key-level logging |
| Scope control | Repo, branch, workflow | SA permissions only | Key permissions only |

## Migration Notes

### Default Vertex AI location changed from `us-east5` to `global`

Previous versions defaulted to `us-east5` via the `cloud_ml_region` input. This
release changes the default to `global` (via the new `google_cloud_location`
input), which routes requests to the nearest available region.

If your workflow relied on the implicit `us-east5` default, add an explicit
location:

```yaml
- uses: redhat-community-ai-tools/cicaddy-action@main
  with:
    google_cloud_location: us-east5   # pin to previous default
```

### `cloud_ml_region` is deprecated

The `cloud_ml_region` input still works but emits a warning. Replace it with
`google_cloud_location` in your workflows.

## Security Considerations

### `submit_review` and fork pull requests

When `submit_review: 'true'` is set, the action submits a formal GitHub review
(APPROVE or REQUEST\_CHANGES) on behalf of the token owner. If your repository
accepts pull requests from forks and you use `pull_request_target` to expose
secrets, an attacker could craft a PR that tricks the AI into approving
malicious code.

Mitigations:

- Do **not** combine `submit_review: 'true'` with `pull_request_target` on
  repositories that accept fork PRs.
- Use `pull_request` (not `pull_request_target`) when possible — it runs in the
  fork's context and cannot access repository secrets.
- If you must use `pull_request_target`, restrict `submit_review` to trusted
  contributors via a branch protection rule or a job-level `if:` condition.

## Provider Inputs Reference

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | `gemini`, `openai`, `claude`, `anthropic-vertex`, or `gemini-vertex` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | No | API key (not needed for `anthropic-vertex` or `gemini-vertex`) |
| `vertex_project_id` | No | GCP project ID for Vertex AI Claude (falls back to `google_cloud_project`) |
| `google_cloud_project` | No | GCP project ID for Vertex AI (required for `gemini-vertex`, optional fallback for `anthropic-vertex`) |
| `google_cloud_location` | No | Vertex AI location (default: `global`) |
