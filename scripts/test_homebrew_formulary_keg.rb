# SPDX-FileCopyrightText: 2026 Alexey Zhokhov
# SPDX-License-Identifier: Apache-2.0

require "fileutils"
require "tmpdir"
require "pathname"
require "formula"
require "formulary"

tap = Pathname.new(ARGV.fetch(0)).realpath
Dir.mktmpdir("jackin-formulary-kegs") do |temporary|
  root = Pathname.new(temporary)

  load_archived_formula = lambda do |name, source = nil, label = name, marker = nil|
    keg = root/label
    recipe = keg/".brew"/"#{name}.rb"
    helper = keg/"lib"/"jackin_formula_support.rb"
    FileUtils.mkdir_p(recipe.dirname)
    FileUtils.mkdir_p(helper.dirname)
    File.write(recipe, source || File.read(tap/"Formula"/"#{name}.rb"))
    marker ||= label
    helper_source = File.read(tap/"lib"/"jackin_formula_support.rb")
    injected_revision = "    Module.new do\n      define_method(:jackin_helper_revision) { #{marker.dump} }\n"
    helper_source = helper_source.sub("    Module.new do\n", injected_revision)
    raise "could not create distinct archived helper fixture" if helper_source == File.read(tap/"lib"/"jackin_formula_support.rb")
    File.write(helper, helper_source)
    formula = Formulary.from_contents(name, recipe, recipe.read)
    expected = helper.to_s
    raise "archived install method did not load from the keg helper" unless formula.method(:install).source_location.first == expected
    raise "archived assertions did not load from the keg helper" unless formula.method(:jackin_package_test).source_location.first == expected
    [formula, helper]
  end

  stable, stable_helper = load_archived_formula.call("jackin", nil, "jackin-stable", "stable-helper-v1")
  stable_install = stable.method(:install).source_location
  stable_assertions = stable.method(:jackin_package_test).source_location
  preview, preview_helper = load_archived_formula.call("jackin-preview", nil, "jackin-preview", "preview-helper-v2")
  updated_source = File.read(tap/"Formula/jackin.rb")
  updated_source = updated_source
    .sub('source-sha: ' + ("0" * 40), 'source-sha: ' + ("a" * 40))
    .sub('version "0.0.0"', 'version "0.6.4"')
    .gsub("releases/download/v0.0.0/", "releases/download/v0.6.4/")
    .gsub(/sha256 "0{64}"/, 'sha256 "' + ("b" * 64) + '"')
  updated_stable, updated_stable_helper = load_archived_formula.call(
    "jackin", updated_source, "jackin-updated", "stable-helper-v3"
  )

  raise "archived recipes share mutable helper modules" if stable.method(:install).owner == preview.method(:install).owner
  raise "updated stable recipe shares a mutable helper module" if stable.method(:install).owner == updated_stable.method(:install).owner
  raise "later recipe changed stable helper binding" unless stable.method(:install).source_location == stable_install
  raise "later recipe changed stable assertion binding" unless stable.method(:jackin_package_test).source_location == stable_assertions
  raise "later helper version replaced stable implementation" unless stable.jackin_helper_revision == "stable-helper-v1"
  raise "preview helper version was not isolated" unless preview.jackin_helper_revision == "preview-helper-v2"
  raise "updated stable helper version was not isolated" unless updated_stable.jackin_helper_revision == "stable-helper-v3"
  raise "preview install method is not keg-local" unless preview.method(:install).source_location.first == preview_helper.to_s
  raise "stable install method is not keg-local" unless stable_install.first == stable_helper.to_s
  raise "stable sentinel disable state does not follow its version" unless stable.disabled? == (stable.version.to_s == "0.0.0")
  raise "updated stable release should be enabled" if updated_stable.disabled?
  raise "updated stable helper is not keg-local" unless updated_stable.method(:install).source_location.first == updated_stable_helper.to_s
  expected_resources = [
    "jackin-capsule-aarch64-unknown-linux-gnu",
    "jackin-capsule-x86_64-unknown-linux-gnu",
  ]
  raise "stable capsule resource inventory changed" unless stable.resources.map(&:name).sort == expected_resources
  raise "preview capsule resource inventory changed" unless preview.resources.map(&:name).sort == expected_resources

  install_from_local_fixtures = lambda do |formula, helper, label|
    source = root/"inputs-#{label}"
    prefix = root/"prefix-#{label}"
    capsule_target = Hardware::CPU.arm? ? "aarch64-unknown-linux-gnu" : "x86_64-unknown-linux-gnu"
    FileUtils.mkdir_p(source)
    %w[jackin jackin-role jackin-usage-broker].each { |name| File.write(source/name, "#{name}\n") }
    capsule_stage = source/"capsule-stage"
    FileUtils.mkdir_p(capsule_stage)
    File.write(capsule_stage/"jackin-capsule", "capsule\n")

    bin_path = prefix/"bin"
    lib_path = prefix/"lib"
    libexec_path = prefix/"libexec"
    FileUtils.mkdir_p(bin_path)
    FileUtils.mkdir_p(libexec_path)
    formula.define_singleton_method(:bin) { bin_path }
    formula.define_singleton_method(:lib) { lib_path }
    formula.define_singleton_method(:libexec) { libexec_path }
    staged_resource = Object.new
    staged_resource.define_singleton_method(:stage) { |&block| Dir.chdir(capsule_stage, &block) }
    formula.define_singleton_method(:resource) { |_name| staged_resource }

    FileUtils.cp(helper, root/"before-#{label}.rb")
    Dir.chdir(source) { formula.install }
    raise "formula install removed its captured helper" unless helper.file?
    raise "formula install changed its captured helper" unless helper.binread == File.binread(root/"before-#{label}.rb")
    installed_helper = lib_path/"jackin_formula_support.rb"
    raise "formula install did not copy the helper into keg/lib" unless installed_helper.file?
    raise "installed helper bytes differ from the loaded source" unless installed_helper.binread == helper.binread
  end

  install_from_local_fixtures.call(stable, stable_helper, "stable")
  install_from_local_fixtures.call(preview, preview_helper, "preview")
  install_from_local_fixtures.call(updated_stable, updated_stable_helper, "updated-stable")
end

puts "Homebrew Formulary loaded both stored keg recipes with isolated helper implementations."
