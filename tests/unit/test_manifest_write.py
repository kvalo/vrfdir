# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import errno
import json
import os
import stat
import sys

import pytest

SHA256_A = 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'
MD5_A = '0cc175b9c0f1b6a831c399e269772661'


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()

    return tmp_path


def entry(checksum='sha256:' + SHA256_A, size=1):
    return {'checksum': checksum, 'size': size}


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_new_repository_has_no_backup(vrfdir, workdir):
    vrfdir.VrfdirRepo().write()

    assert (workdir / vrfdir.VRFDIR_MANIFEST_PATH).exists()
    assert not (workdir / vrfdir.VRFDIR_BACKUP_PATH).exists()


def test_backup_is_the_previous_file(vrfdir, workdir):
    vrfdir.VrfdirRepo().write()
    before = read(vrfdir.VRFDIR_MANIFEST_PATH)

    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()
    repo.write()

    assert read(vrfdir.VRFDIR_BACKUP_PATH) == before
    assert read(vrfdir.VRFDIR_MANIFEST_PATH) != before


def test_unchanged_repository_keeps_the_backup(vrfdir, workdir):
    vrfdir.VrfdirRepo().write()
    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()
    repo.write()
    backup = read(vrfdir.VRFDIR_BACKUP_PATH)

    vrfdir.VrfdirRepo.open().write()

    assert read(vrfdir.VRFDIR_BACKUP_PATH) == backup


def test_second_write_backs_up_the_first(vrfdir, workdir):
    vrfdir.VrfdirRepo().write()
    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()
    repo.write()
    first = read(vrfdir.VRFDIR_MANIFEST_PATH)

    repo.files['b'] = entry()
    repo.write()

    assert read(vrfdir.VRFDIR_BACKUP_PATH) == first


def test_legacy_backup_is_a_manifest(vrfdir, workdir):
    legacy = '[{"version": 0, "files": {"a": {"md5sum": "%s", ' \
        '"size": 1}}}]\n' % MD5_A
    with open(vrfdir.VRFDIR_LEGACY_PATH, 'w', encoding='utf-8') as f:
        f.write(legacy)

    repo = vrfdir.VrfdirRepo.open()
    repo.files['b'] = entry()
    repo.write()

    assert not (workdir / vrfdir.VRFDIR_LEGACY_PATH).exists()
    assert not (workdir / (vrfdir.VRFDIR_LEGACY_PATH + '.bak')).exists()

    backup = vrfdir.VrfdirRepo(read(vrfdir.VRFDIR_BACKUP_PATH))
    assert backup.version == vrfdir.MANIFEST_VERSION
    assert backup.files == {'a': entry('md5:' + MD5_A)}
    assert json.loads(read(vrfdir.VRFDIR_MANIFEST_PATH))[0]['files'] == {
        'a': entry('md5:' + MD5_A), 'b': entry()}


def test_no_temporary_files_are_left(vrfdir, workdir):
    vrfdir.VrfdirRepo().write()
    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()
    repo.write()

    assert sorted(p.name for p in (workdir / '.vrfdir').iterdir()) == \
        ['manifest.json', 'manifest.json.bak']


# os.pwrite() is not on Windows
@pytest.mark.skipif(sys.platform == 'win32', reason='needs os.pwrite()')
def test_write_which_does_not_read_back_keeps_the_old_file(
        vrfdir, workdir, monkeypatch):
    vrfdir.VrfdirRepo().write()
    before = read(vrfdir.VRFDIR_MANIFEST_PATH)
    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()

    real_fsync = vrfdir.os.fsync

    # the file changes after it was written
    def corrupt(fd):
        vrfdir.os.pwrite(fd, b'X', 0)
        real_fsync(fd)

    monkeypatch.setattr(vrfdir.os, 'fsync', corrupt)

    with pytest.raises(vrfdir.SaveVerifyError):
        repo.write()

    assert read(vrfdir.VRFDIR_MANIFEST_PATH) == before
    assert sorted(p.name for p in (workdir / '.vrfdir').iterdir()) == \
        ['manifest.json']


def test_write_with_a_wrong_checksum_keeps_the_old_file(
        vrfdir, workdir, monkeypatch):
    vrfdir.VrfdirRepo().write()
    before = read(vrfdir.VRFDIR_MANIFEST_PATH)
    repo = vrfdir.VrfdirRepo.open()
    repo.files['a'] = entry()

    # The file is written as it was meant to be, but the checksum in
    # it is not the one of the content, like with a bug in dump_json().
    real_checksum = vrfdir.manifest_checksum
    calls = []

    def first_wrong(version, files):
        calls.append(version)
        checksum = real_checksum(version, files)
        if len(calls) == 1:
            checksum = checksum[:-1] + ('0' if checksum[-1] != '0' else '1')
        return checksum

    monkeypatch.setattr(vrfdir, 'manifest_checksum', first_wrong)

    with pytest.raises(vrfdir.SaveVerifyError):
        repo.write()

    assert read(vrfdir.VRFDIR_MANIFEST_PATH) == before
    assert not (workdir / vrfdir.VRFDIR_MANIFEST_TMP_PATH).exists()


def directory_fsyncs(vrfdir, monkeypatch, error=None):
    real_fsync = vrfdir.os.fsync
    calls = []

    def fsync(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            calls.append(os.fstat(fd).st_ino)
            if error is not None:
                raise OSError(error, os.strerror(error))
        real_fsync(fd)

    monkeypatch.setattr(vrfdir.os, 'fsync', fsync)

    return calls


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX directories')
def test_write_flushes_the_directory(vrfdir, workdir, monkeypatch):
    calls = directory_fsyncs(vrfdir, monkeypatch)

    vrfdir.VrfdirRepo().write()

    assert calls == [os.stat('.vrfdir').st_ino]


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX directories')
def test_directory_which_cannot_be_flushed_is_ignored(vrfdir, workdir,
                                                      monkeypatch):
    calls = directory_fsyncs(vrfdir, monkeypatch, errno.EINVAL)

    vrfdir.VrfdirRepo().write()

    assert len(calls) == 1
    assert (workdir / vrfdir.VRFDIR_MANIFEST_PATH).exists()


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX directories')
def test_directory_flush_error_says_the_file_is_saved(vrfdir, workdir,
                                                      monkeypatch):
    directory_fsyncs(vrfdir, monkeypatch, errno.EIO)

    with pytest.raises(vrfdir.VrfdirError, match='is saved in'):
        vrfdir.VrfdirRepo().write()

    assert vrfdir.VrfdirRepo.open().files == {}
