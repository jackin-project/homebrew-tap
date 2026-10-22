# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
"""Validate Velnor package-release plans and receipts before formula edits."""

from __future__ import annotations

import json
import re
from collections import Counter
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

    source_sha = validate_source_identity(receipt, plan, channel)
    validate_workflow_identity(receipt, source_sha, plan, channel)
    base = validate_release_version(receipt, env, plan, channel, source_sha)
    payload_digests = validate_assets(receipt["assets"])
    validate_products(receipt["products"], base)
    validate_companions(receipt["companions"])
    validate_evidence(receipt["evidence"], payload_digests, channel)
    return payload_digests


def validate_source_identity(receipt: dict[str, Any], plan: dict[str, Any], channel: str) -> str:
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
    return source_sha


def validate_workflow_identity(receipt: dict[str, Any], source_sha: str, plan: dict[str, Any], channel: str) -> None:
    expected_ref = f"refs/heads/{plan['default_branch']}"
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


def validate_release_version(
    receipt: dict[str, Any], env: dict[str, str], plan: dict[str, Any], channel: str, source_sha: str
) -> str:
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
                or int(match.group("count")) != count or receipt["tag"] != f"preview-{source_sha}"):
            raise fail("deterministic preview identity mismatch")
    elif version != base or count is not None or sha7 is not None or receipt["tag"] != f"v{base}":
        raise fail("immutable stable release identity mismatch")

    if (
        env["VELNOR_TAP_RELEASE_VERSION"] != version
        or env["VELNOR_TAP_RELEASE_TAG"] != receipt["tag"]
        or env["VELNOR_TAP_SOURCE_SHA"] != source_sha
    ):
        raise fail("handoff identity differs from receipt")
    return base


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


