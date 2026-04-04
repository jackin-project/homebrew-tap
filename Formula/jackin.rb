class Jackin < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/donbeave/jackin"
  url "https://github.com/donbeave/jackin/archive/refs/tags/v0.4.0.tar.gz"
  sha256 "f28a180a1039e15e1525e7e2c0b7b3aa556d3ff15152cb91048aff4cdcff6b95"
  license "Apache-2.0"
  head "https://github.com/donbeave/jackin.git", branch: "main"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  def install
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "jackin", shell_output("#{bin}/jackin --version")
  end
end
