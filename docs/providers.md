# AI Provider Configuration

cicaddy-action supports multiple AI providers. This guide covers provider-specific setup.

## Gemini

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

## Claude via Vertex AI (GCP)

Uses Google Cloud Workload Identity Federation for keyless authentication — no
service account JSON keys to manage. This is the recommended approach for GCP.

```yaml
name: PR Review (Vertex AI)

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
          workload_identity_provider: 'projects/123/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'cicaddy@my-project.iam.gserviceaccount.com'

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: anthropic-vertex
          ai_model: claude-sonnet-4-6
          vertex_project_id: my-project
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
```

> **Security**: Prefer Workload Identity Federation (shown above) over service
> account keys. If you must use a key, store the JSON as a GitHub secret and pass
> it via `google-github-actions/auth` with `credentials_json`:
> ```yaml
> - uses: google-github-actions/auth@v3
>   with:
>     credentials_json: ${{ secrets.GCP_SA_KEY }}
> ```
> The auth action sets `GOOGLE_APPLICATION_CREDENTIALS` automatically — never
> write keys to disk manually or echo them in scripts.

## Gemini via Vertex AI (GCP)

Uses Google Cloud authentication (Workload Identity Federation or service account)
to call Gemini models through the Vertex AI API — no Gemini API key needed.

```yaml
name: PR Review (Gemini Vertex AI)

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
          workload_identity_provider: 'projects/123/locations/global/workloadIdentityPools/github/providers/my-repo'
          service_account: 'cicaddy@my-project.iam.gserviceaccount.com'

      - uses: redhat-community-ai-tools/cicaddy-action@main
        with:
          ai_provider: gemini-vertex
          ai_model: gemini-3-flash-preview
          google_cloud_project: my-project
          task_file: tasks/pr_review.yml
          post_pr_comment: 'true'
```

> **Note**: `google_cloud_project` is required for `gemini-vertex`. The
> `google-github-actions/auth` step sets `GOOGLE_APPLICATION_CREDENTIALS`
> automatically.

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

## Provider Inputs Reference

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | `gemini`, `openai`, `claude`, `anthropic-vertex`, or `gemini-vertex` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | No | API key (not needed for `anthropic-vertex` or `gemini-vertex`) |
| `vertex_project_id` | No | GCP project ID for Vertex AI Claude (falls back to `google_cloud_project`) |
| `google_cloud_project` | No | GCP project ID for Vertex AI (required for `gemini-vertex`, optional fallback for `anthropic-vertex`) |
| `google_cloud_location` | No | Vertex AI location (default: `global`) |
