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
    ai_model: gpt-4o
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

## Provider Inputs Reference

| Input | Required | Description |
|-------|----------|-------------|
| `ai_provider` | Yes | `gemini`, `openai`, `claude`, or `anthropic-vertex` |
| `ai_model` | Yes | Model identifier |
| `ai_api_key` | No | API key (not needed for `anthropic-vertex`) |
| `vertex_project_id` | No | GCP project ID (required for `anthropic-vertex`) |
| `cloud_ml_region` | No | Vertex AI region (default: `us-east5`) |
