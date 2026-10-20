# source-sha: 0000000000000000000000000000000000000000
class Jackin < Formula
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "0.0.0"
  license "Apache-2.0"

  disable! date: "2026-10-21", because: "has no native stable release yet" if version.to_s == "0.0.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-aarch64-apple-darwin.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  conflicts_with "jackin-project/tap/jackin-preview", because: "preview and stable install the same binary"

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  def install
    bin.install "jackin"
    bin.install "jackin-role"
    bin.install "jackin-usage-broker"
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
    assert_match version.to_s, shell_output("#{bin}/jackin-role --version")
    assert_match version.to_s, shell_output("#{bin}/jackin-usage-broker --version")
    assert_predicate bin/"jackin-role", :executable?
    assert_predicate bin/"jackin-usage-broker", :executable?

    capsule_target = Hardware::CPU.arm? ? "arm64" : "amd64"
    capsule = libexec/"jackin-capsule/linux-#{capsule_target}/jackin-capsule"
    assert_predicate capsule, :executable?
    capsule_header = File.binread(capsule, 20)
    assert_equal "\x7fELF".b, capsule_header.byteslice(0, 4)
    assert_equal 2, capsule_header.getbyte(4)
    assert_equal 1, capsule_header.getbyte(5)
    expected_machine = Hardware::CPU.arm? ? 183 : 62
    assert_equal expected_machine, capsule_header.byteslice(18, 2).unpack1("v")
    if OS.linux?
      assert_match version.to_s, shell_output("#{capsule} --version")
    end
  end
end
