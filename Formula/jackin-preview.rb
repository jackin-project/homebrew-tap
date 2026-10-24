# source-sha: 41bad147b5ba9db09be99b07248531ce1bd867be
require_relative "../lib/jackin_formula_support"

class JackinPreview < Formula
  include JackinFormulaSupport.build
  desc "CLI for orchestrating autonomous AI coding agents"
  homepage "https://github.com/jackin-project/jackin"
  version "0.6.4-preview.1362+41bad14"
  license "Apache-2.0"

  on_macos do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-aarch64-apple-darwin.tar.gz"
      sha256 "987f15722715737cb9b9ea26ce37a46582b33b947cab0b9aaa03a64251c837e4"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-x86_64-apple-darwin.tar.gz"
      sha256 "1f64a993908e359613ce4a6264a06d6db045da890b243d4c08cfdf8dcf35fcdf"
    end
  end

  on_linux do
    on_arm do
      url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-aarch64-unknown-linux-gnu.tar.gz"
      sha256 "e7f05cf4b58cf3dac1014d9000d223ad7f8a723711bf2d8a4d5ce23d91c0df05"
    end
    on_intel do
      url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-x86_64-unknown-linux-gnu.tar.gz"
      sha256 "9bb5e98a3b1d8fd8face31b91e61c2844134fa9026369fa25527fdeaede6b204"
    end
  end

  conflicts_with "jackin-project/tap/jackin", because: "preview and stable install the same binary"

  resource "jackin-capsule-aarch64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-capsule-aarch64-unknown-linux-gnu.tar.gz"
    sha256 "1edb15003f9cbaf785a7470f38a1a90d1674f28494959b05dd903289824e9ef0"
  end

  resource "jackin-capsule-x86_64-unknown-linux-gnu" do
    url "https://github.com/jackin-project/jackin/releases/download/preview-41bad147b5ba9db09be99b07248531ce1bd867be/jackin-capsule-x86_64-unknown-linux-gnu.tar.gz"
    sha256 "ad1a6c25abf8444b7acb5b2300ca01709d7a91385b3dd80119978d7dcbed4d02"
  end

  test do
    jackin_package_test
  end
end
