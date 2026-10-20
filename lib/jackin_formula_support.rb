# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0

module JackinFormulaSupport
  # Homebrew can load archived formulas from separate kegs in one Ruby
  # process. Return a fresh module so a later helper version cannot replace
  # methods already included by an earlier recipe.
  def self.build
    helper_source = File.realpath(__FILE__)
    Module.new do
      define_method(:install) do
        bin.install "jackin"
        bin.install "jackin-role"
        bin.install "jackin-usage-broker"
        lib.mkpath
        FileUtils.cp(helper_source, lib/"jackin_formula_support.rb")

        capsule_target = Hardware::CPU.arm? ? "aarch64-unknown-linux-gnu" : "x86_64-unknown-linux-gnu"
        capsule_arch = Hardware::CPU.arm? ? "arm64" : "amd64"
        resource("jackin-capsule-#{capsule_target}").stage do
          capsule_dir = libexec/"jackin-capsule/linux-#{capsule_arch}"
          capsule_dir.install "jackin-capsule"
          chmod 0755, capsule_dir/"jackin-capsule"
        end
      end

      define_method(:jackin_package_test) do
        assert_match version.to_s, shell_output("#{bin}/jackin --version")
        assert_match version.to_s, shell_output("#{bin}/jackin-role --version")
        assert_match version.to_s, shell_output("#{bin}/jackin-usage-broker --version")
        assert_predicate bin/"jackin-role", :executable?
        assert_predicate bin/"jackin-usage-broker", :executable?

        capsule_target = Hardware::CPU.arm? ? "arm64" : "amd64"
        capsule = libexec/"jackin-capsule/linux-#{capsule_target}/jackin-capsule"
        assert_predicate capsule, :executable?
        capsule_header = File.binread(capsule, 20)
        assert_equal "\x7fELF".b, capsule_header.byteslice(0, 4)
        assert_equal 2, capsule_header.getbyte(4)
        assert_equal 1, capsule_header.getbyte(5)
        expected_machine = Hardware::CPU.arm? ? 183 : 62
        assert_equal expected_machine, capsule_header.byteslice(18, 2).unpack1("v")
        if OS.linux?
          assert_match version.to_s, shell_output("#{capsule} --version")
        end
      end
    end
  end
end
