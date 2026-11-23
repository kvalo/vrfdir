# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys

import pytest


# On Windows the names are not bytes, os.fsdecode() of bytes which are
# not valid UTF-8 fails.
undecodable = pytest.mark.skipif(sys.platform == 'win32',
                                 reason='no undecodable names on Windows')


def surrogate_name(*bad_bytes):
    return os.fsdecode(b'a' + bytes(bad_bytes) + b'b')


@pytest.mark.parametrize('name', [
    'file',
    'dir/file',
    'with space',
    'caf\u00e9',
    '\u65e5\u672c\u8a9e/\u540d\u524d',
    'back\\slash',
    'new\nline',
])
def test_json_name_roundtrip(vrfdir, name):
    assert vrfdir.name_from_json(vrfdir.name_to_json(name)) == name


@undecodable
def test_json_name_roundtrip_invalid_utf8(vrfdir):
    name = surrogate_name(0xff, 0xfe)

    key = vrfdir.name_to_json(name)

    assert vrfdir.name_from_json(key) == name


def test_json_name_is_utf8_bytes(vrfdir):
    # the same key in every locale
    assert vrfdir.name_to_json('caf\u00e9') == 'caf\u00e9'


@undecodable
def test_json_name_of_invalid_utf8(vrfdir):
    assert vrfdir.name_to_json(os.fsdecode(b'a\xffb')) == 'a\udcffb'
    assert vrfdir.name_from_json('a\udcffb') == os.fsdecode(b'a\xffb')


def test_is_valid_name(vrfdir):
    assert vrfdir.is_valid_name('file')
    assert vrfdir.is_valid_name('caf\u00e9')


@undecodable
def test_is_valid_name_undecodable(vrfdir):
    assert not vrfdir.is_valid_name(surrogate_name(0xff))


def test_foreign_name(vrfdir):
    assert vrfdir.foreign_name('plain') == 'plain'
    assert vrfdir.foreign_name('caf\u00e9') == 'caf\u00e9'
    assert vrfdir.foreign_name('a\udcffb') == 'a\\xffb'


def test_name_for_message(vrfdir):
    assert vrfdir.name_for_message('plain') == 'plain'


@undecodable
def test_name_for_message_undecodable(vrfdir):
    assert vrfdir.name_for_message(surrogate_name(0xff)) == 'a\\xffb'


@pytest.mark.parametrize('name', [
    '..',
    '../x',
    '/x',
    '/',
])
def test_is_outside_path(vrfdir, name):
    assert vrfdir.is_outside_path(name)


@pytest.mark.parametrize('name', [
    'x',
    'a/b',
    '..foo',
    'a/..',
    'a/../b',
    '.hidden',
    '.',
])
def test_is_not_outside_path(vrfdir, name):
    assert not vrfdir.is_outside_path(name)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows paths')
@pytest.mark.parametrize('name', ['C:x', 'C:/x', '\\x', '//server/share/x'])
def test_is_outside_path_windows(vrfdir, name):
    # cmd_add() converts the path from the command line first, '\\x'
    # is not an absolute path for os.path.isabs() of every version
    assert vrfdir.is_outside_path(vrfdir.path_to_name(name))


@pytest.mark.parametrize('name', [
    '.vrfdir',
    '.vrfdir/manifest.json',
    '.vrfdir/a/b',
])
def test_is_vrfdir_path(vrfdir, name):
    assert vrfdir.is_vrfdir_path(name)


@pytest.mark.parametrize('name', [
    'x',
    '.vrfdirx',
    '.vrfdir2/x',
    'vrfdir',
    'sub/.vrfdir',
    'sub/.vrfdir/manifest.json',
])
def test_is_not_vrfdir_path(vrfdir, name):
    assert not vrfdir.is_vrfdir_path(name)


@pytest.mark.skipif(not (sys.platform in ('win32', 'darwin')),
                    reason='case-insensitive filesystems')
def test_is_vrfdir_path_case_insensitive(vrfdir):
    assert vrfdir.is_vrfdir_path('.VRFDIR')
    assert vrfdir.is_vrfdir_path('.Vrfdir/manifest.json')


@pytest.mark.skipif(sys.platform in ('win32', 'darwin'),
                    reason='case-sensitive filesystems')
def test_is_vrfdir_path_case_sensitive(vrfdir):
    assert not vrfdir.is_vrfdir_path('.VRFDIR')


@pytest.mark.parametrize('path, name', [
    ('a', 'a'),
    ('./a', 'a'),
    ('a/b', 'a/b'),
    ('a//b', 'a/b'),
    ('a/./b', 'a/b'),
    ('a/b/', 'a/b'),
    ('a/../b', 'b'),
    ('.', '.'),
    ('./', '.'),
    ('../a', '../a'),
])
def test_path_to_name(vrfdir, path, name):
    assert vrfdir.path_to_name(path) == name


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX names')
@pytest.mark.parametrize('name', [
    'a:b',
    'con.txt',
    'x.',
    'x ',
    'back\\slash',
    'a?b',
    'a\x01b',
    'NUL',
])
def test_is_native_name_posix(vrfdir, name):
    assert vrfdir.is_native_name(name)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows names')
@pytest.mark.parametrize('name', [
    'a:b',
    'con.txt',
    'CON',
    'nul .txt',
    'x.',
    'x ',
    'dir/x.',
    'back\\slash',
    'a?b',
    'a*b',
    'a"b',
    'a<b',
    'a\x01b',
    'COM1',
    'dir/aux',
])
def test_is_not_native_name_windows(vrfdir, name):
    assert not vrfdir.is_native_name(name)


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows names')
@pytest.mark.parametrize('name', [
    'file',
    'dir/file.txt',
    '.hidden',
    'dir/../x',
    'console',
    'com10',
    'a b',
])
def test_is_native_name_windows(vrfdir, name):
    assert vrfdir.is_native_name(name)


@pytest.fixture
def tree(tmp_path, monkeypatch):
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'File.txt').write_text('x')
    (tmp_path / 'top').write_text('x')
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_disk_name_exact(vrfdir, tree):
    listings = {}

    assert vrfdir.disk_name('top', listings) == 'top'
    assert vrfdir.disk_name('dir/File.txt', listings) == 'dir/File.txt'


def test_disk_name_current_directory(vrfdir, tree):
    listings = {}

    assert vrfdir.disk_name('.', listings) == '.'
    assert listings == {}


def test_disk_name_missing(vrfdir, tree):
    listings = {}

    assert vrfdir.disk_name('nothing', listings) == 'nothing'
    assert vrfdir.disk_name('dir/nothing', listings) == 'dir/nothing'
    assert vrfdir.disk_name('nodir/x', listings) == 'nodir/x'


def test_disk_name_caches_listings(vrfdir, tree):
    listings = {}

    vrfdir.disk_name('dir/File.txt', listings)

    assert listings['.'] == {'dir', 'top'}
    assert listings['dir'] == {'File.txt'}


def test_disk_name_uses_the_cache(vrfdir, tree):
    # a file which is not in the cache is looked up on the disk
    listings = {'.': {'top'}}

    assert vrfdir.disk_name('top', listings) == 'top'
    assert vrfdir.disk_name('dir', listings) == 'dir'


@pytest.mark.skipif(sys.platform not in ('win32', 'darwin'),
                    reason='case-insensitive filesystems')
def test_disk_name_other_case(vrfdir, tree):
    listings = {}

    assert vrfdir.disk_name('TOP', listings) == 'top'
    assert vrfdir.disk_name('DIR/file.TXT', listings) == 'dir/File.txt'


@pytest.mark.parametrize('name, line', [
    ('file', 'M file'),
    ('back\\slash', 'M back\\slash'),
    ('a\nb', '\\M a\\nb'),
    ('a\rb', '\\M a\\rb'),
    ('a\\\nb', '\\M a\\\\\\nb'),
])
def test_print_named(vrfdir, capsys, name, line):
    vrfdir.print_named('M ', name)

    assert capsys.readouterr().out == line + '\n'


def test_name_for_message_has_one_line(vrfdir):
    assert vrfdir.name_for_message('a\nb\rc') == 'a\\nb\\rc'
