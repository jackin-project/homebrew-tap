class JackinPreview < Formula
  desc "CLI for orchestrating autonomous AI coding agents in isolated sandboxed environments — reproducible, scoped, and fully under your control"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/e20bfd6fe8df84f4edf9c5a93891d072fa8ffd84.tar.gz"
  version "0.6.0-preview.442+e20bfd6"
  sha256 "70a617a352b8cf4c2048c3ef6adaa61b2e0f19416be26f3221d5842ca80aa627"
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
