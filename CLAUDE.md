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
  `tests/specs/` or one of the `tests/specs-*/` directories, e.g.
  `-t status`; `-t` can be repeated and runs the test of that name in
  every directory)
- Keep temporary data of a failed test: `./check -k`
- Run only the tests which work on every system: `./check --portable`
  (only `tests/specs/`, none of the `tests/specs-*/` directories)
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
  workflow and `reuse lint` (REUSE compliance, see License)
- CI: `.github/workflows/ci.yml` runs `./check`, `./unit` and `./lint`
  on Ubuntu, and `./check` and `./unit` on Python 3.11 to 3.15, on
  macOS (`macos-latest`, with GNU coreutils and sed from brew), on
  FreeBSD, OpenBSD and NetBSD (VMs of `cross-platform-actions/action`,
  with GNU coreutils and sed from the packages) and on Windows
  (`windows-latest` and `windows-11-arm`, in the Git Bash of Git for
  Windows).
  It installs `cmdspecs` from a pinned tag, bump the tag when needed

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
- `tests/specs/` runs on every system, also on Windows, where
  cmdspecs runs the scripts with the sh of Git for Windows. cmdspecs
  cannot skip a test, so a test which cannot work everywhere goes to
  one of the directories below (same format), chosen by `./check`
  with `uname -s`.
- `tests/specs-unix/` is for a test which needs a POSIX system, run
  everywhere but on Windows: chmod for a directory which cannot be
  read, symbolic links, named pipes, the flush of a directory, an
  argument like `/dev/null` (the sh of Git for Windows converts an
  absolute POSIX path for a Windows program), or an error text which
  differs on Windows ("Not a directory", "Is a directory").
- `tests/specs-bytenames/` is for a test which needs a filesystem
  where a name is any sequence of bytes: a file name which is not
  valid UTF-8 (APFS refuses it), or names which differ only in the
  case or the normalisation form. `./check` runs it on Linux and the
  BSDs.
- A test which needs Linux goes to `tests/specs-linux/`: `/dev/full`
  or an error text of Linux. `./check` runs it only on Linux.
- `tests/specs-macos/` has the tests of the macOS behaviour
  (normalisation form of names), run only on macOS (`uname -s` is
  Darwin). `tests/specs-caseless/` has the tests of a filesystem which
  ignores the case of the names, run on macOS and Windows.
- `tests/specs-windows/` has the tests of the Windows behaviour
  (backslashes, names which cannot be files there, junctions) and the
  Windows versions of tests in `tests/specs-unix/`, run only on Windows
  (`uname -s` is `MINGW*` or `MSYS*`).
- Only the part of a test which needs a system goes to the directory
  of that system. A test which also has parts for every system is
  split: those stay in `tests/specs/`, and the rest has the same name
  in one `tests/specs-*/` directory, so that `-t <name>` runs both.
  The rest stays together in the directory which its parts need, for
  example `tests/specs-linux/` when one of them needs Linux (also
  when the others only need `tests/specs-bytenames/`), and is
  not split again. The Windows version of a part in
  `tests/specs-unix/`, when there is one, has the same name in
  `tests/specs-windows/`.
- Only CI and the user can run `tests/specs-macos/`,
  `tests/specs-caseless/` and `tests/specs-windows/`: say so when you
  add or change one, the expected output was not seen on a real
  system. Take it from the CI log and check that every line is the
  right behaviour, not only that it is what vrfdir printed.
- Scripts work in `$DATADIR` (temporary directory), call
  `$SRCDIR/vrfdir` and `$SRCDIR/tests/genbackupdata`, and remove
  `.vrfdir` and their data at the end.
- A file which cannot be read is made with
  `$SRCDIR/tests/unreadable FILE`, and `--undo` gives the right back
  before the cleanup. It uses chmod on a POSIX system and a deny entry
  of icacls on Windows, so the test goes to `tests/specs/`. A
  directory which cannot be read needs chmod and `tests/specs-unix/`,
  and a Windows version in `tests/specs-windows/`: there a deny entry
  of a directory has an effect only when vrfdir runs with
  `$SRCDIR/tests/unprivileged SCRIPT [ARGS...]`, without the backup
  and restore privileges which the user of the CI runner has enabled.
- A repository which another vrfdir is changing is made with
  `$SRCDIR/tests/locked SCRIPT [ARGS...]`, which holds the lock of
  `.vrfdir/lock` while it runs the Python script (`$SRCDIR/vrfdir`
  or `tests/inject-at`) in a process of its own. It works on every
  system, so the test goes to `tests/specs/`.
- `filenames-invalid.script`, `encoding.script` and `scan.script` in
  `tests/specs-bytenames/` must stay bash, not sh: dash cannot create
  the weird filenames they need.
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

- vrfdir never changes the data of the user: it writes only in
  `.vrfdir` (and `os.devnull`), no command may create, change,
  rename, remove or touch any other file or directory, also when it
  fails. `tests/specs/data-untouched.script` checks the data (names,
  content and modification times) after every command, and
  `tests/unit/test_data_untouched.py` lists every call of `vrfdir`
  which can write and fails on an unknown one. A new write needs an
  entry in `ALLOWED_WRITES` there, with a path in `.vrfdir`, and a
  new command or a new failure path needs a case in the script.
- `.vrfdir/manifest.json` (see `MANIFEST_VERSION`) must stay readable.
  A format change needs a version bump and migration of existing
  files. Version 1 has the MD5 checksum in the `md5sum` key, version
  2 has `checksum` with the algorithm in front (`sha256:...`, and
  `md5:...` for the files of the older versions until `vrfdir
  upgrade`), version 3 adds the top-level `checksum` of the content
  (`manifest_checksum()`, verified on every read, the older versions
  have none). A repository of version 0 has `.vrfdir/hashes.json` (the
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
- vrfdir has to work on Linux, the BSDs, macOS and Windows. CI runs
  the tests (`./check` and `./unit`) on Linux, FreeBSD, OpenBSD and
  NetBSD (in VMs), macOS and Windows. Say so when you change code
  which is only for one system: for FreeBSD, OpenBSD, NetBSD, macOS
  and Windows CI is the only test.
- The tests are run in a UTF-8 locale.

## Command line options

Every option has both a short and a long form (`-q`/`--quiet`,
`-V`/`--version`), also the ones of the commands. Add both when you
add an option, `test_options_have_short_and_long_forms` checks it.

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
`LICENSES/GPL-3.0-or-later.txt`, and follows the REUSE specification
(<https://reuse.software/>), checked by `reuse lint` in `./lint`.
Every new script, test and markdown file starts with the two SPDX
lines of the existing files (after the shebang, as an HTML comment
after the title in markdown). Files which cannot or should not have a
comment have no header: the expected output files (`.stdout`,
`.stderr`, `.exit`), `tests/data/*.json`, the configuration dotfiles
(`.flake8`, `.mdlrc`, `.mdl_style.rb`, `.gitignore`,
`.gitattributes`) and the license text in `LICENSES/`. `REUSE.toml`
gives their copyright and license instead; add a new file of that
kind there, unless one of its globs already covers it.

## Finding the commit of a version

A `+git` version has a suffix, like `0.1.0+git.1667ecd1`
(`version_string()`). It is not a git commit id but the first 8 hex
digits of the SHA-256 of the `vrfdir` script, so `git show` cannot
resolve it. Hash the script at every commit instead:

    for c in $(git rev-list --all); do
        h=$(git show $c:vrfdir | sha256sum | cut -c1-8)
        [ "$h" = 1667ecd1 ] && git log --oneline -1 $c
    done

Several commits can match, as a commit which does not touch `vrfdir`
has the same hash as its parent. The oldest match is the commit which
made that script. A commit which has no `vrfdir` at all prints an
error, ignore it. If nothing matches, the build had local changes or
is from a commit which is not in this repository (fetch first).

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
2. Push that exact commit to `staging` and wait for CI with
   `gh run watch`. CI is the test on every system (see Constraints),
   so it has to pass on all of them. If the commit changes afterwards,
   e.g. by amending, CI has to pass again and the tag must point at
   the new hash.
3. The user signs and tags the exact commit which was tested, e.g.
   `git tag -s vX.Y.Z <hash> -m "vrfdir vX.Y.Z"`, and pushes the
   commit and the tag to `main`. Never push to `main` or create the
   tag; remind the user instead.
4. Once the tag is on origin, ask, then create the GitHub release:
   save the `[X.Y.Z]` section of CHANGELOG.md, without its heading,
   to a scratchpad file, and save the `vrfdir` script of the tag
   (`git show vX.Y.Z:vrfdir`, executable) to a scratchpad file named
   `vrfdir`, so that the asset is the same as the tagged commit. Run
   `gh release create vX.Y.Z --verify-tag --title "vrfdir vX.Y.Z"
   --notes-file <file> <scratchpad>/vrfdir`. `--verify-tag` makes it
   fail when the tag has not been pushed. The script is attached as a
   release asset so that users can download it directly.
5. Once `origin/main` and the tag are on the release commit, make the
   post-release commit, subject `vrfdir: mark version as X.Y.Z+git`:
   set `VERSION` to `X.Y.Z+git`, add `## [Unreleased]` back above
   `[X.Y.Z]` in CHANGELOG.md and its
   `[Unreleased]: .../compare/vX.Y.Z...HEAD` link reference. Run
   `./check`, `./unit` and `./lint`.

## Commits

Commits follow the style of the Linux kernel
(`Documentation/process/submitting-patches.rst`):

- One logical change in a commit. Split unrelated changes, and do not
  split one change so that a commit makes no sense alone.
- Subject is `<component>: <lowercase imperative summary>` without a
  trailing period, where the component is the file name (`vrfdir:`,
  `tests:`, `benchmark:`, `TODO.md:`). Adding a new file uses no
  prefix (`add genbackupdata`).
- The body is short prose in the imperative mood: what the problem
  is and why the change solves it. Wrap it at 72 columns.
- Refer to an earlier commit with its 12 character id and subject:
  `commit 0dc3216a5717 ("vrfdir: add -V as the short form of
  --version")`.

A commit must never break `git bisect`: every commit on its own has to
pass `./check`, `./unit` and `./lint`, and CI on every system which
`ci.yml` of that commit tests. Order the commits so that a fix comes
before what needs it, for example a new CI job after the fixes which
make its tests pass. A commit on `staging` which breaks something is
fixed by rebasing, not by a commit on top of it.

Running all the tests on every commit takes a lot of time and is not
needed. Run `./check`, `./unit` and `./lint` on the last commit of
the series. For the commits before it, think about what each one
changes and run only what could break, e.g. `./check -t <name>` of
the tests it touches, or nothing for a commit which only changes
documentation. Run the whole set on every commit, e.g. with
`git rebase --exec './check && ./unit && ./lint' main`, only when
the order of the commits matters, for example when a later commit
fixes something which an earlier one needs.
