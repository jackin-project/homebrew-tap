#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cp -R "$root/." "$tmp/repo"
verified="$tmp/verified"
mkdir "$verified"
version=1.2.3
commit=0123456789abcdef0123456789abcdef01234567
names=(
  "jackin-${version}-aarch64-apple-darwin.tar.gz"
  "jackin-${version}-x86_64-apple-darwin.tar.gz"
  "jackin-${version}-aarch64-unknown-linux-gnu.tar.gz"
  "jackin-${version}-x86_64-unknown-linux-gnu.tar.gz"
  "jackin-capsule-${version}-aarch64-unknown-linux-gnu.tar.gz"
  "jackin-capsule-${version}-x86_64-unknown-linux-gnu.tar.gz"
  "jackin-desktop-${version}-aarch64-apple-darwin.zip"
)
: > "$tmp/assets.jsonl"
for name in "${names[@]}"; do
  printf 'fixture-%s\n' "$name" > "$verified/$name"
  digest=$(shasum -a 256 "$verified/$name" | awk '{print $1}')
  jq -cn --arg name "$name" --arg sha256 "$digest" '{name:$name,sha256:$sha256}' >> "$tmp/assets.jsonl"
done
jq -Sn --arg source_repository jackin-project/jackin --arg source_ref refs/tags/v$version \
  --arg source_commit "$commit" --arg version "$version" --slurpfile assets "$tmp/assets.jsonl" \
  '{schema:"velnor.package-release.v1",source_repository:$source_repository,source_ref:$source_ref,source_commit:$source_commit,version:$version,assets:$assets}' > "$verified/release-manifest.json"
jq -Sn --arg source_repository jackin-project/jackin --arg source_ref refs/tags/v$version \
  --arg source_digest "$commit" --slurpfile manifest "$verified/release-manifest.json" \
  '{source_repository:$source_repository,source_ref:$source_ref,source_digest:$source_digest,manifest:$manifest[0]}' > "$verified/identity.json"

(
  cd "$tmp/repo"
  VELNOR_VERIFIED_PACKAGE_DIR="$verified" ./scripts/package-update.sh
  shasum -a 256 Formula/jackin.rb Casks/jackin-desktop.rb > "$tmp/first.sha"
  VELNOR_VERIFIED_PACKAGE_DIR="$verified" ./scripts/package-update.sh
  shasum -a 256 -c "$tmp/first.sha"
  grep -F 'version "1.2.3"' Formula/jackin.rb
  grep -F 'version "1.2.3"' Casks/jackin-desktop.rb
  test "$(grep -h -c 'sha256 "[0-9a-f]\{64\}"' Formula/jackin.rb Casks/jackin-desktop.rb | awk '{n+=$1} END{print n}')" -eq 7
)

preview_verified="$tmp/preview-verified"
mkdir "$preview_verified"
preview_version=1.2.3-preview.42+0123456
preview_names=(
  jackin-aarch64-apple-darwin.tar.gz
  jackin-x86_64-apple-darwin.tar.gz
  jackin-aarch64-unknown-linux-gnu.tar.gz
  jackin-x86_64-unknown-linux-gnu.tar.gz
  jackin-capsule-aarch64-unknown-linux-gnu.tar.gz
  jackin-capsule-x86_64-unknown-linux-gnu.tar.gz
)
mkdir "$tmp/preview-binary"
cat > "$tmp/preview-binary/jackin" <<EOF
#!/usr/bin/env bash
echo 'jackin $preview_version'
EOF
chmod 0755 "$tmp/preview-binary/jackin"
: > "$tmp/preview-assets.jsonl"
for name in "${preview_names[@]}"; do
  if test "$name" = jackin-x86_64-unknown-linux-gnu.tar.gz; then
    tar -czf "$preview_verified/$name" -C "$tmp/preview-binary" jackin
  else
    printf 'fixture-%s\n' "$name" > "$preview_verified/$name"
  fi
  digest=$(shasum -a 256 "$preview_verified/$name" | awk '{print $1}')
  jq -cn --arg name "$name" --arg sha256 "$digest" '{name:$name,sha256:$sha256}' >> "$tmp/preview-assets.jsonl"
done
jq -Sn --arg source_repository jackin-project/jackin --arg source_ref refs/heads/main \
  --arg source_commit "$commit" --arg version "$preview_version" --slurpfile assets "$tmp/preview-assets.jsonl" \
  '{schema:"velnor.package-release.v1",source_repository:$source_repository,source_ref:$source_ref,source_commit:$source_commit,version:$version,assets:$assets}' \
  > "$preview_verified/release-manifest.json"
jq -Sn --arg source_repository jackin-project/jackin --arg source_ref refs/heads/main \
  --arg source_digest "$commit" --slurpfile manifest "$preview_verified/release-manifest.json" \
  '{source_repository:$source_repository,source_ref:$source_ref,source_digest:$source_digest,manifest:$manifest[0]}' \
  > "$preview_verified/identity.json"

(
  cd "$tmp/repo"
  VELNOR_PACKAGE_CHANNEL=preview VELNOR_VERIFIED_PACKAGE_DIR="$preview_verified" ./scripts/package-update.sh
  grep -Fx "# source-sha: $commit" Formula/jackin-preview.rb
  grep -F "version \"$preview_version\"" Formula/jackin-preview.rb
  test "$(grep -cE 'sha256 \"[0-9a-f]{64}\"$' Formula/jackin-preview.rb)" -eq 6
  if grep -Eq 'sha256 \"[0-9a-f]{64}  ' Formula/jackin-preview.rb; then
    exit 1
  fi
  shasum -a 256 Formula/jackin-preview.rb > "$tmp/preview.sha"
)

preview_mismatch_verified="$tmp/preview-mismatch-verified"
cp -R "$preview_verified" "$preview_mismatch_verified"
jq '.manifest.source_commit = "fedcba9876543210fedcba9876543210fedcba98"' \
  "$preview_mismatch_verified/identity.json" > "$tmp/bad-preview-identity.json"
mv "$tmp/bad-preview-identity.json" "$preview_mismatch_verified/identity.json"
if (cd "$tmp/repo" && VELNOR_PACKAGE_CHANNEL=preview VELNOR_VERIFIED_PACKAGE_DIR="$preview_mismatch_verified" ./scripts/package-update.sh); then
  echo "mismatched identity manifest was accepted" >&2
  exit 1
fi
(
  cd "$tmp/repo"
  shasum -a 256 -c "$tmp/preview.sha"
)

incomplete_verified="$tmp/incomplete-verified"
cp -R "$verified" "$incomplete_verified"
rm "$incomplete_verified/jackin-${version}-aarch64-apple-darwin.tar.gz"
if (cd "$tmp/repo" && VELNOR_VERIFIED_PACKAGE_DIR="$incomplete_verified" ./scripts/package-update.sh); then
  echo "incomplete package was accepted" >&2
  exit 1
fi
(
  cd "$tmp/repo"
  shasum -a 256 -c "$tmp/first.sha"
)
