class Jackin < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/refs/tags/v0.4.0.tar.gz"
  sha256 "f28a180a1039e15e1525e7e2c0b7b3aa556d3ff15152cb91048aff4cdcff6b95"
  license "Apache-2.0"
  head "https://github.com/jackin-project/jackin.git", branch: "main"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  conflicts_with "jackin-project/tap/jackin-preview", because: "stable and preview install the same binary"

  def install
    ENV["JACKIN_VERSION_OVERRIDE"] = version.to_s
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/jackin --version")
  end
end
