class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/d21ec30ef3134048c6c92cdb0f50b4be5566d2a1.tar.gz"
  version "0.5.0-preview+d21ec30"
  sha256 "dd542cc0e3f54b5054c52f4d259beade9ab4625bf6437039033e1767efcc794c"
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
