# source-sha: a506eee0581ef7add4f615281dbb90d828d5a657
class JackinPreview < Formula
  require_relative "../lib/jackin_formula_support"
  include JackinFormulaSupport.build
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "0.6.4-preview.1181+a506eee"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-apple-darwin.tar.gz"
      sha256 "8b1bcecdd9798a84cbe0d9358374b2bf3425984e84dbda81279a7050c9854b7d"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "48b4d07c3309266c9877ea31aa865b68acfa922448df25e3fefd8b1505acecbc"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "3d276461105b3297f77b82ffc0f8f39c01ec3b68a6670648f06426759b28ca21"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "e3fe87061bad25b2850089dd9de558a317714bf7711c25ce9328a2e63381f9c7"
    end
  end

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "6c24b131f74bb9574ab5e0670150da6d7ec17b006210fd5132dce148d40e606b"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "7cf2f29c55799ddbc359ab0b2b39f4b8a2307f4e96b9c1c601e7e8f780fb6b89"
  end

  test do
    jackin_package_test
  end
end
