# -*- coding: iso-8859-1 -*-

import copy
import os
import os.path
import signal
import webbrowser

import wx
import wx.svg

import trelby.dialogs.recoverydlg as recoverydlg
import trelby.dialogs.cfgdlg as cfgdlg
import trelby.commands as commands
import trelby.dialogs.commandsdlg as commandsdlg
import trelby.config as config
import trelby.ui.configgui as configgui
import trelby.ui.fileio as fileio
import trelby.formats as formats
import trelby.ui.gutil as gutil
import trelby.ui.homeview as homeview
import trelby.mcpserver.app as mcpapp
import trelby.ui.icons as icons
import trelby.ui.menubar as menubar
import trelby.ui.menus as menus
import trelby.misc as misc
import trelby.ui.scriptactions as scriptactions
import trelby.dialogs.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.dialogs.spellcheckdlg as spellcheckdlg
import trelby.ui.splash as splash
import trelby.ui.statusbar as statusbar
import trelby.ui.tablereader as tablereader
import trelby.ui.tabctrl as tabctrl
import trelby.ui.theming as theming
import trelby.ui.toolbar as toolbar
import trelby.translations as translations
import trelby.util as util
from trelby.ui.ids import *
from trelby.ui.trelbypanel import MyPanel


# lets scripts, and the files of the import formats, be dropped on the main
# window to open them (formats.openFormat)
class ScriptDropTarget(wx.FileDropTarget):
    def __init__(self, frame):
        wx.FileDropTarget.__init__(self)

        self.frame = frame

    def OnDragOver(self, x, y, defResult):
        return wx.DragCopy

    def OnDropFiles(self, x, y, filenames):
        # opened after the drop has finished, so that the program the
        # files came from doesn't wait for the loading or a message box
        wx.CallAfter(self.frame.openFiles, list(filenames))

        return True


class MyFrame(wx.Frame):

    def __init__(self, parent, id, title, gd, myApp):
        wx.Frame.__init__(self, parent, id, title, name="Trelby")

        # first, so that everything created in it, the dialogs included,
        # is laid out in the same direction
        self.SetLayoutDirection(gutil.layoutDirection)

        if misc.isUnix:
            # automatically reaps zombies
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)

        self.gd = gd
        self.myApp = myApp

        # reads the current script aloud (Tools / Read aloud)
        self.reader = tablereader.TableReader(self)

        self.SetSizeHints(gd.cvars.getMin("width"), gd.cvars.getMin("height"))

        self.Move(gd.posX, gd.posY)
        self.SetSize(wx.Size(gd.width, gd.height))

        util.removeTempFiles(misc.tmpPrefix)

        self.mySetIcons()
        # Windows' native menu bar has a fixed, cramped height, so there we
        # draw our own, with the toolbar below it in the sizer instead of
        # being managed by the frame
        self.ownMenuBar = misc.isWindows

        if self.ownMenuBar:
            self.menuBar = menubar.MyMenuBar(self, self.getCfgGui)
        else:
            self.menuBar = wx.MenuBar()

        # the menus, keyboard menu commands and toolbar buttons (see
        # menus.py). {name: menus.Action}, and {key: wx.Menu} for the
        # submenus the toolbar pops up.
        menuTable, otherActions = menus.makeTable()
        self.actions = {
            a.name: a for a in menus.allActions(menuTable, otherActions)
        }
        self.popupMenus = menus.build(self.menuBar, menuTable, gd, self.OnLanguage)


        if self.ownMenuBar:
            self.toolBar = wx.ToolBar(self, style=wx.TB_HORIZONTAL | wx.TB_NODIVIDER)
        else:
            self.SetMenuBar(self.menuBar)
            self.toolBar = self.CreateToolBar(wx.TB_HORIZONTAL)

        self.tools = toolbar.MainToolBar(self.toolBar, gd, self.runBarAction)
        self.tools.fill()

        self.statusBar = statusbar.MainStatusBar(self, gd, self.runBarAction)

        self.Bind(wx.EVT_MOVE, self.OnMove)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        vsizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(vsizer)

        if self.ownMenuBar:
            vsizer.Add(self.menuBar, 0, wx.EXPAND)
            vsizer.Add(self.toolBar, 0, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.noFSBtn = tabctrl.MyFSButton(self, -1, self.getCfgGui)
        self.noFSBtn.SetToolTip(_("Exit fullscreen"))
        self.noFSBtn.Show(False)
        hsizer.Add(self.noFSBtn)

        self.Bind(wx.EVT_BUTTON, self.ToggleFullscreen, id=self.noFSBtn.GetId())

        self.tabCtrl = tabctrl.MyTabCtrl(self, -1, self.getCfgGui)
        hsizer.Add(self.tabCtrl, 1, wx.EXPAND)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        # where the tabs' pages are shown
        self.tabArea = tabctrl.MyTabCtrl2(self, -1, self.tabCtrl)
        vsizer.Add(self.tabArea, 1, wx.EXPAND)

        # whether the Home screen is shown in place of the tabs, the
        # toolbar and the status bar, which it is while no script is open
        # (see setHomeShown)
        self.homeShown = False

        self.home = homeview.HomeView(self, self)
        self.home.Hide()
        vsizer.Add(self.home, 1, wx.EXPAND)

        vsizer.Add(self.statusBar, 0, wx.EXPAND)

        self.Bind(wx.EVT_MENU_HIGHLIGHT_ALL, self.OnMenuHighlight)

        self.tabCtrl.setPageChangedFunc(self.OnPageChange)
        self.tabCtrl.setNewTabFunc(lambda: self.runAction("NewScript"))
        self.tabCtrl.setCloseFunc(self.closeScript)
        self.applyThemeColors()

        menus.bind(self, self.actions.values())

        self.menuBar.Check(
            {
                gd.VIEWMODE_DRAFT: ID_VIEW_STYLE_DRAFT,
                gd.VIEWMODE_LAYOUT: ID_VIEW_STYLE_LAYOUT,
            }.get(gd.viewMode, ID_VIEW_STYLE_SIDE_BY_SIDE),
            True,
        )
        self.menuBar.Check(ID_SHOW_HIDE_TOOLBAR, True)
        self.checkSideItems()
        self.menuBar.Check(ID_VIEW_BEAT_BOARD, gd.showBeatBoard)

        self.Bind(
            wx.EVT_MENU_RANGE,
            self.OnMRUFile,
            id=gd.mru.getIds()[0],
            id2=gd.mru.getIds()[1],
        )
        self.Bind(wx.EVT_MENU, self.OnClearRecentFiles, id=gd.mru.clearId)

        # alternate zoom shortcuts the menu labels can't express: CTRL-+
        # (shifted '=' on many keyboards) and the numeric keypad
        accels = [
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("="), ID_VIEW_ZOOM_IN),
            (wx.ACCEL_CTRL, wx.WXK_NUMPAD_ADD, ID_VIEW_ZOOM_IN),
            (wx.ACCEL_CTRL, wx.WXK_NUMPAD_SUBTRACT, ID_VIEW_ZOOM_OUT),
            (wx.ACCEL_CTRL, wx.WXK_NUMPAD0, ID_VIEW_ZOOM_RESET),
        ]

        # a native menu bar handles its items' own accelerators
        if self.ownMenuBar:
            accels += self.menuBar.getAccelEntries()

        self.SetAcceleratorTable(wx.AcceleratorTable(accels))

        # the windows in it without drop targets of their own pass drops on
        # to it
        self.SetDropTarget(ScriptDropTarget(self))

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

        self.autosaveTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnAutosaveTimer, self.autosaveTimer)

        self.Layout()

    # with no script open, so the Home screen is shown. the first tab is
    # still made, as the hidden empty script the next one opened or made
    # goes in.
    def init(self):
        self.updateKeyMap()
        self.panel = self.createNewPanel()
        self.setHomeShown(True)
        self.updateAutosaveTimer()

    # show the Home screen in place of the tabs, or the tabs again. it's
    # shown while no script is open: at startup, and after closing the last
    # one, whose tab stays, hidden, with an empty script in it. opening or
    # making a script puts it in that tab (see leaveHome), as the current
    # tab's script is replaced when it's untouched.
    def setHomeShown(self, show):
        self.homeShown = show

        if show:
            self.reader.stop()
            self.home.refresh()

        self.home.Show(show)
        self.tabArea.Show(not show)
        self.updateBars()
        self.updateTitle()
        self.focusCurrent()

    # leave the Home screen if the current tab's script is no longer the
    # empty one, after something was opened in it. if opening it failed,
    # Home stays, with the recent files as they now are.
    def leaveHome(self):
        if not self.homeShown:
            return

        if self.panel.ctrl.isUntouched():
            self.home.refresh()
        else:
            self.setHomeShown(False)

    # show or hide the tab bar, the toolbar and the status bar for the
    # Home screen, fullscreen and the View menu's toolbar item
    def updateBars(self):
        full = self.IsFullScreen()
        home = self.homeShown

        self.noFSBtn.Show(full)
        self.tabCtrl.Show(not home)
        self.statusBar.Show(not (full or home))

        # in fullscreen the frame hides the bars it manages itself
        if self.ownMenuBar:
            self.menuBar.Show(not full)

        if self.ownMenuBar or not full:
            self.toolBar.Show(
                not (full or home) and self.menuBar.IsChecked(ID_SHOW_HIDE_TOOLBAR)
            )

        self.Layout()

    # give the keyboard focus to the Home screen or the current script
    def focusCurrent(self):
        if self.homeShown:
            self.home.SetFocus()
        else:
            self.panel.ctrl.SetFocus()

    # (re)start or stop the autosave timer according to the configuration
    def updateAutosaveTimer(self):
        minutes = self.gd.cfgGl.autosaveInterval

        if minutes > 0:
            self.autosaveTimer.Start(minutes * 60 * 1000)
        else:
            self.autosaveTimer.Stop()

    def OnAutosaveTimer(self, event=None):
        for c in self.getCtrls():
            c.autosave()

    # show the current script's autosave state in the status bar. if ctrl
    # is given, only does anything if that's the current script.
    def updateAutosaveStatus(self, ctrl=None):
        panel = getattr(self, "panel", None)

        if panel and ((ctrl is None) or (ctrl is panel.ctrl)):
            self.statusBar.showAutosave(panel.ctrl)

    # show the state of the script in the trelbyctrl.MyCtrl ctrl in the
    # toolbar, the status bar and the Undo / Redo menu items
    def showScriptState(self, ctrl):
        ed = ctrl.ed

        self.tools.setElemTypes(ctrl.sp.cfg)
        self.tools.setState(
            ctrl.sp.lines[ed.line].lt, ed.getFormatState(), ed.getCenteredState()
        )
        self.statusBar.showScript(ctrl)

        canUndo = ed.undoHistory.canUndo()
        canRedo = ed.undoHistory.canRedo()

        self.menuBar.Enable(ID_EDIT_UNDO, canUndo)
        self.menuBar.Enable(ID_EDIT_REDO, canRedo)
        self.tools.enableUndo(canUndo, canRedo)

    # if recovery copies were left over by a session that didn't exit
    # cleanly, offer to restore them
    def offerRecovery(self):
        recoverydlg.offerRecovery(self)

    def mySetIcons(self):
        wx.Image.AddHandler(wx.PNGHandler())

        ib = wx.IconBundle()

        for sz in ("16", "32", "64", "128", "256"):
            ib.AddIcon(wx.Icon(icons.getBitmap("trelby/resources/icon%s.png" % sz)))

        self.SetIcons(ib)

    # add a tab with an empty script. addPage selects it, so OnPageChange
    # has set self.panel to it by the time this returns. the tab text is
    # set again here because the MyCtrl's constructor set it before the
    # page was added, when findPage couldn't find it.
    def createNewPanel(self):
        newPanel = MyPanel(self.tabCtrl.getTabParent(), -1, self.gd)
        self.tabCtrl.addPage(newPanel, "")
        newPanel.ctrl.setTabText()
        newPanel.ctrl.SetFocus()

        return newPanel

    # show the current script's name in the window title. if ctrl is
    # given, only does anything if that's the current script.
    #
    # this, updateAutosaveStatus and OnUpdateMenuItem can be called while
    # init creates the first tab, before self.panel exists, hence getattr.
    def updateTitle(self, ctrl=None):
        panel = getattr(self, "panel", None)

        if not panel or ((ctrl is not None) and (ctrl is not panel.ctrl)):
            return

        if self.homeShown:
            self.SetTitle("Trelby")
        else:
            self.SetTitle("Trelby - %s" % panel.ctrl.getTitleText())

    def setTabText(self, panel, text):
        i = self.findPage(panel)

        if i != -1:
            # strip out ".trelby" suffix from tab names (it's a bit
            # complicated since if we open the same file multiple times,
            # we have e.g. "foo.trelby" and "foo.trelby-2", so actually
            # we just strip out ".trelby" if it's found anywhere in the
            # string)

            s = text.replace(".trelby", "")
            self.tabCtrl.setTabText(i, s)

    # iterates over all tabs and finds out the corresponding page number
    # for the given panel.
    def findPage(self, panel):
        for i in range(self.tabCtrl.getPageCount()):
            p = self.tabCtrl.getPage(i)
            if p == panel:
                return i

        return -1

    # get list of MyCtrl objects for all open scripts
    def getCtrls(self):
        l = []

        for i in range(self.tabCtrl.getPageCount()):
            l.append(self.tabCtrl.getPage(i).ctrl)

        return l

    # returns True if any open script has been modified
    def isModifications(self):
        for c in self.getCtrls():
            if c.sp.isModified():
                return True

        return False

    # rebuild gd.keyMap from the global config. MyCtrl.OnKeyChar looks keys
    # up in it, and calls MyCtrl.cmd<name>(cs) for an editing command, and
    # On<name>() here, with no event, for a menu command, which is why the
    # On* handlers default event to None.
    def updateKeyMap(self):
        self.gd.keyMap = self.gd.cfgGl.getKeyMap()

        if commands.getConflictingKeys(self.gd.cfgGl.commands) != None:
            wx.MessageBox(
                _(
                    "You have at least one key bound to more than one\ncommand. The program will not work correctly until\nyou fix this."
                ),
                _("Warning"),
                wx.OK,
                self,
            )

    # open script, in the current tab if it's untouched, or in a new one
    # otherwise
    def openScript(self, filename):
        if not self.tabCtrl.getPage(self.findPage(self.panel)).ctrl.isUntouched():
            self.panel = self.createNewPanel()

        # absolute, since the Home screen shows the recent files' folders
        if self.panel.ctrl.loadFile(filename):
            self.gd.mru.add(os.path.abspath(filename))

        self.panel.ctrl.updateScreen()
        self.leaveHome()

    def checkFonts(self):
        names = ["Normal", "Bold", "Italic", "Bold-Italic"]
        failed = []

        for i, fi in enumerate(self.gd.cfgGui.fonts):
            if not gutil.isFixedWidth(fi.font):
                failed.append(names[i])

        if failed:
            wx.MessageBox(
                _(
                    "The fonts listed below are not fixed width and\nwill cause the program not to function correctly.\nPlease change the fonts at Edit/Settings.\n\n\n"
                ).join(failed),
                _("Error"),
                wx.OK,
                self,
            )

    # If we get focus, pass it on to ctrl, or the Home screen.
    def OnFocus(self, event):
        self.focusCurrent()

    def OnMenuHighlight(self, event):
        # default implementation modifies status bar, so we need to
        # override it and do nothing
        pass

    def OnPageChange(self, page):
        self.reader.stop()
        self.panel = self.tabCtrl.getPage(page)
        self.panel.ctrl.SetFocus()
        self.panel.ctrl.updateCommon()
        self.updateTitle()
        self.updateAutosaveStatus()

    def selectScript(self, toNext):
        current = self.tabCtrl.getSelectedPageIndex()
        pageCnt = self.tabCtrl.getPageCount()

        if toNext:
            pageNr = current + 1
        else:
            pageNr = current - 1

        if pageNr == -1:
            pageNr = pageCnt - 1
        elif pageNr == pageCnt:
            pageNr = 0

        if pageNr == current:
            # only one tab, nothing to do
            return

        self.tabCtrl.selectPage(pageNr)

    # a new script, laid out in the format with the given key (see
    # scriptformats), or as a screenplay
    def OnNewScript(self, formatKey=None):
        # on the Home screen, the hidden tab's empty script is the new one
        if self.homeShown:
            self.setHomeShown(False)
        else:
            self.panel = self.createNewPanel()

        if formatKey:
            self.panel.ctrl.useFormat(formatKey)

    def OnMRUFile(self, event):
        self.openRecent(event.GetId() - self.gd.mru.getIds()[0])

    # open the i'th recent file, or if it's gone, say so and take it off
    # the list
    def openRecent(self, i):
        filename = self.gd.mru.get(i)

        if not os.path.exists(filename):
            wx.MessageBox(
                _(
                    "File not found:\n\n{}\n\nIt has been removed from the recent files list."
                ).format(filename),
                _("Error"),
                wx.OK,
                self,
            )
            self.removeRecent(i)

            return

        self.openScript(filename)

    # take the i'th file off the recent files
    def removeRecent(self, i):
        self.gd.mru.remove(i)

        if self.homeShown:
            self.home.refresh()

    def OnClearRecentFiles(self, event=None):
        self.gd.mru.clear()

        if self.homeShown:
            self.home.refresh()

    def OnOpen(self, event=None):
        dlg = wx.FileDialog(
            self,
            _("File to open"),
            misc.scriptDir,
            wildcard=_("Trelby files (*.trelby)")
            + "|*.trelby|"
            + _("All files")
            + "|*",
            style=wx.FD_OPEN,
        )

        if dlg.ShowModal() == wx.ID_OK:
            misc.scriptDir = dlg.GetDirectory()
            self.openScript(dlg.GetPath())

        dlg.Destroy()

    # import a script in the formats.Format fmt
    def OnImportScript(self, fmt):
        dlg = wx.FileDialog(
            self,
            _("File to import"),
            misc.scriptDir,
            wildcard="%s|%s|*" % (fmt.getWildcard(), _("All files")),
            style=wx.FD_OPEN,
        )

        if dlg.ShowModal() == wx.ID_OK:
            misc.scriptDir = dlg.GetDirectory()

            self.importScript(dlg.GetPath(), fmt)

        dlg.Destroy()

    # import the file at path in the formats.Format fmt, in the current tab
    # if it's untouched, or in a new one otherwise
    def importScript(self, path, fmt):
        if not self.tabCtrl.getPage(self.findPage(self.panel)).ctrl.isUntouched():
            self.panel = self.createNewPanel()

        self.panel.ctrl.importFile(path, fmt)
        self.panel.ctrl.updateScreen()
        self.leaveHome()

    # open files dropped on the window: scripts are opened and the import
    # formats' files imported, each in its own tab. returns the names of
    # the ones that are neither.
    def openFiles(self, paths):
        bad = []

        for path in paths:
            fmt = formats.openFormat(path)

            if fmt is formats.SCRIPT:
                self.openScript(path)
            elif fmt:
                self.importScript(path, fmt)
            else:
                bad.append(os.path.basename(path))

        if bad:
            gutil.messageBox(
                _("These files are not scripts Trelby can open:")
                + "\n\n"
                + "\n".join(bad),
                _("Error"),
                wx.OK | wx.ICON_ERROR,
                self,
            )

        return bad

    def OnCloseScript(self, event=None):
        self.closeScript(self.tabCtrl.getSelectedPageIndex())

    # close the script in tab i, from File / Close or the tab's close
    # button, after asking about unsaved changes. closing the last one
    # empties its tab and shows the Home screen.
    def closeScript(self, i):
        ctrl = self.tabCtrl.getPage(i).ctrl

        if not ctrl.canBeClosed():
            return

        ctrl.removeRecovery()

        if self.tabCtrl.getPageCount() > 1:
            self.tabCtrl.deletePage(i)
        else:
            ctrl.createEmptySp()
            ctrl.updateScreen()
            self.setHomeShown(True)

    def OnSettings(self):
        dlg = cfgdlg.CfgDlg(
            self,
            copy.deepcopy(self.gd.cfgGl),
            self.applyGlobalCfg,
            True,
            self.gd,
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.applyGlobalCfg(dlg.cfg)

        dlg.Destroy()

    # apply the global config newCfgGl to all scripts and the window, and
    # save it unless writeCfg is False
    def applyGlobalCfg(self, newCfgGl, writeCfg=True):
        oldCfgGl = self.gd.cfgGl

        self.gd.cfgGl = copy.deepcopy(newCfgGl)

        # if user has ventured from the old default directory, keep it as
        # the current one, otherwise set the new default as current.
        if misc.scriptDir == oldCfgGl.scriptDir:
            misc.scriptDir = self.gd.cfgGl.scriptDir

        # must be done before refreshGuiConfig, since the screen colors
        # depend on whether the theme is dark. compares Theme objects, as
        # reloading the custom themes can change one under the same name.
        appearanceChanged = (
            config.findTheme(self.gd.cfgGl.theme) is not self.gd.cfgGui.themeChoice
        )

        if appearanceChanged:
            configgui.applyAppearance(self.gd.cfgGl.theme)

        self.gd.cfgGl.recalc()
        self.refreshGuiConfig()
        self.updateKeyMap()

        if self.gd.cfgGl.checkSpelling:
            spellcheckdlg.loadDict(self)

        # every script keeps a reference to the global config, which has
        # just been replaced by a copy
        for c in self.getCtrls():
            c.sp.cfgGl = self.gd.cfgGl
            c.refreshCache()
            c.makeLineVisible(c.ed.line)
            c.adjustScrollBar()

        self.panel.ctrl.updateScreen()

        # in case tab colors have been changed
        self.tabCtrl.Refresh(False)
        self.tools.refreshColors()
        self.noFSBtn.Refresh(False)
        self.applyThemeColors()
        self.home.Refresh(False)

        # and the open dialogs, like the settings dialog this may have been
        # applied from
        theming.themeAllWindows()

        # the toolbar icons' color depends on the theme
        if appearanceChanged or (
            self.gd.cfgGl.toolbarIconSize != oldCfgGl.toolbarIconSize
        ):
            self.tools.fill()
            self.SendSizeEvent()
            self.panel.ctrl.updateCommon()

        if self.gd.cfgGl.autosaveInterval != oldCfgGl.autosaveInterval:
            self.updateAutosaveTimer()

        if (self.gd.cfgGl.mcpEnabled, self.gd.cfgGl.mcpPort) != (
            oldCfgGl.mcpEnabled,
            oldCfgGl.mcpPort,
        ):
            mcpapp.configure(self.gd, self)

        if writeCfg:
            fileio.writeToFile(
                self.gd.confFilename, self.gd.cfgGl.save(), self
            )

        self.checkFonts()

    # remake the screen fonts and colors for the global config and zoom
    def refreshGuiConfig(self):
        self.gd.cfgGui = configgui.ConfigGui(self.gd.cfgGl, self.gd.zoom)

    # run the menus.Action with the given name for a toolbar or status bar
    # control, and give the keyboard focus back to the script
    def runBarAction(self, name):
        self.runAction(name)
        self.focusCurrent()

    # the LoadSettings / SaveSettingsAs keyboard commands. the settings
    # dialog has buttons for these too.
    def OnLoadSettings(self, event=None):
        path = cfgdlg.askSettingsFile(self, self.gd.confFilename, False)
        if not path:
            return

        c = cfgdlg.loadGlobalCfg(path, self)
        if c:
            self.gd.confFilename = path
            self.applyGlobalCfg(c, False)

    def OnSaveSettingsAs(self, event=None):
        path = cfgdlg.askSettingsFile(self, self.gd.confFilename, True)
        if not path:
            return

        if fileio.writeToFile(path, self.gd.cfgGl.save(), self):
            self.gd.confFilename = path

    # from the View menu item, which wx has already (un)checked, or its
    # keyboard command
    def OnToggleShowFormatting(self):
        self.gd.showFormatting = not self.gd.showFormatting
        self.menuBar.Check(ID_VIEW_SHOW_FORMATTING, self.gd.showFormatting)
        self.panel.ctrl.Refresh(False)

    # from the View menu item or the toolbar button, which share an id, or
    # the keyboard command
    def OnToggleSidePanel(self):
        self.setShowSidePanel(not self.gd.showSidePanel)

    # from View / Outline, Notes or Read aloud, or their keyboard commands:
    # show the side panel at that tab (GlobalData.SIDE_*), or hide it if it's
    # already showing it
    def OnToggleSideTab(self, tab):
        if self.gd.showSidePanel and (self.gd.sideTab == tab):
            self.setShowSidePanel(False)
        else:
            self.showSideTab(tab)

    # show the side panel at the given tab in all tabs
    def showSideTab(self, tab):
        self.gd.sideTab = tab

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).showSideTab(tab)

        self.setShowSidePanel(True)

    # show or hide the side panel in all tabs, keeping the View menu items
    # and the toolbar button in sync
    def setShowSidePanel(self, show):
        self.gd.showSidePanel = show

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).showSide(show)

        self.checkSideItems()
        self.toolBar.ToggleTool(ID_VIEW_SIDE_PANEL, show)

    def checkSideItems(self):
        gd = self.gd
        self.menuBar.Check(ID_VIEW_SIDE_PANEL, gd.showSidePanel)
        self.menuBar.Check(
            ID_VIEW_SHOW_OUTLINE,
            gd.showSidePanel and (gd.sideTab == gd.SIDE_OUTLINE),
        )
        self.menuBar.Check(ID_VIEW_SHOW_NOTES, gd.notesShown())
        self.menuBar.Check(
            ID_VIEW_SHOW_READ_ALOUD,
            gd.showSidePanel and (gd.sideTab == gd.SIDE_READ_ALOUD),
        )

    # the table read (self.reader) started, stopped, paused or went on to
    # another element: show it in the Read aloud tabs
    def readerChanged(self):
        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).side.readAloud.updateState()

    # from the View menu item or the toolbar button, which share an id, or
    # the keyboard command
    def OnToggleBeatBoard(self):
        self.setShowBeatBoard(not self.gd.showBeatBoard)

    # show the beat board in every tab instead of the script and the
    # outline, or the other way around, keeping the View menu item and the
    # toolbar in sync
    def setShowBeatBoard(self, show):
        self.reader.stop()
        self.gd.showBeatBoard = show
        self.menuBar.Check(ID_VIEW_BEAT_BOARD, show)
        self.tools.setBoardShown(show)

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).showBeatBoard(show)

        # the board has its own zoom level
        self.statusBar.updateZoom()

        self.panel.ctrl.SetFocus()
        self.panel.ctrl.updateCommon()

    # use the theme's colors for the status bar and the parts of each
    # script's panel not drawn by MyCtrl
    def applyThemeColors(self):
        cfgGui = self.gd.cfgGui

        theming.setTitleBarColors(self, cfgGui)

        self.statusBar.applyTheme(cfgGui)

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).applyTheme(cfgGui)

    def ShowHideToolbar(self, event=None):
        self.updateBars()

    # from the View menu items, or the keyboard commands
    def setViewMode(self, mode):
        self.menuBar.Check(
            {
                self.gd.VIEWMODE_DRAFT: ID_VIEW_STYLE_DRAFT,
                self.gd.VIEWMODE_LAYOUT: ID_VIEW_STYLE_LAYOUT,
            }.get(mode, ID_VIEW_STYLE_SIDE_BY_SIDE),
            True,
        )
        self.gd.setViewMode(mode)

        for c in self.getCtrls():
            c.refreshCache()

        c = self.panel.ctrl
        c.makeLineVisible(c.ed.line)
        c.updateScreen()

    def OnZoomIn(self, event=None):
        self.setZoom(self.gd.getZoomStep(1))

    def OnZoomOut(self, event=None):
        self.setZoom(self.gd.getZoomStep(-1))

    def OnZoomReset(self, event=None):
        self.setZoom(100)

    # set zoom level (in percent) for all open scripts, or while the beat
    # board is shown, for the boards (see setBoardZoom)
    def setZoom(self, zoom, pos=None):
        if self.gd.showBeatBoard:
            self.setBoardZoom(zoom, pos)

            return

        if zoom == self.gd.zoom:
            return

        self.gd.zoom = zoom
        self.statusBar.updateZoom()

        # zooming scales the screen fonts in gd.cfgGui, which all tabs
        # share, so it's rebuilt once. each tab's page size and mm2p
        # follow from the font sizes, so refreshCache recomputes them.
        self.refreshGuiConfig()

        for c in self.getCtrls():
            c.refreshCache()

        c = self.panel.ctrl
        c.makeLineVisible(c.ed.line)
        c.updateScreen()

    # set the beat boards' zoom level (in percent). the current tab's board
    # keeps the point at pos (in its window, by default the middle) where
    # it is.
    def setBoardZoom(self, zoom, pos=None):
        if zoom == self.gd.boardZoom:
            return

        self.gd.boardZoom = zoom
        self.statusBar.updateZoom()

        for i in range(self.tabCtrl.getPageCount()):
            page = self.tabCtrl.getPage(i)
            page.board.setZoom(zoom, pos if page is self.panel else None)

    def ToggleFullscreen(self, event=None):
        # FULLSCREEN_ALL only hides the bars the frame manages, so
        # updateBars does the rest
        self.ShowFullScreen(not self.IsFullScreen(), wx.FULLSCREEN_ALL)
        self.updateBars()
        self.focusCurrent()

    def OnSpellCheckerDictionaryDlg(self, event=None):
        dlg = spellcheckcfgdlg.SCDictDlg(self, copy.deepcopy(self.gd.scDict), True)

        if dlg.ShowModal() == wx.ID_OK:
            self.gd.scDict = dlg.scDict
            self.gd.saveScDict()

        dlg.Destroy()

    # run the menus.Action with the given name
    def runAction(self, name):
        menus.runAction(self, self.actions[name])

    # pop up the menu with the given key (see menus.Menu) below the mouse,
    # for the toolbar buttons
    def popupMenu(self, key):
        self.PopupMenu(self.popupMenus[key])

    def OnHelpCommands(self, event=None):
        dlg = commandsdlg.CommandsDlg(self.gd.cfgGl)
        dlg.Show()

    def OnHelpManual(self, event=None):
        webbrowser.open("file://" + misc.getFullPath("trelby/manual.html"))

    def OnLanguage(self, language):
        if language == self.gd.cfgGl.language:
            return

        self.gd.cfgGl.language = language
        fileio.writeToFile(self.gd.confFilename, self.gd.cfgGl.save(), self)

        # in the new language, which whoever picked it can presumably read
        newGettext = translations.getTranslation(language).gettext

        dlg = wx.MessageDialog(
            self,
            newGettext("Language change needs a restart."),
            newGettext("Language"),
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_INFORMATION,
        )
        dlg.SetYesNoLabels(newGettext("Restart now"), newGettext("Restart later"))
        restart = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()

        if restart:
            # main() starts Trelby again once this one has closed, which
            # asks about unsaved changes first and may be cancelled
            self.myApp.restart = True
            if not self.Close():
                self.myApp.restart = False

    def OnAbout(self, event=None):
        win = splash.SplashWindow(self, -1)
        win.Show()

    def OnCloseWindow(self, event):
        doExit = True
        discard = False
        if event.CanVeto() and self.isModifications():
            close_msg_box = wx.MessageDialog(
                self,
                _("You have unsaved changes. Do\nyou want to save your changes?"),
                _("Save Changes"),
                wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT,
            )
            close_msg_box.SetYesNoLabels(
                wx.ID_SAVE, misc.mnemonic("D", _("Don't save"))
            )
            response = close_msg_box.ShowModal()
            if response == wx.ID_YES:
                scriptactions.save(self, self.panel.ctrl)
            elif response == wx.ID_NO:
                discard = True
            elif response == wx.ID_CANCEL:
                doExit = False

        if doExit:
            self.autosaveTimer.Stop()
            self.reader.close()

            # for the restart to open them again
            self.myApp.restartFiles = [
                os.path.abspath(c.fileName) for c in self.getCtrls() if c.fileName
            ]

            # changes the user didn't explicitly discard but that still
            # aren't saved (e.g. other tabs, or a cancelled save) are kept
            # for recovery on the next startup
            for c in self.getCtrls():
                if discard:
                    c.removeRecovery()
                else:
                    c.autosave()

            fileio.writeToFile(self.gd.stateFilename, self.gd.save(), self)
            util.removeTempFiles(misc.tmpPrefix)
            mcpapp.shutdown()
            self.Destroy()
            self.myApp.ExitMainLoop()
        else:
            event.Veto()

    def OnExit(self, event):
        self.Close(False)

    def OnMove(self, event):
        self.gd.posX, self.gd.posY = self.GetPosition()
        event.Skip()

    def OnSize(self, event):
        self.gd.width, self.gd.height = self.GetSize()
        event.Skip()

    def getCfgGui(self):
        return self.gd.cfgGui
