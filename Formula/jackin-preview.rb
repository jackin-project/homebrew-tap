class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/413aa5697aebe9b5b2788f2d912eb029d150dca9.tar.gz"
  version "0.6.0-preview.407+413aa56"
  sha256 "dc96eabc07367a97abda913f4974d2b29d30113a7963ab7b96818abafa197557"
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
