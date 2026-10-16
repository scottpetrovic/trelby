import sys

import pytest

import trelby.opts as opts

# tests for the command line arguments


@pytest.fixture
def parse(monkeypatch):
    # put back whatever opts.init() set before, for the other tests
    for name in ("isTest", "conf", "filenames"):
        monkeypatch.setattr(opts, name, getattr(opts, name, None), raising=False)

    def parse(*args):
        monkeypatch.setattr(sys, "argv", ["trelby.py"] + list(args))
        opts.init()

    return parse


def testNoArgs(parse):
    parse()

    assert not opts.isTest
    assert opts.conf is None
    assert opts.filenames == []


def testArgs(parse):
    parse("--test", "a.trelby", "--conf", "Åsa/my.conf", "b.trelby")

    assert opts.isTest
    assert opts.conf == "Åsa/my.conf"
    assert opts.filenames == ["a.trelby", "b.trelby"]


# --conf with nothing after it is ignored
def testConfMissingPath(parse):
    parse("a.trelby", "--conf")

    assert opts.conf is None
    assert opts.filenames == ["a.trelby"]
