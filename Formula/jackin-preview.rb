class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/19d0850aaa2ffb8e521b568c5164769735b28f5c.tar.gz"
  version "0.6.0-preview.419+19d0850"
  sha256 "f3c1e8c9714657c237a1124165153f5a808fdc0f74500ceeded4e3a55b5088f2"
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
