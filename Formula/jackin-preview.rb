class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/f6327ae7974eb9f4f60154836afa3ba5214d8c8d.tar.gz"
  version "0.6.0-preview.1+f6327ae"
  sha256 "01de19f92ecf9f2c2f101f7359cb12fd713b72e40f92413b577034c2d11bad1e"
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
