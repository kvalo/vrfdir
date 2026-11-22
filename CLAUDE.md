# CLAUDE.md

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Overview

vrfdir is a directory checksum verifier: a single-file Python 3 CLI
(`vrfdir`, no `.py` extension). It uses only the standard library and
hashes the files with `hashlib.file_digest()`, which needs Python 3.11
or later. Do not add third-party dependencies. The checksums are the
same as the `sha256sum` binary prints (`md5sum` for the old MD5
checksums), the tests use them to check that.

## Commands

- Run all tests: `./check` (it refuses to run as root, several tests
  need a file which cannot be read)
- Run one test: `./check -t <name>` (base name of a script in
  `tests/specs/`, e.g. `-t status`; `-t` can be repeated)
- Keep temporary data of a failed test: `./check -k`
- Run the pytest unit tests: `./unit [pytest options]` (needs
  python3-pytest, works as root too as no unit test needs an
  unreadable file)
- Coverage of `vrfdir` by both kinds of tests:
  `./coverage [./check options]` (needs python3-coverage, prints the
  lines which no test ran)
- Benchmark:
  `./tests/benchmark [-p] [-k] [-s SIZE] [-d DIR] [TEST]` (long forms
  `--profile`, `--keep-datadir`, `--data-total-size`, `--directory`)
  where TEST is `simple_benchmark` (the default) or `benchmark_status`
- Lint: `./lint` runs flake8 (config in `.flake8`), shellcheck, mdl
  (markdownlint, config in `.mdlrc` and `.mdl_style.rb`) and, if it
  is installed, yamllint (config in `.yamllint`) on the GitHub
  workflow
- CI: `.github/workflows/ci.yml` runs `./check`, `./unit` and `./lint`
  on Ubuntu, and `./check` and `./unit` on Python 3.11 to 3.15. It
  installs `cmdspecs` from a pinned tag, bump the tag when needed

There is no build step. The scripts have no file extensions to glob on,
so when you add a new Python or shell script, or a markdown file, add
it to the file list in `./lint`. The code passes `./lint`; keep it
that way.

`./check` needs `cmdspecs` (a fork of cmdtest) on PATH. It is not part
of this repository. It is available from
<https://github.com/kvalo/cmdspecs>.

## Tests

- Tests are black-box: `tests/specs/<name>.script` is run and its
  output is compared with `<name>.stdout`, and with `<name>.stderr`
  and `<name>.exit` (expected exit code) when present. A change to
  vrfdir's output needs the matching expected files updated.
- Scripts work in `$DATADIR` (temporary directory), call
  `$SRCDIR/vrfdir` and `$SRCDIR/tests/genbackupdata`, and remove
  `.vrfdir` and their data at the end.
- `filenames.script`, `filenames-invalid.script`, `encoding.script`
  and `scan.script` in `tests/specs/` must stay bash, not sh: dash
  cannot create the weird filenames they need.
- The expected files are UTF-8. Output with file names which are not
  valid UTF-8 is piped through `cat -v` in the scripts.
- `tests/genbackupdata` is the local test data generator. Its output
  must stay deterministic; `tests/specs/genbackupdata.script` checks
  that.

## Unit tests

`tests/unit/*.py` are pytest tests which call the functions of
`vrfdir` in the same process. They complement the black-box tests
above, which stay the place for the output and the exit codes of whole
commands, signals, fault injection and unreadable files.

- `vrfdir` has no `.py` extension, `tests/unit/conftest.py` loads it
  and gives it to the tests as the `vrfdir` fixture.
- Do not fake a platform (no patching of `sys.platform` or
  `CASE_INSENSITIVE`). Test the code of another system with
  `pytest.mark.skipif` on the real platform, so that it runs when the
  tests are run on that system.
- Same as the other tests: nothing which depends on the machine
  (locale, environment).
- pytest is only for the tests, vrfdir itself stays standard library
  only.

## Constraints

- `.vrfdir/manifest.json` (see `MANIFEST_VERSION`) must stay readable.
  A format change needs a version bump and migration of existing
  files. Version 1 has the MD5 checksum in the `md5sum` key, version
  2 has `checksum` with the algorithm in front (`sha256:...`, and
  `md5:...` for the files of the older versions until `vrfdir
  upgrade`). A repository of version 0 has `.vrfdir/hashes.json` (the
  old name) which is still read when there is no `manifest.json`.
  Both are converted in memory when loaded and the next write
  converts the file: `manifest.json` is written, then the old file is
  removed. `tests/data/hashes-v0.json` and `tests/data/manifest-v*.json`
  are the real files of those versions, never regenerate them.
- Exit codes are tested behaviour and mean the same in every
  command: 0 success, 1 differences (`status`, and `check` and
  `upgrade` when the names or the sizes differ), 2 corruption
  (`check`, `upgrade`), 3 error (also a
  missing repository), 64 wrong command line and 130 interrupted.
  Every `sys.exit()` in `vrfdir` uses one of the `EXIT_*` defines,
  never a bare number. An error is always `EXIT_ERROR`, never 1: 1 is
  what a Python stacktrace gives, so nothing may get out of `main()`
  uncaught. A new exit value needs a new define, and the table in
  `HELP_MAIN` and the `exit codes:` section of the command updated.
- A file name is a sequence of bytes and vrfdir must work with any
  name in any locale. Inside vrfdir the names are `str` in the
  filesystem encoding, as `os.scandir()` and `sys.argv` give them
  (surrogate escapes for the bytes which cannot be decoded). In
  `manifest.json` a name is its bytes decoded as UTF-8 with
  `surrogateescape`, use `name_to_json()` and `name_from_json()`. On
  stdout a name is written as its bytes. Never decode or encode a name
  with the encoding of the locale in any other way.
- The separator of a name is always `/`, inside vrfdir and in
  `manifest.json`, also on Windows. Only a path from the command line
  is converted, with `path_to_name()`. Do not use `os.sep` or
  `os.path.join()` for the names.
- A repository has to work when it is moved to another operating
  system. An entry of `manifest.json` whose name cannot be a file name
  on the current system (`is_native_name()`) is kept in
  `VrfdirRepo.foreign` and written back as it is, never dropped.
- vrfdir has to work on Linux, the BSDs, macOS and Windows. The tests
  run only on Linux, so nothing checks the code which is only for
  the other systems (`sys.platform`, `CASE_INSENSITIVE`). Say so when
  you change it, the user has to try it by hand.
- The tests are run in a UTF-8 locale.

## Help texts

The help texts in `vrfdir` (the `HELP_*` descriptions and the `help=`
strings in `main()`) are the definition of how each command should
behave: what it does, what it prints and its exit codes. Keep them
up to date. A change to the behaviour of a command needs its help
text changed in the same commit, and when the code and the help text
disagree, one of them has a bug.

## Error messages

- Every message goes through `logger` to stderr and is printed as
  `Error: ...` or `Warning: ...`, also the command line errors of
  argparse. stdout is only for the output of the command.
- The form is `cannot <do what> <name>: <reason>`, or a plain
  statement of the fact, in lowercase and without a trailing period.
  No "failed to" and no "can't". When the user can fix it, tell
  how (`Run 'vrfdir init' ...`).
- The user is not a programmer. Never print `str()` or `repr()` of
  an exception: use `error_reason()` for an `OSError` and write the
  rest of the text yourself. A problem in the content of
  `manifest.json` uses `damaged_error()`.
- A file name in a message goes through `name_for_message()`, and
  a key of `manifest.json` through `foreign_name()`.
- The message of a `VrfdirError` is printed to the user as it is.
- Do not skip what cannot be read. A file or a directory which
  cannot be read is a message and `EXIT_ERROR`, and the command
  still does the rest. `find_files()` gives these in the
  `unreadable` list and the caller has to report them.
- Only a real bug may reach the `except Exception` of `main()`,
  which prints the stacktrace. A new failure which the user can
  cause needs its own message and a test of it in `tests/specs/`.

## Documentation

Documentation files (this file, `README.md`, `TODO.md` and the like)
should strive for lines of at most 72 columns. Reasonable exceptions
are accepted, for example a long command, URL or table row that would
be worse if broken.

## License

vrfdir is GPL-3.0-or-later, the text is in
`LICENSES/GPL-3.0-or-later.txt`. Every new script, test and markdown
file starts with the two SPDX lines of the existing files (after the
shebang, as an HTML comment after the title in markdown). Files which
cannot or should not have a comment have no header: the expected
output files (`.stdout`, `.stderr`, `.exit`), `tests/data/*.json`, the
configuration dotfiles (`.flake8`, `.mdlrc`, `.mdl_style.rb`,
`.gitignore`) and the license text in `LICENSES/`.

## Release process

The version is only in `VERSION` in `vrfdir`, and CHANGELOG.md has a
heading for it. Between releases the version is `<release>+git` and
CHANGELOG.md has an `## [Unreleased]` heading above the last release.
`test_changelog_matches_version` checks that they match. The version
has nothing to do with `MANIFEST_VERSION`.

The user pushes to `main` and tags. Claude prepares the commits,
creates the GitHub release with `gh` (after asking) and reminds the
user of the other steps. Version numbers look like `0.1.0` and tags
like `v0.1.0`.

1. Make the release commit, subject `vrfdir: release vX.Y.Z`:
   - Replace the `+git` version with `X.Y.Z` in `VERSION` in `vrfdir`.
   - In CHANGELOG.md, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`.
     Do not leave an empty `[Unreleased]` heading in the release
     commit.
   - Fix the link references at the bottom: remove `[Unreleased]` and
     add
     `[X.Y.Z]: https://github.com/kvalo/vrfdir/compare/vPREV...vX.Y.Z`
     (the first release has
     `https://github.com/kvalo/vrfdir/releases/tag/vX.Y.Z`).
   - Run `./check`, `./unit` and `./lint`.
2. Test that exact commit on Windows and macOS by hand, as nothing
   checks the code for them (see Constraints). If the commit changes
   afterwards, e.g. by amending, the tag must point at the new hash.
   Also push the commit to `staging` (ask first) and wait for CI
   with `gh run watch`.
3. The user signs and tags the exact commit which was tested, e.g.
   `git tag -s vX.Y.Z <hash> -m "vrfdir vX.Y.Z"`, and pushes the
   commit and the tag to `main`. Never push to `main` or create the
   tag; remind the user instead.
4. Once the tag is on origin, ask, then create the GitHub release:
   save the `[X.Y.Z]` section of CHANGELOG.md, without its heading,
   to a scratchpad file and run
   `gh release create vX.Y.Z --verify-tag --title "vrfdir vX.Y.Z"
   --notes-file <file>`. `--verify-tag` makes it fail when the tag has
   not been pushed.
5. Once `origin/main` and the tag are on the release commit, make the
   post-release commit, subject `vrfdir: mark version as X.Y.Z+git`:
   set `VERSION` to `X.Y.Z+git`, add `## [Unreleased]` back above
   `[X.Y.Z]` in CHANGELOG.md and its
   `[Unreleased]: .../compare/vX.Y.Z...HEAD` link reference. Run
   `./check`, `./unit` and `./lint`.

## Commits

Subject is `<component>: <lowercase imperative summary>` without a
trailing period, where the component is the file name (`vrfdir:`,
`tests:`, `benchmark:`, `TODO.md:`). Adding a new file uses no
prefix (`add genbackupdata`). The body is short prose explaining why.
