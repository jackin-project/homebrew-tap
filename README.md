# Homebrew Tap

Homebrew formulae for [jackin](https://github.com/jackin-project/jackin).

jackin is experimental preview software. Preview upgrades are immutable, signed releases promoted to this tap by an exact-head pull request. Homebrew installs prebuilt binaries; it does not compile Jackin locally.

## Installation

```sh
brew tap jackin-project/tap
brew trust jackin-project/tap
brew install jackin@preview
brew install jackin-dev
```

The stable `jackin` formula is intentionally disabled until the first stable release.
Install `jackin-dev` alongside the preview CLI when you need the local pull request verification helper.

Homebrew can refuse to load formulae from taps that have not been trusted. Run `brew trust jackin-project/tap` once after tapping this repository.

## Updating

```sh
brew update
brew upgrade jackin@preview
brew upgrade jackin-dev
```

Each preview formula revision names one immutable Jackin release tag and pins
the SHA-256 digest of each platform archive. The package updater consumes only
Velnor's authenticated `release.json` handoff and changes literal formula
metadata. It does not download, extract, or execute release payloads.

Velnor's native `homebrew-preview-install` check taps this checkout on an
Apple Silicon macOS runner, installs through the `jackin@preview` alias, and
runs Homebrew's formula test against the installed prebuilt binaries. Before
running Homebrew, the check binds the exact relative alias symlink and regular
formula file to the captured `VELNOR_CHECK_HEAD` tree (including PR merge
checkouts whose second parent is that head). The check reads the alias at
runtime because Velnor's named checks execute against a captured commit and do
not hash symlink paths as ordinary file inputs. The test checks all three CLI
versions and verifies the packaged capsule is a Linux ELF for the expected
architecture. The capsule is executed only on Linux; its
runtime loading is verified separately by Jackin's container-backed checks.
The install gate rejects rolling `/download/preview/` URLs, so the current
rolling bootstrap formula is not evidence that immutable promotion works.
