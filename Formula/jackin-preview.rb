class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/cc9dd1d0763a1504ad0e3b51e64e12a8e4bad5d2.tar.gz"
  version "0.6.0-preview.411+cc9dd1d"
  sha256 "9533040442aeaef1a612ec27bed0f5a6bf5b62aac499da38fdc63a1bdd13a0a4"
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
