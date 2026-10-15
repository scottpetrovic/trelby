# -*- coding: iso-8859-1 -*-

import gettext
import os
import os.path
import sys

import wx

import trelby
import trelby.config as config
import trelby.mcpapp as mcpapp
import trelby.misc as misc
import trelby.opts as opts
import trelby.util as util
import trelby.translations as translations
from trelby.globaldata import GlobalData
from trelby.trelbyframe import MyFrame

# Boolean to determine if toolbar should be shown or not.
toolbarshown = True

# keycodes
KC_CTRL_A = 1
KC_CTRL_B = 2
KC_CTRL_D = 4
KC_CTRL_E = 5
KC_CTRL_F = 6
KC_CTRL_N = 14
KC_CTRL_P = 16
KC_CTRL_V = 22


_ = translations.trelby_translations_load()


class MyApp(wx.App):

    def OnInit(self):

        if (wx.MAJOR_VERSION != 4) or (wx.MINOR_VERSION < 0):
            wx.MessageBox(
                _(
                    "You seem to have an invalid version\n({}) of wxWidgets installed. This\nprogram needs version 4.x.".format(
                        wx.VERSION_STRING
                    )
                ),
                _("Error"),
                wx.OK,
            )
            sys.exit()

        # fixed name, so per-user data wx keeps (e.g. the built-in PDF
        # viewer's browser profile) goes to the same place for source runs
        # and the exe
        self.SetAppName("Trelby")

        misc.init()
        util.init()

        gd = GlobalData()

        # for gutil.currentCfgGui
        self.gd = gd

        if misc.isWindows:
            major = sys.getwindowsversion()[0]
            if major < 5:
                wx.MessageBox(
                    _(
                        "You seem to have a version of Windows\nolder than Windows 2000, which is the minimum\nrequirement for this program."
                    ),
                    _("Error"),
                    wx.OK,
                )
                sys.exit()

        if not "unicode" in wx.PlatformInfo:
            wx.MessageBox(
                _(
                    "You seem to be using a non-Unicode build of\n wxWidgets. This is not supported."
                ),
                _("Error"),
                wx.OK,
            )
            sys.exit()

        os.chdir(misc.progPath)

        cfgGl = config.ConfigGlobal()
        gd.cfgGl = cfgGl
        cfgGl.setDefaults()

        if util.fileExists(gd.confFilename):
            s = util.loadFile(gd.confFilename, None)

            if s:
                cfgGl.load(s)
        else:
            # we want to write out a default config file at startup for
            # various reasons, if no default config file yet exists
            util.writeToFile(gd.confFilename, cfgGl.save(), None)

        # errors are shown on the Theme settings page
        for err in config.loadCustomThemes():
            print("Skipped theme file", err, file=sys.stderr)

        # wx wants this done before any windows are created
        config.applyAppearance(cfgGl.theme)

        # cfgGl.scriptDir is the directory used on startup, while
        # misc.scriptDir is updated every time the user opens something in
        # a different directory.
        misc.scriptDir = cfgGl.scriptDir

        if util.fileExists(gd.stateFilename):
            s = util.loadFile(gd.stateFilename, None)

            if s:
                gd.load(s)

        gd.setViewMode(gd.viewMode)

        # refreshGuiConfig()
        gd.cfgGui = config.ConfigGui(gd.cfgGl, gd.zoom)

        if util.fileExists(gd.scDictFilename):
            s = util.loadFile(gd.scDictFilename, None)

            if s:
                gd.scDict.load(s)

        mainFrame = MyFrame(None, -1, "Trelby", gd, self)
        gd.mainFrame = mainFrame
        mainFrame.init()

        for arg in opts.filenames:
            mainFrame.openScript(arg)

        mainFrame.Show(True)

        # windows needs this for some reason
        mainFrame.panel.ctrl.SetFocus()

        self.SetTopWindow(mainFrame)

        mainFrame.checkFonts()

        # start the MCP server if it's turned on. before offering recovery,
        # since calls queued after that wait until its dialog is closed.
        wx.CallAfter(mcpapp.configure, gd, mainFrame)

        # after the main window is up, so the question has a parent
        wx.CallAfter(mainFrame.offerRecovery)

        return True


def main():
    # Trelby.exe --mcp-bridge [--port N]: run as the stdio bridge to the MCP
    # server in a running Trelby (see mcpserver.py), for exe users with no
    # Python to run "python -m trelby.mcpserver --app" with
    if sys.argv[1:2] == ["--mcp-bridge"]:
        import trelby.mcpserver as mcpserver

        mcpserver.main(["--app"] + sys.argv[2:])

        return

    opts.init()

    myApp = MyApp(0)

    myApp.MainLoop()
