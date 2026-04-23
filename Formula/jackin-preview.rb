class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/5dd4ae36107ffc85f6cf65d65c1a929c9d6a9041.tar.gz"
  version "0.6.0-preview.479+5dd4ae3"
  sha256 "c6cc98d5d42e57d2ca62db1de0f20eda770d2a6d75468ad08c46fe46f83ce0a0"
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
