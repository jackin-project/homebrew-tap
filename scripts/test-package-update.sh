#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
PYTHONDONTWRITEBYTECODE=1 python "$root/scripts/test_package_update.py"
PYTHONDONTWRITEBYTECODE=1 python "$root/scripts/test_homebrew_install_policy.py"
