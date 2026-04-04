class Jackin < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/donbeave/jackin"
  url "https://github.com/donbeave/jackin/archive/refs/tags/v0.3.0.tar.gz"
  sha256 "1f73eca48c76c2cc9573817fecca9a6b0076b535ffe5d39c29444950c60629c3"
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
