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
SHA256_LINE_RE = re.compile(r'^\s+sha256 "([0-9a-f]{64})"$')
URL_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])url(?![A-Za-z0-9_])")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
FORMULA_PATHS = {"preview": "Formula/jackin-preview.rb", "stable": "Formula/jackin.rb"}
FORMULA_SUPPORT_PATH = "lib/jackin_formula_support.rb"
UNSUPPORTED_CHANNEL = "release channel is unsupported"


class InvalidReleaseFormula(ValueError):
    """The formula does not describe one exact release channel inventory."""


def validate_formula_text(formula: str, channel: str = "preview") -> tuple[str, tuple[str, ...]]:
    """Return version and exact URLs, rejecting any inventory drift."""
    if channel not in FORMULA_PATHS:
        raise InvalidReleaseFormula(UNSUPPORTED_CHANNEL)
    version = _validate_version(formula, channel)
    _validate_source_identity(formula, version, channel)
    expected_urls = _expected_urls(version, channel, _source_sha(formula))
    actual_urls = _validate_formula_asset_inventory(formula, expected_urls)
    return version, actual_urls


def _validate_version(formula: str, channel: str) -> str:
    version_lines = [line for line in formula.splitlines() if line.startswith("  version")]
    versions = [match.group(1) for line in version_lines if (match := VERSION_LINE_RE.fullmatch(line))]
    version_pattern = VERSION_RE if channel == "preview" else STABLE_VERSION_RE
    if len(version_lines) != 1 or len(versions) != 1 or version_pattern.fullmatch(versions[0]) is None:
        raise InvalidReleaseFormula("formula version does not match the selected release channel")
    return versions[0]


def _source_sha(formula: str) -> str:
    source_lines = [line for line in formula.splitlines() if line.startswith("# source-sha")]
    source_shas = [match.group(1) for line in source_lines if (match := SOURCE_SHA_LINE_RE.fullmatch(line))]
    if len(source_lines) != 1 or len(source_shas) != 1:
        raise InvalidReleaseFormula("formula source commit does not match the selected release version")
    return source_shas[0]


def _validate_source_identity(formula: str, version: str, channel: str) -> None:
    source_sha = _source_sha(formula)
    if channel == "preview" and not source_sha.startswith(version.rsplit("+", 1)[1]):
        raise InvalidReleaseFormula("formula source commit does not match the selected release version")
    if channel == "stable" and (version == "0.0.0" or source_sha == "0" * 40):
        raise InvalidReleaseFormula("stable formula does not identify a published release")


def _expected_urls(version: str, channel: str, source_sha: str) -> tuple[str, ...]:
    tag = f"preview-{source_sha}" if channel == "preview" else f"v{version}"
    prefix = f"https://github.com/jackin-project/jackin/releases/download/{tag}/"

    return tuple(prefix + archive for archive in ARCHIVES)


def _validate_formula_asset_inventory(formula: str, expected_urls: tuple[str, ...]) -> tuple[str, ...]:
    urls: list[str] = []
    checksums: list[str] = []
    for line in formula.splitlines():
        match = URL_LINE_RE.fullmatch(line)
        if match is not None:
            urls.append(match.group(1))
        elif URL_TOKEN_RE.search(line) is not None:
            raise InvalidReleaseFormula("formula contains an unsupported or nonliteral URL declaration")
        checksum = SHA256_LINE_RE.fullmatch(line)
        if checksum is not None:
            checksums.append(checksum.group(1))
    urls = tuple(urls)
    if Counter(urls) != Counter(expected_urls):
        raise InvalidReleaseFormula("formula URLs must exactly match the six immutable release assets")
    if len(checksums) != len(ARCHIVES) or any(checksum == "0" * 64 for checksum in checksums):
        raise InvalidReleaseFormula("formula must contain six published nonzero SHA-256 checksums")
    return urls


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


def validate_runtime_formula(repository: Path, channel: str, check_head: str) -> None:
    """Bind the directly installed channel formula to the captured source head."""
    if channel not in FORMULA_PATHS:
        raise InvalidReleaseFormula(UNSUPPORTED_CHANNEL)
    if COMMIT_RE.fullmatch(check_head) is None:
        raise InvalidReleaseFormula("the native check must provide a full source commit")

    root = repository.resolve(strict=True)
    formula = root / FORMULA_PATHS[channel]
    formula_parent = root / "Formula"
    if not stat.S_ISDIR(formula_parent.lstat().st_mode):
        raise InvalidReleaseFormula("formula parent must be a real directory")
    mode = formula.lstat().st_mode
    if not stat.S_ISREG(mode) or formula.resolve(strict=True).parent != formula_parent:
        raise InvalidReleaseFormula("formula must be a regular file contained by the captured repository")
    _validate_checkout_head(root, check_head)
    _validate_captured_formula(root, formula, channel, check_head)
    _validate_captured_support(root, check_head)
    validate_formula(formula, channel)


def _validate_checkout_head(root: Path, check_head: str) -> None:
    checkout_head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    try:
        checkout_source = _git(root, "rev-parse", "--verify", "HEAD^2^{commit}").decode("ascii").strip()
    except InvalidReleaseFormula:
        checkout_source = ""
    if check_head not in (checkout_head, checkout_source):
        raise InvalidReleaseFormula("the native check head is not the checkout commit or its PR merge second parent")


def _validate_captured_formula(root: Path, formula: Path, channel: str, check_head: str) -> None:
    relative_path = FORMULA_PATHS[channel]
    tree_entry = _git(root, "ls-tree", "-z", "--full-tree", check_head, "--", relative_path)
    records = tree_entry.split(b"\0")
    if len(records) != 2 or not records[0]:
        raise InvalidReleaseFormula("captured source tree must contain exactly one channel formula")
    metadata, separator, name = records[0].partition(b"\t")
    fields = metadata.split()
    if separator != b"\t" or name != relative_path.encode("ascii") or len(fields) != 3:
        raise InvalidReleaseFormula("captured formula tree entry is malformed")
    mode, object_type, object_id = fields
    if mode not in (b"100644", b"100755") or object_type != b"blob":
        raise InvalidReleaseFormula("captured channel formula must be a regular file blob")
    blob = _git(root, "cat-file", "blob", object_id.decode("ascii"))
    if formula.read_bytes() != blob:
        raise InvalidReleaseFormula("working formula differs from the captured source tree")


def _validate_captured_support(root: Path, check_head: str) -> None:
    support = root / FORMULA_SUPPORT_PATH
    support_parent = root / "lib"
    try:
        parent_mode = support_parent.lstat().st_mode
        metadata = support.lstat()
        real_parent = support.resolve(strict=True).parent
    except OSError as error:
        raise InvalidReleaseFormula("formula support is missing or inaccessible") from error
    if not stat.S_ISDIR(parent_mode):
        raise InvalidReleaseFormula("formula support parent must be a real directory")
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise InvalidReleaseFormula("formula support must be a regular single-link file")
    if real_parent != support_parent:
        raise InvalidReleaseFormula("formula support must be contained by the captured repository")

    tree_entry = _git(root, "ls-tree", "-z", "--full-tree", check_head, "--", FORMULA_SUPPORT_PATH)
    records = tree_entry.split(b"\0")
    if len(records) != 2 or not records[0]:
        raise InvalidReleaseFormula("captured source tree must contain exactly one formula support file")
    metadata, separator, name = records[0].partition(b"\t")
    fields = metadata.split()
    if separator != b"\t" or name != FORMULA_SUPPORT_PATH.encode("ascii") or len(fields) != 3:
        raise InvalidReleaseFormula("captured formula support tree entry is malformed")
    mode, object_type, object_id = fields
    if mode not in (b"100644", b"100755") or object_type != b"blob":
        raise InvalidReleaseFormula("captured formula support must be a regular file blob")
    blob = _git(root, "cat-file", "blob", object_id.decode("ascii"))
    if support.read_bytes() != blob:
        raise InvalidReleaseFormula("formula support differs from the captured source tree")


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (2, 3):
            raise InvalidReleaseFormula("usage: homebrew_install_policy.py REPOSITORY [preview|stable]")
        repository = Path(sys.argv[1])
        channel = sys.argv[2] if len(sys.argv) == 3 else os.environ.get("VELNOR_TAP_CHANNEL", "preview")
        if channel not in FORMULA_PATHS:
            raise InvalidReleaseFormula(UNSUPPORTED_CHANNEL)
        root = repository.resolve(strict=True)
        validate_runtime_formula(root, channel, os.environ.get("VELNOR_CHECK_HEAD", ""))
    except (IndexError, OSError, UnicodeError, InvalidReleaseFormula) as error:
        print(f"Homebrew formula rejected: {error}", file=sys.stderr)
        raise SystemExit(2) from error
