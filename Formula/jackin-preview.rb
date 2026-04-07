class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/3d57d8197cc31674bd2755cf53d265d602a80fa5.tar.gz"
  version "0.5.0-preview+3d57d81"
  sha256 "1c7915fa035848a8be8a7fa2cc4b169c25918660295f1d5a7a28d2ac310936ca"
  license "Apache-2.0"

  depends_on "rust" => :build
  depends_on "docker" => :optional

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  def install
    system "cargo", "install", *std_cargo_args
  end

  test do
    assert_match "jackin", shell_output("#{bin}/jackin --version")
  end
end
