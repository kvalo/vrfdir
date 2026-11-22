# SPDX-FileCopyrightText: 2026 Kalle Valo
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.machinery
import importlib.util
import logging
import os
import sys

import pytest

SRCDIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


# vrfdir and genbackupdata have no .py extension so they cannot be
# imported by name.
def load_script(name, path):
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)

    # do not leave a __pycache__ in the source directory
    dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = dont_write_bytecode

    return module


def load_vrfdir():
    module = load_script('vrfdir', os.path.join(SRCDIR, 'vrfdir'))

    # main() sets this, the functions which log need it
    module.logger = logging.getLogger('vrfdir')

    return module


@pytest.fixture(scope='session')
def vrfdir():
    return load_vrfdir()


@pytest.fixture(scope='session')
def genbackupdata():
    return load_script('genbackupdata',
                       os.path.join(SRCDIR, 'tests', 'genbackupdata'))
