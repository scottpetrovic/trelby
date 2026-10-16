import json
import os

import pytest

import tests.u as u
import trelby.ui.autosave as autosave
import trelby.ui.gutil as gutil
import trelby.translations as translations
import trelby.util as util

_ = translations.trelby_translations_load()

# atomic writes


def readBytes(path):
    with open(path, "rb") as f:
        return f.read()


def testAtomicWriteNewFile(tmp_path):
    u.init()

    path = str(tmp_path / "new.trelby")
    util.atomicWrite(path, "héllo", backup=True)

    assert readBytes(path) == "héllo".encode("UTF-8")

    # nothing to back up, and no temp files left behind
    assert os.listdir(tmp_path) == ["new.trelby"]


def testAtomicWriteBytes(tmp_path):
    u.init()

    path = str(tmp_path / "f.bin")
    util.atomicWrite(path, b"\x00\x01")

    assert readBytes(path) == b"\x00\x01"


def testAtomicWriteBackup(tmp_path):
    u.init()

    path = str(tmp_path / "s.trelby")
    util.atomicWrite(path, "one")
    util.atomicWrite(path, "two", backup=True)

    assert readBytes(path) == b"two"
    assert readBytes(path + ".bak") == b"one"

    # only one generation is kept
    util.atomicWrite(path, "three", backup=True)

    assert readBytes(path) == b"three"
    assert readBytes(path + ".bak") == b"two"
    assert sorted(os.listdir(tmp_path)) == ["s.trelby", "s.trelby.bak"]


def testAtomicWriteNoBackupByDefault(tmp_path):
    u.init()

    path = str(tmp_path / "default.conf")
    util.atomicWrite(path, "one")
    util.atomicWrite(path, "two")

    assert readBytes(path) == b"two"
    assert not os.path.exists(path + ".bak")


def testAtomicWriteFailureKeepsTarget(tmp_path, monkeypatch):
    u.init()

    path = str(tmp_path / "s.trelby")
    util.atomicWrite(path, "original")

    def failingFsync(fd):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "fsync", failingFsync)

    with pytest.raises(OSError):
        util.atomicWrite(path, "new contents", backup=True)

    assert readBytes(path) == b"original"

    # temp file cleaned up, and no backup made of a save that didn't happen
    assert os.listdir(tmp_path) == ["s.trelby"]


def testAtomicWriteFailureOnReplace(tmp_path, monkeypatch):
    u.init()

    path = str(tmp_path / "s.trelby")
    util.atomicWrite(path, "original")

    def failingReplace(src, dst):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(os, "replace", failingReplace)

    with pytest.raises(OSError):
        util.atomicWrite(path, "new contents")

    assert readBytes(path) == b"original"
    assert os.listdir(tmp_path) == ["s.trelby"]


def testAtomicWriteBadData(tmp_path):
    u.init()

    path = str(tmp_path / "s.trelby")
    util.atomicWrite(path, "original")

    # not str or bytes: fails inside the write
    with pytest.raises(TypeError):
        util.atomicWrite(path, 12345)

    assert readBytes(path) == b"original"
    assert os.listdir(tmp_path) == ["s.trelby"]


def testWriteToFileReportsError(tmp_path, monkeypatch):
    u.init()

    shown = []
    monkeypatch.setattr(gutil.wx, "MessageBox", lambda *args: shown.append(args))

    path = str(tmp_path / "missing-dir" / "s.trelby")

    assert not gutil.writeToFile(path, "data", None)
    assert len(shown) == 1


# recovery files


def notAlive(pid):
    return False


def testRecoveryWriteListRemove(tmp_path):
    u.init()

    d = str(tmp_path / "recovery")
    recId = autosave.newRecoveryId()

    autosave.writeRecovery(d, recId, b"script data", "/scripts/my script.trelby")

    scriptPath, infoPath = autosave.getRecoveryPaths(d, recId)
    assert scriptPath == os.path.join(d, recId + ".trelby")
    assert infoPath == os.path.join(d, recId + ".json")
    assert readBytes(scriptPath) == b"script data"

    entries = autosave.listRecoveries(d, notAlive)
    assert len(entries) == 1

    e = entries[0]
    assert e.recId == recId
    assert e.scriptPath == scriptPath
    assert e.original == "/scripts/my script.trelby"
    assert e.pid == os.getpid()
    assert e.getDisplayName() == "my script.trelby"

    # rewriting replaces the same files
    autosave.writeRecovery(d, recId, b"newer data", None)
    entries = autosave.listRecoveries(d, notAlive)
    assert len(entries) == 1
    assert entries[0].original is None
    assert entries[0].getDisplayName() == _("untitled")
    assert readBytes(scriptPath) == b"newer data"

    autosave.removeRecovery(d, recId)
    assert os.listdir(d) == []
    assert autosave.listRecoveries(d, notAlive) == []

    # removing again is harmless
    autosave.removeRecovery(d, recId)


def testRecoveryIdsUnique():
    ids = {autosave.newRecoveryId() for i in range(100)}

    assert len(ids) == 100


def testListRecoveriesMissingDir(tmp_path):
    assert autosave.listRecoveries(str(tmp_path / "nope"), notAlive) == []


def writeInfo(d, recId, info):
    with open(autosave.getRecoveryPaths(d, recId)[1], "w", encoding="UTF-8") as f:
        f.write(info if isinstance(info, str) else json.dumps(info))


def writeScript(d, recId):
    with open(autosave.getRecoveryPaths(d, recId)[0], "wb") as f:
        f.write(b"data")


def testListRecoveriesSkipsLiveInstances(tmp_path):
    u.init()

    d = str(tmp_path)

    writeScript(d, "a")
    writeInfo(d, "a", {"original": "a.trelby", "pid": 111, "time": 2})

    writeScript(d, "b")
    writeInfo(d, "b", {"original": "b.trelby", "pid": 222, "time": 1})

    # our own pid can only be a reused one from a crashed session
    writeScript(d, "c")
    writeInfo(d, "c", {"original": "c.trelby", "pid": os.getpid(), "time": 3})

    entries = autosave.listRecoveries(d, lambda pid: pid == 111)

    # oldest first
    assert [e.recId for e in entries] == ["b", "c"]


def testListRecoveriesBadInfo(tmp_path):
    u.init()

    d = str(tmp_path)

    # crashed between writing the script and its info file
    writeScript(d, "noinfo")

    writeScript(d, "badjson")
    writeInfo(d, "badjson", "{not json")

    writeScript(d, "notdict")
    writeInfo(d, "notdict", "[1, 2]")

    # info without script: nothing to restore
    writeInfo(d, "noscript", {"original": None, "pid": 1, "time": 1})

    # unrelated file
    with open(os.path.join(d, "readme.txt"), "w") as f:
        f.write("x")

    entries = autosave.listRecoveries(d, notAlive)

    assert sorted(e.recId for e in entries) == ["badjson", "noinfo", "notdict"]

    for e in entries:
        assert e.original is None
        assert e.pid is None


def testIsProcessAlive():
    u.init()

    assert autosave.isProcessAlive(os.getpid())

    # pids are never this large on any supported platform
    assert not autosave.isProcessAlive(2**30 + 1)
