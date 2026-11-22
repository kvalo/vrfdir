# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest


@pytest.fixture
def clock(vrfdir, monkeypatch):
    class Clock:
        now = 1000.0

    monkeypatch.setattr(vrfdir.time, 'monotonic', lambda: Clock.now)

    return Clock


def meter(vrfdir, quiet=False):
    return vrfdir.ProgressMeter('Checking', quiet)


def test_first_update_prints(vrfdir, clock, capsys):
    meter(vrfdir).update(1, 4, 5, 20)

    assert capsys.readouterr().out == \
        '\rChecking: 25% (1/4 files, 5 B of 20 B) '


def test_update_is_throttled(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(1, 4, 5, 20)
    capsys.readouterr()

    clock.now += vrfdir.PROGRESS_INTERVAL - 0.1
    m.update(2, 4, 10, 20)
    assert capsys.readouterr().out == ''

    clock.now += 0.1
    m.update(3, 4, 15, 20)
    assert capsys.readouterr().out == \
        '\rChecking: 75% (3/4 files, 15 B of 20 B, 15 B/s, 0:00 left) '


def test_done_always_prints_and_ends_the_line(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(1, 4, 5, 20)
    capsys.readouterr()

    m.update(4, 4, 20, 20, done=True)

    assert capsys.readouterr().out == \
        '\rChecking: 100% (4/4 files, 20 B of 20 B)\n'


def test_speed_and_time_left(vrfdir, clock, capsys):
    m = meter(vrfdir)
    mib = 1024 ** 2

    m.update(0, 4, 0, 100 * mib)
    capsys.readouterr()

    clock.now += 10
    m.update(1, 4, 20 * mib, 100 * mib)

    assert capsys.readouterr().out == (
        '\rChecking: 20% (1/4 files, 20.0 MiB of 100.0 MiB, '
        '2.0 MiB/s, 0:40 left) ')


def test_done_shows_the_average_speed_and_time_used(vrfdir, clock, capsys):
    m = meter(vrfdir)
    mib = 1024 ** 2

    m.update(0, 4, 0, 100 * mib)
    capsys.readouterr()

    clock.now += 50
    m.update(4, 4, 100 * mib, 100 * mib, done=True)

    assert capsys.readouterr().out == (
        '\rChecking: 100% (4/4 files, 100.0 MiB of 100.0 MiB, '
        '2.0 MiB/s, 0:50)\n')


def test_no_speed_before_any_data_is_read(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(0, 4, 0, 20)
    capsys.readouterr()

    clock.now += 5
    m.update(0, 4, 0, 20)

    assert capsys.readouterr().out == \
        '\rChecking: 0% (0/4 files, 0 B of 20 B) '


def test_unread_bytes_are_not_counted_for_the_speed(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(0, 4, 0, 100)
    capsys.readouterr()

    clock.now += 10
    m.update(2, 4, 60, 100, unread=50)

    assert capsys.readouterr().out == (
        '\rChecking: 60% (2/4 files, 60 B of 100 B, 1 B/s, 0:40 left) ')

    clock.now += 10
    m.update(4, 4, 100, 100, done=True, unread=100)

    # without a speed, the line is padded over the longer previous one
    assert capsys.readouterr().out.rstrip() == \
        '\rChecking: 100% (4/4 files, 100 B of 100 B)'


def test_quiet_prints_nothing(vrfdir, clock, capsys):
    m = meter(vrfdir, quiet=True)

    m.update(1, 4, 5, 20)
    m.update(4, 4, 20, 20, done=True)
    m.interrupt()

    assert capsys.readouterr().out == ''


def test_no_size_prints_nothing(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(0, 0, 0, 0)
    m.update(0, 0, 0, 0, done=True)

    assert capsys.readouterr().out == ''


def test_a_shorter_line_overwrites_a_longer_one(vrfdir, clock, capsys):
    m = meter(vrfdir)
    long_line = 'Checking: 100% (100/100 files, 1.0 KiB of 1.0 KiB)'
    short_line = 'Checking: 0% (0/100 files, 0 B of 1.0 KiB)'

    m.update(100, 100, 1024, 1024)
    capsys.readouterr()

    clock.now += vrfdir.PROGRESS_INTERVAL
    m.update(0, 100, 0, 1024)

    padding = ' ' * (len(long_line) - len(short_line))
    assert capsys.readouterr().out == '\r%s%s ' % (short_line, padding)


def test_interrupt_ends_an_unfinished_line(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(1, 4, 5, 20)
    capsys.readouterr()

    m.interrupt()
    assert capsys.readouterr().out == '\n'

    # once, and the next update starts a new line
    m.interrupt()
    assert capsys.readouterr().out == ''


def test_interrupt_without_a_line_does_nothing(vrfdir, capsys):
    meter(vrfdir).interrupt()

    assert capsys.readouterr().out == ''


def test_interrupt_after_done_does_nothing(vrfdir, clock, capsys):
    m = meter(vrfdir)

    m.update(4, 4, 20, 20, done=True)
    capsys.readouterr()

    m.interrupt()
    assert capsys.readouterr().out == ''
