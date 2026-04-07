class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/a31e949be8bee5017cd8770f3a06c7bf2202cc8e.tar.gz"
  version "0.5.0-preview+a31e949"
  sha256 "9a0ae8f37806ebf8021ba9c487241e90c39a2e4aee3aa1c1e5d9a96488c8927d"
  license "Apache-2.0"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  def install
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "jackin", shell_output("#{bin}/jackin --version")
  end
end
