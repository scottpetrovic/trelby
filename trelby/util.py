# -*- coding: utf-8 -*-

import functools
import glob
import gzip
import os
import shutil
import stat
import tempfile
import time
from typing import TYPE_CHECKING, AnyStr, Optional

import trelby.misc as misc

# only for type hints: importing config here makes a circular import
if TYPE_CHECKING:
    import trelby.config as config

if "TRELBY_TESTING" in os.environ:
    import unittest.mock as mock

    wx = mock.Mock()
else:
    import wx

# alignment values
ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2
VALIGN_TOP = 1
VALIGN_CENTER = 2
VALIGN_BOTTOM = 3

# this has to be below the ALIGN stuff, otherwise things break due to
# circular dependencies
import trelby.fontinfo as fontinfo


# permanent memory DC to get text extents etc
permDc = None


def init(doWX=True):
    global permDc

    if doWX:
        # dunno if the bitmap needs to be big enough to contain the text
        # we're measuring...
        permDc = wx.MemoryDC()
        permDc.SelectObject(wx.Bitmap(512, 32))


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


# TODO: move all GUI stuff to gutil


# return True if given font is a fixed-width one.
def isFixedWidth(font):
    return getTextExtent(font, "iiiii")[0] == getTextExtent(font, "OOOOO")[0]


# get extent of 's' as (w, h)
def getTextExtent(font, s):
    permDc.SetFont(font)

    # if we simply return permDc.GetTextExtent(s) from here, on some
    # versions of Windows we will incorrectly reject as non-fixed width
    # fonts (through isFixedWidth) some fonts that actually are fixed
    # width. it's especially bad because one of them is our default font,
    # "Courier New".
    #
    # these are the widths we get for the strings below for Courier New, italic:
    #
    # iiiii 40
    # iiiiiiiiii 80
    # OOOOO 41
    # OOOOOOOOOO 81
    #
    # we can see i and O are both 8 pixels wide, so the font is
    # fixed-width, but for whatever reason, on the O variants there is one
    # additional pixel returned in the width, no matter what the length of
    # the string is.
    #
    # to get around this, we actually call GetTextExtent twice, once with
    # the actual string we want to measure, and once with the string
    # duplicated, and take the difference between those two as the actual
    # width. this handily negates the one-extra-pixel returned and gives
    # us an accurate way of checking if a font is fixed width or not.
    #
    # it's a bit slower but this is not called from anywhere that's
    # performance critical.

    w1, h = permDc.GetTextExtent(s)
    w2 = permDc.GetTextExtent(s + s)[0]

    return (w2 - w1, h)


# get height of font in pixels
def getFontHeight(font):
    permDc.SetFont(font)
    return permDc.GetTextExtent("_\xC5")[1]


# return how many mm tall given font size is.
def getTextHeight(size):
    return (size / 72.0) * 25.4


# return how many mm wide given text is at given style with given size.
def getTextWidth(text, style, size):
    return (fontinfo.getMetrics(style).getTextWidth(text, size) / 72.0) * 25.4


# create a font that's height is at most 'height' pixels. other parameters
# are the same as in wx.Font's constructor.
def createPixelFont(height, family, style, weight):
    fs = 6

    selected = fs
    closest = 1000
    over = 0

    # FIXME: what's this "keep trying even once we go over the max height"
    # stuff? get rid of it.
    while 1:
        fn = wx.Font(fs, family, style, weight, encoding=wx.FONTENCODING_ISO8859_1)
        h = getFontHeight(fn)
        diff = height - h

        if diff >= 0:
            if diff < closest:
                closest = diff
                selected = fs
        else:
            over += 1

        if (over >= 3) or (fs > 144):
            break

        fs += 2

    return wx.Font(selected, family, style, weight, encoding=wx.FONTENCODING_ISO8859_1)


def reverseComboSelect(combo, clientData):
    for i in range(combo.GetCount()):
        if combo.GetClientData(i) == clientData:
            if combo.GetSelection() != i:
                combo.SetSelection(i)

            return True

    return False


# set widget's client size. if w or h is -1, that dimension is not changed.
def setWH(ctrl, w=-1, h=-1):
    size = ctrl.GetClientSize()

    if w != -1:
        size.width = w

    if h != -1:
        size.height = h

    ctrl.SetMinSize(wx.Size(size.width, size.height))
    ctrl.SetClientSize(size.width, size.height)


# wxMSW doesn't respect the control's min/max values at all, so we have to
# implement this ourselves
def getSpinValue(spinCtrl):
    tmp = clamp(spinCtrl.GetValue(), spinCtrl.GetMin(), spinCtrl.GetMax())
    spinCtrl.SetValue(tmp)

    return tmp


def cmpfunc(a, b):
    return (a > b) - (a < b)


# put everything from dictionary d into a list as (key, value) tuples,
# then sort the list and return that. by default sorts by "desc(value)
# asc(key)", but a custom sort function can be given
def sortDict(d, sortFunc=None):
    def tmpSortFunc(o1, o2):
        ret = cmpfunc(o2[1], o1[1])

        if ret != 0:
            return ret
        else:
            return cmpfunc(o1[0], o2[0])

    if sortFunc == None:
        sortFunc = tmpSortFunc

    tmp = []
    for k, v in d.items():
        tmp.append((k, v))

    tmp = sorted(tmp, key=functools.cmp_to_key(sortFunc))

    return tmp


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


# DrawLine-wrapper that makes it easier when the end-point is just
# offsetted from the starting point
def drawLine(dc, x, y, xd, yd):
    dc.DrawLine(x, y, x + xd, y + yd)


# draws text aligned somehow. returns a (w, h) tuple of the text extent.
def drawText(dc, text, x, y, align=ALIGN_LEFT, valign=VALIGN_TOP):
    w, h = dc.GetTextExtent(text)

    if align == ALIGN_CENTER:
        x -= w // 2
    elif align == ALIGN_RIGHT:
        x -= w

    if valign == VALIGN_CENTER:
        y -= h // 2
    elif valign == VALIGN_BOTTOM:
        y -= h

    dc.DrawText(text, x, y)

    return (w, h)


# create pad sizer for given window whose controls are in topSizer, with
# 'pad' pixels of padding on each side, resize window to correct size, and
# optionally center it.
def finishWindow(window, topSizer, pad=20, center=False):
    padSizer = wx.BoxSizer(wx.VERTICAL)
    padSizer.Add(topSizer, 1, wx.EXPAND | wx.ALL, pad)
    window.SetSizerAndFit(padSizer)
    window.Layout()

    # dialogs and other top-level windows are shown in the theme's colors
    if window.IsTopLevel():
        import trelby.gutil as gutil

        gutil.themeWindow(window)

    if center:
        window.Center()


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


# load at most maxSize (all if -1) bytes from 'filename', returning the
# data as a string or None on errors. pops up message boxes with 'frame'
# as parent on errors.
def loadFile(
    filename: str, frame: Optional[wx.Frame], maxSize: int = -1, binary: bool = False
) -> Optional[AnyStr]:
    try:
        if binary:
            f = open(misc.toPath(filename), "rb")
        else:
            f = open(misc.toPath(filename), "r", encoding="UTF-8")

        try:
            ret = f.read(maxSize)
        except MemoryError as error:
            print(_("File too large: {}").format(error))
            ret = None
        finally:
            f.close()

    except IOError as xxx_todo_changeme:
        (errno, strerror) = xxx_todo_changeme.args
        wx.MessageBox(
            _("Error loading file '{}': {}").format(filename, strerror),
            _("Error"),
            wx.OK,
            frame,
        )
        ret = None

    return ret


# unused. note that the encoding name lands in loadFile's 'binary'
# parameter, so this reads the file as bytes rather than decoding it as
# Latin-1.
def loadLatin1EncodedFile(
    filename: str, frame: Optional[wx.Frame], maxSize: int = -1
) -> Optional[AnyStr]:
    return loadFile(filename, frame, maxSize, "ISO-8859-1")


# like loadFile, but if file doesn't exist, tries to load a .gz compressed
# version of it.
def loadMaybeCompressedFile(filename, frame):
    doGz = False

    if not fileExists(filename):
        filename += ".gz"
        doGz = True

    if not doGz:
        s = loadFile(filename, frame)
        return s

    try:
        f = gzip.open(filename, "r")
        return f.read().decode("utf-8")
    except:
        wx.MessageBox(
            _("Error loading file '{}': Decompression failed").format(filename),
            _("Error"),
            wx.OK,
            frame,
        )
        return None


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


# write data to filename (see atomicWrite), showing an error message box
# on failure. returns True on success.
def writeToFile(
    filename: str, data: AnyStr, frame: wx.TopLevelWindow, backup: bool = False
) -> bool:
    try:
        atomicWrite(filename, data, backup)

        return True

    except OSError as e:
        wx.MessageBox(
            _("Error writing file '{}': {}").format(filename, e.strerror or e),
            _("Error"),
            wx.OK,
            frame,
        )

        return False


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


# get a windows environment variable in its native unicode format, or None
# if not found
def getWindowsUnicodeEnvVar(name):
    import ctypes

    n = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)

    if n == 0:
        return None

    buf = ctypes.create_unicode_buffer("\0" * n)
    ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, n)

    return buf.value


# show PDF file, in the built-in viewer if it's enabled and available,
# otherwise in the external viewer application.
def showPDF(
    filename: str, cfgGl: "config.ConfigGlobal", frame: wx.TopLevelWindow
) -> None:
    import trelby.pdfviewer as pdfviewer

    if cfgGl.pdfUseBuiltinViewer and pdfviewer.isAvailable():
        pdfviewer.show(filename, cfgGl)
    else:
        showPDFExternal(filename, cfgGl, frame)


# show PDF file in the external viewer application.
def showPDFExternal(
    filename: str, cfgGl: "config.ConfigGlobal", frame: wx.TopLevelWindow
) -> None:
    def complain():
        wx.MessageBox(
            _(
                "PDF viewer application not found.\n\nYou can change your PDF viewer\nsettings at Edit/Settings/Misc."
            ),
            _("Error"),
            wx.OK,
            frame,
        )

    pdfProgram = cfgGl.pdfViewerPath
    pdfArgs = cfgGl.pdfViewerArgs

    # If configured pdf viewer does not exist, try finding one
    # automatically
    if not fileExists(pdfProgram):
        found = False

        regPDF, regArgs = getPDFViewer()

        if regPDF:
            wx.MessageBox(
                _("Currently set PDF viewer ({}) was not found.\nChange this in Edit/Settings/Misc.\n\nUsing the default PDF viewer instead:\n{}").format(
                    pdfProgram, regPDF
                ),
                _("Warning"),
                wx.OK,
                frame,
            )

            pdfProgram = regPDF
            pdfArgs = regArgs

            found = True

        if not found:
            complain()

            return

    if misc.isMac:
        # on Mac, we should use 'open', so wrap the whole call in that
        args = ["open", "-a", pdfProgram, filename]
        if pdfArgs:
            args = args + ["--args"] + pdfArgs.split()
        pdfProgram = "/usr/bin/open"
    else:
        # on Windows, Acrobat complains about "invalid path" if we
        # give the full path of the program as first arg, so give a
        # dummy arg.
        args = ["pdf"] + pdfArgs.split() + [filename]

    # there's a race condition in checking if the path exists, above, and
    # using it, below. if the file disappears between those two we get an
    # OSError exception from spawnv, so we need to catch it and handle it.

    # TODO: spawnv does not support Unicode paths as of this moment
    # (Python 2.4). for now, convert it to UTF-8 and hope for the best.
    try:
        os.spawnv(os.P_NOWAIT, pdfProgram.encode("UTF-8"), args)
    except OSError:
        complain()
