# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later
#
# vrfdir may only write in .vrfdir, never the data of the user.
# tests/specs/data-untouched.script checks that the commands leave the
# data as it is. These tests read the source of vrfdir and check where
# it can write at all, so that a new way to change a file does not
# slip in unnoticed. A new write which is right needs an entry in
# ALLOWED_WRITES, which makes the author look at the path it uses.

import ast
import os

from conftest import SRCDIR

# Nothing which can copy, move or delete files by itself or run
# another program. Every module vrfdir imports is listed.
ALLOWED_IMPORTS = {'argparse', 'errno', 'hashlib', 'heapq', 'itertools',
                   'locale', 'logging', 'json', 'os', 'platform', 're',
                   'stat', 'sys', 'time'}

# functions of os which change a file, a directory or what is run
OS_WRITERS = {
    'remove', 'unlink', 'rename', 'renames', 'replace', 'rmdir', 'mkdir',
    'makedirs', 'removedirs', 'utime', 'chmod', 'lchmod', 'chown',
    'lchown', 'chflags', 'lchflags', 'truncate', 'ftruncate', 'symlink',
    'link', 'mkfifo', 'mknod', 'write', 'writev', 'pwrite', 'pwritev',
    'sendfile', 'copy_file_range', 'setxattr', 'removexattr', 'fchmod',
    'fchown', 'system', 'popen', 'startfile', 'fork', 'forkpty',
    'posix_spawn', 'posix_spawnp',
}

OS_OPEN_WRITE_FLAGS = {'O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC',
                       'O_APPEND'}

# (function, call) of every place which writes. The path is checked
# below, it is either one of the files in .vrfdir or os.devnull.
ALLOWED_WRITES = {
    # the temporary file of save_file(), then renamed over its name
    ('save_file',
     "open(tmpname, 'w', encoding='utf-8', newline='\\n')"),
    ('save_file', 'os.unlink(tmpname)'),
    ('replace_file', 'os.replace(src, dst)'),
    # the old name of manifest.json, removed after the conversion
    ('VrfdirRepo.write', 'os.unlink(VRFDIR_LEGACY_PATH)'),
    ('cmd_init', 'os.makedirs(VRFDIR_DIRECTORY)'),
    # stdout and stderr which were closed
    ('discard_stdout', 'os.open(os.devnull, os.O_WRONLY)'),
    ('main', "open(os.devnull, 'w')"),
}

# the arguments of save_file() are paths in .vrfdir
SAVE_FILE_CALLERS = {'VrfdirRepo.write'}


def parse():
    with open(os.path.join(SRCDIR, 'vrfdir'), encoding='utf-8') as f:
        return ast.parse(f.read())


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return None if base is None else '%s.%s' % (base, node.attr)

    return None


def calls(tree):
    """Yield (qualified name of the function, call) of every call.

    A function inside a function belongs to the outer one."""

    def visit(node, scope, in_function):
        if isinstance(node, ast.ClassDef):
            scope = scope + [node.name]
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not in_function:
                scope = scope + [node.name]
            in_function = True

        if isinstance(node, ast.Call):
            yield '.'.join(scope) or '<module>', node

        for child in ast.iter_child_nodes(node):
            yield from visit(child, scope, in_function)

    return visit(tree, [], False)


def call_mode(node):
    """The mode of an open() call, None when it is not a constant."""
    mode = node.args[1] if len(node.args) > 1 else None

    for kw in node.keywords:
        if kw.arg == 'mode':
            mode = kw.value

    if mode is None:
        return 'r'

    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return mode.value

    return None


def writes(tree):
    """Yield (function, text of the call) of the calls which write."""
    for (scope, node) in calls(tree):
        name = dotted(node.func)

        if name == 'open':
            mode = call_mode(node)
            if mode is None or set(mode) & set('wax+'):
                yield scope, ast.unparse(node)

        elif name == 'os.open':
            flags = {n.attr for n in ast.walk(node.args[1])
                     if isinstance(n, ast.Attribute)}
            if flags & OS_OPEN_WRITE_FLAGS or 'O_RDONLY' not in flags:
                yield scope, ast.unparse(node)

        elif name is not None and name.startswith('os.'):
            if name[3:] in OS_WRITERS or name.startswith('os.exec'):
                yield scope, ast.unparse(node)

        elif name is not None and name.startswith('os.spawn'):
            yield scope, ast.unparse(node)


def test_only_known_modules_are_imported():
    imported = set()

    for node in ast.walk(parse()):
        if isinstance(node, ast.Import):
            imported.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module.split('.')[0])

    assert imported <= ALLOWED_IMPORTS, sorted(imported - ALLOWED_IMPORTS)


def test_only_known_places_write():
    found = set(writes(parse()))

    assert found == ALLOWED_WRITES


def test_the_scan_finds_writes():
    # a test which finds nothing would pass whatever vrfdir does
    tree = ast.parse(
        'def f(name):\n'
        '    open(name, "wb")\n'
        '    open(name, mode=m)\n'
        '    open(name)\n'
        '    os.open(name, os.O_RDWR | os.O_CREAT)\n'
        '    os.open(name, os.O_RDONLY)\n'
        '    os.rename(name, "x")\n'
        '    os.utime(name)\n')

    assert sorted(text for (_, text) in writes(tree)) == [
        "open(name, 'wb')", 'open(name, mode=m)',
        'os.open(name, os.O_RDWR | os.O_CREAT)', "os.rename(name, 'x')",
        'os.utime(name)']


def test_save_file_writes_only_in_vrfdir(vrfdir):
    found = 0

    for (scope, node) in calls(parse()):
        if dotted(node.func) != 'save_file':
            continue

        assert scope in SAVE_FILE_CALLERS, 'line %d' % node.lineno

        # the name of the file and the name of its temporary file
        for arg in node.args[:2]:
            assert isinstance(arg, ast.Name), 'line %d' % node.lineno
            assert getattr(vrfdir, arg.id).startswith(
                vrfdir.VRFDIR_DIRECTORY + '/'), arg.id

        found += 1

    assert found == 2


def test_replace_file_is_only_called_by_save_file():
    found = [(scope, ast.unparse(node)) for (scope, node) in calls(parse())
             if dotted(node.func) == 'replace_file']

    assert found == [('save_file', 'replace_file(tmpname, filename)')]


def test_the_old_manifest_is_in_vrfdir(vrfdir):
    # the only file which is removed and is not a temporary file
    assert vrfdir.VRFDIR_LEGACY_PATH.startswith(vrfdir.VRFDIR_DIRECTORY + '/')
