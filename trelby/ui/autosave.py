# Crash recovery: periodically written copies of modified scripts.
#
# Each open script that has unsaved changes gets a recovery copy in the
# recovery directory under the config dir, named by a random per-script id:
#
#   <id>.trelby  the script, in the normal file format
#   <id>.json    {"original": filename or null, "pid": ..., "time": ...}
#
# The copies are removed when the script is saved, closed or discarded, so
# any left over at startup are from a session that didn't exit cleanly.
# The user's real files are never touched.

import json
import os
import time
import uuid

import trelby.misc as misc
import trelby.util as util

SCRIPT_EXT = ".trelby"
INFO_EXT = ".json"


def getRecoveryDir():
    return os.path.join(misc.confPath, "recovery")


def newRecoveryId():
    return uuid.uuid4().hex[:16]


# returns (script path, info path) for the given recovery id
def getRecoveryPaths(dirPath, recId):
    base = os.path.join(dirPath, recId)

    return (base + SCRIPT_EXT, base + INFO_EXT)


# write a recovery copy of a script. data is the script as returned by
# Editor.save(), originalFileName the file it was loaded from / will be
# saved to, or None. raises OSError on failure.
def writeRecovery(dirPath, recId, data, originalFileName):
    os.makedirs(dirPath, exist_ok=True)

    scriptPath, infoPath = getRecoveryPaths(dirPath, recId)

    info = {
        "original": originalFileName,
        "pid": os.getpid(),
        "time": time.time(),
    }

    util.atomicWrite(scriptPath, data)
    util.atomicWrite(infoPath, json.dumps(info))


# remove the recovery copy with the given id, if it exists
def removeRecovery(dirPath, recId):
    for path in getRecoveryPaths(dirPath, recId):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:
            # nothing useful to do about it; it'll be offered for recovery
            # next time, which is harmless
            pass


class RecoveryEntry:
    def __init__(self, recId, scriptPath, original, mtime, pid):
        self.recId = recId

        # path of the recovery copy
        self.scriptPath = scriptPath

        # the file the script belonged to, or None for an unsaved script
        self.original = original

        # time the copy was written (seconds since the epoch)
        self.time = mtime

        # process id of the Trelby that wrote it, or None
        self.pid = pid

    def getDisplayName(self):
        if self.original:
            return os.path.basename(self.original)
        else:
            return _("untitled")


# returns True if a process with the given id is currently running
def isProcessAlive(pid):
    if misc.isWindows:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)

        if not handle:
            return False

        try:
            code = ctypes.c_ulong()

            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False

            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

        return True


# returns a list of RecoveryEntry objects for the recovery copies left over
# from sessions that are no longer running, oldest first. copies belonging
# to another Trelby that's still running are skipped. isAlive is for
# testing.
def listRecoveries(dirPath, isAlive=isProcessAlive):
    try:
        names = os.listdir(dirPath)
    except OSError:
        return []

    ret = []

    for name in names:
        recId, ext = os.path.splitext(name)

        if ext != SCRIPT_EXT:
            continue

        scriptPath, infoPath = getRecoveryPaths(dirPath, recId)

        original = None
        pid = None

        try:
            mtime = os.path.getmtime(scriptPath)
        except OSError:
            continue

        # the info file is written after the script, so it can be missing
        # if we crashed in between; the script is still worth offering.
        try:
            with open(infoPath, "r", encoding="UTF-8") as f:
                info = json.load(f)

            if isinstance(info.get("original"), str):
                original = info["original"]

            if isinstance(info.get("pid"), int):
                pid = info["pid"]

            if isinstance(info.get("time"), (int, float)):
                mtime = info["time"]
        except (OSError, ValueError, AttributeError):
            pass

        # our own pid can only match if it's been reused since the crash,
        # since we haven't written anything yet.
        if (pid is not None) and (pid != os.getpid()) and isAlive(pid):
            continue

        ret.append(RecoveryEntry(recId, scriptPath, original, mtime, pid))

    ret.sort(key=lambda e: e.time)

    return ret
