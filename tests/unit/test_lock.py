# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later
#
# The lock of the repository, RepoLock. Two locks in the same process
# conflict as two processes do, flock() and LockFile() both lock per
# open file, so these work on every system.

import errno
import logging
import os
import subprocess
import sys

import pytest

UNITDIR = os.path.dirname(os.path.abspath(__file__))

# Takes the lock with the code of vrfdir and waits until it is killed,
# without releasing anything itself.
HOLDER = '''
import sys
sys.path.insert(0, sys.argv[1])
import conftest
vrfdir = conftest.load_vrfdir()
lock = vrfdir.RepoLock()
lock.acquire()
assert lock.fd is not None
print('locked', flush=True)
sys.stdin.read()
'''


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()

    return tmp_path


# a lock which is held fails at once and not after the retries
@pytest.fixture
def no_retries(vrfdir, monkeypatch):
    monkeypatch.setattr(vrfdir, 'LOCK_RETRIES', 0)


def assert_held(vrfdir):
    with pytest.raises(vrfdir.VrfdirError,
                       match='another vrfdir is changing it'):
        vrfdir.RepoLock().acquire()


def test_lock_creates_the_lock_file(vrfdir, workdir):
    with vrfdir.RepoLock():
        assert (workdir / vrfdir.VRFDIR_LOCK_PATH).is_file()

    # it stays, only its lock matters
    assert (workdir / vrfdir.VRFDIR_LOCK_PATH).read_bytes() == b''


def test_second_lock_fails(vrfdir, workdir, no_retries):
    with vrfdir.RepoLock():
        assert_held(vrfdir)


def test_lock_is_released_by_exit(vrfdir, workdir, no_retries):
    with vrfdir.RepoLock():
        pass

    with vrfdir.RepoLock():
        assert_held(vrfdir)


def test_lock_is_released_by_an_exception(vrfdir, workdir, no_retries):
    with pytest.raises(SystemExit):
        with vrfdir.RepoLock():
            sys.exit(3)

    with vrfdir.RepoLock() as lock:
        assert lock.fd is not None


def test_lock_retries(vrfdir, workdir, monkeypatch):
    attempts = []

    def held_twice(fd, shared=False):
        attempts.append(fd)
        if len(attempts) <= 2:
            raise vrfdir.LOCK_HELD_ERROR(errno.EAGAIN, 'held')

    monkeypatch.setattr(vrfdir, 'try_lock', held_twice)
    monkeypatch.setattr(vrfdir, 'LOCK_RETRY_DELAY', 0)

    with vrfdir.RepoLock() as lock:
        assert lock.fd is not None

    assert len(attempts) == 3


def test_lock_without_locking_warns(vrfdir, workdir, monkeypatch, caplog):
    def cannot_lock(fd, shared=False):
        raise OSError(errno.ENOLCK, os.strerror(errno.ENOLCK))

    monkeypatch.setattr(vrfdir, 'try_lock', cannot_lock)

    with vrfdir.RepoLock() as lock:
        assert lock.fd is None

    # one warning, __enter__ does not try again
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert caplog.records[0].getMessage().startswith(
        'cannot lock the repository .vrfdir/lock: ')


@pytest.mark.parametrize('kind', ['missing', 'file'])
def test_lock_without_repository_directory(vrfdir, tmp_path, monkeypatch,
                                           kind):
    # open_repo() tells what is wrong, as for the other commands
    monkeypatch.chdir(tmp_path)
    if kind == 'file':
        (tmp_path / '.vrfdir').write_text('foobar')

    with vrfdir.RepoLock() as lock:
        assert lock.fd is None

    assert not os.path.isdir(tmp_path / '.vrfdir')


# with the retries: Windows can take a moment to release the lock of a
# process which has ended, they are for that
def test_lock_of_a_killed_process_is_released(vrfdir, workdir):
    holder = subprocess.Popen([sys.executable, '-B', '-c', HOLDER, UNITDIR],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True)
    try:
        assert holder.stdout.readline() == 'locked\n'
        assert_held(vrfdir)
    finally:
        holder.kill()
        holder.wait()

    with vrfdir.RepoLock() as lock:
        assert lock.fd is not None


def test_writer_active_without_a_lock_file(vrfdir, workdir):
    assert not vrfdir.writer_active()

    # a read never creates the lock file
    assert not (workdir / vrfdir.VRFDIR_LOCK_PATH).exists()


def test_writer_active_while_locked(vrfdir, workdir):
    with vrfdir.RepoLock():
        assert vrfdir.writer_active()

    assert not vrfdir.writer_active()


def test_writer_active_releases_its_lock(vrfdir, workdir, no_retries):
    with vrfdir.RepoLock():
        pass

    assert not vrfdir.writer_active()

    with vrfdir.RepoLock() as lock:
        assert lock.fd is not None


@pytest.mark.parametrize('locked', [False, True])
def test_open_while_another_vrfdir_saves(vrfdir, workdir, caplog, locked):
    # the temporary file of the save which the lock holder does now
    vrfdir.VrfdirRepo().write()
    (workdir / vrfdir.VRFDIR_MANIFEST_TMP_PATH).write_text('garbage')

    with vrfdir.RepoLock():
        vrfdir.VrfdirRepo.open(locked=locked)

    # The holder of the lock itself knows that the file is stale. The
    # other vrfdir, which only reads, does not warn.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == (1 if locked else 0)
