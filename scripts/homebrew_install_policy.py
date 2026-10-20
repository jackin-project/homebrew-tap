#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
"""Validate the selected native release formula inventory before Homebrew runs."""

from __future__ import annotations

import re
import os
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path


ARCHIVES = (
    "jackin-aarch64-apple-darwin.tar.gz",
    "jackin-x86_64-apple-darwin.tar.gz",
    "jackin-aarch64-unknown-linux-gnu.tar.gz",
    "jackin-x86_64-unknown-linux-gnu.tar.gz",
    "jackin-capsule-aarch64-unknown-linux-gnu.tar.gz",
    "jackin-capsule-x86_64-unknown-linux-gnu.tar.gz",
)
VERSION_RE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-preview\.[1-9][0-9]*\+[0-9a-f]{7}\Z")
STABLE_VERSION_RE = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
VERSION_LINE_RE = re.compile(r'^ {2}version "([^"]+)"$')
SOURCE_SHA_LINE_RE = re.compile(r"^# source-sha: ([0-9a-f]{40})$")
URL_LINE_RE = re.compile(r'^\s+url "([^"]+)"$')
URL_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])url(?![A-Za-z0-9_])")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
ALIAS_PATH = "Aliases/jackin@preview"
ALIAS_TARGET = b"../Formula/jackin-preview.rb"
FORMULA_PATHS = {"preview": "Formula/jackin-preview.rb", "stable": "Formula/jackin.rb"}


class InvalidReleaseFormula(ValueError):
    """The formula does not describe one exact release channel inventory."""


def validate_formula_text(formula: str, channel: str = "preview") -> tuple[str, tuple[str, ...]]:
    """Return version and exact URLs, rejecting any inventory drift."""
    if channel not in FORMULA_PATHS:
        raise InvalidReleaseFormula("release channel is unsupported")
    version_lines = [line for line in formula.splitlines() if line.startswith("  version")]
    versions = [match.group(1) for line in version_lines if (match := VERSION_LINE_RE.fullmatch(line))]
    version_pattern = VERSION_RE if channel == "preview" else STABLE_VERSION_RE
    if len(version_lines) != 1 or len(versions) != 1 or version_pattern.fullmatch(versions[0]) is None:
        raise InvalidReleaseFormula("formula version does not match the selected release channel")

    version = versions[0]
    source_lines = [line for line in formula.splitlines() if line.startswith("# source-sha")]
    source_shas = [match.group(1) for line in source_lines if (match := SOURCE_SHA_LINE_RE.fullmatch(line))]
    if len(source_lines) != 1 or len(source_shas) != 1 or (channel == "preview" and not source_shas[0].startswith(version.rsplit("+", 1)[1])):
        raise InvalidReleaseFormula("formula source commit does not match the selected release version")
    tag = "preview" if channel == "preview" else f"v{version}"
    prefix = f"https://github.com/jackin-project/jackin/releases/download/{tag}/"
    expected = tuple(prefix + archive for archive in ARCHIVES)
    urls: list[str] = []
    for line in formula.splitlines():
        match = URL_LINE_RE.fullmatch(line)
        if match is not None:
            urls.append(match.group(1))
        elif URL_TOKEN_RE.search(line) is not None:
            raise InvalidReleaseFormula("formula contains an unsupported or nonliteral URL declaration")
    urls = tuple(urls)
    if Counter(urls) != Counter(expected):
        raise InvalidReleaseFormula("formula URLs must exactly match the six immutable release assets")
    return version, urls


def validate_formula(path: Path, channel: str = "preview") -> tuple[str, tuple[str, ...]]:
    _require_regular_formula(path)
    return validate_formula_text(path.read_text(encoding="utf-8"), channel)


def _require_regular_formula(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise InvalidReleaseFormula("formula must be a regular file")


def _git(repository: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(
            ("git", "-C", str(repository), *arguments),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise InvalidReleaseFormula("could not verify the captured repository tree") from error


def validate_runtime_alias(repository: Path, check_head: str) -> None:
    """Bind the installed alias to its exact symlink blob at the captured source head."""
    if COMMIT_RE.fullmatch(check_head) is None:
        raise InvalidReleaseFormula("the native check must provide a full source commit")

    root = repository.resolve(strict=True)
    formula = root / "Formula/jackin-preview.rb"
    _validate_alias_layout(root, formula)
    _validate_checkout_head(root, check_head)
    _validate_alias_blob(root, check_head)

def _validate_alias_layout(root: Path, formula: Path) -> None:
    formula_parent = root / "Formula"
    alias_parent = root / "Aliases"
    alias_path = root / ALIAS_PATH

    for parent in (formula_parent, alias_parent):
        mode = parent.lstat().st_mode
        if not stat.S_ISDIR(mode):
            raise InvalidReleaseFormula("formula and alias parents must be real directories")
    formula_mode = formula.lstat().st_mode
    if not stat.S_ISREG(formula_mode) or formula.resolve(strict=True).parent != formula_parent:
        raise InvalidReleaseFormula("formula must be a regular file contained by the captured repository")
    if not alias_path.is_symlink() or os.readlink(alias_path) != ALIAS_TARGET.decode("ascii"):
        raise InvalidReleaseFormula("preview alias must be the exact relative formula symlink")


def _validate_checkout_head(root: Path, check_head: str) -> None:
    checkout_head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    try:
        checkout_source = _git(root, "rev-parse", "--verify", "HEAD^2^{commit}").decode("ascii").strip()
    except InvalidReleaseFormula:
        checkout_source = ""
    if check_head not in (checkout_head, checkout_source):
        raise InvalidReleaseFormula("the native check head is not the checkout commit or its PR merge second parent")


def _validate_alias_blob(root: Path, check_head: str) -> None:
    alias_path = root / ALIAS_PATH
    tree_entry = _git(root, "ls-tree", "-z", "--full-tree", check_head, "--", ALIAS_PATH)
    records = tree_entry.split(b"\0")
    if len(records) != 2 or not records[0]:
        raise InvalidReleaseFormula("captured source tree must contain exactly one preview alias")
    metadata, separator, name = records[0].partition(b"\t")
    fields = metadata.split()
    if separator != b"\t" or name != ALIAS_PATH.encode("ascii") or len(fields) != 3:
        raise InvalidReleaseFormula("captured preview alias tree entry is malformed")
    mode, object_type, object_id = fields
    if mode != b"120000" or object_type != b"blob":
        raise InvalidReleaseFormula("captured preview alias must be a symlink blob")
    blob = _git(root, "cat-file", "blob", object_id.decode("ascii"))
    if blob != ALIAS_TARGET:
        raise InvalidReleaseFormula("captured preview alias has an unexpected symlink target")
    if os.readlink(alias_path).encode("utf-8") != blob:
        raise InvalidReleaseFormula("working preview alias differs from the captured source tree")


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (2, 3):
            raise InvalidReleaseFormula("usage: homebrew_install_policy.py REPOSITORY [preview|stable]")
        repository = Path(sys.argv[1])
        channel = sys.argv[2] if len(sys.argv) == 3 else os.environ.get("VELNOR_TAP_CHANNEL", "preview")
        if channel not in FORMULA_PATHS:
            raise InvalidReleaseFormula("release channel is unsupported")
        root = repository.resolve(strict=True)
        validate_formula(root / FORMULA_PATHS[channel], channel)
        if channel == "preview":
            validate_runtime_alias(root, os.environ.get("VELNOR_CHECK_HEAD", ""))
    except (IndexError, OSError, UnicodeError, InvalidReleaseFormula) as error:
        print(f"Homebrew formula rejected: {error}", file=sys.stderr)
        raise SystemExit(2) from error
