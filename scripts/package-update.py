#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
"""Rewrite only a channel formula's literal metadata from Velnor's handoff."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


SOURCE_REPOSITORY = "jackin-project/jackin"
FORMULA_PATHS = {"preview": "Formula/jackin-preview.rb", "stable": "Formula/jackin.rb"}
CAPSULE_MANIFEST_NAME = "capsule-manifest.json"
TARGETS = (
    "aarch64-apple-darwin",
    "aarch64-unknown-linux-gnu",
    "x86_64-apple-darwin",
    "x86_64-unknown-linux-gnu",
)
CAPSULE_TARGETS = ("aarch64-unknown-linux-gnu", "x86_64-unknown-linux-gnu")
PRODUCTS = {
    "jackin": ("jackin", ("jackin", "jackin-role", "jackin-usage-broker"), TARGETS),
    "jackin-capsule": ("jackin-capsule", ("jackin-capsule",), CAPSULE_TARGETS),
}
PAYLOAD_NAMES = tuple(
    sorted(f"{product_id}-{target}.tar.gz" for product_id, (_, _, targets) in PRODUCTS.items() for target in targets)
)
ENVIRONMENT = (
    "VELNOR_TAP_BASE_SHA",
    "VELNOR_TAP_FORMULA_PATH",
    "VELNOR_TAP_RELEASE_PLAN",
    "VELNOR_TAP_RELEASE_PLAN_SHA256",
    "VELNOR_TAP_RELEASE_RECEIPT",
    "VELNOR_TAP_RELEASE_RECEIPT_SHA256",
    "VELNOR_TAP_RELEASE_VERSION",
    "VELNOR_TAP_RELEASE_TAG",
    "VELNOR_TAP_SOURCE_SHA",
)
MAX_RECEIPT_BYTES = 1024 * 1024
U64_MAX = (1 << 64) - 1
U32_MAX = (1 << 32) - 1
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
PREVIEW_VERSION = re.compile(
    r"(?P<base>(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))-preview\.(?P<count>[1-9][0-9]*)\+(?P<sha>[0-9a-f]{7})\Z"
)


class UpdateError(ValueError):
    """Rejected receipt or formula input."""


def fail(reason: str) -> UpdateError:
    return UpdateError(reason)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise fail("duplicate JSON object key")
        value[key] = item
    return value


def exact_keys(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise fail(f"invalid {field} fields")
    return value


def string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise fail(f"invalid {field}")
    return value


def canonical_receipt(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > MAX_RECEIPT_BYTES or any(byte > 0x7F for byte in raw):
        raise fail("receipt size or encoding invalid")
    try:
        receipt = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise fail("receipt JSON invalid") from error
    if not isinstance(receipt, dict):
        raise fail("receipt root must be an object")
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("ascii")
    if encoded != raw:
        raise fail("receipt is not canonical JSON")
    return receipt


def validate_plan(raw: bytes) -> dict[str, Any]:
    plan = canonical_receipt(raw)
    exact_keys(plan, {"schema", "channel", "repository", "default_branch", "base_version", "products", "companions"}, "release plan")
    if plan["schema"] != "velnor.package-release-plan.v1" or plan["channel"] not in FORMULA_PATHS:
        raise fail("unsupported release plan")
    if plan["repository"] != SOURCE_REPOSITORY or not isinstance(plan["default_branch"], str):
        raise fail("release plan source identity mismatch")
    if not SEMVER.fullmatch(plan["base_version"]):
        raise fail("release plan base version malformed")
    if plan["channel"] == "preview" and plan["default_branch"] != "main":
        raise fail("preview release plan must target main")
    if not isinstance(plan["products"], list) or not isinstance(plan["companions"], list):
        raise fail("release plan inventory malformed")
    expected_products = []
    for product_id, (package, bins, targets) in sorted(PRODUCTS.items()):
        expected_products.append({"id": product_id, "package": package, "bins": list(bins), "targets": list(targets), "format": "tar-gz"})
    if plan["products"] != expected_products:
        raise fail("release plan product inventory mismatch")
    if plan["companions"] != [{"id": "capsule-manifest", "path": "capsule-manifest.json", "asset_name": CAPSULE_MANIFEST_NAME}]:
        raise fail("release plan companion inventory mismatch")
    return plan


def validate_receipt(receipt: dict[str, Any], env: dict[str, str], plan: dict[str, Any]) -> dict[str, str]:
    exact_keys(
        receipt,
        {"schema", "channel", "repository", "source", "workflow", "version", "tag", "products", "companions", "assets", "evidence"},
        "receipt",
    )
    channel = receipt["channel"]
    if receipt["schema"] != "velnor.package-release.v2" or channel not in FORMULA_PATHS:
        raise fail("unsupported package release")
    if env["VELNOR_TAP_FORMULA_PATH"] != FORMULA_PATHS[channel]:
        raise fail("release channel formula destination mismatch")
    if channel != plan["channel"]:
        raise fail("release plan channel mismatch")

    repository = exact_keys(receipt["repository"], {"slug", "id"}, "repository")
    if (
        repository["slug"] != SOURCE_REPOSITORY
        or type(repository["id"]) is not int
        or not 0 < repository["id"] <= U64_MAX
    ):
        raise fail("source repository mismatch")

    source = exact_keys(
        receipt["source"],
        {"commit_sha", "ref", "default_branch", "event", "ci_run_id", "ci_run_attempt"},
        "source",
    )
    source_sha = string(source["commit_sha"], "source commit")
    expected_ref = f"refs/heads/{plan['default_branch']}"
    expected_event = "workflow_run" if channel == "preview" else "workflow_dispatch"
    if (
        not HEX40.fullmatch(source_sha)
        or source["ref"] != expected_ref
        or source["default_branch"] != plan["default_branch"]
        or source["event"] != expected_event
        or type(source["ci_run_id"]) is not int
        or not 0 < source["ci_run_id"] <= U64_MAX
        or type(source["ci_run_attempt"]) is not int
        or not 0 < source["ci_run_attempt"] <= U32_MAX
    ):
        raise fail("source identity mismatch")

    workflow = exact_keys(
        receipt["workflow"],
        {"path", "ref", "authority_sha", "run_id", "run_attempt", "producer_run_id", "producer_run_attempt", "signer_job_id", "signer_workflow"},
        "workflow",
    )
    workflow_path = ".github/workflows/binary-preview.yml" if channel == "preview" else ".github/workflows/binary-release.yml"
    signer_job = "preview-signer" if channel == "preview" else "stable-signer"
    if (
        workflow["path"] != workflow_path
        or workflow["ref"] != expected_ref
        or workflow["authority_sha"] != source_sha
        or workflow["run_id"] != workflow["producer_run_id"]
        or workflow["run_attempt"] != workflow["producer_run_attempt"]
        or type(workflow["run_id"]) is not int
        or not 0 < workflow["run_id"] <= U64_MAX
        or type(workflow["run_attempt"]) is not int
        or not 0 < workflow["run_attempt"] <= U32_MAX
        or workflow["signer_job_id"] != signer_job
        or workflow["signer_workflow"] != workflow_path
    ):
        raise fail("workflow identity mismatch")

    version_record = exact_keys(receipt["version"], {"base", "value", "commit_count", "source_sha7"}, "version")
    base = string(version_record["base"], "base version")
    version = string(version_record["value"], "release version")
    match = PREVIEW_VERSION.fullmatch(version)
    count = version_record["commit_count"]
    sha7 = version_record["source_sha7"]
    if not SEMVER.fullmatch(base) or base != plan["base_version"]:
        raise fail("release base version differs from plan")
    if channel == "preview":
        if (not match or match.group("base") != base or not source_sha.startswith(match.group("sha"))
                or match.group("sha") != sha7 or type(count) is not int or not 0 < count <= U64_MAX
                or int(match.group("count")) != count or receipt["tag"] != "preview"):
            raise fail("deterministic preview identity mismatch")
    elif version != base or count is not None or sha7 is not None or receipt["tag"] != f"v{base}":
        raise fail("immutable stable release identity mismatch")

    if (
        env["VELNOR_TAP_RELEASE_VERSION"] != version
        or env["VELNOR_TAP_RELEASE_TAG"] != receipt["tag"]
        or env["VELNOR_TAP_SOURCE_SHA"] != source_sha
    ):
        raise fail("handoff identity differs from receipt")

    validate_products(receipt["products"], base)
    validate_companions(receipt["companions"])
    payload_digests = validate_assets(receipt["assets"])
    validate_evidence(receipt["evidence"], payload_digests, channel)
    return payload_digests


def validate_products(products: Any, base: str) -> None:
    if not isinstance(products, list) or len(products) != len(PRODUCTS):
        raise fail("product inventory mismatch")
    if [product.get("id") if isinstance(product, dict) else None for product in products] != sorted(PRODUCTS):
        raise fail("product inventory is not canonically ordered")
    seen: set[str] = set()
    for product in products:
        validate_product(product, base, seen)


def validate_product(product: Any, base: str, seen: set[str]) -> None:
    product = exact_keys(product, {"id", "package", "package_version", "bins", "payloads"}, "product")
    product_id = string(product["id"], "product id")
    expected = PRODUCTS.get(product_id)
    if not expected or product_id in seen:
        raise fail("unexpected product identity")
    seen.add(product_id)
    package, bins, targets = expected
    if product["package"] != package or product["package_version"] != base or product["bins"] != list(bins):
        raise fail("product package or executable inventory mismatch")
    payloads = product["payloads"]
    if not isinstance(payloads, list) or len(payloads) != len(targets):
        raise fail("product target inventory mismatch")
    for payload, target in zip(payloads, targets, strict=True):
        payload = exact_keys(payload, {"format", "target", "name", "members"}, "payload")
        name = f"{product_id}-{target}.tar.gz"
        if payload != {"format": "tar-gz", "target": target, "name": name, "members": list(bins)}:
            raise fail("payload inventory mismatch")


def validate_companions(companions: Any) -> None:
    if companions != [{"id": "capsule-manifest", "name": CAPSULE_MANIFEST_NAME}]:
        raise fail("companion inventory mismatch")


def validate_assets(assets: Any) -> dict[str, str]:
    if not isinstance(assets, list) or len(assets) != 27:
        raise fail("release asset inventory size mismatch")
    expected: dict[str, tuple[str, str | None, str | None, str | None]] = {}
    for product_id, (_package, _bins, targets) in PRODUCTS.items():
        for target in targets:
            name = f"{product_id}-{target}.tar.gz"
            owner = (product_id, target, name)
            expected[name] = ("payload", *owner)
            expected[f"{name}.sha256"] = ("sha256", *owner)
            expected[f"{name}.bundle"] = ("signature_bundle", *owner)
            expected[f"{name}.sbom.json"] = ("sbom", *owner)
    expected["SHA256SUMS"] = ("checksum_list", None, None, None)
    expected[CAPSULE_MANIFEST_NAME] = ("companion", None, None, CAPSULE_MANIFEST_NAME)
    expected["capsule-manifest.json.bundle"] = (
        "companion_signature_bundle", None, None, CAPSULE_MANIFEST_NAME
    )
    if any(not isinstance(asset, dict) or not isinstance(asset.get("name"), str) for asset in assets):
        raise fail("release asset record malformed")
    if set(expected) != {asset["name"] for asset in assets}:
        raise fail("release asset names mismatch")
    by_name: dict[str, str] = {}
    for asset in assets:
        asset = exact_keys(asset, {"name", "kind", "product_id", "target", "subject_name", "size", "sha256"}, "asset")
        name = string(asset["name"], "asset name")
        kind, product_id, target, subject = expected.get(name, ("", None, None, None))
        if (
            asset["kind"] != kind
            or asset["product_id"] != product_id
            or asset["target"] != target
            or asset["subject_name"] != subject
            or type(asset["size"]) is not int
            or not 0 < asset["size"] <= U64_MAX
            or not isinstance(asset["sha256"], str)
            or not HEX64.fullmatch(asset["sha256"])
        ):
            raise fail("release asset binding mismatch")
        if name in by_name:
            raise fail("duplicate release asset")
        by_name[name] = asset["sha256"]
    if tuple(asset["name"] for asset in assets) != tuple(sorted(expected)):
        raise fail("release assets are not canonical order")
    return {name: by_name[name] for name in PAYLOAD_NAMES}


def validate_evidence(evidence: Any, payload_digests: dict[str, str], channel: str) -> None:
    evidence = exact_keys(
        evidence,
        {"profile", "sbom_format", "signer_issuer", "signer_workflow_ref", "attestation_predicate", "attested_subject_names"},
        "evidence",
    )
    expected_subjects = sorted([*payload_digests, CAPSULE_MANIFEST_NAME, "release.json"])
    workflow_path = ".github/workflows/binary-preview.yml" if channel == "preview" else ".github/workflows/binary-release.yml"
    if (
        evidence["profile"] != "signed-sbom-v1"
        or evidence["sbom_format"] != "CycloneDX-JSON"
        or evidence["signer_issuer"] != "https://token.actions.githubusercontent.com"
        or evidence["signer_workflow_ref"]
        != f"jackin-project/jackin/{workflow_path}@refs/heads/main"
        or evidence["attestation_predicate"] != "https://slsa.dev/provenance/v1"
        or evidence["attested_subject_names"] != expected_subjects
    ):
        raise fail("release evidence identity mismatch")


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
