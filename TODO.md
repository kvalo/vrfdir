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

## lock the repository

Nothing prevents two vrfdir processes from changing the same
repository. Two add commands at the same time both read
manifest.json, and the one which writes last drops the files the
other one added. They also share the same manifest.json.tmp name,
and a command started while another one is writing warns about a
stale manifest.json.tmp even though nothing is wrong.

Take a lock (fcntl.flock() on a file in .vrfdir) in the commands
which write: init and add, later refresh and rm. The read-only
commands do not need it as the rename in write() is atomic.

Windows has no fcntl module, there the lock needs
msvcrt.locking().

## smaller issues found in the review

- add ignores a symbolic link given on the command line without
  any message, but a link to a file inside an added directory is
  followed and added. Decide which one is right.

- An old manifest.json can have paths outside of the repository
  ('../x', absolute paths) or inside .vrfdir. add refuses those
  now, but the old entries stay and status shows them as
  conflicts (C). The rm command would solve this.

- No modification time is stored, only size and checksum. A file
  which was edited on purpose and a file which was corrupted look
  the same in check. Related to the refresh item below.

- vrfdir only works in the directory which has .vrfdir, it does
  not look for it in the parent directories like git does.

- check prints "N file(s) deleted or changed, checksums not
  checked" and exits without saying which files. The user has to
  run status to see them, as the message tells.

- scan reports only the files with an invalid name. A directory
  with an invalid name is not reported if it has no files.

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
text of add and test it. tests/specs-linux/case-names.script records
what happens now.

## every time manifest.json is modified, create a backup file

For example: manifest.json.201412241311

If the file already exists, just overwrite it. One backup file per
minute is enough.

Maybe these should be in a separate directory?

## implement 'vrfdir refresh'

The refresh command updates all changes (deletions, checksum
changes etc) in the files to the json list. But does NOT add new
files, those need to be explicitly added with 'vrfdir add'.

maybe should ask for confirmation from the user first?

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
directories as argument.

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
- Where the version comes from. There is `MANIFEST_VERSION` for
  manifest.json but no release version yet, see the versioning item.
- Add the new files to `./lint` and check that the tests still
  pass from a clean install.

## test on the other operating systems

vrfdir has code for Windows and macOS (the '/' separator, names
with a different case, junctions, names which cannot exist on
Windows) but the tests are sh scripts. CI runs the ones which work
on macOS (`./check --portable`) and `./unit` on `macos-latest`, the
rest run only on Linux. So far the code for Windows and the BSDs is
tried only by hand.

Add tests which can run on every system, for example a Python
script which uses only the standard library, and try vrfdir on a
real macOS and BSD machine. The pytest tests in `tests/unit` are
meant for this: they call the functions in the same process and
need no shell, so they can be run on a Windows or macOS runner and
the tests of the code for that system (`skipif` on the real
platform) run there.

Until then, the code which no test reaches on Linux has to be tried by
hand on each system after a change. What to try:

- Windows: init, add and check of a directory with sub directories,
  `vrfdir add dir\sub\file` gives the name `dir/sub/file`, and the
  same manifest.json works on Linux. A repository from Linux with the
  names `a:b`, `con.txt`, `x.` and `back\slash` is kept as it is
  (status shows them as D, add and check do not touch them). A
  junction to a directory is not followed. Replacing manifest.json
  while another program has it open is retried.
- Windows and macOS: `vrfdir add A` for a file `a` adds the name as it
  is on the disk, adding `a` and `A` is one file, and `.VRFDIR` is
  the repository directory and not data.
- macOS: a name which is typed in the other Unicode normalisation form
  is the same file.
- the BSDs: run ./check, and try a symbolic link to a directory and a
  file name which is not valid in the locale.

## ignore the files the operating system creates

macOS creates .DS_Store and Windows creates Thumbs.db and
desktop.ini in the directories. status shows them as not added,
and when they are added they change later and look like
corruption. Needs a way to ignore files, maybe a list of patterns
in .vrfdir.

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

## versioning

vrfdir has no version number, only MANIFEST_VERSION for the format of
manifest.json. Without one a user cannot tell which vrfdir they have
or say it in a bug report.

Choose a version scheme, store the version in the vrfdir file and
show it with 'vrfdir --version'. Tag the releases in git with the
same version.

## detect corruption in manifest.json

vrfdir finds corruption in the added files but nothing protects
manifest.json itself. A change which breaks the JSON is noticed, as
the file cannot be loaded, but a flipped bit inside a checksum, a
size or a name is not. Then check blames the file, which is
intact, and nothing tells that the fault is in manifest.json.

Find a way to detect this, with a checksum of the content or
something else, and verify it every time manifest.json is read. The
error message should say clearly that manifest.json is corrupted, not
the files.

Show the checksum also in the info command.

One idea for the checksum: calculate it from the cmd_list() output
with the list sorted by file name, and maybe move the name to the
first column. Store it in manifest.json and also show it with the
info command.

Related to the backup file item above, a backup is what the user
needs when this happens.
