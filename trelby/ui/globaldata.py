# -*- coding: iso-8859-1 -*-

import os
import os.path

import wx

import trelby.misc as misc
import trelby.ui.fileio as fileio
import trelby.ui.mrufiles as mrufiles
import trelby.mypickle as mypickle
import trelby.opts as opts
import trelby.spellcheck as spellcheck
import trelby.util as util
import trelby.ui.viewmode as viewmode
import trelby.writinglog as writinglog


# older versions saved the recently used files list under the translated
# word for "Files" ("Files/1", "Files/2", ... in English, "File/1" etc. in
# Italian), so outside English it was lost whenever the language changed.
# it's now always saved as "Files"; this renames the old keys in 'vals'
# (from mypickle.Vars.makeVals) if they're for the current language.
def renameOldFilesKey(vals):
    old = _("Files")

    if (old == "Files") or ("Files" in vals) or (old not in vals):
        return

    for key in list(vals):
        if (key == old) or key.startswith(old + "/"):
            vals["Files" + key[len(old) :]] = vals.pop(key)


# keeps (hopefully all) global data
class GlobalData:

    # global variables previously floating around the trelby.py file
    mainFrame = None
    cfgGui = None
    cfgGl = None

    # cfgGl's key bindings (see config.ConfigGlobal.getKeyMap), which the
    # editor looks up the keys pressed in
    keyMap = {}

    # Trelby's own clipboard (a screenplay.ClipData, keeping element types),
    # shared by all scripts. the system clipboard is only used by the Copy /
    # Paste (system) commands.
    clipboard = None

    # whether the editor shows the margins and line break types (View /
    # Show formatting). not saved.
    showFormatting = False

    # constants
    (
        VIEWMODE_DRAFT,
        VIEWMODE_LAYOUT,
        VIEWMODE_SIDE_BY_SIDE,
    ) = list(range(3))

    # the side panel's tabs (see sidepanel.SidePanel)
    SIDE_OUTLINE, SIDE_NOTES, SIDE_READ_ALOUD = list(range(3))

    # available zoom levels, in percent
    ZOOM_LEVELS = [50, 67, 75, 90, 100, 125, 150, 175, 200, 250, 300]

    # the beat board's zoom levels, which go further out, to see more of
    # the board
    BOARD_ZOOM_LEVELS = [25, 33, 50, 67, 75, 90, 100, 125, 150, 175, 200]

    def __init__(self):

        self.confFilename = misc.confPath + "/default.conf"
        self.stateFilename = misc.confPath + "/state"
        self.scDictFilename = misc.confPath + "/spell_checker_dictionary"

        # the writing sessions in every script (see writinglog.py), loaded
        # at startup by loadWritingLog
        self.writingLogFilename = misc.confPath + "/writinglog.json"
        self.writingLog = writinglog.WritingLog()

        # why saving the writing log last failed, or None. it's saved
        # every minute or so, so that's not told in a message box each time.
        self.writingLogError = None

        # current script config path
        self.scriptSettingsPath = misc.confPath

        # global spell checker (user) dictionary
        self.scDict = spellcheck.Dict()

        # recently used files list
        self.mru = mrufiles.MRUFiles(5)

        if opts.conf:
            self.confFilename = opts.conf

        v = self.cvars = mypickle.Vars()

        v.addInt("posX", 0, "PositionX", -20, 9999)
        v.addInt("posY", 0, "PositionY", -20, 9999)

        # linux has bigger font by default so it needs a wider window
        defaultW = 750
        if misc.isUnix:
            defaultW = 800

        v.addInt("width", defaultW, "Width", 500, 9999)

        v.addInt("height", 830, "Height", 300, 9999)
        v.addInt(
            "viewMode",
            self.VIEWMODE_DRAFT,
            "ViewMode",
            self.VIEWMODE_DRAFT,
            self.VIEWMODE_SIDE_BY_SIDE,
        )

        v.addInt("zoom", 100, "Zoom", self.ZOOM_LEVELS[0], self.ZOOM_LEVELS[-1])

        # the beat board's own zoom level, shared by every tab's board
        v.addInt(
            "boardZoom",
            100,
            "BoardZoom",
            self.BOARD_ZOOM_LEVELS[0],
            self.BOARD_ZOOM_LEVELS[-1],
        )

        # the side panel with the outline, the notes and the table read's
        # controls: which of them it shows, and its width (whether it's
        # shown is below)
        v.addInt(
            "sideTab",
            self.SIDE_OUTLINE,
            "SideTab",
            self.SIDE_OUTLINE,
            self.SIDE_READ_ALOUD,
        )
        v.addInt("sideWidth", 240, "SideWidth", 120, 2000)

        v.addList("files", [], "Files", mypickle.StrUnicodeVar("", "", ""))

        v.makeDicts()
        v.setDefaults(self)

        # whether the tabs show their scripts' beat boards instead of the
        # scripts (see MyPanel.showBeatBoard). not saved: the app always
        # starts with the scripts.
        self.showBeatBoard = False

        # whether the side panel is shown. not saved either: the app always
        # starts with it hidden.
        self.showSidePanel = False

        # whether focus mode is on (see MyFrame.setFocusMode). not saved.
        self.focusMode = False

        self.height = min(
            self.height, wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y) - 50
        )

        self.vmDraft = viewmode.ViewModeDraft()
        self.vmLayout = viewmode.ViewModeLayout()
        self.vmSideBySide = viewmode.ViewModeSideBySide()

        self.setViewMode(self.viewMode)

        self.makeConfDir()

    def makeConfDir(self):
        makeDir = not util.fileExists(misc.confPath)

        if makeDir:
            try:
                os.mkdir(misc.toPath(misc.confPath), mode=0o755)
            except OSError as e:
                wx.MessageBox(
                    _("Error creating configuration directory\n'{}': {}").format(
                        misc.confPath, e.strerror or e
                    ),
                    _("Error"),
                    wx.OK,
                    None,
                )

    # set viewmode, the parameter is one of the VIEWMODE_ defines.
    def setViewMode(self, viewMode):
        self.viewMode = viewMode

        if viewMode == self.VIEWMODE_DRAFT:
            self.vm = self.vmDraft
        elif viewMode == self.VIEWMODE_LAYOUT:
            self.vm = self.vmLayout
        elif viewMode == self.VIEWMODE_SIDE_BY_SIDE:
            self.vm = self.vmSideBySide
        else:
            self.vm = self.vmDraft

    # whether the side panel is shown at the notes
    def notesShown(self):
        return self.showSidePanel and (self.sideTab == self.SIDE_NOTES)

    # the zoom level of what's shown: the beat board's while it's shown,
    # otherwise the script's
    def currentZoom(self):
        return self.boardZoom if self.showBeatBoard else self.zoom

    # return the zoom level 'step' levels away from the current one (see
    # currentZoom) (1 = next larger, -1 = next smaller). the current zoom
    # need not be one of the levels (the state file can be edited by hand).
    def getZoomStep(self, step):
        zoom = self.currentZoom()
        levels = self.BOARD_ZOOM_LEVELS if self.showBeatBoard else self.ZOOM_LEVELS

        if step > 0:
            larger = [z for z in levels if z > zoom]
            return larger[0] if larger else zoom
        else:
            smaller = [z for z in levels if z < zoom]
            return smaller[-1] if smaller else zoom

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        vals = self.cvars.makeVals(s)
        renameOldFilesKey(vals)
        self.cvars.load(vals, "", self)
        self.mru.items = self.files

    # save to a string and return that.
    def save(self):
        self.files = self.mru.items

        return self.cvars.save("", self)

    # save global spell checker dictionary to disk
    def saveScDict(self):
        fileio.writeToFile(self.scDictFilename, self.scDict.save(), self.mainFrame)

    # load the writing log. a file that can't be read is kept as
    # writinglog.json.bad, and the log starts again.
    def loadWritingLog(self):
        self.writingLog, err = writinglog.loadFile(self.writingLogFilename)

        if err:
            wx.MessageBox(
                _(
                    "The writing log could not be read, and has been started again. The old one was kept as\n\n{}\n\nThe error was: {}"
                ).format(self.writingLogFilename + ".bad", err),
                _("Error"),
                wx.OK,
                None,
            )

    # save the writing log if it has changed
    def saveWritingLog(self):
        log = self.writingLog

        if not log.dirty:
            return

        try:
            util.atomicWrite(self.writingLogFilename, log.save())
        except OSError as e:
            self.writingLogError = e.strerror or str(e)

            return

        log.dirty = False
        self.writingLogError = None
