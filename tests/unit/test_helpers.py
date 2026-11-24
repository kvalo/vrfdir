# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import errno
import hashlib
import os
import sys
import time

import pytest


@pytest.mark.parametrize('size, expected', [
    (0, '0 B'),
    (1023, '1023 B'),
    (1024, '1.0 KiB'),
    (1536, '1.5 KiB'),
    (1024 ** 2, '1.0 MiB'),
    (1024 ** 3, '1.0 GiB'),
    (1024 ** 4, '1.0 TiB'),
    (1024 ** 5, '1.0 PiB'),
    (1024 ** 6, '1024.0 PiB'),
])
def test_bytes2human(vrfdir, size, expected):
    assert vrfdir.bytes2human(size) == expected


@pytest.mark.parametrize('secs, expected', [
    (0, '0:00'),
    (0.9, '0:00'),
    (59, '0:59'),
    (60, '1:00'),
    (3599, '59:59'),
    (3600, '1:00:00'),
    (36000 + 125, '10:02:05'),
])
def test_seconds2human(vrfdir, secs, expected):
    assert vrfdir.seconds2human(secs) == expected


def test_error_reason_is_the_strerror(vrfdir):
    e = OSError(errno.ENOENT, 'No such file or directory', 'some/name')

    assert vrfdir.error_reason(e) == 'No such file or directory'


def test_error_reason_of_a_real_failure(vrfdir, tmp_path):
    with pytest.raises(OSError) as e:
        os.stat(tmp_path / 'missing')

    reason = vrfdir.error_reason(e.value)

    # the text of the operating system, without the error number and
    # the name of str(), on Windows a different text than on POSIX
    assert reason == e.value.strerror
    assert 'missing' not in reason
    assert not reason.startswith('[')


def test_error_reason_without_a_strerror(vrfdir):
    assert vrfdir.error_reason(OSError('something broke')) == \
        'something broke'


@pytest.mark.parametrize('algorithm', ['md5', 'sha256'])
@pytest.mark.parametrize('size', [
    0,
    1,
    1024 * 1024 - 1,
    1024 * 1024,
    5 * 1024 * 1024 + 3,
])
def test_checksum_file(vrfdir, tmp_path, size, algorithm):
    data = bytes(i % 251 for i in range(size))
    path = tmp_path / 'data'
    path.write_bytes(data)

    assert vrfdir.checksum_file(str(path), algorithm) == \
        hashlib.new(algorithm, data).hexdigest()


def test_checksum_file_known_values(vrfdir, tmp_path):
    path = tmp_path / 'data'

    path.write_bytes(b'')
    assert vrfdir.checksum_file(str(path), 'md5') == \
        'd41d8cd98f00b204e9800998ecf8427e'
    assert vrfdir.checksum_file(str(path), 'sha256') == \
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'

    path.write_bytes(b'a')
    assert vrfdir.checksum_file(str(path), 'md5') == \
        '0cc175b9c0f1b6a831c399e269772661'
    assert vrfdir.checksum_file(str(path), 'sha256') == \
        'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'


def test_checksum_file_missing(vrfdir, tmp_path):
    with pytest.raises(FileNotFoundError):
        vrfdir.checksum_file(str(tmp_path / 'missing'), 'sha256')


def test_checksum_file_directory(vrfdir, tmp_path):
    with pytest.raises(OSError):
        vrfdir.checksum_file(str(tmp_path), 'sha256')


def test_split_checksum(vrfdir):
    assert vrfdir.split_checksum('sha256:abc') == ('sha256', 'abc')
    assert vrfdir.split_checksum('md5:abc') == ('md5', 'abc')


def test_is_md5_entry(vrfdir):
    assert vrfdir.is_md5_entry({'checksum': 'md5:abc', 'size': 1})
    assert not vrfdir.is_md5_entry({'checksum': 'sha256:abc', 'size': 1})


def test_replace_file(vrfdir, tmp_path):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.write_text('new')
    dst.write_text('old')

    vrfdir.replace_file(str(src), str(dst))

    assert dst.read_text() == 'new'
    assert not src.exists()


def test_replace_file_missing_source(vrfdir, tmp_path):
    with pytest.raises(FileNotFoundError):
        vrfdir.replace_file(str(tmp_path / 'src'), str(tmp_path / 'dst'))


@pytest.mark.skipif(os.name == 'nt', reason='Windows retries')
def test_replace_file_does_not_retry_on_posix(vrfdir, monkeypatch):
    calls = []

    def replace(src, dst):
        calls.append((src, dst))
        raise PermissionError(errno.EACCES, 'Permission denied')

    monkeypatch.setattr(os, 'replace', replace)

    with pytest.raises(PermissionError):
        vrfdir.replace_file('src', 'dst')

    assert calls == [('src', 'dst')]


# Windows cannot replace a file which another program has open without
# FILE_SHARE_DELETE, and open() of Python does not use it. The file is
# closed during the first wait, so the second try works.
@pytest.mark.skipif(sys.platform != 'win32', reason='Windows retries')
def test_replace_file_retries_while_the_file_is_open(vrfdir, tmp_path,
                                                     monkeypatch):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.write_text('new')
    dst.write_text('old')
    sleeps = []

    with open(dst) as f:
        def sleep(seconds):
            sleeps.append(seconds)
            f.close()

        monkeypatch.setattr(time, 'sleep', sleep)

        vrfdir.replace_file(str(src), str(dst))

    assert sleeps == [vrfdir.REPLACE_RETRY_DELAY]
    assert dst.read_text() == 'new'
    assert not src.exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows retries')
def test_replace_file_gives_up_when_the_file_stays_open(vrfdir, tmp_path,
                                                        monkeypatch):
    src = tmp_path / 'src'
    dst = tmp_path / 'dst'
    src.write_text('new')
    dst.write_text('old')
    sleeps = []

    monkeypatch.setattr(time, 'sleep', sleeps.append)

    with open(dst):
        with pytest.raises(PermissionError):
            vrfdir.replace_file(str(src), str(dst))

    assert len(sleeps) == vrfdir.REPLACE_RETRIES
    assert dst.read_text() == 'old'
    assert src.read_text() == 'new'


def test_environment_info(vrfdir):
    info = vrfdir.environment_info()
    assert [key for (key, _, _) in info] == [
        'vrfdir', 'python', 'system', 'fs_encoding', 'locale_encoding',
        'case_insensitive']
    values = {key: value for (key, _, value) in info}
    assert values['vrfdir'] == vrfdir.version_string()
    assert values['python'].startswith('%d.%d.%d ' % sys.version_info[:3])
    assert values['fs_encoding'].startswith(sys.getfilesystemencoding())
    # nothing personal
    for value in values.values():
        assert os.path.expanduser('~') not in value
