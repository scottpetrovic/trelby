# -*- coding: utf-8 -*-

import glob
import os
import shutil
import stat
import tempfile
import time
from typing import AnyStr

import trelby.pdf.fontinfo as fontinfo
import trelby.misc as misc

# alignment values
ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2
VALIGN_TOP = 1
VALIGN_CENTER = 2
VALIGN_BOTTOM = 3


# clamps the given value to a specific range. both limits are optional.
def clamp(val, minVal=None, maxVal=None):
    ret = val

    if minVal != None:
        ret = max(ret, minVal)

    if maxVal != None:
        ret = min(ret, maxVal)

    return ret


# like clamp, but gets/sets value directly from given object
def clampObj(obj, name, minVal=None, maxVal=None):
    setattr(obj, name, clamp(getattr(obj, name), minVal, maxVal))


# convert given string to float, clamping it to the given range
# (optional). never throws any exceptions, return defVal (possibly clamped
# as well) on any errors.
def str2float(s, defVal, minVal=None, maxVal=None):
    val = defVal

    try:
        val = float(s)
    except (ValueError, OverflowError):
        pass

    return clamp(val, minVal, maxVal)


# like str2float, but for ints.
def str2int(s, defVal, minVal=None, maxVal=None, radix=10):
    val = defVal

    try:
        val = int(s, radix)
    except ValueError:
        pass

    return clamp(val, minVal, maxVal)


# extract 'name' field from each item in 'seq', put it in a list, and
# return that list.
def listify(seq, name):
    l = []
    for it in seq:
        l.append(getattr(it, name))

    return l


# return name, made unique among the names in taken by adding "-2", "-3"...
# if needed
def uniqueName(name, taken):
    i = 1
    unique = name

    while unique in taken:
        i += 1
        unique = "%s-%d" % (name, i)

    return unique


# return percentage of 'val1' of 'val2' (both ints) as an int (50% -> 50
# etc.), or 0 if val2 is 0.
def pct(val1, val2):
    if val2 != 0:
        return (100 * val1) // val2
    else:
        return 0


# return percentage of 'val1' of 'val2' (both ints/floats) as a float (50%
# -> 50.0 etc.), or 0.0 if val2 is 0.0
def pctf(val1, val2):
    if val2 != 0.0:
        return (100.0 * val1) / val2
    else:
        return 0.0


# return float(val1) / val2, or 0.0 if val2 is 0.0
def safeDiv(val1, val2):
    if val2 != 0.0:
        return float(val1) / val2
    else:
        return 0.0


# return float(val1) / val2, or 0.0 if val2 is 0
def safeDivInt(val1, val2):
    if val2 != 0:
        return float(val1) / val2
    else:
        return 0.0


# for each character in 'flags', starting at beginning, checks if that
# character is found in 's'. if so, appends True to a tuple, False
# otherwise. returns that tuple, whose length is of course is len(flags).
def flags2bools(s, flags):
    b = ()

    for f in flags:
        if s.find(f) != -1:
            b += (True,)
        else:
            b += (False,)

    return b


# reverse of flags2bools. is given a number of objects, if each object
# evaluates to true, chars[i] is appended to the return string. len(chars)
# == len(bools) must be true.
def bools2flags(chars, *bools):
    s = ""

    if len(chars) != len(bools):
        raise TypeError(_("bools2flags: chars and bools are not equal length"))

    for i in range(len(chars)):
        if bools[i]:
            s += chars[i]

    return s


# convert mm to twips (1/1440 inch = 1/20 point).
def mm2twips(mm):
    # 56.69291 = 1440 / 25.4
    return mm * 56.69291


# return how many mm tall given font size is.
def getTextHeight(size):
    return (size / 72.0) * 25.4


# return how many mm wide given text is at given style with given size.
def getTextWidth(text, style, size):
    return (fontinfo.getMetrics(style).getTextWidth(text, size) / 72.0) * 25.4


def cmpfunc(a, b):
    return (a > b) - (a < b)


# return the (key, value) pairs of dictionary d, sorted by "desc(value)
# asc(key)"
def sortDict(d):
    return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))


# an efficient FIFO container of fixed size. can't contain None objects.
class FIFO:
    def __init__(self, size):
        self.arr = [None] * size

        # index of next slot to fill
        self.next = 0

    # add item
    def add(self, obj):
        self.arr[self.next] = obj
        self.next += 1

        if self.next >= len(self.arr):
            self.next = 0

    # get contents as a list, in LIFO order.
    def get(self):
        tmp = []

        j = self.next - 1

        for i in range(len(self.arr)):
            if j < 0:
                j = len(self.arr) - 1

            obj = self.arr[j]

            if obj != None:
                tmp.append(obj)

            j -= 1

        return tmp


# a string-like object that features reasonably fast repeated appends even
# for large strings, since it keeps each appended string as an item in a
# list.
class String:
    def __init__(self, s=None):

        # byte count of data appended
        self.pos = 0

        # list of strings
        self.data = []

        if s:
            self += s

    def __len__(self):
        return self.pos

    def __str__(self):
        return "".join(self.data)

    def __iadd__(self, s):
        s2 = str(s)

        self.data.append(s2)
        self.pos += len(s2)

        return self


# write data to filename so that a crash or error halfway through never
# leaves a partially written file behind: the data goes to a temp file in
# the same directory, which then replaces the target in one step. if
# backup is True and the target already exists, its previous contents are
# kept as filename + ".bak". raises OSError on failure, in which case the
# target is untouched.
def atomicWrite(filename: str, data: AnyStr, backup: bool = False) -> None:
    if isinstance(data, str):
        data = data.encode("UTF-8")

    path = os.path.abspath(filename)
    dirName = os.path.dirname(path)
    exists = os.path.exists(path)

    fd, tmpPath = tempfile.mkstemp(
        prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=dirName
    )

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        # mkstemp creates the file as owner-only; keep the permissions an
        # in-place write would have had. (on Windows the only "mode" is the
        # read-only flag, which we don't want to copy to the temp file.)
        if not misc.isWindows:
            if exists:
                mode = stat.S_IMODE(os.stat(path).st_mode)
            else:
                umask = os.umask(0)
                os.umask(umask)
                mode = 0o666 & ~umask

            os.chmod(tmpPath, mode)

        if backup and exists:
            # a failed backup shouldn't stop the user's work from being
            # saved
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass

        os.replace(tmpPath, path)

    except BaseException:
        try:
            os.remove(tmpPath)
        except OSError:
            pass

        raise

    # make the rename itself durable. not possible / needed on Windows.
    if not misc.isWindows:
        try:
            dirFd = os.open(dirName, os.O_RDONLY)

            try:
                os.fsync(dirFd)
            finally:
                os.close(dirFd)
        except OSError:
            pass


def removeTempFiles(prefix):
    files = glob.glob(tempfile.gettempdir() + "/%s*" % prefix)

    for fn in files:
        try:
            os.remove(fn)
        except OSError:
            continue


# return True if given file exists.
def fileExists(filename):
    try:
        os.stat(misc.toPath(filename))
    except OSError:
        return False

    return True


# look for file 'filename' in all the directories listed in 'dirs', which
# is a list of absolute directory paths. if found, return the absolute
# filename, otherwise None.
def findFile(filename, dirs):
    for d in dirs:
        if d[-1] != "/":
            d += "/"

        path = d + filename

        if fileExists(path):
            return path

    return None


# look for file 'filename' in all the directories listed in $PATH. if
# found, return the absolute filename, otherwise None.
def findFileInPath(filename):
    dirs = os.getenv("PATH")
    if not dirs:
        return None

    # I have no idea how one should try to cope if PATH contains entries
    # with non-UTF8 characters, so just ignore any errors
    dirs = str(dirs).split(":")

    # only accept absolute paths. this strips out things like "~/bin/"
    # etc.
    dirs = [d for d in dirs if d and d[0] == "/"]

    return findFile(filename, dirs)


# simple timer class for use during development only
class TimerDev:

    # how many TimerDev instances are currently in existence
    nestingLevel = 0

    def __init__(self, msg=""):
        self.msg = msg
        self.__class__.nestingLevel += 1
        self.t = time.time()

    def __del__(self):
        self.t = time.time() - self.t
        self.__class__.nestingLevel -= 1
        print(
            "{}{} took {:.5f} seconds".format(
                " " * self.__class__.nestingLevel, self.msg, self.t
            )
        )


# Get the Windows default PDF viewer path from registry and return that,
# or None on errors.
def _getWindowsPDFViewer():
    try:
        import winreg

        # HKCR/.pdf: gives the class of the PDF program.
        # Example : AcroRead.Document or FoxitReader.Document

        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ".pdf")
        pdfClass = winreg.QueryValue(key, "")

        # HKCR/<class>/shell/open/command: the path to the PDF viewer program
        # Example: "C:\Program Files\Acrobat 8.0\acroread.exe" "%1"

        key2 = winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, pdfClass + r"\shell\open\command"
        )

        # Almost every PDF program out there accepts passing the PDF path
        # as the argument, so we don't parse the arguments from the
        # registry, just get the program path.

        path = winreg.QueryValue(key2, "").split('"')[1]

        if fileExists(path):
            return path
    except:
        pass

    return None


# Get a tuple of the default PDF viewer path and args for the current platform
# and return that, or a tuple of two Nones on errors.
def getPDFViewer():
    # list of programs to look for. each item is of the form (name,
    # args). if name is an absolute path only that exact location is
    # looked at, otherwise PATH is searched for the program (on
    # Windows, all paths are interpreted as absolute). args is the
    # list of arguments for the program.
    progs = []

    if misc.isMac:
        # Need to check for Mac before Unix as macOS is a Unix
        progs = [("/System/Applications/Preview.app", "")]
    elif misc.isUnix:
        progs = [("/usr/bin/xdg-open", "")]
    elif misc.isWindows:
        # get value via registry if possible, or fallback to old method.
        viewer = _getWindowsPDFViewer()
        if viewer:
            return (viewer, "")

        progs = [
            (r"C:\Program Files\Adobe\Reader 11.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Reader 10.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Reader 9.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Reader 8.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Acrobat 7.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Acrobat 6.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Acrobat 5.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Adobe\Acrobat 4.0\Reader\AcroRd32.exe", ""),
            (r"C:\Program Files\Foxit Software\Foxit Reader\Foxit Reader.exe", ""),
        ]
    else:
        # Unknown platform, don't know where to look
        pass
    for name, args in progs:
        if misc.isWindows or (name[0] == "/"):
            if fileExists(name):
                return (name, args)
        else:
            name = findFileInPath(name)
            if name:
                return (name, args)
    return (None, None)


