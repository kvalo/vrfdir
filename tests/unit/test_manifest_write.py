# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import json

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
