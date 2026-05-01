class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/b029e2ae65fd4e7835c2184df4e3ad4b63fd8f93.tar.gz"
  version "0.6.0-preview.539+b029e2a"
  sha256 "017321110a012cc7f482f682dc6d33ce048bbd453dc4ddfcfafc2c68b352f23c"
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
