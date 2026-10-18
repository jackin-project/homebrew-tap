#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
"""Acceptance tests for the credential-free, formula-only preview updater."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts/package-update.py"
FORMULA = ROOT / "Formula/jackin-preview.rb"
SCRIPT = ROOT / "scripts/package-update.sh"
SOURCE_OLD = "0123456" + "1" * 33
SOURCE_NEW = "abcdef0" + "2" * 33
SOURCE_TAMPERED = "fedcba9" + "3" * 33
TARGETS = (
    "aarch64-apple-darwin",
    "aarch64-unknown-linux-gnu",
    "x86_64-apple-darwin",
    "x86_64-unknown-linux-gnu",
)
CAPSULE_TARGETS = ("aarch64-unknown-linux-gnu", "x86_64-unknown-linux-gnu")
PRODUCTS = (
    ("jackin", "jackin", ["jackin", "jackin-role", "jackin-usage-broker"], TARGETS),
    ("jackin-capsule", "jackin-capsule", ["jackin-capsule"], CAPSULE_TARGETS),
)

spec = importlib.util.spec_from_file_location("package_update", UPDATER)
if spec is None or spec.loader is None:
    raise RuntimeError("could not load updater module")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fixture_receipt(
    source_sha: str = SOURCE_NEW,
    count: int = 42,
    base: str = "0.6.4",
    inventory_mutation: str | None = None,
) -> dict[str, Any]:
    version = f"{base}-preview.{count}+{source_sha[:7]}"
    products: list[dict[str, Any]] = []
    payload_names: list[tuple[str, str, str]] = []
    for product_id, package, bins, targets in PRODUCTS:
        payloads = []
        for target in targets:
            name = f"{product_id}-{target}.tar.gz"
            payload_names.append((product_id, target, name))
            payloads.append({"format": "tar-gz", "target": target, "name": name, "members": bins})
        products.append(
            {"id": product_id, "package": package, "package_version": base, "bins": bins, "payloads": payloads}
        )

    records: dict[str, tuple[str, str | None, str | None, str | None]] = {}
    for product_id, target, name in payload_names:
        binding = (product_id, target, name)
        records[name] = ("payload", *binding)
        records[f"{name}.sha256"] = ("sha256", *binding)
        records[f"{name}.bundle"] = ("signature_bundle", *binding)
        records[f"{name}.sbom.json"] = ("sbom", *binding)
    records["SHA256SUMS"] = ("checksum_list", None, None, None)
    records["capsule-manifest.json"] = ("companion", None, None, "capsule-manifest.json")
    records["capsule-manifest.json.bundle"] = (
        "companion_signature_bundle",
        None,
        None,
        "capsule-manifest.json",
    )
    assets = [
        {
            "name": name,
            "kind": kind,
            "product_id": product_id,
            "target": target,
            "subject_name": subject,
            "size": index + 1,
            "sha256": sha256(f"asset:{name}".encode()),
        }
        for index, (name, (kind, product_id, target, subject)) in enumerate(sorted(records.items()))
    ]
    if inventory_mutation == "missing-payload":
        assets = [asset for asset in assets if asset["name"] != payload_names[0][2]]
    elif inventory_mutation == "wrong-target":
        next(asset for asset in assets if asset["kind"] == "payload")["target"] = "x86_64-unknown-linux-gnu"
    elif inventory_mutation == "duplicate-name":
        assets[-1]["name"] = assets[-2]["name"]
    elif inventory_mutation == "wrong-name-type":
        assets[0]["name"] = ["jackin"]
    elif inventory_mutation == "product-order":
        products.reverse()

    return {
        "schema": "velnor.package-release.v2",
        "channel": "preview",
        "repository": {"slug": "jackin-project/jackin", "id": 123456},
        "source": {
            "commit_sha": source_sha,
            "ref": "refs/heads/main",
            "default_branch": "main",
            "event": "push",
            "ci_run_id": 99001,
            "ci_run_attempt": 1,
        },
        "workflow": {
            "path": ".github/workflows/binary-preview.yml",
            "ref": "refs/heads/main",
            "authority_sha": source_sha,
            "run_id": 99002,
            "run_attempt": 1,
            "producer_run_id": 99002,
            "producer_run_attempt": 1,
            "signer_job_id": "preview-signer",
            "signer_workflow": ".github/workflows/binary-preview.yml",
        },
        "version": {
            "base": base,
            "value": version,
            "commit_count": count,
            "source_sha7": source_sha[:7],
        },
        "tag": f"v{version}",
        "products": products,
        "companions": [{"id": "capsule-manifest", "name": "capsule-manifest.json"}],
        "assets": assets,
        "evidence": {
            "profile": "signed-sbom-v1",
            "sbom_format": "CycloneDX-JSON",
            "signer_issuer": "https://token.actions.githubusercontent.com",
            "signer_workflow_ref": "jackin-project/jackin/.github/workflows/binary-preview.yml@refs/heads/main",
            "attestation_predicate": "https://slsa.dev/provenance/v1",
            "attested_subject_names": sorted([name for _, _, name in payload_names] + ["capsule-manifest.json", "release.json"]),
        },
    }


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("ascii")


def formula_for(version: str, source_sha: str, tag: str) -> bytes:
    text = FORMULA.read_text(encoding="ascii")
    text, source_count = re.subn(
        r"(?m)^# source-sha: [0-9a-f]{40}$",
        f"# source-sha: {source_sha}",
        text,
    )
    text, version_count = re.subn(
        r'(?m)^  version "[^"\n]+"$',
        f'  version "{version}"',
        text,
    )
    text, tag_count = re.subn(
        r"(releases/download/)[^/\"\n]+/",
        rf"\g<1>{tag}/",
        text,
    )
    if source_count != 1 or version_count != 1 or tag_count != 6:
        raise AssertionError("preview formula fixture metadata inventory changed")
    return text.encode("ascii")


class PreviewUpdaterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="tap-updater-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "Formula").mkdir()
        (self.repo / "scripts").mkdir()
        shutil.copy2(SCRIPT, self.repo / "scripts/package-update.sh")
        shutil.copy2(UPDATER, self.repo / "scripts/package-update.py")
        self.formula = self.repo / updater.FORMULA_PATH
        self.old_version = "0.6.4-preview.41+0123456"
        self.old_tag = f"v{self.old_version}"
        self.initial = formula_for(self.old_version, SOURCE_OLD, self.old_tag)
        self.formula.write_bytes(self.initial)
        self.receipt_path = self.root / "release.json"
        self.env = self.make_handoff()

    def make_handoff(
        self,
        receipt: dict[str, Any] | None = None,
        *,
        digest_override: str | None = None,
        version_override: str | None = None,
        tag_override: str | None = None,
        source_override: str | None = None,
    ) -> dict[str, str]:
        value = receipt or fixture_receipt()
        raw = canonical(value)
        self.receipt_path.write_bytes(raw)
        return {
            "VELNOR_TAP_BASE_SHA": "9" * 40,
            "VELNOR_TAP_FORMULA_PATH": updater.FORMULA_PATH,
            "VELNOR_TAP_RELEASE_RECEIPT": str(self.receipt_path),
            "VELNOR_TAP_RELEASE_RECEIPT_SHA256": digest_override or sha256(raw),
            "VELNOR_TAP_RELEASE_VERSION": version_override or value["version"]["value"],
            "VELNOR_TAP_RELEASE_TAG": tag_override or value["tag"],
            "VELNOR_TAP_SOURCE_SHA": source_override or value["source"]["commit_sha"],
        }

    def test_payload_targets_follow_native_publisher_lexical_order(self) -> None:
        native_targets = {
            "jackin": [
                "aarch64-apple-darwin",
                "aarch64-unknown-linux-gnu",
                "x86_64-apple-darwin",
                "x86_64-unknown-linux-gnu",
            ],
            "jackin-capsule": [
                "aarch64-unknown-linux-gnu",
                "x86_64-unknown-linux-gnu",
            ],
        }
        self.assertEqual(
            native_targets,
            {product_id: list(targets) for product_id, (_, _, targets) in updater.PRODUCTS.items()},
        )
        fixture_products = {product["id"]: [payload["target"] for payload in product["payloads"]]
                            for product in fixture_receipt()["products"]}
        self.assertEqual(native_targets, fixture_products)

    def run_updater(self, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        task_env = os.environ.copy()
        for key in updater.ENVIRONMENT:
            task_env.pop(key, None)
        task_env.update(self.env if env is None else env)
        return subprocess.run(
            ["python", str(UPDATER)],
            cwd=self.repo,
            env=task_env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_version_grammar_rejects_unicode_decimal_digits(self) -> None:
        base = "10.20.30"
        version = f"{base}-preview.40+abcdef0"
        self.assertIsNotNone(updater.SEMVER.fullmatch(base))
        self.assertIsNotNone(updater.PREVIEW_VERSION.fullmatch(version))
        for index in (1, 4, 7):
            with self.subTest(base_index=index):
                unicode_base = base[:index] + "٠" + base[index + 1 :]
                self.assertIsNone(updater.SEMVER.fullmatch(unicode_base))
                self.assertIsNone(updater.PREVIEW_VERSION.fullmatch(f"{unicode_base}-preview.40+abcdef0"))
        self.assertIsNone(updater.PREVIEW_VERSION.fullmatch(f"{base}-preview.4٠+abcdef0"))

    def test_updates_only_literal_metadata_and_retry_is_byte_identical(self) -> None:
        result = self.run_updater()
        self.assertEqual(0, result.returncode, result.stderr)
        first = self.formula.read_bytes()
        self.assertNotEqual(self.initial, first)
        self.assertIn(f"# source-sha: {SOURCE_NEW}".encode(), first)
        self.assertIn(b'version "0.6.4-preview.42+abcdef0"', first)
        self.assertIn(b"releases/download/v0.6.4-preview.42+abcdef0/", first)
        self.assertIn(b'bin.install "jackin-usage-broker"', first)
        actual_urls = re.findall(rb"releases/download/v[^/]+/([^\"]+)", first)
        actual_hashes = re.findall(rb'^\s+sha256 "([0-9a-f]{64})"$', first, re.MULTILINE)
        expected_hashes = {
            asset["name"]: asset["sha256"]
            for asset in fixture_receipt()["assets"]
            if asset["kind"] == "payload"
        }
        self.assertEqual(6, len(actual_urls))
        self.assertEqual(6, len(actual_hashes))
        self.assertEqual(
            expected_hashes,
            {name.decode("ascii"): digest.decode("ascii") for name, digest in zip(actual_urls, actual_hashes, strict=True)},
        )

        # Only the literal metadata may change; all surrounding Ruby stays byte exact.
        base_lines = self.initial.splitlines(keepends=True)
        actual_lines = first.splitlines(keepends=True)
        self.assertEqual(len(base_lines), len(actual_lines))
        metadata_prefixes = (b"# source-sha: ", b"  version ", b"      url ", b"      sha256 ", b"    url ", b"    sha256 ")
        for old, new in zip(base_lines, actual_lines, strict=True):
            if not old.startswith(metadata_prefixes):
                self.assertEqual(old, new)

        retry = self.run_updater()
        self.assertEqual(0, retry.returncode, retry.stderr)
        self.assertEqual(first, self.formula.read_bytes())

    def assert_rejected_without_formula_write(self, env: dict[str, str] | None = None) -> str:
        result = self.run_updater(env)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(self.initial, self.formula.read_bytes())
        return result.stderr

    def test_tampered_receipt_digest_and_handoff_identities_reject_without_write(self) -> None:
        self.receipt_path.write_bytes(self.receipt_path.read_bytes() + b" ")
        self.assert_rejected_without_formula_write()

        for key, value in (
            ("VELNOR_TAP_RELEASE_VERSION", "0.6.4-preview.43+abcdef0"),
            ("VELNOR_TAP_RELEASE_TAG", "v0.6.4-preview.43+abcdef0"),
            ("VELNOR_TAP_SOURCE_SHA", SOURCE_TAMPERED),
            ("VELNOR_TAP_BASE_SHA", "bad"),
            ("VELNOR_TAP_FORMULA_PATH", "Formula/evil.rb"),
        ):
            with self.subTest(key=key):
                env = self.env.copy()
                env[key] = value
                self.assert_rejected_without_formula_write(env)

        for key in updater.ENVIRONMENT:
            with self.subTest(missing=key):
                env = self.env.copy()
                env.pop(key)
                self.assert_rejected_without_formula_write(env)

    def test_tampered_receipt_inventory_is_rejected_even_with_recomputed_handoff_digest(self) -> None:
        for mutation in (
            "missing-payload",
            "wrong-target",
            "duplicate-name",
            "wrong-name-type",
            "product-order",
        ):
            with self.subTest(mutation=mutation):
                invalid = fixture_receipt(inventory_mutation=mutation)
                env = self.make_handoff(invalid)
                self.assert_rejected_without_formula_write(env)

    def test_downgrade_and_conflicting_equal_version_retry_reject_without_write(self) -> None:
        downgrade = fixture_receipt(count=40, source_sha=SOURCE_TAMPERED)
        self.assert_rejected_without_formula_write(self.make_handoff(downgrade))

        conflict = fixture_receipt(count=41, source_sha=SOURCE_NEW)
        self.assert_rejected_without_formula_write(self.make_handoff(conflict))

    def test_malicious_formula_metadata_is_rejected_without_write(self) -> None:
        malicious = self.initial.replace(
            b'      url "https://github.com/jackin-project/jackin/releases/download/'
            + self.old_tag.encode()
            + b'/jackin-aarch64-apple-darwin.tar.gz"\n',
            b'      url "https://github.com/jackin-project/jackin/releases/download/'
            + self.old_tag.encode()
            + b'/jackin-aarch64-apple-darwin.tar.gz"; system "curl evil"\n',
            1,
        )
        self.formula.write_bytes(malicious)
        self.initial = malicious
        self.assert_rejected_without_formula_write()

    def test_rolling_preview_formula_is_rejected_until_bootstrapped_to_immutable_tag(self) -> None:
        rolling = self.initial.replace(b"releases/download/" + self.old_tag.encode(), b"releases/download/preview")
        self.formula.write_bytes(rolling)
        self.initial = rolling
        self.assert_rejected_without_formula_write()

    def test_wrapper_executes_python_updater(self) -> None:
        wrapper = self.repo / "scripts/package-update.sh"
        result = subprocess.run([str(wrapper)], cwd=self.repo, env={**os.environ, **self.env}, check=False, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(b'version "0.6.4-preview.42+abcdef0"', self.formula.read_bytes())

    def test_updater_has_no_network_archive_or_process_execution_surface(self) -> None:
        tree = ast.parse(UPDATER.read_text(encoding="utf-8"))
        forbidden_imports = {"http", "https", "urllib", "requests", "socket", "subprocess", "tarfile", "zipfile"}
        imported = {
            alias.name.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".", maxsplit=1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertFalse(imported & forbidden_imports)
        forbidden_calls = {"Popen", "system", "popen", "run", "check_call", "check_output"}
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (isinstance(node.func, ast.Attribute) or isinstance(node.func, ast.Name))
        }
        self.assertFalse(called & forbidden_calls)


class PackageUpdateDispatchTest(unittest.TestCase):
    handoff_names = (
        "VELNOR_TAP_BASE_SHA",
        "VELNOR_TAP_FORMULA_PATH",
        "VELNOR_TAP_RELEASE_RECEIPT",
        "VELNOR_TAP_RELEASE_RECEIPT_SHA256",
        "VELNOR_TAP_RELEASE_VERSION",
        "VELNOR_TAP_RELEASE_TAG",
        "VELNOR_TAP_SOURCE_SHA",
    )

    def run_dispatch(self, mode: str) -> tuple[subprocess.CompletedProcess[str], set[str]]:
        with tempfile.TemporaryDirectory(prefix="tap-dispatch-test-") as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy2(SCRIPT, scripts / "package-update.sh")
            marker_dir = root / "markers"
            marker_dir.mkdir()
            for filename, marker in (("test-package-update.sh", "tests"),):
                target = scripts / filename
                target.write_text(f"#!/bin/sh\n/usr/bin/touch '{marker_dir / marker}'\n", encoding="utf-8")
                target.chmod(0o755)

            subprocess.run(("git", "init", "-q", str(root)), check=True)
            subprocess.run(("git", "-C", str(root), "config", "user.name", "Test"), check=True)
            subprocess.run(("git", "-C", str(root), "config", "user.email", "test@example.invalid"), check=True)
            subprocess.run(("git", "-C", str(root), "add", "."), check=True)
            subprocess.run(("git", "-C", str(root), "commit", "-qm", "dispatch fixture"), check=True)
            head = subprocess.run(
                ("git", "-C", str(root), "rev-parse", "HEAD"),
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            owned_bin = root / "toolchain/owned/bin"
            owned_bin.mkdir(parents=True)
            fake_python = owned_bin / "python"
            fake_python.write_text(
                f"#!/bin/sh\n/usr/bin/touch '{marker_dir / 'updater'}'\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            env = {
                "PATH": f"{owned_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
                "VELNOR_CHECK_ID": "homebrew-preview-update",
                "VELNOR_CHECK_PLATFORM": "linux_x64",
                "VELNOR_CHECK_HEAD": head,
            }
            if mode == "full":
                env.update({name: f"fixture-{index}" for index, name in enumerate(self.handoff_names)})
            elif mode == "partial":
                env[self.handoff_names[0]] = "fixture-base-sha"
            elif mode == "empty":
                env[self.handoff_names[0]] = ""
            elif mode == "invalid-head":
                env["VELNOR_CHECK_HEAD"] = "f" * 40
            elif mode == "missing-check-id":
                env.pop("VELNOR_CHECK_ID")
            elif mode == "wrong-check-id":
                env["VELNOR_CHECK_ID"] = "another-check"
            elif mode == "wrong-platform":
                env["VELNOR_CHECK_PLATFORM"] = "macos_arm64"

            result = subprocess.run(
                (str(scripts / "package-update.sh"),),
                cwd=root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            markers = {path.name for path in marker_dir.iterdir()}
            return result, markers

    def test_ordinary_exact_head_check_runs_updater_regression_tests(self) -> None:
        result, markers = self.run_dispatch("check")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"tests"}, markers)

    def test_complete_handoff_dispatches_to_authenticated_updater(self) -> None:
        result, markers = self.run_dispatch("full")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"updater"}, markers)

    def test_partial_and_empty_handoffs_fail_before_any_child_runs(self) -> None:
        for mode in ("partial", "empty"):
            with self.subTest(mode=mode):
                result, markers = self.run_dispatch(mode)
                self.assertEqual(2, result.returncode)
                self.assertEqual(set(), markers)

    def test_invalid_native_context_fails_before_any_child_runs(self) -> None:
        for mode in ("invalid-head", "missing-check-id", "wrong-check-id", "wrong-platform"):
            with self.subTest(mode=mode):
                result, markers = self.run_dispatch(mode)
                self.assertEqual(2, result.returncode)
                self.assertEqual(set(), markers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
