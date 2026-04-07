class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/fde8258757682b8cc1915e06865d70b23399be70.tar.gz"
  version "0.5.0-preview+fde8258"
  sha256 "196cb685951251610cdc2f535c9c503838c91a98d410b1418ec8868560da1ea0"
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
