#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
BREW="/opt/homebrew/bin/brew"
release_channel="${VELNOR_TAP_CHANNEL:-preview}"
case "$release_channel" in
  preview)
    expected_check_id="homebrew-preview-install"
    formula="jackin-preview"
    ;;
  stable)
    expected_check_id="homebrew-stable-install"
    formula="jackin"
    ;;
  *)
    printf '%s\n' 'Homebrew installation test received an unsupported release channel.' >&2
    exit 2
    ;;
esac

if [[ "${VELNOR_CHECK_ID:-}" != "$expected_check_id" \
  || "${VELNOR_CHECK_PLATFORM:-}" != "macos_arm64" \
  || ! "${VELNOR_CHECK_HEAD:-}" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'Homebrew installation test requires the selected native macos_arm64 Velnor check context.' >&2
  exit 2
fi

checkout_head=$(git -C "$root" rev-parse --verify 'HEAD^{commit}')
merge_source=$(git -C "$root" rev-parse --verify 'HEAD^2^{commit}' 2>/dev/null || true)
if [[ "$VELNOR_CHECK_HEAD" != "$checkout_head" && "$VELNOR_CHECK_HEAD" != "$merge_source" ]]; then
  printf '%s\n' 'VELNOR_CHECK_HEAD must equal the checkout commit or the PR merge second parent.' >&2
  exit 2
fi

if ! PYTHONDONTWRITEBYTECODE=1 python "$root/scripts/homebrew_install_policy.py" "$root" "$release_channel"; then
  exit 2
fi

if [[ ! -x "$BREW" ]]; then
  printf 'The fixed Homebrew executable is unavailable: %s\n' "$BREW" >&2
  exit 2
fi

export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export HOMEBREW_NO_ANALYTICS=1
export HOMEBREW_NO_ENV_HINTS=1

"$BREW" ruby "$root/scripts/test_homebrew_formulary_keg.rb" "$root"
"$BREW" tap jackin-project/tap "$root"
"$BREW" trust --tap jackin-project/tap
"$BREW" install --formula --force "$formula"
"$BREW" test --formula "$formula"
