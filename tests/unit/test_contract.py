# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import logging
import re

import pytest

from conftest import SRCDIR

COMMANDS = ['init', 'add', 'status', 'check', 'list', 'export', 'info',
            'scan']


def exit_defines(vrfdir):
    return {name: getattr(vrfdir, name) for name in dir(vrfdir)
            if name.startswith('EXIT_')}


def documented_exit_codes(text):
    section = text.split('exit codes', 1)[1]

    return {int(m.group(1)) for m in
            re.finditer(r'^\s+(\d+)\s', section, re.MULTILINE)}


def test_exit_codes(vrfdir):
    assert exit_defines(vrfdir) == {
        'EXIT_DIFFERENCES': 1,
        'EXIT_CORRUPTION': 2,
        'EXIT_ERROR': 3,
        'EXIT_USAGE': 64,
        'EXIT_INTERRUPTED': 130,
    }


def test_exit_codes_are_documented_in_the_main_help(vrfdir):
    codes = set(exit_defines(vrfdir).values()) | {0}

    assert documented_exit_codes(vrfdir.HELP_MAIN) == codes


@pytest.mark.parametrize('command', COMMANDS)
def test_every_command_documents_its_exit_codes(vrfdir, command):
    text = getattr(vrfdir, 'HELP_' + command.upper())
    known = set(exit_defines(vrfdir).values()) | {0}

    assert 'exit codes:' in text
    assert documented_exit_codes(text) <= known


# the regular expression of https://semver.org/
SEMVER_RE = re.compile(
    r'(?P<core>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))'
    r'(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)'
    r'(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?'
    r'(\+(?P<build>[0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?')


def test_version_is_semver(vrfdir):
    assert SEMVER_RE.fullmatch(vrfdir.VERSION)


def test_changelog_matches_version(vrfdir):
    with open('%s/CHANGELOG.md' % SRCDIR) as f:
        headings = re.findall(r'^## \[([^\]]+)\]', f.read(), re.MULTILINE)

    # a git build has Unreleased at the top, a released version has its
    # own section there, the release commit has no empty Unreleased
    if vrfdir.VERSION.endswith('+git'):
        assert headings[0] == 'Unreleased'
    else:
        assert headings[0] == vrfdir.VERSION


def exit_calls():
    with open('%s/vrfdir' % SRCDIR) as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and
                isinstance(node.func, ast.Attribute) and
                node.func.attr == 'exit'):
            yield node


def test_exit_is_called_with_a_define():
    calls = list(exit_calls())

    # sys.exit() calls and the exit() of the argument parser
    assert len(calls) > 10

    for node in calls:
        assert node.args, 'line %d: exit() without a code' % node.lineno
        code = node.args[0]
        assert isinstance(code, ast.Name), 'line %d' % node.lineno
        assert code.id.startswith('EXIT_'), 'line %d' % node.lineno


def test_exit_defines_are_defined(vrfdir):
    for node in exit_calls():
        assert hasattr(vrfdir, node.args[0].id)


@pytest.mark.parametrize('command', COMMANDS)
def test_every_command_has_a_function(vrfdir, command):
    assert callable(getattr(vrfdir, 'cmd_' + command))


@pytest.mark.parametrize('argv', [
    ['vrfdir'],
    ['vrfdir', 'nosuchcommand'],
    ['vrfdir', '--nosuchoption', 'info'],
    ['vrfdir', 'add'],
    ['vrfdir', 'info', 'extra'],
])
def test_wrong_command_line(vrfdir, monkeypatch, capsys, argv):
    monkeypatch.setattr('sys.argv', argv)

    with pytest.raises(SystemExit) as e:
        vrfdir.run_command()

    out, err = capsys.readouterr()
    assert e.value.code == vrfdir.EXIT_USAGE
    assert out == ''
    # the usage, the error in the same format as the others, and the
    # command which has the help
    assert re.fullmatch(r"usage: .*\nError: [^\n]+\n"
                        r"Run 'vrfdir( [a-z]+)? --help' for the "
                        r"instructions\.\n", err, re.DOTALL)


@pytest.fixture
def main(vrfdir, monkeypatch, caplog):
    # main() changes these for the whole process
    monkeypatch.setattr(logging, 'raiseExceptions', True)
    monkeypatch.setattr(vrfdir, 'discard_stdout', lambda: None)

    def run(exception):
        def fail():
            raise exception

        monkeypatch.setattr(vrfdir, 'run_command', fail)

        with pytest.raises(SystemExit) as e:
            vrfdir.main()

        return e.value.code, [r.getMessage() for r in caplog.records]

    return run


def test_main_interrupted(vrfdir, main):
    assert main(KeyboardInterrupt()) == (vrfdir.EXIT_INTERRUPTED,
                                         ['interrupted'])


def test_main_broken_pipe(vrfdir, main):
    assert main(BrokenPipeError()) == (vrfdir.EXIT_ERROR, [])


def test_main_failed_output(vrfdir, main):
    code, messages = main(OSError(28, 'No space left on device'))

    assert code == vrfdir.EXIT_ERROR
    assert len(messages) == 1
    assert messages[0].startswith('cannot write the output: ')


def test_main_failed_access(vrfdir, main):
    code, messages = main(PermissionError(13, 'Permission denied', 'x'))

    assert code == vrfdir.EXIT_ERROR
    assert messages == ['cannot access x: Permission denied']


def test_main_a_bug_is_not_exit_code_1(vrfdir, main):
    code, messages = main(ZeroDivisionError('bug'))

    assert code == vrfdir.EXIT_ERROR
    assert code != vrfdir.EXIT_DIFFERENCES
    assert messages == ['internal error, this is a bug in vrfdir']
