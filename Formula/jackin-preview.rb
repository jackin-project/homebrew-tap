class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/8bc6afcce0ceeab28e39441ce759b3753900c47b.tar.gz"
  version "0.6.0-preview.541+8bc6afc"
  sha256 "d21f7829cd20f463382d55a8151b73efcdcb5c0ef6efe12734b52f3308f4b710"
  license "Apache-2.0"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  def install
    ENV["JACKIN_VERSION_OVERRIDE"] = version.to_s
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/jackin --version")
  end
end
