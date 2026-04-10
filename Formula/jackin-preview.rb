class JackinPreview < Formula
  desc "Matrix-inspired CLI for orchestrating AI coding agents at scale"
  homepage "https://github.com/jackin-project/jackin"
  url "https://github.com/jackin-project/jackin/archive/0038638852b368c67f63116c9f41aff13e65af0a.tar.gz"
  version "0.6.0-preview.337+0038638"
  sha256 "342363a494e910b84984249deb9e4da337fd33e46cc3d421da02e2345098aaca"
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
