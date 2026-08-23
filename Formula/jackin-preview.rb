<<<<<<< Updated upstream
# source-sha: 2246b779e0c424a648491e837d8314b8af5bc523
class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  version "0.6.4-preview.1115+2246b77"
=======
# source-sha: 2c01e048d5184d733e6e605bdd0770af9a1abb29
class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  version "0.6.4-preview.1103+2c01e04"
>>>>>>> Stashed changes
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-apple-darwin.tar.gz"
<<<<<<< Updated upstream
      sha256 "7088d3cf456abdf0d472c3acd7ee8dc64d57b901774c8715e12eec8c7ae99b4e"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "5e244b901bd0c2dd6a009144dfe801294982e5c54d1e1647b4c935120c21eca8"
=======
      sha256 "fd7b8105240072f5f115c04173c899bd6077c46d5cbebb7ef091c8cb237ebd4c"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "86f3948b5e0c048843b1dd8da831dae2bc99f6dfd01443dbbc49257da82804a4"
>>>>>>> Stashed changes
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-unknown-linux-gnu.tar.gz"
<<<<<<< Updated upstream
      sha256 "f5a61d9af40db704e36df11ba332e3b8eab489cfdf9852bafd64cda5980100d5"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "74ceb32dc3292e4dff47169e6a0275dfc05b39b1cb66dc72082d3dd5c6813150"
=======
      sha256 "ec21a0ebee49b717052c10095434e8086d27b36a5f46a631d862ff0ace68a180"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "12ecac5b49d3c3261a546f24c311b592d6017b159385709341514b30b14dcc28"
>>>>>>> Stashed changes
    end
  end

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
<<<<<<< Updated upstream
    sha256 "bacc1ed22c19f237e72b7239d750efdb79e306b4d6e6114ef59b839cd0cacda2"
=======
    sha256 "cdcd82905e02b68d765968a88547fe301500c7f53176d687f8e9536114b7c25a"
>>>>>>> Stashed changes
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
<<<<<<< Updated upstream
    sha256 "7f16a325763cfbac0f3f06e2147773125e865614a43feb1aff2fac93d49fd3ab"
=======
    sha256 "2c0ae7ee956ee9f1add3a0375304eca32cd8ad1bfebffd06ecc1d8b3a448f1b6"
>>>>>>> Stashed changes
  end

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

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
