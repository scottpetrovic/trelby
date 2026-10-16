# -*- coding: iso-8859-1 -*-

import os
import os.path

import wx

import trelby.misc as misc
import trelby.mypickle as mypickle
import trelby.opts as opts
import trelby.spellcheck as spellcheck
import trelby.util as util
import trelby.viewmode as viewmode


# keeps (hopefully all) global data
class GlobalData:

    # global variables previously floating around the trelby.py file
    mainFrame = None
    cfgGui = None
    cfgGl = None

    # constants
    (
        VIEWMODE_DRAFT,
        VIEWMODE_LAYOUT,
        VIEWMODE_SIDE_BY_SIDE,
    ) = list(range(3))

    # available zoom levels, in percent
    ZOOM_LEVELS = [50, 67, 75, 90, 100, 125, 150, 175, 200, 250, 300]

    def __init__(self):

        self.confFilename = misc.confPath + "/default.conf"
        self.stateFilename = misc.confPath + "/state"
        self.scDictFilename = misc.confPath + "/spell_checker_dictionary"

        # current script config path
        self.scriptSettingsPath = misc.confPath

        # global spell checker (user) dictionary
        self.scDict = spellcheck.Dict()

        # recently used files list
        self.mru = misc.MRUFiles(5)

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

        v.addBool("showOutline", False, "ShowOutline")
        v.addInt("outlineWidth", 240, "OutlineWidth", 120, 2000)

        v.addList("files", [], _("Files"), mypickle.StrUnicodeVar("", "", ""))

        v.makeDicts()
        v.setDefaults(self)

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
            except OSError(os.errno, os.strerror):
                wx.MessageBox(
                    _("Error creating configuration directory\n'{}': {}").format(
                        misc.confPath, os.strerror
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

    # return the zoom level 'step' levels away from the current one (1 =
    # next larger, -1 = next smaller). the current zoom need not be one of
    # ZOOM_LEVELS (the state file can be edited by hand).
    def getZoomStep(self, step):
        if step > 0:
            larger = [z for z in self.ZOOM_LEVELS if z > self.zoom]
            return larger[0] if larger else self.zoom
        else:
            smaller = [z for z in self.ZOOM_LEVELS if z < self.zoom]
            return smaller[-1] if smaller else self.zoom

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        self.cvars.load(self.cvars.makeVals(s), "", self)
        self.mru.items = self.files

    # save to a string and return that.
    def save(self):
        self.files = self.mru.items

        return self.cvars.save("", self)

    # save global spell checker dictionary to disk
    def saveScDict(self):
        util.writeToFile(self.scDictFilename, self.scDict.save(), self.mainFrame)
