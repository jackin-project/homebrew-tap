#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
cd "$root"

handoff_vars=(
  VELNOR_TAP_BASE_SHA
  VELNOR_TAP_FORMULA_PATH
  VELNOR_TAP_RELEASE_RECEIPT
  VELNOR_TAP_RELEASE_RECEIPT_SHA256
  VELNOR_TAP_RELEASE_VERSION
  VELNOR_TAP_RELEASE_TAG
  VELNOR_TAP_SOURCE_SHA
)
present=0
for name in "${handoff_vars[@]}"; do
  if declare -p "$name" >/dev/null 2>&1; then
    if [[ -z "${!name}" ]]; then
      printf 'Package updater handoff variable %s must not be empty.\n' "$name" >&2
      exit 2
    fi
    ((present += 1))
  fi
done

if (( present == ${#handoff_vars[@]} )); then
  exec python "$root/scripts/package-update.py"
fi

if (( present != 0 )); then
  printf '%s\n' 'Package updater requires either the complete Velnor handoff or no handoff variables.' >&2
  exit 2
fi

if [[ "${VELNOR_CHECK_ID:-}" != "homebrew-preview-update" \
  || "${VELNOR_CHECK_PLATFORM:-}" != "linux_x64" \
  || ! "${VELNOR_CHECK_HEAD:-}" =~ ^[0-9a-f]{40}$ ]]; then
  printf '%s\n' 'Package updater regression mode requires a full-head Velnor named-check context.' >&2
  exit 2
fi

checkout_head=$(git rev-parse --verify 'HEAD^{commit}')
merge_source=$(git rev-parse --verify 'HEAD^2^{commit}' 2>/dev/null || true)
if [[ "$VELNOR_CHECK_HEAD" != "$checkout_head" && "$VELNOR_CHECK_HEAD" != "$merge_source" ]]; then
  printf '%s\n' 'VELNOR_CHECK_HEAD must equal the checkout commit or the PR merge second parent.' >&2
  exit 2
fi

exec "$root/scripts/test-package-update.sh"
