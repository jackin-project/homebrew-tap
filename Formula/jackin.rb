class Jackin < Formula
  desc "CLI for orchestrating AI coding agents in Docker containers at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/refs/tags/v0.5.0.tar.gz"
  sha256 "c758fff9d41670d208498da32531b70e7ce5f00735d31eef6e2fb8fa355bc775"
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
