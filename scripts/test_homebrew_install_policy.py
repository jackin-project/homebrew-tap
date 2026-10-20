#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_SPEC = importlib.util.spec_from_file_location(
    "homebrew_install_policy", SCRIPT_DIR / "homebrew_install_policy.py"
)
assert MODULE_SPEC is not None
assert MODULE_SPEC.loader is not None
POLICY = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(POLICY)


class HomebrewInstallPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = (SCRIPT_DIR.parent / "Formula/jackin-preview.rb").read_text(encoding="utf-8")
        match = re.search(r'^  version "([^"]+)"$', source, re.MULTILINE)
        assert match is not None
        cls.version = match.group(1)
        cls.prefix = "https://github.com/jackin-project/jackin/releases/download/preview/"
        cls.urls = tuple(cls.prefix + archive for archive in POLICY.ARCHIVES)

    def formula(self, urls: tuple[str, ...] | None = None, version: str | None = None) -> str:
        actual_version = self.version if version is None else version
        actual_urls = self.urls if urls is None else urls
        source_sha = (actual_version.rsplit("+", 1)[1] + "1" * 33) if "+" in actual_version else "a" * 40
        return '\n'.join((f'# source-sha: {source_sha}', f'  version "{actual_version}"', *(f'      url "{url}"' for url in actual_urls)))

    def stable_formula(self) -> str:
        version = "0.7.0"
        prefix = f"https://github.com/jackin-project/jackin/releases/download/v{version}/"
        return self.formula(tuple(prefix + archive for archive in POLICY.ARCHIVES), version)

    def test_accepts_exact_rolling_preview_six_asset_inventory(self) -> None:
        version, urls = POLICY.validate_formula_text(self.formula())
        self.assertEqual(self.version, version)
        self.assertCountEqual(self.urls, urls)

    def test_preview_version_rejects_unicode_decimal_digits(self) -> None:
        version = "10.20.30-preview.40+abcdef0"
        self.assertIsNotNone(POLICY.VERSION_RE.fullmatch(version))
        for index in (1, 4, 7, 18):
            with self.subTest(index=index):
                unicode_version = version[:index] + "٠" + version[index + 1 :]
                self.assertIsNone(POLICY.VERSION_RE.fullmatch(unicode_version))
                formula = self.formula(version=unicode_version)
                with self.assertRaisesRegex(POLICY.InvalidReleaseFormula, "selected release channel"):
                    POLICY.validate_formula_text(formula)

    def test_url_tokens_keep_ascii_identifier_boundaries(self) -> None:
        for token in ("éurl", "urlé"):
            with self.subTest(token=token):
                formula = self.formula() + f'\n    {token}("https://attacker.invalid/payload.tar.gz")\n'
                with self.assertRaisesRegex(POLICY.InvalidReleaseFormula, "unsupported or nonliteral URL"):
                    POLICY.validate_formula_text(formula)
        self.assertIsNone(POLICY.URL_TOKEN_RE.search("my_url"))
        self.assertIsNone(POLICY.URL_TOKEN_RE.search("url_suffix"))

    def test_rejects_wrong_host_that_contains_trusted_url_as_substring(self) -> None:
        hostile = "https://attacker.invalid/" + self.urls[0]
        urls = (hostile, *self.urls[1:])
        formula = self.formula(urls)
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula)

    def test_rejects_duplicate_payload_and_missing_payload(self) -> None:
        duplicated = (*self.urls[:5], self.urls[0])
        formula = self.formula(duplicated)
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula)
        formula = self.formula(self.urls[:5])
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula)

    def test_rejects_wrong_tag_even_when_asset_names_match(self) -> None:
        wrong_version = "0.6.4-preview.1182+deadbee"
        wrong_prefix = f"https://github.com/jackin-project/jackin/releases/download/v{wrong_version}/"
        wrong_urls = tuple(wrong_prefix + archive for archive in POLICY.ARCHIVES)
        formula = self.formula(wrong_urls)
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula)

    def test_rejects_noncanonical_rolling_tag(self) -> None:
        rolling = tuple(url.replace("/download/preview/", "/download/latest/") for url in self.urls)
        formula = self.formula(rolling)
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula)

    def test_accepts_stable_semver_with_immutable_version_tag(self) -> None:
        stable_version = "0.7.0"
        prefix = f"https://github.com/jackin-project/jackin/releases/download/v{stable_version}/"
        formula = self.formula(tuple(prefix + archive for archive in POLICY.ARCHIVES), stable_version)
        actual, urls = POLICY.validate_formula_text(formula, "stable")
        self.assertEqual(stable_version, actual)
        self.assertEqual(6, len(urls))
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(formula, "preview")

    def test_rejects_preview_source_comment_that_disagrees_with_version(self) -> None:
        text = self.formula().replace("# source-sha: ", "# source-sha: f", 1)
        with self.assertRaisesRegex(POLICY.InvalidReleaseFormula, "source commit"):
            POLICY.validate_formula_text(text)

    def test_rejects_alternate_url_call_after_valid_inventory(self) -> None:
        text = self.formula() + '\n    url("https://attacker.invalid/payload.tar.gz")\n'
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(text)

    def test_rejects_dynamic_url_declaration(self) -> None:
        text = self.formula() + '\n    url "https://attacker.invalid/#{version}.tar.gz"\n'
        with self.assertRaises(POLICY.InvalidReleaseFormula):
            POLICY.validate_formula_text(text)

    def make_repository(self, alias_target: str = "../Formula/jackin-preview.rb") -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory()
        repository = Path(temporary.name)
        (repository / "Formula").mkdir()
        (repository / "Aliases").mkdir()
        (repository / "Formula/jackin-preview.rb").write_text(self.formula(), encoding="utf-8")
        os.symlink(alias_target, repository / "Aliases/jackin@preview")
        self.git(repository, "init", "-q")
        self.git(repository, "config", "user.name", "Test")
        self.git(repository, "config", "user.email", "test@example.invalid")
        self.git(repository, "add", ".")
        self.git(repository, "commit", "-qm", "fixture")
        head = self.git(repository, "rev-parse", "HEAD").decode().strip()
        return temporary, repository, head

    @staticmethod
    def git(repository: Path, *args: str) -> bytes:
        return subprocess.run(
            ("git", "-C", str(repository), *args),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout

    def test_accepts_exact_alias_at_captured_full_head(self) -> None:
        temporary, repository, head = self.make_repository()
        with temporary:
            POLICY.validate_runtime_alias(repository, head)

    def test_rejects_malicious_alias_target_and_tree_blob(self) -> None:
        temporary, repository, head = self.make_repository("../../outside.rb")
        with temporary:
            with self.assertRaises(POLICY.InvalidReleaseFormula):
                POLICY.validate_runtime_alias(repository, head)

    def test_rejects_working_alias_that_differs_from_captured_tree(self) -> None:
        temporary, repository, head = self.make_repository()
        with temporary:
            alias_path = repository / "Aliases/jackin@preview"
            alias_path.unlink()
            os.symlink("../../outside.rb", alias_path)
            with self.assertRaises(POLICY.InvalidReleaseFormula):
                POLICY.validate_runtime_alias(repository, head)

    def test_rejects_symlinked_alias_parent(self) -> None:
        temporary, repository, head = self.make_repository()
        with temporary:
            (repository / "Aliases").rename(repository / "Aliases-real")
            os.symlink("Aliases-real", repository / "Aliases")
            with self.assertRaises(POLICY.InvalidReleaseFormula):
                POLICY.validate_runtime_alias(repository, head)

    def test_rejects_formula_symlink(self) -> None:
        temporary, repository, _head = self.make_repository()
        with temporary:
            formula = repository / "Formula/jackin-preview.rb"
            formula.unlink()
            formula.symlink_to(repository / "outside.rb")
            with self.assertRaises(POLICY.InvalidReleaseFormula):
                POLICY.validate_formula(formula)

    def test_accepts_pull_request_merge_checkout_for_exact_second_parent(self) -> None:
        temporary, repository, source_head = self.make_repository()
        with temporary:
            tree = self.git(repository, "rev-parse", f"{source_head}^{{tree}}").decode().strip()
            first_parent = self.git(repository, "commit-tree", tree.encode().decode(), "-p", source_head, "-m", "base").decode().strip()
            merge = self.git(repository, "commit-tree", tree, "-p", first_parent, "-p", source_head, "-m", "merge").decode().strip()
            self.git(repository, "update-ref", "refs/heads/main", merge)
            self.git(repository, "checkout", "-q", "--detach", merge)
            POLICY.validate_runtime_alias(repository, source_head)

    def run_install_gate(
        self,
        formula: str,
        head: str,
        *,
        channel: str | None = None,
        check_id: str | None = None,
        platform: str = "macos_arm64",
    ) -> tuple[subprocess.CompletedProcess[bytes], list[str], bool]:
        temporary, repository, _ = self.make_repository()
        with temporary:
            (repository / "Formula/jackin-preview.rb").write_text(formula, encoding="utf-8")
            (repository / "Formula/jackin.rb").write_text(self.stable_formula(), encoding="utf-8")
            scripts = repository / "scripts"
            scripts.mkdir()
            policy = scripts / "homebrew_install_policy.py"
            policy.write_bytes((SCRIPT_DIR / "homebrew_install_policy.py").read_bytes())
            policy.chmod(0o755)
            install_script = scripts / "test-homebrew-install.sh"
            script_text = (SCRIPT_DIR / "test-homebrew-install.sh").read_text(encoding="utf-8")
            production_brew = 'BREW="/opt/homebrew/bin/brew"'
            self.assertEqual(1, script_text.count(production_brew))
            install_script.write_text(
                script_text.replace(production_brew, f'BREW="{repository}/owned/bin/brew"'),
                encoding="utf-8",
            )
            install_script.chmod(0o755)
            self.git(repository, "add", ".")
            self.git(repository, "commit", "-qm", "gate fixture")
            check_head = self.git(repository, "rev-parse", "HEAD").decode().strip()
            fake_bin = repository / "owned/bin"
            fake_bin.mkdir(parents=True)
            log = repository / "brew.log"
            brew = fake_bin / "brew"
            brew.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{log}'\n", encoding="utf-8")
            brew.chmod(0o755)
            python = fake_bin / "python"
            python.write_text(
                f"#!/bin/sh\nexec '{sys.executable}' \"$@\"\n",
                encoding="utf-8",
            )
            python.chmod(0o755)
            env = {
                "PATH": f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin",
                "VELNOR_CHECK_ID": check_id or ("homebrew-stable-install" if channel == "stable" else "homebrew-preview-install"),
                "VELNOR_CHECK_PLATFORM": platform,
                "VELNOR_CHECK_HEAD": check_head if head == "captured" else head,
            }
            if channel is not None:
                env["VELNOR_TAP_CHANNEL"] = channel
            result = subprocess.run(
                (str(scripts / "test-homebrew-install.sh"),),
                cwd=repository,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            commands = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return result, commands, log.exists()

    def test_rejected_head_stops_before_brew_can_run(self) -> None:
        result, _commands, log_exists = self.run_install_gate(self.formula(), "0" * 40)
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(log_exists)

    def test_wrong_native_check_context_stops_before_brew_can_run(self) -> None:
        for check_id, platform in (
            ("another-check", "macos_arm64"),
            ("homebrew-preview-install", "linux_x64"),
        ):
            with self.subTest(check_id=check_id, platform=platform):
                result, _commands, log_exists = self.run_install_gate(
                    self.formula(), "captured", check_id=check_id, platform=platform
                )
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(log_exists)

    def test_preview_channel_defaults_and_installs_only_the_rolling_formula(self) -> None:
        result, commands, _log_exists = self.run_install_gate(self.formula(), "captured")
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("install --formula --force jackin@preview", commands[2])
        self.assertEqual("test --formula jackin@preview", commands[3])

    def test_stable_channel_installs_only_the_stable_formula(self) -> None:
        result, commands, _log_exists = self.run_install_gate(self.stable_formula(), "captured", channel="stable")
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual("install --formula --force jackin", commands[2])
        self.assertEqual("test --formula jackin", commands[3])

    def test_channel_and_native_check_must_match_before_brew_runs(self) -> None:
        for channel, check_id in (
            ("stable", "homebrew-preview-install"),
            ("preview;touch injected", "homebrew-preview-install"),
            ("../../Formula/evil.rb", "homebrew-preview-install"),
        ):
            with self.subTest(channel=channel):
                result, _commands, log_exists = self.run_install_gate(
                    self.formula(), "captured", channel=channel, check_id=check_id
                )
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(log_exists)

    def test_homebrew_trust_occurs_after_validation_before_install(self) -> None:
        result, commands, _log_exists = self.run_install_gate(self.formula(), "captured")
        self.assertEqual(0, result.returncode, result.stderr.decode())
        self.assertEqual(4, len(commands))
        self.assertTrue(commands[0].startswith("tap jackin-project/tap "))
        self.assertEqual(
            [
                "trust --tap jackin-project/tap",
                "install --formula --force jackin@preview",
                "test --formula jackin@preview",
            ],
            commands[1:],
        )

    def test_rejected_url_syntax_stops_before_brew_can_run(self) -> None:
        formula = self.formula() + '\n    url("https://attacker.invalid/payload.tar.gz")\n'
        result, _commands, log_exists = self.run_install_gate(formula, "captured")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(log_exists)

    def test_tampered_source_checksum_stops_before_brew_can_run(self) -> None:
        formula = self.formula()
        source = re.search(r"(?m)^# source-sha: ([0-9a-f]{40})$", formula)
        self.assertIsNotNone(source)
        tampered_sha = "f" + source.group(1)[1:]
        formula = formula.replace(source.group(1), tampered_sha, 1)
        result, _commands, log_exists = self.run_install_gate(formula, "captured")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(log_exists)


if __name__ == "__main__":
    unittest.main()
