# Changelog

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

All notable changes to vrfdir are documented in this file.

The format is based on [Keep a Changelog][keepachangelog], and this
project adheres to [Semantic Versioning][semver].

## [Unreleased]

### Added

- `vrfdir init`, `add` and `upgrade` lock the repository with
  `.vrfdir/lock`. While one of them runs, another one fails with an
  error and nothing is lost: before, two `add` commands at the same
  time could drop the files the other one added. The commands which
  only read the repository do not wait for the lock. A filesystem
  which cannot lock gives a warning and the command works without
  the lock.

### Fixed

- A command which reads the repository while another vrfdir saves it
  no longer warns about a stale `.vrfdir/manifest.json.tmp`, the file
  of that save.

## [0.2.0] - 2026-11-24

### Added

- manifest.json has a checksum of its own content (format version
  3), verified every time it is read. A damaged manifest.json is an
  error about manifest.json, not a corrupted file. `vrfdir info`
  shows the checksum. A repository of an older format is converted
  by the next command which saves it, for example `vrfdir upgrade`.
- Every save keeps the previous manifest.json as
  `.vrfdir/manifest.json.bak`. An old `hashes.json` is kept there in
  the format of manifest.json.
- A saved manifest.json and its backup are read back, and the
  checksum of manifest.json verified, before they replace the old
  files. A file which does not read back as it was written is an
  error and the old file stays.
- The `.vrfdir` directory is flushed to the disk after a save, so
  that the new manifest.json is still there after a power cut. Not
  on Windows, which cannot do it.

- `-V` is the short form of `--version`.
- `vrfdir info --full` (`-f`) also prints the version of vrfdir,
  Python and the system, for bug reports. `vrfdir --full-version`
  prints the same without a repository.

### Changed

- `vrfdir list` and `vrfdir export` print the files sorted by the
  bytes of the name, not in the order they were added.

### Fixed

- On Windows the messages and the help ended the lines with CRLF,
  now with a plain newline like the rest of the output.

## [0.1.0] - 2026-11-22

### Added

- First release.

[keepachangelog]: https://keepachangelog.com/en/1.1.0/
[semver]: https://semver.org/spec/v2.0.0.html
[Unreleased]: https://github.com/kvalo/vrfdir/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kvalo/vrfdir/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kvalo/vrfdir/releases/tag/v0.1.0
