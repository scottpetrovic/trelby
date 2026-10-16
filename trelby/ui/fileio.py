import gzip
import os
import tempfile
from typing import AnyStr, Optional

import wx

import trelby.config as config
import trelby.misc as misc
import trelby.util as util
from trelby.error import MiscError, TrelbyError

# loading and writing files, and showing PDFs, with message boxes on errors


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

    if not util.fileExists(filename):
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


# write data to filename (see atomicWrite), showing an error message box
# on failure. returns True on success.
def writeToFile(
    filename: str, data: AnyStr, frame: wx.TopLevelWindow, backup: bool = False
) -> bool:
    try:
        util.atomicWrite(filename, data, backup)

        return True

    except OSError as e:
        wx.MessageBox(
            _("Error writing file '{}': {}").format(filename, e.strerror or e),
            _("Error"),
            wx.OK,
            frame,
        )

        return False


# show PDF file, in the built-in viewer if it's enabled and available,
# otherwise in the external viewer application.
def showPDF(
    filename: str, cfgGl: "config.ConfigGlobal", frame: wx.TopLevelWindow
) -> None:
    import trelby.ui.pdfviewer as pdfviewer

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
    if not util.fileExists(pdfProgram):
        found = False

        regPDF, regArgs = util.getPDFViewer()

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


# show PDF document 'pdfData' in an external viewer program. writes out a
# temporary file, first deleting all old temporary files, then opens PDF
# viewer application. 'mainFrame' is used as a parent for message boxes in
# case there are any errors.
def showTempPDF(
    pdfData: bytes, cfgGl: "config.ConfigGlobal", mainFrame: wx.TopLevelWindow
) -> None:
    try:
        try:
            util.removeTempFiles(misc.tmpPrefix)

            fd, filename = tempfile.mkstemp(prefix=misc.tmpPrefix, suffix=".pdf")

            try:
                if isinstance(pdfData, str):
                    os.write(fd, pdfData)
                else:
                    os.write(fd, pdfData)
            finally:
                os.close(fd)

            showPDF(filename, cfgGl, mainFrame)

        except IOError as xxx_todo_changeme:
            (errno, strerror) = xxx_todo_changeme.args
            raise MiscError("IOError: %s" % strerror)

    except TrelbyError as e:
        wx.MessageBox(
            _("Error writing temporary PDF file: {}").format(e),
            _("Error"),
            wx.OK,
            mainFrame,
        )
