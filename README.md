# Homebrew Tap

Homebrew formulae for [jackin](https://github.com/jackin-project/jackin).

jackin is experimental software. Preview and stable formulae install prebuilt binaries from Jackin GitHub Releases; Homebrew does not compile Jackin locally.

## Installation

```sh
brew tap jackin-project/tap
brew trust jackin-project/tap
brew install jackin-preview
brew install jackin-dev
```

The stable `jackin` formula starts with an explicit `0.0.0` unpublished sentinel.
The native install gate rejects that sentinel before invoking Homebrew, including
when `brew install --force` would otherwise bypass Homebrew's disabled-formula
notice. A verified stable-release handoff replaces it with permanent versioned
release URLs and checksums.
Install `jackin-dev` alongside the preview CLI when you need the local pull request verification helper.

Homebrew can refuse to load formulae from taps that have not been trusted. Run `brew trust jackin-project/tap` once after tapping this repository.

## Updating

```sh
brew update
brew upgrade jackin-preview
brew upgrade jackin-dev
```

`Formula/jackin-preview.rb` uses an immutable `preview-<full source SHA>`
release for each eligible main commit. Each formula revision binds its build
version and complete source commit to SHA-256 digests for all six payloads.
`Formula/jackin.rb` uses permanent `vX.Y.Z` stable release URLs. Published
release tags and assets must never be replaced.

The credential-free package updater consumes Velnor's checksum-bound release
plan and authenticated `release.json` handoff. It selects the formula from the
release channel, changes only existing literal metadata, and rejects downgrades
and conflicting retries. It does not download, extract, or execute release
payloads. The isolated Velnor writer independently validates the proposal and
opens a pull request; it never pushes directly to `main`.

Velnor's native `homebrew-preview-install` check taps this checkout on an
Apple Silicon macOS runner, installs `jackin-preview`, and runs Homebrew's
formula test against the installed prebuilt binaries. The stable channel uses
`jackin` and the separate `homebrew-stable-install` check identity. Before
running Homebrew, the wrapper validates the selected channel and binds the
regular formula file to the captured `VELNOR_CHECK_HEAD` tree, including PR
merge checkouts whose second parent is that head. The test checks all three CLI
versions and verifies the packaged capsule is a Linux ELF for the expected
architecture. The capsule is executed only on Linux; its
runtime loading is verified separately by Jackin's container-backed checks.

Unattended promotion requires successful required checks, no unaddressed
feedback, and an independently qualified review-completion signal for the exact
pull request head. An empty review list is not completion. A newer preview
generation invalidates an older pending formula update.
