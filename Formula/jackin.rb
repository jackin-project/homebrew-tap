class Jackin < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/donbeave/jackin"
  url "https://github.com/donbeave/jackin/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "a5a6170ee7e301e886cbcc1fc68f1f75d03efaf9b4433d097ab67a271d08f852"
  license "Apache-2.0"
  head "https://github.com/donbeave/jackin.git", branch: "main"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  def install
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "jackin", shell_output("#{bin}/jackin --version")
  end
end
