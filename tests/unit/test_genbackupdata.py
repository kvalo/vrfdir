# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import argparse

import pytest


class TestParseSize:

    @pytest.mark.parametrize('text, expected', [
        ('1', 1),
        ('512', 512),
        ('1k', 1024),
        ('1K', 1024),
        ('2m', 2 * 1024 ** 2),
        ('2M', 2 * 1024 ** 2),
        ('3g', 3 * 1024 ** 3),
        ('3G', 3 * 1024 ** 3),
        ('007', 7),
    ])
    def test_valid(self, genbackupdata, text, expected):
        assert genbackupdata.parse_size(text) == expected

    @pytest.mark.parametrize('text', [
        '', 'k', '1x', '1.5M', '1kB', '1_000', '+5', '-5', ' 5', '5 ',
        '1 k', '0x10',
        # Arabic-Indic digit, int() would accept it
        '١',
        # a digit of another script with a suffix
        '١k',
    ])
    def test_invalid(self, genbackupdata, text):
        with pytest.raises(argparse.ArgumentTypeError,
                           match='invalid size'):
            genbackupdata.parse_size(text)

    @pytest.mark.parametrize('text', ['0', '0k', '000'])
    def test_zero(self, genbackupdata, text):
        with pytest.raises(argparse.ArgumentTypeError,
                           match='must be positive'):
            genbackupdata.parse_size(text)

    def test_too_many_digits(self, genbackupdata):
        # more digits than int() converts, with the default limit of
        # 4300 digits
        with pytest.raises(argparse.ArgumentTypeError,
                           match='invalid size'):
            genbackupdata.parse_size('1' * 5000)


class TestSeededInt:

    def test_range(self, genbackupdata):
        values = {genbackupdata.seeded_int(5, 9, f'seed{i}')
                  for i in range(200)}
        assert values <= set(range(5, 10))
        # 200 seeds hit every value of such a small range
        assert values == set(range(5, 10))

    def test_single_value(self, genbackupdata):
        assert genbackupdata.seeded_int(7, 7, 'any') == 7

    def test_deterministic(self, genbackupdata):
        assert (genbackupdata.seeded_int(0, 10 ** 9, 'seed') ==
                genbackupdata.seeded_int(0, 10 ** 9, 'seed'))

    def test_seed_matters(self, genbackupdata):
        values = {genbackupdata.seeded_int(0, 10 ** 9, f'seed{i}')
                  for i in range(20)}
        assert len(values) > 1

    # Pins the algorithm (sha256 of the seed), the output of the
    # generator depends on it. The value is what sha256 of 'seed'
    # gives, it must not change with a Python version.
    def test_pinned(self, genbackupdata):
        digest = ('19b25856e1c150ca834cffc8b59b23adbd0ec0389e58eb22b3b6'
                  '4768098d002b')
        assert (genbackupdata.seeded_int(0, 999, 'seed') ==
                int(digest, 16) % 1000)


class TestFileSizeLimits:

    @pytest.mark.parametrize('total, expected', [
        (1, 1024),
        (1024 ** 2 - 1, 1024),
        (1024 ** 2, 64 * 1024),
        (10 * 1024 ** 2 - 1, 64 * 1024),
        (10 * 1024 ** 2, 128 * 1024),
        (100 * 1024 ** 2 - 1, 128 * 1024),
        (100 * 1024 ** 2, 512 * 1024),
        (1024 ** 3 - 1, 512 * 1024),
        (1024 ** 3, 1024 ** 2),
    ])
    def test_min_file_size_boundaries(self, genbackupdata, total,
                                      expected):
        assert genbackupdata.calculate_min_file_size(total) == expected

    @pytest.mark.parametrize('total', [
        1, 2, 100, 511, 512, 1024, 4096, 1024 ** 2, 9 * 1024 ** 2,
        100 * 1024 ** 2, 1024 ** 3, 4 * 1024 ** 3, 1024 ** 4,
    ])
    def test_limits_are_sane(self, genbackupdata, total):
        low, high = genbackupdata.file_size_limits(total)
        assert 1 <= low <= high <= genbackupdata.MAX_FILE_SIZE

    def test_tiny_total_has_one_byte_files(self, genbackupdata):
        assert genbackupdata.file_size_limits(1) == (1, 1)

    def test_max_is_capped(self, genbackupdata):
        low, high = genbackupdata.file_size_limits(1024 ** 4)
        assert high == genbackupdata.MAX_FILE_SIZE


class TestGenerateFileData:

    def test_size_and_chunks(self, genbackupdata):
        chunk = genbackupdata.CHUNK_SIZE
        size = 2 * chunk + 5
        chunks = list(genbackupdata.generate_file_data(size, 'seed'))
        assert [len(c) for c in chunks] == [chunk, chunk, 5]

    def test_empty(self, genbackupdata):
        assert list(genbackupdata.generate_file_data(0, 'seed')) == []

    def test_deterministic(self, genbackupdata):
        a = b''.join(genbackupdata.generate_file_data(1000, 'seed'))
        b = b''.join(genbackupdata.generate_file_data(1000, 'seed'))
        assert a == b

    def test_seed_matters(self, genbackupdata):
        a = b''.join(genbackupdata.generate_file_data(1000, 'seed1'))
        b = b''.join(genbackupdata.generate_file_data(1000, 'seed2'))
        assert a != b


class TestCreateTestData:

    @pytest.mark.parametrize('size', [
        1, 2, 511, 512, 513, 1024, 5000, 64 * 1024, 1024 ** 2,
        1024 ** 2 + 1, 3 * 1024 ** 2,
    ])
    def test_total_size(self, genbackupdata, tmp_path, size):
        target = tmp_path / 'data'
        gen = genbackupdata.create_test_data(target, size, quiet=True)

        total = sum(p.stat().st_size for p in target.rglob('*')
                    if p.is_file())
        assert total == size
        assert gen.bytes_created == size
        assert gen.file_count == sum(1 for p in target.rglob('*')
                                     if p.is_file())
        assert gen.dir_count == sum(1 for p in target.rglob('*')
                                    if p.is_dir())

    def test_file_names_are_numbered(self, genbackupdata, tmp_path):
        target = tmp_path / 'data'
        gen = genbackupdata.create_test_data(target, 2 * 1024 ** 2,
                                             quiet=True)

        names = sorted(p.name for p in target.rglob('file*'))
        assert names == [f'file{i:08d}'
                         for i in range(1, gen.file_count + 1)]

    def test_makes_directories(self, genbackupdata, tmp_path):
        gen = genbackupdata.create_test_data(tmp_path / 'data',
                                             2 * 1024 ** 2, quiet=True)
        assert gen.dir_count > 0

    def test_file_size_limits(self, genbackupdata, tmp_path):
        size = 3 * 1024 ** 2
        target = tmp_path / 'data'
        genbackupdata.create_test_data(target, size, quiet=True)

        _, high = genbackupdata.file_size_limits(size)
        assert all(p.stat().st_size <= high
                   for p in target.rglob('file*'))

    def test_same_content_in_any_directory(self, genbackupdata,
                                           tmp_path):
        a = tmp_path / 'a'
        b = tmp_path / 'deeper' / 'name' / 'b'
        genbackupdata.create_test_data(a, 1024 ** 2, quiet=True)
        genbackupdata.create_test_data(b, 1024 ** 2, quiet=True)

        files_a = sorted(p.relative_to(a) for p in a.rglob('*'))
        files_b = sorted(p.relative_to(b) for p in b.rglob('*'))
        assert files_a == files_b
        for name in files_a:
            if (a / name).is_file():
                assert (a / name).read_bytes() == (b / name).read_bytes()

    def test_existing_empty_directory(self, genbackupdata, tmp_path):
        target = tmp_path / 'data'
        target.mkdir()
        genbackupdata.create_test_data(target, 1024, quiet=True)
        assert any(target.iterdir())

    def test_not_empty_directory(self, genbackupdata, tmp_path):
        (tmp_path / 'old').write_text('x')
        with pytest.raises(genbackupdata.GenError, match='is not empty'):
            genbackupdata.create_test_data(tmp_path, 1024, quiet=True)

    def test_target_is_a_file(self, genbackupdata, tmp_path):
        target = tmp_path / 'file'
        target.write_text('x')
        with pytest.raises(genbackupdata.GenError,
                           match='cannot create directory'):
            genbackupdata.create_test_data(target, 1024, quiet=True)

    def test_quiet_prints_nothing(self, genbackupdata, tmp_path,
                                  capsys):
        genbackupdata.create_test_data(tmp_path / 'q', 1024, quiet=True)
        assert capsys.readouterr().out == ''

    def test_not_quiet_prints_created(self, genbackupdata, tmp_path,
                                      capsys):
        genbackupdata.create_test_data(tmp_path / 'v', 1024,
                                       quiet=False)
        out = capsys.readouterr().out
        assert out.startswith('Created file file00000001 (')
