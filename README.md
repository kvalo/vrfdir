# vrfdir

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

vrfdir is a directory checksum verifier. It stores the SHA-256
checksum and the size of every file you add to it, and later tells you
if any of those files were changed, deleted or silently corrupted. It
is meant for data which should not change: photo archives, backups and
the like.

vrfdir only detects the damage, it does not repair anything. You need
a backup to restore a corrupted file from.

## Requirements

- Python 3.11 or later
- Linux, one of the BSDs, macOS or Windows

vrfdir is developed on Linux, and its tests are run also on FreeBSD,
OpenBSD, NetBSD, macOS and Windows. See [Windows](#windows) below for
the differences there.

That is all. vrfdir is one file which uses only the Python standard
library, there is nothing to build or install with pip.

## Installation

Copy the `vrfdir` file to a directory in your `PATH`, or run it
straight from a clone of this repository.

### Windows

Windows does not run a file without an extension, start vrfdir with
the Python launcher:

    C:\data\photos> py C:\path\to\vrfdir status

The rest of this document applies as it is, with these differences:

- The names are always printed and stored with `/` as the separator,
  `dir/file.jpg`. On the command line both `/` and `\` work.
- The output is UTF-8, also when it is redirected to a file. Its
  lines and the messages end with a plain newline.
- A path longer than 260 characters works only if long paths are
  enabled in Windows. Otherwise `add` and `check` report the file as
  an error.

### Moving a repository between systems

`.vrfdir/manifest.json` is the same on every system, so the data can be
added on one and checked on another, for example on a disk which is
moved between Linux and Windows.

Windows cannot have all the file names Linux can: a name with `\`,
`:` or bytes which are not valid UTF-8, a name which ends with a dot
or a space, or a device name like `NUL`. On Windows `status` shows
those files as deleted (`D`), but `refresh` does not remove them.
Their checksums are kept and work again on the system where the files
were added.

## Usage

vrfdir works in the current directory, which has to be the top
directory of the data. The checksums are stored there in
`.vrfdir/manifest.json`. It has a checksum of its own content, so
a damaged `manifest.json` is reported as such and not as corrupted
files. Do not edit it by hand, vrfdir refuses the changed file.
Every save keeps the previous version as
`.vrfdir/manifest.json.bak`, rename it to `manifest.json` to go
back one save.

Create the repository and add all the files:

    $ cd /data/photos
    $ vrfdir init
    $ vrfdir add .
    Adding files: 100% (3/3 files, 12 B of 12 B, 12 B/s, 0:01)

Later, check that the files have not changed. `status` is the quick
check which compares only the names and the sizes, `check` reads
every file and compares the checksum:

    $ vrfdir status
    $ vrfdir check
    M photos/a.jpg
    Checking: 100% (3/3 files, 12 B of 12 B, 12 B/s, 0:01)
    1 file(s) modified

`vrfdir --help` lists all the commands and `vrfdir COMMAND --help`
describes a command, its output and its exit codes.

`export` prints the checksums in the format of `sha256sum`, so that
the files can be verified without vrfdir:

    $ vrfdir export | sha256sum -c

### Deleted and changed files

When you delete a file or change it on purpose, `status` shows it as
deleted (`D`) or with a new size (`S`). `refresh` writes those
changes to the repository, `--dry-run` shows first what it would do:

    $ vrfdir refresh --dry-run .
    D photos/old.jpg
    S photos/edited.jpg
    1 file(s) would be removed, 1 file(s) would be updated
    $ vrfdir refresh .
    D photos/old.jpg
    S photos/edited.jpg
    1 file(s) removed, 1 file(s) updated

A path limits it to the files below it, for example
`vrfdir refresh photos`. `refresh` does not add new files, use `add`
for them. It never reads a file whose size is the same as before:
vrfdir cannot tell such a change from corruption, so a file which
`check` reports as modified (`M`) keeps its checksum.

### Repositories of an older vrfdir

Older versions stored the MD5 checksum. Such a repository still
works, `check` compares the MD5 checksums as before, and the files
you add now get SHA-256 checksums. `list` shows the algorithm in front
of every checksum (`md5:` or `sha256:`). To replace the MD5 checksums
run:

    $ vrfdir upgrade

The checksums cannot be converted, so `upgrade` reads every file
which has an MD5 checksum. A file which does not match its MD5
checksum is printed as `M` and keeps it, so that an already corrupted
file does not get a SHA-256 checksum of its damaged content. `export`
refuses to print anything while a file still has an MD5 checksum.

### Good to know

- Only regular files are added. Inside an added directory a symbolic
  link to a file is followed, a link to a directory is not. A
  junction of Windows is a link to a directory.
- File names can be any bytes, also ones which are not valid in the
  encoding of your locale.
- Changing a file on purpose without changing its size looks the same
  as corruption, and there is no command yet to accept such a change
  or to remove an added file which still exists.
- SHA-256 is used to catch accidental corruption. The checksums are
  stored next to the files, so they do not protect against somebody
  modifying both on purpose.

### Reporting a bug

Please report bugs on the [Issues page][issues] of the project in
GitHub and attach the output of `vrfdir info --full`. Its last lines
have the version of vrfdir, Python and the system, and nothing about
you or your files. If the repository is broken and `info` cannot read
it, `vrfdir --version` prints the same without a repository.

[issues]: https://github.com/kvalo/vrfdir/issues

## Development

### Requirements

Everything in [Requirements](#requirements) above, and in addition:

| Tool                  | Needed for                                 |
|-----------------------|--------------------------------------------|
| `cmdspecs`            | `./check`, a fork of cmdtest, has to be on `PATH` |
| `bash`                | some of the tests, dash cannot create the file names they use |
| `md5sum`, `sha256sum` and the other coreutils | the tests, they compare vrfdir's checksums with those commands |
| Git for Windows       | the tests on Windows, run `./check` and `./unit` in its Git Bash, which has `sh` and the coreutils |
| a UTF-8 locale        | running the tests                          |
| `flake8`              | `./lint`                                   |
| `shellcheck`          | `./lint`                                   |
| `mdl` (markdownlint)  | `./lint`                                   |
| `yamllint`            | `./lint`, optional, checks the GitHub workflow |
| `python3-pytest`      | `./unit`, the unit tests                   |
| `python3-coverage`    | `./coverage`                               |

`cmdspecs` is not part of this repository. `./tests/benchmark`
needs nothing extra, the test data is created with the
`tests/genbackupdata` script in this repository.

### Commands

    ./check                  # run all tests
    ./check -t status        # run one test, tests/specs/status.script
    ./check -k               # keep the temporary data of a failed test
    ./check --portable       # only tests/specs, for every system
    ./coverage               # run all tests, show the lines not run
    ./lint                   # flake8, shellcheck, mdl and yamllint
    ./tests/benchmark        # simple_benchmark, see --help

The tests are black-box: each `tests/specs/<name>.script` is run and
its output and exit code are compared with the expected files next to
it. The tests in `tests/specs/` run on every system, the ones in
`tests/specs-unix/`, `tests/specs-bytenames/`, `tests/specs-linux/`,
`tests/specs-macos/`, `tests/specs-caseless/` and
`tests/specs-windows/` only on the systems `./check` picks for them.
See `./tests/benchmark --help` for the options of the benchmark.

Known problems and plans are in [TODO.md](TODO.md).

## License

vrfdir is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version. See
[LICENSES/GPL-3.0-or-later.txt](LICENSES/GPL-3.0-or-later.txt).

The project follows the [REUSE](https://reuse.software/)
specification: every file has [SPDX](https://spdx.dev/) copyright and
license tags in a header comment, or in `REUSE.toml` when it cannot
have one. `reuse lint` checks it.
