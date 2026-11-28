# TODO

<!--
SPDX-FileCopyrightText: 2026 Kalle Valo
SPDX-License-Identifier: GPL-3.0-or-later
-->

## sha256sum -c on Ubuntu 26.04

Ubuntu 26.04 has the sha256sum of uutils coreutils (0.10.0), not the
GNU one. It reads a line without the backslash marker with the name
unescaped (`back\nslash` becomes a name with a newline), and it does
not accept a line with the marker at all, not even one which it wrote
itself ("no properly formatted checksum lines found"). So
`vrfdir export | sha256sum -c` cannot work for a name with a newline
or a backslash there, whatever vrfdir prints, and `filenames-newline`
and two `manifest-json-compat` tests fail. This is a bug of uutils, so
the CI matrix runs on ubuntu-24.04 until it is fixed. Report it to
uutils, and when a newer version works, make the CI use `ubuntu-latest`
again.

## smaller issues found in the review

- add ignores a symbolic link given on the command line without
  any message, but a link to a file inside an added directory is
  followed and added. Decide which one is right.

- An old manifest.json can have paths outside of the repository
  ('../x', absolute paths) or inside .vrfdir. add refuses those
  now, but the old entries stay and status shows them as
  conflicts (C) or deleted (D). 'vrfdir refresh .' removes them,
  but only with '.', a path cannot name them. Test that.

- No modification time is stored, only size and checksum. A file
  which was edited on purpose without changing its size and a file
  which was corrupted look the same in check, and refresh cannot
  accept the edit. See the item of the modification time below.

- vrfdir only works in the directory which has .vrfdir, it does
  not look for it in the parent directories like git does.

- check prints "N file(s) deleted or changed, checksums not
  checked" and exits without saying which files. The user has to
  run status to see them, as the message tells.

- scan reports only the files with an invalid name. A directory
  with an invalid name is not reported if it has no files.

- write() saves the backup before manifest.json. When manifest.json
  cannot be replaced, for example on Windows while another program
  has it open, the backup is already a copy of the current
  manifest.json and the version one save older is lost. The
  repository itself is fine. tests/specs-windows/manifest-open
  checks what happens now.

- When the backup manifest.json.bak cannot be replaced, the error
  says "cannot save the repository .vrfdir/manifest.json" and does
  not name the backup, which was the file that failed.
  tests/specs-windows/manifest-open checks what happens now.

## add_file(): stat and hash the same open file

add_file() calls os.stat() and then hashes the file. A file which
changes in between is stored with a size which does not match the
checksum, and status or check blames the file later. Open the file
once and take the size with os.fstat() of the same file object.
tests/inject-at can make the first os.stat() fail, but not change a
file in between: a new kind of fault for it is needed to test this.

## a .vrfdir in a subdirectory is not ignored

Only the .vrfdir in the current directory is skipped, a
sub/.vrfdir/manifest.json is a normal file which add adds and status
shows. That may be wanted (a repository inside the data is just data),
but the help texts do not say it. Decide, document it in the help
text of add and test it. tests/specs/vrfdir-in-subdir.script records
what happens now.

## store the modification time of every file (manifest version 4)

refresh accepts only what status sees: deleted files, names which
are not files anymore and new sizes. A file which was edited on
purpose without changing its size looks the same as corruption, and
check reports it as modified forever. With the modification time
(`st_mtime_ns`) in every entry, a changed checksum with a new mtime
is most likely an edit, and one with the same mtime is corruption,
which does not touch the mtime. Then status could show a same-size
edit without reading the file, and refresh could accept it.

- Needs `MANIFEST_VERSION` 4, the mtime in `manifest_checksum()` and
  a migration: the old entries have no mtime until refresh or
  upgrade sets it.
- The repository has to work after a move: a copy without the
  timestamps (`cp`, `rsync` without `-t`) changes every mtime, and
  the precision differs (FAT 2 s, exFAT 10 ms, HFS+ 1 s, NTFS 100
  ns). Compare with the coarser precision, and decide what a changed
  mtime with the same checksum does.
- An mtime can be set back on purpose (`touch -r`, `tar`), so it is
  a hint and not a proof. That makes an edit look like corruption,
  never the other way around.
- The same format change can bring the created and last-modified
  fields and `last_checked` of the items below.

## cmd_add: should run verify_files() first

just to make sure that the repo is intact and there's no
corruption. If there are changes, print an error and bail out

## cmd_check: add --time-limit

so that it's possible to run check 10 min run every day from cron

should choose files randomly, should add --random or is it implicit?

maybe store last_checked for each file in json and always start
from oldest? or just check randomly?

## add created and last-modified fields to manifest.json

naturally show them also in info command

## cmd_rm: implement

Make it possible to remove files from json. Also can take
directories as argument. It takes the lock of the repository like
add.

Until then there is no way to remove a file which still exists:
manifest.json has a checksum of its content and vrfdir refuses a
manifest.json which was edited by hand. 'vrfdir refresh' removes
only the deleted files.

## add syslog support

Make it possible to send logs to syslog, could be enabled like with
'--syslog'. For example, this would be useful with cron. But on the
other hand we would like to get errors also stderr/stdout, so that
cron can send mails about those. So maybe levels above warning to
stdout and debug etc to syslog?

- <file:///usr/share/doc/python-doc/html/library/syslog.html>
- <http://stackoverflow.com/questions/3968669/how-to-configure-logging-to-syslog-in-python>

## add manpage

The only documentation of the commands is README.md and the help
texts. Add vrfdir(1) which describes the commands, the options and
the exit codes.

## add standard python packaging

vrfdir is a single script without an extension, so it cannot be
installed with pip or pipx. Add the standard packaging files, most
likely a `pyproject.toml` with the metadata (name, version,
`requires-python = ">=3.11"`, no dependencies) and a console script
entry point so that `pip install .` and `pipx install .` give a
`vrfdir` command.

Open questions, the tools have not been chosen yet:

- Which build backend: setuptools, hatchling, flit or something
  else. Prefer the simplest one which works with a pure standard
  library project.
- The script has no `.py` extension and is not a module. It needs
  to become a module (or be installed as a script file) for an
  entry point to work, and the tests call `$SRCDIR/vrfdir`
  directly, so they must keep working.
- Where the version comes from. The release version is `VERSION` in
  the script, it must stay the only place (`MANIFEST_VERSION` is the
  format of manifest.json and unrelated).
- Add the new files to `./lint` and check that the tests still
  pass from a clean install.

## ignore the files the operating system creates

macOS creates .DS_Store and Windows creates Thumbs.db and
desktop.ini in the directories. status shows them as not added,
and when they are added they change later and look like
corruption. Needs a way to ignore files, maybe a list of patterns
in .vrfdir.

## the case of the names on a filesystem which ignores it on Linux

`CASE_INSENSITIVE` is set by the system (Windows and macOS), not by
the filesystem. On Linux an exFAT or FAT32 disk, the usual one moved
between systems, ignores the case too, and vrfdir then treats the two
spellings of a name as two files. Tried on CI on the Ubuntu runner
with loop mounted exFAT and vfat images, both behave the same:

- A name given in another case is stored as it was typed:
  `disk_name()` is only called when `CASE_INSENSITIVE`. With the
  file `photo.jpg`, `vrfdir add PHOTO.JPG` adds `PHOTO.JPG`, status
  shows `C PHOTO.JPG` and `? photo.jpg` (exit value 1), and check
  refuses with "1 file(s) deleted or changed". `vrfdir add
  photo.jpg` then adds the same file a second time, list has both
  names.
- `is_vrfdir_path()` folds the case only when `CASE_INSENSITIVE`.
  `vrfdir add .vrfdir` is refused, but `vrfdir add .VRFDIR` (and
  `.VRFDIR/manifest.json`) adds the files of vrfdir itself as
  `.VRFDIR/lock`, `.VRFDIR/manifest.json` and
  `.VRFDIR/manifest.json.bak`. status shows them as `C`, and check
  refuses with "3 file(s) deleted or changed" from then on, as
  manifest.json changes with every save. Most likely nothing can
  remove them, see cmd_rm above. `vrfdir add .` finds `.vrfdir`
  with its real name and skips it, as it should.

Whether the filesystem ignores the case has to be found out per
repository, for example once at the start by comparing the
`os.stat()` of `.vrfdir` and of the same name in another case, and
then used instead of `CASE_INSENSITIVE` (also for the output of
`vrfdir info`). The tests need a filesystem which ignores the case on
Linux, see the item of the filesystems of a moved disk below: the
tests of `tests/specs-caseless/` should then pass there too.

## measure the coverage on every system in CI

`./coverage` runs only on Linux, so nothing measures which lines the
tests run of the code which is only for Windows or macOS
(`sys.platform` checks, `CASE_INSENSITIVE`, `msvcrt` instead of
`fcntl`). Today that every such line has a test is a reading of the
code, not a number. Run it in CI:

- Fix `./coverage` for the Git Bash of Windows. `PYTHONPATH` is
  joined with `:`, Windows needs `;` (`os.pathsep`), and
  `include = $srcdir/vrfdir` is an MSYS path (`/d/a/...`) which
  coverage does not match with the `D:\a\...` of the Python of
  Windows (`cygpath -m` gives one which does). Check that the
  `sitecustomize.py` is loaded by every vrfdir which the tests start,
  also through `tests/console`, `tests/unprivileged` and the `py`
  launcher of `py-launcher`, which may pick another Python without
  coverage installed.
- macOS and the BSDs should work as they are, check it.
- Install coverage in the jobs (`pip install coverage`, the BSDs in
  their venv).
- Run the tests only once per job: either `./coverage` instead of
  `./check` and `./unit`, which then decides the result of the job
  (it exits with the status of the tests), or both, which doubles the
  time (the Windows jobs take 4-6 minutes for `./check`).
- A report per system is mostly noise, each one misses the lines of
  the other systems. The useful number is the combination: upload
  the data of each job as an artifact (`actions/upload-artifact`)
  and combine them in a job of its own with a `[paths]` section
  which maps the source directories of the runners
  (`/home/runner/work/vrfdir/vrfdir`, `D:\a\vrfdir\vrfdir`,
  `/Users/runner/work/...` and the ones in the VMs) to one. Its
  report lists the lines which no system ran.
- The report is for information, no minimum percentage fails the
  job. A line in the combined report is a missing test, or code
  which cannot run anywhere.

## test on the filesystems of a disk which is moved

README.md tells that the data can be added on one system and checked
on another, for example on a disk which is moved between Linux and
Windows. Such a disk often has exFAT or FAT32, but CI runs the tests
only on ext4 (Linux), UFS/FFS (the BSDs), APFS (macOS) and NTFS
(Windows). What differs there:

- The case of the names is ignored also on Linux, but
  `CASE_INSENSITIVE` is set by the system and not by the filesystem.
  See the item of the case of the names on Linux above, which these
  tests have to cover.
- A name which is not valid UTF-8 cannot be created (exFAT stores
  UTF-16), and FAT32 and exFAT refuse `\ : * ? " < > |`, like
  Windows. Linux may give an error which differs from Windows here.
- There are no permissions: chmod does nothing (the owner and the
  mode come from the mount options), so a file which cannot be read
  cannot be made, and `tests/unreadable` does not work there.
- There are no symbolic links, hard links or named pipes.
- The timestamps are coarse (FAT 2 s, exFAT 10 ms), which matters
  for the item of the modification time above.
- FAT32 cannot have a file of 4 GiB or more.
- The flush of a directory (`fsync_directory()`) has to work or fail
  with EINVAL, which it ignores, and the lock of `.vrfdir/lock` has
  to work or give the warning of a filesystem which cannot lock. Any
  other error of these would stop every command which saves.

How to test it in CI:

- Linux: the Ubuntu runner has sudo, so a job can make an image
  (`truncate -s 512M`, `mkfs.exfat` of exfatprogs, `mkfs.vfat` of
  dosfstools), mount it with `-o loop,uid=$(id -u),gid=$(id -g)` and
  run the tests as the normal user with the data on it. cmdspecs
  takes its data directory from Python's `tempfile`, so
  `TMPDIR=/mnt/exfat` should be enough, check it.
- macOS: `hdiutil create -fs ExFAT` (and `MS-DOS FAT32`) makes and
  `hdiutil attach` mounts an image without root.
- Windows: a VHD made with `New-VHD` or diskpart and formatted as
  exFAT or FAT32 needs an administrator, which the runner user is.
- Many tests cannot pass there by design (names which are bytes,
  symbolic links, chmod), so the tests for these filesystems need a
  selection of their own, for example a `tests/specs-fat/` directory
  with the parts which differ and a list of the tests of
  `tests/specs/` which must also pass there. Decide which.
- The real use, a disk written on one system and read on another,
  could be tested by one job which makes a repository on the image
  and uploads it as an artifact, and a job on another system which
  mounts it and runs status and check. An image for Windows has to be
  a VHD (`qemu-img convert -O vpc`), `Mount-DiskImage` does not
  mount a raw image.

## Ctrl-C: die from SIGINT instead of exit code 130

After Ctrl-C vrfdir cleans up and calls sys.exit(130). For `$?`
that is the same as a program killed by SIGINT (128 + 2), but the
shell can tell the difference: bash stops a script on Ctrl-C only
when the child really died from the signal. So a loop like this
continues with the next directory instead of stopping:

    for d in /data/*; do (cd "$d" && vrfdir check); done

The correct way is to restore the default handler after the cleanup
and send the signal to itself:

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    os.kill(os.getpid(), signal.SIGINT)

This belongs in the KeyboardInterrupt handler of main(), and
cmd_add() has to get there too after it has saved the files. stdout
and stderr have to be flushed first, the signal kills the process
without it.

Windows has no signals like this, os.kill() with SIGINT does not
work there. Keep sys.exit(EXIT_INTERRUPTED) on win32. The help texts
can still say 130, that is what the shell shows.
