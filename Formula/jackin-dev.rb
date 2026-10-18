class JackinDev < Formula
  desc "Developer tooling for local jackin pull request verification"
  homepage "https://github.com/jackin-project/jackin"
  version "0.1.52"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/jackin-dev-v0.1.52/jackin-dev-0.1.52-aarch64-apple-darwin.tar.gz"
      sha256 "22069056dd2d2147d16794097bf60dd34efc461fa566839774d9d0af3f6226a7"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/jackin-dev-v0.1.52/jackin-dev-0.1.52-x86_64-apple-darwin.tar.gz"
      sha256 "4125e6c42229c4153c049563ad8061d46b7f267fccfe3e88de00af8fbd9347b1"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/jackin-dev-v0.1.52/jackin-dev-0.1.52-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "c1a9bc8f79a5765aaa5594f39b898da05526277b0eae38904cc1bb01f372c8f7"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/jackin-dev-v0.1.52/jackin-dev-0.1.52-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "1f8d5bf29fa94a4cf76b93103f53754ceabe5c5116215b1d24c6c593375ef108"
    end
  end

  def install
    bin.install "jackin-dev"
  end

  test do
    system "#{bin}/jackin-dev", "--help"
  end
end
