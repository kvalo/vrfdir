# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse
import logging
import os
import sys

import pytest

MD5_A = 'md5:0cc175b9c0f1b6a831c399e269772661'
SHA256_A = 'sha256:' \
    'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()

    return tmp_path


def make_file(path, content='a'):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)


def make_symlink(target, link):
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip('cannot create symbolic links here')


# A junction is the link to a directory of Windows, Python does not see
# it as a symbolic link.
def make_junction(target, link):
    import _winapi

    _winapi.CreateJunction(os.path.abspath(target), link)


def find(vrfdir, directory='.'):
    unreadable = []
    found = list(vrfdir.VrfdirRepo.find_files(directory, unreadable))

    return found, unreadable


def repo_with(vrfdir, **sizes):
    repo = vrfdir.VrfdirRepo()

    for name, size in sizes.items():
        repo.files[name] = {'checksum': MD5_A, 'size': size}

    repo.update_stats()

    return repo


def test_find_files(vrfdir, workdir):
    make_file('top')
    make_file('dir/a')
    make_file('dir/sub/b')
    make_file('empty-file', '')
    os.mkdir('empty-dir')

    found, unreadable = find(vrfdir)

    assert sorted(found) == ['dir/a', 'dir/sub/b', 'empty-file', 'top']
    assert unreadable == []


def test_find_files_in_a_directory(vrfdir, workdir):
    make_file('top')
    make_file('dir/a')
    make_file('dir/sub/b')

    found, unreadable = find(vrfdir, 'dir')

    assert sorted(found) == ['dir/a', 'dir/sub/b']
    assert unreadable == []


def test_find_files_skips_the_repository(vrfdir, workdir):
    make_file('.vrfdir/manifest.json')
    make_file('.vrfdir/other')
    make_file('x')

    found, unreadable = find(vrfdir)

    assert found == ['x']


def test_find_files_follows_a_link_to_a_file(vrfdir, workdir):
    make_file('target')
    make_symlink('target', 'link')

    found, unreadable = find(vrfdir)

    assert sorted(found) == ['link', 'target']


def test_find_files_does_not_follow_a_link_to_a_directory(vrfdir, workdir):
    make_file('dir/a')
    make_symlink('dir', 'dirlink')

    found, unreadable = find(vrfdir)

    assert found == ['dir/a']


def test_find_files_ignores_a_dangling_link(vrfdir, workdir):
    make_symlink('nothing', 'dangling')
    make_file('x')

    found, unreadable = find(vrfdir)

    assert found == ['x']
    assert unreadable == []


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junctions')
def test_is_junction(vrfdir, workdir):
    os.mkdir('dir')
    make_junction('dir', 'junction')

    assert vrfdir.is_junction('junction')
    assert not vrfdir.is_junction('dir')
    assert not vrfdir.is_junction('missing')

    # also an entry of os.scandir()
    with os.scandir('.') as entries:
        by_name = {entry.name: entry for entry in entries}

    assert vrfdir.is_junction(by_name['junction'])
    assert not vrfdir.is_junction(by_name['dir'])


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows junctions')
def test_find_files_does_not_follow_a_junction(vrfdir, workdir):
    make_file('dir/a')
    make_junction('dir', 'junction')

    found, unreadable = find(vrfdir)

    assert found == ['dir/a']
    assert unreadable == []


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='no named pipes')
def test_find_files_ignores_a_named_pipe(vrfdir, workdir):
    os.mkfifo('pipe')
    make_file('x')

    found, unreadable = find(vrfdir)

    assert found == ['x']


def test_find_files_missing_directory(vrfdir, workdir):
    found, unreadable = find(vrfdir, 'missing')

    assert found == []
    assert len(unreadable) == 1
    assert unreadable[0][0] == 'missing'
    assert unreadable[0][1].startswith(
        'cannot read the directory missing: ')


def test_walk_repository_classifies_the_files(vrfdir, workdir):
    make_file('ok', 'a')
    make_file('size', 'abc')
    make_file('unknown')
    os.mkdir('conflict')
    repo = repo_with(vrfdir, ok=1, size=1, conflict=1, deleted=1)

    (ok, different, conflicted, deleted, unknown,
     unreadable) = repo.walk_repository('.')

    assert ok == ['ok']
    assert different == ['size']
    assert conflicted == ['conflict']
    assert deleted == ['deleted']
    assert unknown == ['unknown']
    assert unreadable == []


def test_walk_repository_does_not_read_the_content(vrfdir, workdir):
    # the same size and another content is not seen, check does that
    make_file('x', 'b')
    repo = repo_with(vrfdir, x=1)

    assert repo.walk_repository('.')[0] == ['x']


def test_walk_repository_foreign_entries_are_deleted(vrfdir, workdir):
    repo = vrfdir.VrfdirRepo()
    repo.foreign['a:b'] = {'checksum': MD5_A, 'size': 1}
    repo.foreign['x\udcffy'] = {'checksum': MD5_A, 'size': 1}

    deleted = repo.walk_repository('.')[3]

    assert deleted == ['a:b', 'x\\xffy']


def test_verify_counts_the_differences(vrfdir, workdir):
    make_file('ok', 'a')
    make_file('size', 'abc')
    make_file('unknown')
    os.mkdir('conflict')
    repo = repo_with(vrfdir, ok=1, size=1, conflict=1, deleted=1)

    errors, unreadable = repo.verify()

    # not the unknown file
    assert errors == 3
    assert unreadable == []


def test_check_finds_the_modified_files(vrfdir, workdir, capsys):
    make_file('good', 'a')
    make_file('bad', 'b')
    repo = repo_with(vrfdir, good=1, bad=1)
    progress = vrfdir.ProgressMeter('Checking', True)

    modified, failed = repo.check(progress)

    assert (modified, failed) == (1, 0)
    assert capsys.readouterr().out == 'M bad\n'


def test_check_reports_what_it_cannot_read(vrfdir, workdir, capsys,
                                           caplog):
    # a directory where a file was added, it cannot be read as a file
    os.mkdir('dir')
    make_file('good', 'a')
    repo = repo_with(vrfdir, dir=1, good=1)
    progress = vrfdir.ProgressMeter('Checking', True)

    modified, failed = repo.check(progress)

    assert (modified, failed) == (0, 1)
    assert capsys.readouterr().out == ''
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    assert caplog.records[0].getMessage().startswith('cannot read dir: ')


def test_check_with_nothing_added(vrfdir, workdir, capsys):
    repo = vrfdir.VrfdirRepo()

    assert repo.check(vrfdir.ProgressMeter('Checking', True)) == (0, 0)
    assert capsys.readouterr().out == ''


def add(vrfdir, repo, *paths):
    progress = vrfdir.ProgressMeter('Adding', True)

    return repo.add_paths(list(paths), progress)


def test_add_paths_adds_files_and_directories(vrfdir, workdir):
    make_file('top', 'a')
    make_file('dir/a', 'abc')
    make_file('dir/sub/b', '')
    repo = vrfdir.VrfdirRepo()

    errors = add(vrfdir, repo, 'top', './dir/')

    assert errors == 0
    assert repo.files == {
        'top': {'checksum': SHA256_A, 'size': 1},
        'dir/a': {'checksum': 'sha256:ba7816bf8f01cfea414140de5dae2223b00361'
                              'a396177a9cb410ff61f20015ad', 'size': 3},
        'dir/sub/b': {'checksum': 'sha256:e3b0c44298fc1c149afbf4c8996fb924'
                                  '27ae41e4649b934ca495991b7852b855',
                      'size': 0},
    }
    assert repo.get_stats()['Files'] == 3
    assert repo.get_stats()['Size'] == 4


def test_add_paths_adds_a_file_once(vrfdir, workdir):
    make_file('x', 'a')
    repo = vrfdir.VrfdirRepo()

    add(vrfdir, repo, 'x', './x', '.')

    assert list(repo.files) == ['x']
    assert repo.get_stats()['Files'] == 1


def test_add_paths_keeps_the_added_files(vrfdir, workdir):
    make_file('x', 'a')
    repo = repo_with(vrfdir, x=1)
    repo.files['x']['checksum'] = 'recorded'

    add(vrfdir, repo, 'x')

    assert repo.files['x']['checksum'] == 'recorded'


def test_add_paths_ignores_a_link_on_the_command_line(vrfdir, workdir):
    make_file('target', 'a')
    make_symlink('target', 'link')
    repo = vrfdir.VrfdirRepo()

    add(vrfdir, repo, 'link')

    assert repo.files == {}


@pytest.mark.parametrize('path, reason', [
    ('', "cannot add '': empty file name"),
    ('..', 'cannot add ..: it is outside of the current directory'),
    ('../x', 'cannot add ../x: it is outside of the current directory'),
    ('/etc/passwd',
     'cannot add /etc/passwd: it is outside of the current directory'),
    ('.vrfdir',
     'cannot add .vrfdir: it is inside .vrfdir, the directory of vrfdir '
     'itself'),
    ('.vrfdir/manifest.json',
     'cannot add .vrfdir/manifest.json: it is inside .vrfdir, the '
     'directory of vrfdir itself'),
    ('missing', 'cannot add missing: it does not exist'),
])
def test_add_paths_refuses(vrfdir, workdir, path, reason):
    repo = vrfdir.VrfdirRepo()

    with pytest.raises(vrfdir.VrfdirError) as e:
        add(vrfdir, repo, path)

    assert str(e.value) == reason
    assert repo.files == {}


@pytest.mark.skipif(not hasattr(os, 'mkfifo'), reason='no named pipes')
def test_add_paths_refuses_a_named_pipe(vrfdir, workdir):
    os.mkfifo('pipe')

    with pytest.raises(vrfdir.VrfdirError) as e:
        add(vrfdir, vrfdir.VrfdirRepo(), 'pipe')

    assert str(e.value) == 'cannot add pipe: it is not a file or a directory'


def test_add_paths_refuses_before_adding_anything(vrfdir, workdir):
    make_file('x', 'a')
    repo = vrfdir.VrfdirRepo()

    with pytest.raises(vrfdir.VrfdirError):
        add(vrfdir, repo, 'x', 'missing')

    assert repo.files == {}


def test_add_paths_reports_an_unreadable_file_and_adds_the_rest(
        vrfdir, workdir, caplog, monkeypatch):
    make_file('bad', 'a')
    make_file('good', 'a')
    repo = vrfdir.VrfdirRepo()
    checksum_file = vrfdir.checksum_file

    def fail_for_bad(name, algorithm):
        if name == 'bad':
            raise PermissionError(13, 'Permission denied', name)

        return checksum_file(name, algorithm)

    monkeypatch.setattr(vrfdir, 'checksum_file', fail_for_bad)

    errors = add(vrfdir, repo, '.')

    assert errors == 1
    assert list(repo.files) == ['good']
    assert [r.getMessage() for r in caplog.records] == [
        'cannot add bad: Permission denied']


def test_write_replaces_hashes_json(vrfdir, workdir):
    repo = repo_with(vrfdir, a=1)
    repo.write()

    repo.files['b'] = {'checksum': MD5_A, 'size': 1}
    repo.write()

    assert sorted(os.listdir('.vrfdir')) == ['manifest.json',
                                             'manifest.json.bak']
    assert sorted(vrfdir.VrfdirRepo.open().files) == ['a', 'b']


def test_failed_write_keeps_the_old_file(vrfdir, workdir, monkeypatch):
    repo = repo_with(vrfdir, a=1)
    repo.write()
    with open('.vrfdir/manifest.json') as f:
        before = f.read()

    def fail(fd):
        raise OSError(28, 'No space left on device')

    monkeypatch.setattr(os, 'fsync', fail)
    repo.files['b'] = {'checksum': MD5_A, 'size': 1}

    with pytest.raises(OSError):
        repo.write()

    # no partial temporary file either
    assert os.listdir('.vrfdir') == ['manifest.json']
    with open('.vrfdir/manifest.json') as f:
        assert f.read() == before


def test_open_warns_about_the_temporary_file(vrfdir, workdir, caplog):
    repo = repo_with(vrfdir, a=1)
    repo.write()
    make_file('.vrfdir/manifest.json.tmp', 'partial')

    opened = vrfdir.VrfdirRepo.open()

    assert list(opened.files) == ['a']
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    assert caplog.records[0].getMessage().startswith(
        '.vrfdir/manifest.json.tmp exists: ')
    # not removed, it can belong to another vrfdir
    assert os.path.exists('.vrfdir/manifest.json.tmp')


def test_open_without_a_repository(vrfdir, workdir):
    os.rmdir('.vrfdir')

    with pytest.raises(FileNotFoundError):
        vrfdir.VrfdirRepo.open()


def test_open_binary_file(vrfdir, workdir):
    with open('.vrfdir/manifest.json', 'wb') as f:
        f.write(b'\xff\xfe\x00')

    with pytest.raises(vrfdir.VrfdirError) as e:
        vrfdir.VrfdirRepo.open()

    assert str(e.value).endswith('is damaged: it is not a text file')


@pytest.mark.parametrize('paths,selected', [
    (['.'], ['a', 'dir/b', 'dir/sub/c', 'gone']),
    (['dir'], ['dir/b', 'dir/sub/c']),
    (['dir/'], ['dir/b', 'dir/sub/c']),
    (['dir/b'], ['dir/b']),
    # a deleted file can be named
    (['gone'], ['gone']),
    (['a', 'dir/sub'], ['a', 'dir/sub/c']),
])
def test_refresh_selection(vrfdir, workdir, paths, selected):
    make_file('a')
    make_file('dir/b')
    make_file('dir/sub/c')
    repo = repo_with(vrfdir, **{'a': 1, 'dir/b': 1, 'dir/sub/c': 1,
                                'gone': 1})

    assert sorted(repo.refresh_selection(paths)) == selected


@pytest.mark.parametrize('path,reason', [
    # only whole names, not the start of one
    ('di', 'it has no added files'),
    ('new', 'it has no added files'),
    ('', 'empty file name'),
    ('../x', 'it is outside of the current directory'),
    ('.vrfdir/manifest.json', 'it is inside .vrfdir'),
])
def test_refresh_selection_refuses(vrfdir, workdir, path, reason):
    make_file('dir/b')
    make_file('new')
    repo = repo_with(vrfdir, **{'dir/b': 1})

    with pytest.raises(vrfdir.VrfdirError) as e:
        repo.refresh_selection(['dir', path])

    assert ': %s' % reason in str(e.value)


def test_rehash_updates_the_entries(vrfdir, workdir, caplog):
    make_file('a')
    make_file('b', 'bb')
    repo = repo_with(vrfdir, a=2, b=1, gone=1)
    updated = []

    failed = repo.rehash(['a', 'gone'], vrfdir.ProgressMeter('', True),
                         updated)

    assert updated == ['a']
    assert failed == 1
    # an MD5 checksum becomes SHA-256
    assert repo.files['a'] == {'checksum': SHA256_A, 'size': 1}
    # the others keep their entries
    assert repo.files['b'] == {'checksum': MD5_A, 'size': 1}
    assert repo.files['gone'] == {'checksum': MD5_A, 'size': 1}
    # a replaced entry is not counted twice
    assert repo.get_stats()['Files'] == 3
    assert repo.get_stats()['Size'] == 3
    # the reason depends on the system
    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage().startswith('cannot refresh gone: ')


def test_refresh_keeps_the_foreign_entries(vrfdir, workdir, monkeypatch):
    # Only Windows has foreign names, here the entry is put in by hand.
    # walk_repository() gives it in the deleted list.
    repo = repo_with(vrfdir, a=1, gone=1)
    repo.foreign['x:y'] = {'checksum': MD5_A, 'size': 1}
    make_file('a')

    monkeypatch.setattr(vrfdir, 'open_repo', lambda locked=False: repo)
    vrfdir.refresh_repo(argparse.Namespace(files=['.'], quiet=True,
                                           dry_run=False))

    assert sorted(repo.files) == ['a']
    assert repo.foreign == {'x:y': {'checksum': MD5_A, 'size': 1}}
    with open('.vrfdir/manifest.json') as f:
        assert '"x:y"' in f.read()
