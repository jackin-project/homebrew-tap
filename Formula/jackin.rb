# source-sha: 0000000000000000000000000000000000000000
require_relative "../lib/jackin_formula_support"

class Jackin < Formula
  include JackinFormulaSupport.build
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "0.0.0"
  license "Apache-2.0"

  disable! date: "2026-10-20", because: "has no native stable release yet" if version.to_s == "0.0.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-aarch64-apple-darwin.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "0000000000000000000000000000000000000000000000000000000000000000"
    end
  end

  conflicts_with "jackin-project/tap/jackin-preview", because: "preview and stable install the same binary"

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/v0.0.0/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end

  test do
    jackin_package_test
  end
end
