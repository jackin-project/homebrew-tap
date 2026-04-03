class Jackin < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/donbeave/jackin"
  url "https://github.com/donbeave/jackin/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "301b79d921a51be441b77c4f1138c1b0315170355b78f298461772fcc33ba6dc"
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
