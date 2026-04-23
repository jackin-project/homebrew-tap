class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/94f32a9777b292c1a04dfa72a4f3efa0523e9aa7.tar.gz"
  version "0.6.0-preview.475+94f32a9"
  sha256 "480ac5c87d358ac43f9f4e2c31a67bc64b874e3820b00fdfddcd4cd90eb44b36"
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
