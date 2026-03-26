# Shared Task Notes: PR Review Support

## What was done
- Added `submit_pr_review()` method to `GitHubAnalyzer` — calls PyGithub's `pr.create_review(body, event)` with `APPROVE`, `REQUEST_CHANGES`, or `COMMENT`
- Added `submit_review` bool setting + `SUBMIT_REVIEW` env var handling in `load_settings()`
- Added `extract_review_verdict()` function that parses `<!-- VERDICT: APPROVE -->` or `<!-- VERDICT: REQUEST_CHANGES -->` from AI output (defaults to `COMMENT`)
- Updated `GitHubPRAgent.send_notifications()` to submit a formal review when `submit_review=true`
- Updated built-in PR review prompt to include verdict instructions when `submit_review` is enabled
- Added `submit_review` input to `action.yml` and `entrypoint.sh`
- Added tests for all new functionality (all 104 tests pass)
- Updated `README.md` inputs table

## What still needs doing
- Update `.claude/skills/cicaddy-action/SKILL.md` — add `submit_review` to both the inputs table (line ~125) and the settings list (after `post_pr_comment` at line ~190). Permission was denied during this iteration.
- Consider adding `submit_review: 'true'` to the `pr-review.yml` workflow example in README
- Consider adding `submit_review` to `.github/workflows/pr-review.yml` to dogfood the feature
- DSPy task files: users with custom task files need to include a VERDICT line in their prompt template for the verdict extraction to work. Document this.
- The `_format_review_body()` strips the VERDICT line from the review body so it's not visible in the rendered review. Verify this looks clean with a real PR.
- Consider whether `submit_review` should imply `post_pr_comment` (currently they are independent — you can have both, one, or neither).
