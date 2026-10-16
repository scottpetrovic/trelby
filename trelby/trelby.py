# -*- coding: iso-8859-1 -*-

import gettext
import os
import os.path
import subprocess
import sys

import wx

import trelby
import trelby.config as config
import trelby.dialogs.spellcheckdlg as spellcheckdlg
import trelby.ui.configgui as configgui
import trelby.ui.fileio as fileio
import trelby.ui.gutil as gutil
import trelby.mcpserver.app as mcpapp
import trelby.misc as misc
import trelby.opts as opts
import trelby.util as util
import trelby.translations as translations
from trelby.ui.globaldata import GlobalData
from trelby.ui.trelbyframe import MyFrame

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


# besides returning it, this installs _ in builtins, which is where every
# other module gets it from. done on import, in the system's language, so
# it's there before anything is translated; OnInit installs the configured
# language once it has read the config.
_ = translations.trelby_translations_load()


class MyApp(wx.App):
    # set by the Language menu's "Restart now", for main() to start Trelby
    # again after it closes, with the scripts that were open
    restart = False
    restartFiles = []

    def OnInit(self):
        # replaced below if the config picks a language
        global _

        if (wx.MAJOR_VERSION != 4) or (wx.MINOR_VERSION < 0):
            wx.MessageBox(
                _("You seem to have an invalid version\n({}) of wxWidgets installed. This\nprogram needs version 4.x.").format(
                    wx.VERSION_STRING
                ),
                _("Error"),
                wx.OK,
            )
            sys.exit()

        # fixed name, so per-user data wx keeps (e.g. the built-in PDF
        # viewer's browser profile) goes to the same place for source runs
        # and the exe
        self.SetAppName("Trelby")

        # misc.init sets the paths (progPath, confPath) and platform flags
        # that GlobalData and everything after it rely on
        misc.init()
        gutil.init()

        gd = GlobalData()

        # for theming.currentCfgGui
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

        s = None
        confExists = util.fileExists(gd.confFilename)
        if confExists:
            s = fileio.loadFile(gd.confFilename, None)

        cfgGl = loadGlobalCfg(s)

        # switch to the language chosen in the Language menu. the config is
        # built again, since it translates the commands' descriptions.
        if cfgGl.language:
            _ = translations.trelby_translations_load(cfgGl.language)
            cfgGl = loadGlobalCfg(s)

        gutil.loadWxTranslations(translations.getLanguage(cfgGl.language))

        gd.cfgGl = cfgGl

        if not confExists:
            # we want to write out a default config file at startup for
            # various reasons, if no default config file yet exists
            fileio.writeToFile(gd.confFilename, cfgGl.save(), None)

        # errors are shown on the Theme settings page
        for err in config.loadCustomThemes():
            print("Skipped theme file", err, file=sys.stderr)

        # wx wants this done before any windows are created
        configgui.applyAppearance(cfgGl.theme)

        # cfgGl.scriptDir is the directory used on startup, while
        # misc.scriptDir is updated every time the user opens something in
        # a different directory.
        misc.scriptDir = cfgGl.scriptDir

        if util.fileExists(gd.stateFilename):
            s = fileio.loadFile(gd.stateFilename, None)

            if s:
                gd.load(s)

        # gd.load only sets the viewMode number from the state file, not
        # the ViewMode object (gd.vm) that goes with it
        gd.setViewMode(gd.viewMode)

        # refreshGuiConfig()
        gd.cfgGui = configgui.ConfigGui(gd.cfgGl, gd.zoom)

        if util.fileExists(gd.scDictFilename):
            s = fileio.loadFile(gd.scDictFilename, None)

            if s:
                gd.scDict.load(s)

        # built in two steps: init creates the first script tab, and a
        # MyCtrl's constructor already calls the frame through gd.mainFrame
        # (tab names, status bar, toolbar), so that has to be set first
        mainFrame = MyFrame(None, -1, "Trelby", gd, self)
        gd.mainFrame = mainFrame
        mainFrame.init()

        # for underlining misspelled words. it takes a tenth of a second.
        if gd.cfgGl.checkSpelling:
            spellcheckdlg.loadDict(mainFrame)

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


def loadGlobalCfg(s):
    """Return a ConfigGlobal with the defaults, plus the saved config s if
    it's not empty."""

    cfgGl = config.ConfigGlobal()
    cfgGl.setDefaults()

    if s:
        cfgGl.load(s)

    return cfgGl


def restartArgs(files):
    """Return the command line arguments that start Trelby again in the
    same mode, opening files."""

    args = []

    if opts.isTest:
        args.append("--test")

    if opts.conf:
        args += ["--conf", opts.conf]

    return args + files


def restartCommand(args):
    """Return the command and environment that start a new Trelby with the
    arguments args."""

    env = dict(os.environ)

    if getattr(sys, "frozen", False):
        # a new instance of the exe rather than a child of this one, whose
        # unpacked files are about to go away
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

        return [sys.executable] + args, env

    # from source, however it was started (trelby.py, the trelby entry
    # point, ...), and wherever the package is
    pkgParent = os.path.dirname(os.path.dirname(os.path.abspath(trelby.__file__)))
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (pkgParent, env.get("PYTHONPATH")) if p
    )

    return [
        sys.executable,
        "-c",
        "import trelby.trelby; trelby.trelby.main()",
    ] + args, env


def main():
    # Trelby.exe --mcp-bridge [--port N]: run as the stdio bridge to the MCP
    # server in a running Trelby (see mcpserver/server.py), for exe users with no
    # Python to run "python -m trelby.mcpserver --app" with
    if sys.argv[1:2] == ["--mcp-bridge"]:
        import trelby.mcpserver.server as mcpserver

        mcpserver.main(["--app"] + sys.argv[2:])

        return

    # OnInit changes to misc.progPath, but relative paths in the arguments
    # (--test's config directory, --conf) are from here
    startDir = os.getcwd()

    opts.init()

    myApp = MyApp(0)

    myApp.MainLoop()

    if myApp.restart:
        cmd, env = restartCommand(restartArgs(myApp.restartFiles))
        subprocess.Popen(cmd, cwd=startDir, env=env)
