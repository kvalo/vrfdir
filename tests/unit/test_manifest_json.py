# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import json
import os
import random
import sys

import pytest

MD5_EMPTY = 'd41d8cd98f00b204e9800998ecf8427e'
MD5_A = '0cc175b9c0f1b6a831c399e269772661'
SHA256_EMPTY = \
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
SHA256_A = 'ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb'

# A hashes.json of version 0 as a vrfdir before the rename wrote it. It
# has to stay readable.
LEGACY_GOLDEN = (
    '[{"version": 0, "files": {'
    '"empty": {"md5sum": "d41d8cd98f00b204e9800998ecf8427e", "size": 0}, '
    '"dir/a": {"md5sum": "0cc175b9c0f1b6a831c399e269772661", "size": 1}, '
    '"caf\\u00e9": {"md5sum": "0cc175b9c0f1b6a831c399e269772661", '
    '"size": 1}}}]\n')

# A manifest.json of version 1, which has the MD5 checksums without the
# algorithm. It has to stay readable too.
V1_GOLDEN = LEGACY_GOLDEN.replace('"version": 0', '"version": 1')

# What the two are written as now, with the algorithm of the checksum
# and the checksum of the content.
CONVERTED = (
    '[{"version": 3, "checksum": "sha256:'
    'e4423bfca138e07b871c996b512beacc36d4db2769e105cb92858a61e58ac019", '
    '"files": {'
    '"empty": {"checksum": "md5:d41d8cd98f00b204e9800998ecf8427e", '
    '"size": 0}, '
    '"dir/a": {"checksum": "md5:0cc175b9c0f1b6a831c399e269772661", '
    '"size": 1}, '
    '"caf\\u00e9": {"checksum": "md5:0cc175b9c0f1b6a831c399e269772661", '
    '"size": 1}}}]\n')

# A manifest.json of version 2, which has the algorithm in front of the
# checksums but no checksum of its own content.
V2_GOLDEN = (
    '[{"version": 2, "files": {'
    '"empty": {"checksum": "sha256:%s", "size": 0}, '
    '"dir/a": {"checksum": "sha256:%s", "size": 1}, '
    '"caf\\u00e9": {"checksum": "sha256:%s", "size": 1}}}]\n' %
    (SHA256_EMPTY, SHA256_A, SHA256_A))

# A manifest.json written now.
GOLDEN_CHECKSUM = \
    'sha256:198be353462b040b6a42123081d07b0100eca09be7ea0ac5886570de961d33a0'
GOLDEN = V2_GOLDEN.replace(
    '"version": 2,', '"version": 3, "checksum": "%s",' % GOLDEN_CHECKSUM)

# The checksum of a manifest with no files.
EMPTY_CHECKSUM = \
    'sha256:05b7184ec4debc87f91316a7a72cb1708e67bc7c1487857ea4ec8d18bad308a7'

# A checksum of the right form, for the tests of broken entries whose
# checksum cannot be calculated.
ANY_CHECKSUM = 'sha256:' + SHA256_A


# The checksum of the content of manifest.json, calculated here
# separately from vrfdir so that a change of the form is noticed.
def checksum_of(files, version=3):
    h = hashlib.sha256(b'vrfdir manifest %d\n' % version)

    for key in sorted(files, key=lambda k: k.encode('utf-8',
                                                    'surrogateescape')):
        h.update(key.encode('utf-8', 'surrogateescape') + b'\0' +
                 files[key]['checksum'].encode('ascii') + b'\0' +
                 b'%d\0' % files[key]['size'])

    return 'sha256:' + h.hexdigest()


# Version 3 and later have the checksum of the files, the older ones not.
def make_json(files, version=3, checksum=None):
    a = {'version': version}

    if version >= 3:
        a['checksum'] = checksum or checksum_of(files, version)

    a['files'] = files

    return json.dumps([a])


def entry(checksum='sha256:' + SHA256_A, size=1):
    return {'checksum': checksum, 'size': size}


def load(vrfdir, buf):
    return vrfdir.VrfdirRepo(buf)


def test_empty_repo(vrfdir):
    repo = vrfdir.VrfdirRepo()

    assert repo.version == vrfdir.MANIFEST_VERSION
    assert repo.files == {}
    assert repo.foreign == {}
    assert repo.get_stats() == {'Files': 0, 'Size': 0, 'FileVersion': 3,
                                'Foreign': 0}
    assert repo.get_details() == {'Md5': 0, 'Largest': []}
    assert repo.checksum is None


def test_dump_empty_repo(vrfdir):
    repo = vrfdir.VrfdirRepo()

    assert repo.dump_json() == \
        '[{"version": 3, "checksum": "%s", "files": {}}]\n' % EMPTY_CHECKSUM
    assert repo.checksum == EMPTY_CHECKSUM


def test_manifest_version(vrfdir):
    # a change needs a version bump and a migration, see CLAUDE.md
    assert vrfdir.MANIFEST_VERSION == 3
    assert vrfdir.CHECKSUMMED_MANIFEST_VERSION == 3
    assert vrfdir.ALGORITHM_MANIFEST_VERSION == 2
    assert vrfdir.MD5_MANIFEST_VERSION == 1
    assert vrfdir.LEGACY_VERSION == 0


def test_golden_file_loads(vrfdir):
    repo = load(vrfdir, GOLDEN)

    assert repo.files == {
        'empty': entry('sha256:' + SHA256_EMPTY, 0),
        'dir/a': entry(),
        'café': entry(),
    }
    assert repo.foreign == {}
    assert repo.checksum == GOLDEN_CHECKSUM
    assert repo.get_stats() == {'Files': 3, 'Size': 2, 'FileVersion': 3,
                                'Foreign': 0}
    assert repo.get_details() == {'Md5': 0,
                                  'Largest': [(1, 'café'), (1, 'dir/a'),
                                              (0, 'empty')]}


def test_golden_file_is_written_as_it_was(vrfdir):
    assert load(vrfdir, GOLDEN).dump_json() == GOLDEN


def test_checksum_of_the_golden_file(vrfdir):
    files = json.loads(GOLDEN)[0]['files']

    assert vrfdir.manifest_checksum(3, files) == GOLDEN_CHECKSUM
    assert checksum_of(files) == GOLDEN_CHECKSUM


def test_version_2_golden_file_loads_without_checksum(vrfdir):
    repo = load(vrfdir, V2_GOLDEN)

    assert repo.version == 2
    assert repo.checksum is None
    assert repo.files == load(vrfdir, GOLDEN).files

    # the conversion happens in write()
    repo.version = vrfdir.MANIFEST_VERSION
    assert repo.dump_json() == GOLDEN
    assert repo.checksum == GOLDEN_CHECKSUM


GOLDEN_SIZE_A = '"dir/a": {"checksum": "sha256:%s", "size": 1}' % SHA256_A


# A flipped bit or another change in the content which still is a valid
# manifest.json.
@pytest.mark.parametrize('old, new', [
    # a digit of the checksum of a file
    (SHA256_EMPTY, SHA256_EMPTY[:-1] + '4'),
    # the size of a file
    (GOLDEN_SIZE_A, GOLDEN_SIZE_A.replace('"size": 1', '"size": 3')),
    # a letter of the name
    ('"dir/a"', '"dir/c"'),
    # the name of an entry is the same as of the other one, so only the
    # last of them is read
    ('"dir/a"', '"empty"'),
    # an entry is removed
    (GOLDEN_SIZE_A + ', ', ''),
    # an entry is added
    ('"files": {', '"files": {"new": {"checksum": "sha256:%s", '
     '"size": 0}, ' % SHA256_EMPTY),
    # the checksum of the manifest itself
    (GOLDEN_CHECKSUM, GOLDEN_CHECKSUM[:-1] + '1'),
])
def test_checksum_mismatch(vrfdir, old, new):
    buf = GOLDEN.replace(old, new, 1)
    assert buf != GOLDEN

    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, buf)

    assert str(e.value) == (
        'the repository .vrfdir/manifest.json is damaged: its content '
        'does not match its checksum. The checksums of the files cannot be '
        'trusted, restore .vrfdir/manifest.json from a backup')


@pytest.mark.parametrize('checksum, reason', [
    (None, 'the checksum of the repository is missing'),
    (1, 'invalid checksum of the repository'),
    ('', 'invalid checksum of the repository'),
    (GOLDEN_CHECKSUM.upper(), 'invalid checksum of the repository'),
    (GOLDEN_CHECKSUM[7:], 'invalid checksum of the repository'),
    ('md5:' + MD5_A, 'invalid checksum of the repository'),
    (GOLDEN_CHECKSUM + '\n', 'invalid checksum of the repository'),
])
def test_invalid_checksum_of_the_manifest(vrfdir, checksum, reason):
    j = json.loads(GOLDEN)
    if checksum is None:
        del j[0]['checksum']
    else:
        j[0]['checksum'] = checksum

    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, json.dumps(j))

    assert str(e.value) == \
        'the repository .vrfdir/manifest.json is damaged: %s' % reason


# An older version never had the checksum, so the version has changed.
@pytest.mark.parametrize('version', [1, 2])
def test_checksum_in_an_older_version(vrfdir, version):
    buf = GOLDEN.replace('"version": 3', '"version": %d' % version)

    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, buf)

    assert str(e.value).endswith('is damaged: invalid version %d' % version)


def test_checksum_does_not_depend_on_the_formatting(vrfdir):
    j = json.loads(GOLDEN)
    j[0]['files'] = dict(reversed(list(j[0]['files'].items())))

    repo = load(vrfdir, json.dumps(j, indent=4, ensure_ascii=False))

    assert repo.files == load(vrfdir, GOLDEN).files


def test_checksum_covers_the_foreign_entries(vrfdir):
    repo = vrfdir.VrfdirRepo()
    repo.files['a'] = entry()
    repo.foreign['x\udcffy'] = entry()

    j = json.loads(repo.dump_json())
    assert j[0]['checksum'] == checksum_of({'a': entry(),
                                            'x\udcffy': entry()})

    j[0]['files']['x\udcffy']['size'] = 2
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, json.dumps(j))

    assert 'does not match its checksum' in str(e.value)


# A NUL separates the fields, so moving a character from the name to the
# next field or from an entry to the next one changes the checksum.
def test_checksum_of_similar_content_differs(vrfdir):
    similar = [{'a\nb': entry(size=1)},
               {'a\nb': entry(size=11)},
               {'a': entry(size=1), 'b': entry(size=1)},
               {'a': entry(size=11)},
               {'a': entry(size=1), 'a/b': entry(size=1)}]

    checksums = [vrfdir.manifest_checksum(3, f) for f in similar]

    assert len(set(checksums)) == len(similar)
    assert checksums == [checksum_of(f) for f in similar]


def test_dump_is_ascii(vrfdir):
    repo = load(vrfdir, make_json({'café': entry(),
                                   'a\udcffb': entry()}))

    repo.dump_json().encode('ascii')


@pytest.mark.parametrize('buf, reason', [
    ('', 'it is empty'),
    ('  \n', 'it is empty'),
    ('{', 'it is not valid JSON (line 1, column 2)'),
    ('[{"version": 1,\n "files": }]', 'it is not valid JSON (line 2'),
    ('[' * 100000, 'it is not valid JSON'),
    ('null', 'the version or the list of the files is missing'),
    ('[]', 'the version or the list of the files is missing'),
    ('{}', 'the version or the list of the files is missing'),
    ('[[]]', 'the version or the list of the files is missing'),
    ('[{}]', 'the version or the list of the files is missing'),
    ('[{"version": 1}]', 'the version or the list of the files is missing'),
    ('[{"files": {}}]', 'the version or the list of the files is missing'),
    ('[{"version": 1, "files": []}]',
     'the version or the list of the files is missing'),
    ('[{"version": 1, "files": null}]',
     'the version or the list of the files is missing'),
    ('[{"version": true, "files": {}}]', 'invalid version True'),
    ('[{"version": 1.0, "files": {}}]', 'invalid version 1.0'),
    ('[{"version": -1, "files": {}}]', 'invalid version -1'),
    ('[{"version": "0", "files": {}}]', "invalid version '0'"),
    ('[{"version": null, "files": {}}]', 'invalid version None'),
])
def test_damaged(vrfdir, buf, reason):
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, buf)

    assert str(e.value).startswith(
        'the repository .vrfdir/manifest.json is damaged: ')
    assert reason in str(e.value)


def test_legacy_golden_file_loads(vrfdir):
    repo = vrfdir.VrfdirRepo(LEGACY_GOLDEN, legacy=True)

    assert repo.legacy
    assert repo.path == vrfdir.VRFDIR_LEGACY_PATH
    assert repo.version == 0
    assert repo.get_stats()['FileVersion'] == 0
    assert sorted(repo.files) == ['café', 'dir/a', 'empty']

    # the conversion happens in write()
    repo.version = vrfdir.MANIFEST_VERSION
    assert repo.dump_json() == CONVERTED


def test_version_1_golden_file_loads_as_md5(vrfdir):
    repo = load(vrfdir, V1_GOLDEN)

    assert not repo.legacy
    assert repo.version == 1
    assert repo.files == {
        'empty': entry('md5:' + MD5_EMPTY, 0),
        'dir/a': entry('md5:' + MD5_A),
        'café': entry('md5:' + MD5_A),
    }

    # the conversion happens in write()
    repo.version = vrfdir.MANIFEST_VERSION
    assert repo.dump_json() == CONVERTED


def test_version_1_entries_keep_the_other_fields(vrfdir):
    buf = make_json({'x': {'md5sum': MD5_A, 'size': 1, 'other': 2}},
                    version=1)
    repo = load(vrfdir, buf)

    # the other fields stay and 'checksum' is the first one
    assert list(repo.files['x'].items()) == [
        ('checksum', 'md5:' + MD5_A), ('size', 1), ('other', 2)]


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows names')
def test_version_1_foreign_entries_are_converted(vrfdir):
    buf = make_json({'a:b': {'md5sum': MD5_A, 'size': 1}}, version=1)

    repo = load(vrfdir, buf)

    assert repo.files == {}
    assert repo.foreign == {'a:b': entry('md5:' + MD5_A)}


def test_legacy_only_accepts_its_version(vrfdir):
    with pytest.raises(vrfdir.VrfdirError) as e:
        vrfdir.VrfdirRepo(V1_GOLDEN, legacy=True)

    assert 'the repository .vrfdir/hashes.json has format version 1' \
        in str(e.value)
    assert 'knows only version 0' in str(e.value)


def test_manifest_does_not_accept_the_legacy_version(vrfdir):
    with pytest.raises(vrfdir.VrfdirError) as e:
        vrfdir.VrfdirRepo(LEGACY_GOLDEN)

    assert 'the repository .vrfdir/manifest.json is damaged: ' \
        'invalid version 0' in str(e.value)


def test_legacy_damaged_names_the_old_file(vrfdir):
    with pytest.raises(vrfdir.VrfdirError) as e:
        vrfdir.VrfdirRepo('', legacy=True)

    assert str(e.value) == \
        'the repository .vrfdir/hashes.json is damaged: it is empty'


def test_newer_version(vrfdir):
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, make_json({}, version=4))

    # not damaged, it is the file of a newer vrfdir
    assert 'damaged' not in str(e.value)
    assert 'has format version 4' in str(e.value)
    assert 'knows only version 3' in str(e.value)


@pytest.mark.parametrize('key', ['', 'a\0b', '\0'])
def test_invalid_name(vrfdir, key):
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, make_json({key: entry()}))

    assert 'is damaged: invalid file name' in str(e.value)


@pytest.mark.parametrize('value', [
    None,
    [],
    'abc',
    {},
    {'checksum': 'md5:' + MD5_A},
    {'size': 1},
    {'checksum': None, 'size': 1},
    {'checksum': 1, 'size': 1},
    {'checksum': 'md5:' + MD5_A, 'size': None},
    {'checksum': 'md5:' + MD5_A, 'size': '1'},
    {'checksum': 'md5:' + MD5_A, 'size': 1.0},
    {'checksum': 'md5:' + MD5_A, 'size': True},
    {'checksum': 'md5:' + MD5_A, 'size': -1},
    # the key of version 1
    {'md5sum': MD5_A, 'size': 1},
])
def test_invalid_entry(vrfdir, value):
    # the entries are checked before the checksum
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, make_json({'file': value}, checksum=ANY_CHECKSUM))

    assert str(e.value).endswith('is damaged: invalid checksum or size '
                                 'of file')


@pytest.mark.parametrize('checksum', [
    '',
    MD5_A,
    SHA256_A,
    'md5:',
    'md5:' + MD5_A[:-1],
    'md5:' + MD5_A + '0',
    'md5:' + SHA256_A,
    'sha256:' + MD5_A,
    'sha256:' + SHA256_A.upper(),
    'sha256:' + SHA256_A[:-1] + 'g',
    'sha1:' + SHA256_A[:40],
    'MD5:' + MD5_A,
    ' md5:' + MD5_A,
    'md5:' + MD5_A + '\n',
    '\\sha256:' + SHA256_A,
])
def test_invalid_checksum(vrfdir, checksum):
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, make_json({'file': entry(checksum)}))

    assert str(e.value).endswith('is damaged: invalid checksum of file')


@pytest.mark.parametrize('checksum', ['md5:' + MD5_A, 'sha256:' + SHA256_A])
def test_valid_checksum(vrfdir, checksum):
    repo = load(vrfdir, make_json({'file': entry(checksum)}))

    assert repo.files['file']['checksum'] == checksum


def test_invalid_checksum_of_version_1(vrfdir):
    for md5sum in ['abc', MD5_A[:-1], MD5_A.upper()]:
        with pytest.raises(vrfdir.VrfdirError) as e:
            load(vrfdir, make_json(
                {'file': {'md5sum': md5sum, 'size': 1}}, version=1))

        assert str(e.value).endswith('is damaged: invalid checksum of file')


def test_invalid_entry_message_shows_the_name_safely(vrfdir):
    with pytest.raises(vrfdir.VrfdirError) as e:
        load(vrfdir, make_json({'a\udcffb': {}}, checksum=ANY_CHECKSUM))

    assert str(e.value).endswith('of a\\xffb')


@pytest.mark.parametrize('stored', [
    '\\' + MD5_A,
    '\\\\' + MD5_A,
])
def test_leading_backslash_of_old_versions_is_removed(vrfdir, stored):
    repo = load(vrfdir, make_json({'a\\b': {'md5sum': stored, 'size': 1}},
                                  version=1))

    assert repo.files['a\\b']['checksum'] == 'md5:' + MD5_A


def test_entries_keep_the_other_fields(vrfdir):
    value = entry()
    value['other'] = 'kept'

    repo = load(vrfdir, make_json({'file': value}))

    assert repo.files['file'] == value


def test_names_are_converted(vrfdir):
    bad = os.fsdecode(b'a\xffb')

    repo = load(vrfdir, make_json({'a\udcffb': entry()}))

    assert list(repo.files) == [bad]
    assert json.loads(repo.dump_json())[0]['files'] == {'a\udcffb': entry()}


def test_stats(vrfdir):
    repo = load(vrfdir, make_json({'a': entry(size=10),
                                   'b': entry(size=5),
                                   'c': entry('md5:' + MD5_EMPTY, 0)}))

    assert repo.get_stats() == {'Files': 3, 'Size': 15, 'FileVersion': 3,
                                'Foreign': 0}
    assert repo.get_details() == {
        'Md5': 1, 'Largest': [(10, 'a'), (5, 'b'), (0, 'c')]}


def test_stats_count_the_foreign_entries(vrfdir):
    repo = vrfdir.VrfdirRepo()
    repo.files['a'] = entry(size=10)
    repo.foreign['x:y'] = entry(size=5)

    repo.update_stats()

    assert repo.get_stats() == {'Files': 2, 'Size': 15, 'FileVersion': 3,
                                'Foreign': 1}
    assert repo.get_details() == {'Md5': 0, 'Largest': [(10, 'a')]}


def test_entries_list_the_foreign_ones_too(vrfdir):
    repo = vrfdir.VrfdirRepo()
    repo.files['a'] = entry()
    repo.foreign['x\udcffy'] = entry('md5:' + MD5_EMPTY, 0)

    assert list(repo.entries()) == [('a', entry()),
                                    ('x\\xffy', entry('md5:' + MD5_EMPTY, 0))]


def test_foreign_entries_are_written_back(vrfdir):
    repo = vrfdir.VrfdirRepo()
    repo.files['a'] = entry()
    repo.foreign['a:b'] = entry()
    repo.foreign['con.txt'] = entry()

    files = json.loads(repo.dump_json())[0]['files']

    assert files == {'a': entry(), 'a:b': entry(), 'con.txt': entry()}


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows names')
@pytest.mark.parametrize('key', ['a:b', 'con.txt', 'x.', 'back\\slash'])
def test_foreign_names_on_windows(vrfdir, key):
    repo = load(vrfdir, make_json({key: entry()}))

    assert repo.files == {}
    assert key in repo.foreign
    assert json.loads(repo.dump_json())[0]['files'] == {key: entry()}


@pytest.mark.skipif(sys.platform == 'win32', reason='POSIX names')
@pytest.mark.parametrize('key', ['a:b', 'con.txt', 'x.', 'back\\slash'])
def test_native_names_on_posix(vrfdir, key):
    repo = load(vrfdir, make_json({key: entry()}))

    assert key in repo.files
    assert repo.foreign == {}


def random_name(rnd):
    alphabet = ['a', 'b', 'Z', '0', ' ', '.', '-', '\\', '\n', 'café',
                '日', '\U0001f600', '\udcff', '\udc80']
    parts = []

    for _ in range(rnd.randint(1, 3)):
        part = ''.join(rnd.choice(alphabet)
                       for _ in range(rnd.randint(1, 6)))
        # these are never a name
        if part in ('.', '..'):
            part = 'x' + part
        parts.append(part)

    return '/'.join(parts)


def random_json(rnd):
    files = {}

    for _ in range(rnd.randint(0, 20)):
        if rnd.random() < 0.5:
            checksum = 'sha256:%064x' % rnd.getrandbits(256)
        else:
            checksum = 'md5:%032x' % rnd.getrandbits(128)

        files[random_name(rnd)] = entry(
            checksum, rnd.choice([0, 1, 2 ** 40]))

    return make_json(files)


def test_dump_of_a_load_is_the_same_data(vrfdir):
    rnd = random.Random(20260101)

    for _ in range(200):
        buf = random_json(rnd)

        repo = load(vrfdir, buf)
        dumped = repo.dump_json()

        assert dumped.endswith('\n')
        dumped.encode('ascii')
        assert json.loads(dumped) == json.loads(buf)

        # and the same again from the written file
        assert load(vrfdir, dumped).dump_json() == dumped


def test_write_and_open(vrfdir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()
    repo = vrfdir.VrfdirRepo()
    repo.files['a'] = entry()
    repo.files['café'] = entry('md5:' + MD5_EMPTY, 0)

    repo.write()
    opened = vrfdir.VrfdirRepo.open()

    assert opened.files == repo.files
    assert sorted(os.listdir('.vrfdir')) == ['manifest.json']


def test_open_reads_the_legacy_file_and_write_converts_it(
        vrfdir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()
    (tmp_path / '.vrfdir' / 'hashes.json').write_text(LEGACY_GOLDEN)

    repo = vrfdir.VrfdirRepo.open()

    assert repo.legacy
    assert sorted(repo.files) == ['café', 'dir/a', 'empty']
    # reading changes nothing
    assert os.listdir('.vrfdir') == ['hashes.json']

    repo.write()

    # the backup is the old file converted, the content is the same
    assert sorted(os.listdir('.vrfdir')) == ['manifest.json',
                                             'manifest.json.bak']
    with open('.vrfdir/manifest.json') as f:
        assert f.read() == CONVERTED
    with open('.vrfdir/manifest.json.bak') as f:
        assert f.read() == CONVERTED

    again = vrfdir.VrfdirRepo.open()
    assert not again.legacy
    assert again.files == repo.files


def test_open_prefers_manifest_json(vrfdir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.vrfdir').mkdir()
    (tmp_path / '.vrfdir' / 'hashes.json').write_text(LEGACY_GOLDEN)
    (tmp_path / '.vrfdir' / 'manifest.json').write_text(make_json({}))

    assert vrfdir.VrfdirRepo.open().files == {}
