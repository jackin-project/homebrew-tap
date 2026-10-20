#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
"""Rewrite only a channel formula's literal metadata from Velnor's handoff."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


from package_update_validation import (
    ENVIRONMENT,
    FORMULA_PATHS,
    HEX40,
    HEX64,
    MAX_RECEIPT_BYTES,
    PREVIEW_VERSION,
    PRODUCTS,
    SEMVER,
    SOURCE_REPOSITORY,
    canonical_receipt,
    fail,
    validate_plan,
    validate_receipt,
)


def parse_old_version(value: str, source: str, channel: str) -> tuple[tuple[int, int, int], int]:
    if channel == "preview":
        match = PREVIEW_VERSION.fullmatch(value)
        if not match or not source.startswith(match.group("sha")):
            raise fail("formula preview identity malformed")
        return tuple(int(part) for part in match.group("base").split(".")), int(match.group("count"))
    if not SEMVER.fullmatch(value) or not HEX40.fullmatch(source):
        raise fail("formula stable identity malformed")
    return tuple(int(part) for part in value.split(".")), 0


def parse_release_url(value: str) -> tuple[str, str]:
    prefix = f"https://github.com/{SOURCE_REPOSITORY}/releases/download/"
    if not value.startswith(prefix):
        raise fail("formula release URL source mismatch")
    remainder = value[len(prefix) :]
    if "/" not in remainder:
        raise fail("formula release URL malformed")
    tag, name = remainder.split("/", 1)
    if not tag or not name or "/" in name:
        raise fail("formula release URL malformed")
    return tag, name


class FormulaRewrite:
    """Track the exact literal metadata slots while preserving all other bytes."""

    def __init__(self, receipt: dict[str, Any], payload_digests: dict[str, str]) -> None:
        self.receipt = receipt
        self.payload_digests = payload_digests
        self.slots = {"source": 0, "version": 0, "urls": 0, "hashes": 0}
        self.prior_source: str | None = None
        self.prior_version: str | None = None
        self.last_url: str | None = None
        self.seen: list[str] = []
        self.channel = receipt["channel"]

    def rewrite_line(self, line: str) -> str:
        if line.startswith("# source-sha:"):
            return self.rewrite_source(line)
        if line.startswith("  version "):
            return self.rewrite_version(line)
        url_prefix = next((prefix for prefix in ('      url "', '    url "') if line.startswith(prefix)), None)
        if url_prefix is not None:
            return self.rewrite_url(line, url_prefix)
        hash_prefix = next((prefix for prefix in ('      sha256 "', '    sha256 "') if line.startswith(prefix)), None)
        if hash_prefix is not None:
            return self.rewrite_hash(line, hash_prefix)
        if line.startswith(("# source-sha:", "  version ", "      url ", "      sha256 ", "    url ", "    sha256 ")):
            raise fail("unsupported formula metadata syntax")
        return line

    def rewrite_source(self, line: str) -> str:
        if not line.startswith("# source-sha: ") or not line.endswith("\n"):
            raise fail("unsupported source metadata syntax")
        old_source = line[len("# source-sha: ") : -1]
        if not HEX40.fullmatch(old_source):
            raise fail("formula source SHA malformed")
        self.slots["source"] += 1
        self.prior_source = old_source
        return f"# source-sha: {self.receipt['source']['commit_sha']}\n"

    def rewrite_version(self, line: str) -> str:
        prefix, suffix = '  version "', '"\n'
        if not line.startswith(prefix) or not line.endswith(suffix):
            raise fail("unsupported version metadata syntax")
        old_version = line[len(prefix) : -len(suffix)]
        parse_old_version(old_version, self.prior_source or "", self.channel)
        self.slots["version"] += 1
        self.prior_version = old_version
        return f'  version "{self.receipt["version"]["value"]}"\n'

    def rewrite_url(self, line: str, prefix: str) -> str:
        if not line.endswith('"\n'):
            raise fail("unsupported URL metadata syntax")
        old_tag, name = parse_release_url(line[len(prefix) : -2])
        expected_old_tag = "preview" if self.channel == "preview" else f"v{self.prior_version}"
        if self.prior_version is None or old_tag != expected_old_tag or name not in self.payload_digests:
            raise fail("formula base release binding mismatch")
        if name not in self.seen:
            self.seen.append(name)
        self.last_url = name
        self.slots["urls"] += 1
        indent = line[: len(line) - len(line.lstrip(" "))]
        return f'{indent}url "https://github.com/{SOURCE_REPOSITORY}/releases/download/{self.receipt["tag"]}/{name}"\n'

    def rewrite_hash(self, line: str, prefix: str) -> str:
        if not line.endswith('"\n'):
            raise fail("unsupported SHA-256 metadata syntax")
        old_hash = line[len(prefix) : -2]
        if not HEX64.fullmatch(old_hash) or self.last_url is None:
            raise fail("formula SHA-256 metadata malformed or unpaired")
        replacement = f'{line[: len(line) - len(line.lstrip(" "))]}sha256 "{self.payload_digests[self.last_url]}"\n'
        self.slots["hashes"] += 1
        self.last_url = None
        return replacement

    def validate(self) -> None:
        slots = self.slots
        if slots["source"] != 1 or slots["version"] != 1 or len(self.seen) != 6 or slots["urls"] != 6 or slots["hashes"] != 6 or self.last_url is not None:
            raise fail("formula metadata inventory mismatch")
        if set(self.seen) != set(self.payload_digests):
            raise fail("formula payload inventory mismatch")
        if self.prior_source is None or self.prior_version is None:
            raise fail("formula source or version missing")
        validate_channel_transition(self.prior_source, self.prior_version, self.receipt, self.channel)

    def is_exact_retry(self) -> bool:
        if self.prior_source != self.receipt["source"]["commit_sha"] or self.prior_version is None:
            return False
        if self.channel == "stable":
            return self.prior_version == self.receipt["version"]["value"]
        prior_base, prior_count = parse_old_version(self.prior_version, self.prior_source, self.channel)
        return prior_base == tuple(int(part) for part in self.receipt["version"]["base"].split(".")) and prior_count == self.receipt["version"]["commit_count"]


def validate_channel_transition(prior_source: str, prior_version: str, receipt: dict[str, Any], channel: str) -> None:
    old_version, old_count = parse_old_version(prior_version, prior_source, channel)
    new_version = tuple(int(part) for part in receipt["version"]["base"].split("."))
    new_count = receipt["version"]["commit_count"] if channel == "preview" else 0
    if new_version < old_version or (channel == "preview" and new_version == old_version and new_count < old_count):
        raise fail(f"{channel} formula downgrade")
    if new_version == old_version and (channel == "stable" or new_count == old_count):
        if prior_source != receipt["source"]["commit_sha"]:
            raise fail(f"{channel} formula retry identity conflict")


def rewrite_formula(base: bytes, receipt: dict[str, Any], payload_digests: dict[str, str]) -> bytes:
    if not base or len(base) > 1024 * 1024 or any(byte > 0x7F for byte in base):
        raise fail("formula size or encoding invalid")
    try:
        text = base.decode("ascii")
    except UnicodeDecodeError as error:
        raise fail("formula encoding invalid") from error
    rewrite = FormulaRewrite(receipt, payload_digests)
    output = [rewrite.rewrite_line(line) for line in text.splitlines(keepends=True)]
    rewrite.validate()
    result = "".join(output).encode("ascii")
    if rewrite.is_exact_retry() and result != base:
        raise fail("release retry changes published formula metadata")
    return result


def read_handoff_file(path_value: str, digest: str, label: str) -> bytes:
    path = Path(path_value)
    if not path.is_absolute():
        raise fail(f"{label} path must be absolute")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_RECEIPT_BYTES:
            raise fail(f"{label} path is not a bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(MAX_RECEIPT_BYTES + 1)
    finally:
        os.close(fd)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise fail(f"{label} digest mismatch")
    return raw


def load_handoff(env: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    unexpected = sorted(key for key in env if key.startswith("VELNOR_TAP_") and key not in ENVIRONMENT)
    if unexpected:
        raise fail(f"unexpected Velnor tap handoff field: {unexpected[0]}")
    missing = [key for key in ENVIRONMENT if not env.get(key)]
    if missing:
        raise fail(f"missing Velnor handoff field: {missing[0]}")
    if env["VELNOR_TAP_FORMULA_PATH"] not in FORMULA_PATHS.values():
        raise fail("unexpected formula path")
    base_sha = env["VELNOR_TAP_BASE_SHA"]
    source_sha = env["VELNOR_TAP_SOURCE_SHA"]
    receipt_digest = env["VELNOR_TAP_RELEASE_RECEIPT_SHA256"]
    if not HEX40.fullmatch(base_sha) or not HEX40.fullmatch(source_sha) or not HEX64.fullmatch(receipt_digest):
        raise fail("handoff digest or commit identity malformed")

    plan_raw = read_handoff_file(
        env["VELNOR_TAP_RELEASE_PLAN"], env["VELNOR_TAP_RELEASE_PLAN_SHA256"], "release plan"
    )
    receipt_raw = read_handoff_file(env["VELNOR_TAP_RELEASE_RECEIPT"], receipt_digest, "receipt")
    plan = validate_plan(plan_raw)
    receipt = canonical_receipt(receipt_raw)
    payload_digests = validate_receipt(receipt, env, plan)
    return receipt, plan, payload_digests


def atomic_write_formula(path: Path, content: bytes) -> None:
    parent_metadata = path.parent.lstat()
    if not stat.S_ISDIR(parent_metadata.st_mode):
        raise fail("formula parent is not a real directory")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise fail("formula path is not a regular file")
    original = path.read_bytes()
    if original == content:
        return
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".jackin-preview.", delete=False) as stream:
            temporary = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, stat.S_IMODE(metadata.st_mode))
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def main() -> int:
    try:
        receipt, _plan, payload_digests = load_handoff(dict(os.environ))
        formula_path = Path(FORMULA_PATHS[receipt["channel"]])
        if not stat.S_ISDIR(formula_path.parent.lstat().st_mode):
            raise fail("formula parent is not a real directory")
        if not stat.S_ISREG(formula_path.lstat().st_mode):
            raise fail("formula path is not a regular file")
        base = formula_path.read_bytes()
        updated = rewrite_formula(base, receipt, payload_digests)
        atomic_write_formula(formula_path, updated)
    except (OSError, ValueError, RecursionError) as error:
        print(f"Homebrew formula update rejected: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
