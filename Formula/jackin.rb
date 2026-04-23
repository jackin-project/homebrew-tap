class Jackin < Formula
  desc "CLI for orchestrating AI coding agents in Docker containers at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/refs/tags/v0.5.0.tar.gz"
  sha256 "85628d048a3099b70641b3cb713f93d5a09cb92ebdcdbd33312e1f111619b38b"
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
