#!/usr/bin/env bash
set -euo pipefail

verified=${VELNOR_VERIFIED_PACKAGE_DIR:?missing VELNOR_VERIFIED_PACKAGE_DIR}
manifest="$verified/release-manifest.json"
identity="$verified/identity.json"
channel=${VELNOR_PACKAGE_CHANNEL:-stable}

if ! jq -s -e --slurpfile release_manifests "$manifest" '
  length == 1 and
  ($release_manifests | length == 1) and
  .[0].manifest == $release_manifests[0]
' "$identity" >/dev/null; then
  echo "identity manifest does not match release manifest" >&2
  exit 1
fi

if test "$channel" = preview; then
  jq -e '
    keys == ["manifest","source_digest","source_ref","source_repository"] and
    .source_repository == "jackin-project/jackin" and
    .source_ref == "refs/heads/main" and
    (.source_digest | test("^[0-9a-f]{40}$"))
  ' "$identity" >/dev/null

  version=$(jq -er '.version | select(test("^[0-9]+[.][0-9]+[.][0-9]+-preview[.][0-9]+[+][0-9a-f]{7}$"))' "$manifest")
  source_commit=$(jq -er '.source_commit' "$manifest")
  test "$(jq -r '.source_digest' "$identity")" = "$source_commit"
  test "${version##*+}" = "${source_commit:0:7}"
  jq -e --arg commit "$source_commit" --arg version "$version" '
    keys == ["assets","schema","source_commit","source_ref","source_repository","supporting_assets","version"] and
    .schema == "velnor.package-release.v1" and
    .source_repository == "jackin-project/jackin" and
    .source_ref == "refs/heads/main" and
    .source_commit == $commit and .version == $version and
    (.assets | type == "array" and length == 6 and
      all(.[];
        type == "object" and
        keys == ["name","sha256"] and
        (.name | type == "string" and test("^[A-Za-z0-9._+~-]+$")) and
        (.sha256 | type == "string" and test("^[0-9a-f]{64}$")))) and
    (.supporting_assets | type == "array" and length > 0 and
      all(.[];
        type == "object" and
        keys == ["name","sha256"] and
        (.name | type == "string" and test("^[A-Za-z0-9._+~-]+$")) and
        (.sha256 | type == "string" and test("^[0-9a-f]{64}$")))) and
    ([.assets[].name] | sort) == ([
      "jackin-aarch64-apple-darwin.tar.gz",
      "jackin-aarch64-unknown-linux-gnu.tar.gz",
      "jackin-capsule-aarch64-unknown-linux-gnu.tar.gz",
      "jackin-capsule-x86_64-unknown-linux-gnu.tar.gz",
      "jackin-x86_64-apple-darwin.tar.gz",
      "jackin-x86_64-unknown-linux-gnu.tar.gz"
    ] | sort) and
    ([.assets[].name] | unique | length) == 6 and
    ([.supporting_assets[].name] | unique | length) == (.supporting_assets | length) and
    (([.assets[].name] + [.supporting_assets[].name] + ["release-manifest.json","identity.json"])
      | unique | length) == ((.assets | length) + (.supporting_assets | length) + 2)
  ' "$manifest" >/dev/null

  expected_files=$(mktemp)
  actual_files=$(mktemp)
  jq -r '
    (["release-manifest.json","identity.json"] +
      (.assets | map(.name)) + (.supporting_assets | map(.name)))[]
  ' "$manifest" | LC_ALL=C sort > "$expected_files"
  if find "$verified" -mindepth 1 -maxdepth 1 ! -type f -print -quit | grep -q .; then
    echo "verified package directory contains a non-file entry" >&2
    rm -f "$expected_files" "$actual_files"
    exit 1
  fi
  find "$verified" -maxdepth 1 -type f -exec basename {} \; | LC_ALL=C sort > "$actual_files"
  if ! cmp -s "$expected_files" "$actual_files"; then
    echo "verified package directory contains an undeclared or missing file" >&2
    diff -u "$expected_files" "$actual_files" >&2 || true
    rm -f "$expected_files" "$actual_files"
    exit 1
  fi
  rm -f "$expected_files" "$actual_files"

  asset() {
    local name=$1
    if ! test -f "$verified/$name"; then
      echo "missing package asset: $name" >&2
      return 1
    fi
    local digest
    digest=$(jq -er --arg name "$name" '
      [.assets[] | select(.name == $name)]
      | select(length == 1)
      | .[0].sha256
      | select(test("^[0-9a-f]{64}$"))
    ' "$manifest")
    test "$(sha256sum "$verified/$name" | cut -d' ' -f1)" = "$digest"
    printf '%s\n' "$digest"
  }

  supporting_asset() {
    local name=$1
    if ! test -f "$verified/$name"; then
      echo "missing supporting package asset: $name" >&2
      return 1
    fi
    local digest
    digest=$(jq -er --arg name "$name" '
      [.supporting_assets[] | select(.name == $name)]
      | select(length == 1)
      | .[0].sha256
      | select(test("^[0-9a-f]{64}$"))
    ' "$manifest")
    test "$(sha256sum "$verified/$name" | cut -d' ' -f1)" = "$digest"
  }

  mac_arm=$(asset jackin-aarch64-apple-darwin.tar.gz)
  mac_intel=$(asset jackin-x86_64-apple-darwin.tar.gz)
  linux_arm=$(asset jackin-aarch64-unknown-linux-gnu.tar.gz)
  linux_intel=$(asset jackin-x86_64-unknown-linux-gnu.tar.gz)
  capsule_arm=$(asset jackin-capsule-aarch64-unknown-linux-gnu.tar.gz)
  capsule_intel=$(asset jackin-capsule-x86_64-unknown-linux-gnu.tar.gz)

  while IFS= read -r supporting_name; do
    supporting_asset "$supporting_name"
  done < <(jq -er '.supporting_assets[].name' "$manifest")

  binary_dir=$(mktemp -d)
  trap 'rm -rf "$binary_dir"' EXIT
  tar -xzf "$verified/jackin-x86_64-unknown-linux-gnu.tar.gz" -C "$binary_dir"
  test "$("$binary_dir/jackin" --version)" = "jackin $version"

  cat > Formula/jackin-preview.rb <<EOF
# source-sha: $source_commit
class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "$version"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-apple-darwin.tar.gz"
      sha256 "$mac_arm"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "$mac_intel"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "$linux_arm"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "$linux_intel"
    end
  end

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "$capsule_arm"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "$capsule_intel"
  end

  def install
    bin.install "jackin"
    bin.install "jackin-role"
    capsule_target = Hardware::CPU.arm? ? "aarch64-unknown-linux-gnu" : "x86_64-unknown-linux-gnu"
    capsule_arch = Hardware::CPU.arm? ? "arm64" : "amd64"
    resource("jackin-capsule-#{capsule_target}").stage do
      capsule_dir = libexec/"jackin-capsule/linux-#{capsule_arch}"
      capsule_dir.install "jackin-capsule"
      chmod 0755, capsule_dir/"jackin-capsule"
    end
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/jackin --version")
  end
end
EOF
  exit 0
fi

test "$channel" = stable

jq -e '
  keys == ["manifest","source_digest","source_ref","source_repository"] and
  .source_repository == "jackin-project/jackin" and
  (.source_ref | test("^refs/tags/v[0-9]+[.][0-9]+[.][0-9]+$")) and
  (.source_digest | test("^[0-9a-f]{40}$"))
' "$identity" >/dev/null

version=$(jq -er '.version | select(test("^[0-9]+[.][0-9]+[.][0-9]+$"))' "$manifest")
tag="v$version"
jq -e --arg ref "refs/tags/$tag" '
  keys == ["assets","schema","source_commit","source_ref","source_repository","version"] and
  .schema == "velnor.package-release.v1" and
  .source_repository == "jackin-project/jackin" and
  .source_ref == $ref and
  (.source_commit | test("^[0-9a-f]{40}$")) and
  ([.assets[].name] | length) == 7 and
  ([.assets[].name] | unique | length) == 7
' "$manifest" >/dev/null

asset() {
  local name=$1
  if ! test -f "$verified/$name"; then
    echo "missing package asset: $name" >&2
    return 1
  fi
  jq -er --arg name "$name" '
    [.assets[] | select(.name == $name)]
    | select(length == 1)
    | .[0].sha256
    | select(test("^[0-9a-f]{64}$"))
  ' "$manifest"
}

mac_arm=$(asset "jackin-${version}-aarch64-apple-darwin.tar.gz")
mac_intel=$(asset "jackin-${version}-x86_64-apple-darwin.tar.gz")
linux_arm=$(asset "jackin-${version}-aarch64-unknown-linux-gnu.tar.gz")
linux_intel=$(asset "jackin-${version}-x86_64-unknown-linux-gnu.tar.gz")
capsule_arm=$(asset "jackin-capsule-${version}-aarch64-unknown-linux-gnu.tar.gz")
capsule_intel=$(asset "jackin-capsule-${version}-x86_64-unknown-linux-gnu.tar.gz")
desktop_arm=$(asset "jackin-desktop-${version}-aarch64-apple-darwin.zip")
source_commit=$(jq -er '.source_commit' "$manifest")
test "$(jq -r '.source_digest' "$identity")" = "$source_commit"

cat > Formula/jackin.rb <<EOF
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
# source-sha: $source_commit
class Jackin < Formula
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "$version"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-$version-aarch64-apple-darwin.tar.gz"
      sha256 "$mac_arm"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-$version-x86_64-apple-darwin.tar.gz"
      sha256 "$mac_intel"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-$version-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "$linux_arm"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-$version-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "$linux_intel"
    end
  end

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-capsule-$version-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "$capsule_arm"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-capsule-$version-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "$capsule_intel"
  end

  conflicts_with "jackin-project/tap/jackin-preview", because: "stable and preview install the same binary"

  def install
    bin.install "jackin"
    bin.install "jackin-role"
    capsule_target = Hardware::CPU.arm? ? "aarch64-unknown-linux-gnu" : "x86_64-unknown-linux-gnu"
    capsule_arch = Hardware::CPU.arm? ? "arm64" : "amd64"
    resource("jackin-capsule-#{capsule_target}").stage do
      capsule_dir = libexec/"jackin-capsule/linux-#{capsule_arch}"
      capsule_dir.install "jackin-capsule"
      chmod 0755, capsule_dir/"jackin-capsule"
    end
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/jackin --version")
  end
end
EOF

mkdir -p Casks
cat > Casks/jackin-desktop.rb <<EOF
# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0
# source-sha: $source_commit
cask "jackin-desktop" do
  version "$version"
  sha256 "$desktop_arm"

  url "https://github.com/jackin-project/jackin/releases/download/$tag/jackin-desktop-$version-aarch64-apple-darwin.zip"
  name "Jackin Desktop"
  desc "Native macOS surfaces for Jackin"
  homepage "https://github.com/jackin-project/jackin"

  depends_on arch: :arm64
  app "Jackin Desktop.app"
end
EOF
