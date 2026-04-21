# AGENTS.md — homebrew-tap

Homebrew formulae for the `jackin` CLI. **This repo is public.** Every `brew install jackin` reads exactly what's in `Formula/*.rb`. Poisoning a formula is a supply-chain attack on every downstream user.

Treat every commit here as a change to software that will run on other people's machines.

## Threat model

Unlike a secrets-rich repo, the surface here is narrow but sharp:

1. **Formula integrity** — `url` + `sha256` together define what gets installed. If they mismatch or either is manipulated, users get arbitrary code. A mismatch is catastrophic because `brew` trusts the sha256 blindly.
2. **Mutable ref anchoring** — formulas must pin to immutable references (tagged release archive or full commit SHA in `/archive/<sha>.tar.gz`). A URL pointing at a branch HEAD allows silent tampering upstream.
3. **Automation hijack** — the preview formula is auto-bumped by CI in the `jackin` repo. If that automation's token leaks, attackers push poisoned previews. The blast radius covers every user on the `@preview` channel.
4. **Upstream tag immutability** — the stable formula pins to a tag like `v0.5.0`. If tags aren't protected on `jackin`, a force-move silently changes what users install next.

## Hard rules (do not break these)

1. **Never change `url` without recomputing `sha256` in the same commit.** A mismatched pair is the single most catastrophic formula bug.
2. **Never commit a formula whose `url` targets a mutable ref** (branch HEAD, `main`). Only tagged release archives (`/refs/tags/vX.Y.Z.tar.gz`) or full commit SHAs (`/archive/<40-char-sha>.tar.gz`) are acceptable.
3. **Never hand-edit `Formula/jackin-preview.rb`.** This file is owned by CI in the `jackin` repo. Manual edits here are either a mistake or an attempt to bypass the automation — both warrant a PR review and confirmation from the original bumper.
4. **Never commit credentials.** There should be none in this repo at all. If the credential scan below ever fires, something is very wrong — rotate and investigate.

## Required pre-commit checks

Run all three before every `git commit`:

```bash
# 1. What's staged? Anything surprising?
git status --porcelain

# 2. For any changed formula, verify url/sha256 pair via brew
for f in $(git diff --cached --name-only -- 'Formula/*.rb'); do
  brew fetch --retry --force "./$f" || { echo "FAIL: $f"; exit 1; }
done

# 3. Defense-in-depth credential scan — should always be empty
git diff --cached --name-only -z | xargs -0 -r \
  grep -l -iE "ghp_|gho_|ghs_|ghr_|github_pat_|BEGIN [A-Z ]*PRIVATE KEY|aws_access_key_id|aws_secret_access_key|bearer [a-z0-9-]{20,}" 2>/dev/null
```

`brew fetch` downloads the archive and verifies its sha256 against what the formula declares. A failure means either the archive changed upstream (investigate for tampering) or the committed sha256 is wrong (recompute from source).

## Upstream tag protection

Every formula pins to an artifact on `github.com/jackin-project/jackin`. That repo's rulesets must be intact for these formulas to remain trustworthy. Verify periodically:

```bash
gh api repos/jackin-project/jackin/rulesets --jq '[.[] | {name, target, enforcement}]'
```

Expected (as of 2026-04-16, applied via `jackin-github-terraform` Terraform config):

```json
[
  {"name": "protect-main", "target": "branch", "enforcement": "active"},
  {"name": "protect-tags", "target": "tag",    "enforcement": "active"}
]
```

The `protect-tags` ruleset covers `~ALL` tag names with `non_fast_forward = true` and `deletion = true` — so no tag can be force-moved or deleted once created. If that ruleset ever goes missing or falls to `enforcement: disabled`, treat it as an incident: tag force-moves become a silent supply-chain risk, since every `brew install jackin@v0.5.0` trusts whatever commit the tag currently points at.

## Who commits here

Most commits are automated (CI in `jackin` bumps `Formula/jackin-preview.rb` on every build — 400+ commits to date). Manual commits should be rare and should:

- Update the stable `Formula/jackin.rb` only (preview is CI-managed)
- Go through a PR even though no reviewer is required by the ruleset
- Carry a descriptive Conventional Commits message

## Conventions

- Branch naming: `chore/*`, `feat/*`, `fix/*`
- Commit messages: see [Commit Messages](#commit-messages) section below
- `main` is the primary branch
- All changes go through PR (required by the self-referential ruleset)

## What this does NOT protect against

- A compromised `jackin` release process upstream — if the archive is tampered with *before* sha256 is computed and committed here, this repo can't catch it. Mitigation lives in `jackin`'s release pipeline.
- A compromised `jackin-project` org owner force-moving a tag — mitigated by upstream tag rulesets, not by this repo.
- Ruby-level malice in formula code (e.g., `install` doing something unexpected) — out of scope here; relies on PR review and `brew audit --strict --online` sanity checks.

## Commit Messages

All commits in this repository MUST follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

Subject format: `<type>[optional scope][!]: <description>`

Allowed types:

| Type       | Use for                                                |
| ---------- | ------------------------------------------------------ |
| `feat`     | New user-visible feature                               |
| `fix`      | Bug fix                                                |
| `docs`     | Documentation-only change                              |
| `style`    | Formatting, whitespace; no logic change                |
| `refactor` | Internal restructuring; no behavior change             |
| `perf`     | Performance improvement                                |
| `test`     | Adding or updating tests                               |
| `build`    | Build system, tooling, dependencies                    |
| `ci`       | CI configuration                                       |
| `chore`    | Routine maintenance (release, merge, deps)             |
| `revert`   | Reverts a prior commit                                 |

Scope is optional but encouraged when it clarifies the change area.

Breaking changes use `!` after the type/scope (`feat!:` or `feat(api)!:`) and include a `BREAKING CHANGE:` footer in the body.

PR squash-merge: the PR title becomes the commit subject, so PR titles must also follow this convention.

**Exception**: the 91+ release-bot commits matching `jackin@preview <version>+<sha>` (auto-generated by upstream `jackin` CI) are exempt from this format — they embed a SHA cross-reference back to the originating jackin build and the format is fixed by the bot.
