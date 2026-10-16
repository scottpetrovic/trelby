# -*- coding: iso-8859-1 -*-

import copy
import os
import os.path
import signal
import time
import webbrowser
from functools import partial

import wx
import wx.svg

import trelby.autosave as autosave
import trelby.cfgdlg as cfgdlg
import trelby.commands as commands
import trelby.commandsdlg as commandsdlg
import trelby.gutil as gutil
import trelby.keys as keys
import trelby.mcpapp as mcpapp
import trelby.menubar as menubar
import trelby.menus as menus
import trelby.misc as misc
import trelby.scriptactions as scriptactions
import trelby.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.splash as splash
import trelby.statusbar as statusbar
import trelby.tabctrl as tabctrl
import trelby.textfmt as textfmt
import trelby.toolbar as toolbar
import trelby.translations as translations
import trelby.util as util
from trelby.ids import *
from trelby.trelbypanel import MyPanel


class MyFrame(wx.Frame):

    def __init__(self, parent, id, title, gd, myApp):
        wx.Frame.__init__(self, parent, id, title, name="Trelby")

        if misc.isUnix:
            # automatically reaps zombies
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)

        self.gd = gd
        self.myApp = myApp

        self.SetSizeHints(gd.cvars.getMin("width"), gd.cvars.getMin("height"))

        self.Move(gd.posX, gd.posY)
        self.SetSize(wx.Size(gd.width, gd.height))

        util.removeTempFiles(misc.tmpPrefix)

        self.mySetIcons()
        # self.allocIds()

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

        self.fillToolBar()

        self.createStatusBar()

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

        tmp = tabctrl.MyTabCtrl2(self, -1, self.tabCtrl)
        vsizer.Add(tmp, 1, wx.EXPAND)

        vsizer.Add(self.statusBar, 0, wx.EXPAND)

        self.Bind(wx.EVT_MENU_HIGHLIGHT_ALL, self.OnMenuHighlight)

        self.tabCtrl.setPageChangedFunc(self.OnPageChange)
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
        self.menuBar.Check(ID_VIEW_SHOW_OUTLINE, gd.showOutline)

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

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)

        self.autosaveTimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnAutosaveTimer, self.autosaveTimer)

        self.Layout()

    def init(self):
        self.updateKeyMap()
        self.panel = self.createNewPanel()
        self.updateAutosaveTimer()

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

        if not panel or ((ctrl is not None) and (ctrl is not panel.ctrl)):
            return

        c = panel.ctrl

        if c.autosaveError is not None:
            s = _("Autosave failed: %s") % c.autosaveError
        elif c.autosaveTime is not None:
            s = _("Recovery copy autosaved at %s") % time.strftime(
                "%H:%M", time.localtime(c.autosaveTime)
            )
        else:
            s = ""

        self.statusBar.SetStatusText(s, self.SB_HELP)

    # if recovery copies were left over by a session that didn't exit
    # cleanly, offer to restore them
    def offerRecovery(self):
        entries = autosave.listRecoveries(autosave.getRecoveryDir())

        if not entries:
            return

        names = "\n".join(
            "    %s  (%s)"
            % (
                e.getDisplayName(),
                time.strftime("%Y-%m-%d %H:%M", time.localtime(e.time)),
            )
            for e in entries
        )

        dlg = wx.MessageDialog(
            self,
            _(
                "Trelby did not close normally last time. Unsaved changes\nto the following scripts were recovered:\n\n{}\n\nDo you want to restore them?"
            ).format(names),
            _("Recover Unsaved Changes"),
            wx.YES_NO | wx.CANCEL | wx.YES_DEFAULT | wx.ICON_QUESTION,
        )
        dlg.SetYesNoCancelLabels(
            misc.mnemonic("R", _("Restore")),
            misc.mnemonic("D", _("Discard")),
            misc.mnemonic("L", _("Decide later")),
        )
        response = dlg.ShowModal()
        dlg.Destroy()

        if response == wx.ID_YES:
            for e in entries:
                if not self.panel.ctrl.isUntouched():
                    self.panel = self.createNewPanel()

                self.panel.ctrl.loadRecovery(e)
                self.panel.ctrl.updateScreen()

        elif response == wx.ID_NO:
            if (
                wx.MessageBox(
                    _(
                        "Are you sure you want to permanently discard\nthe recovered changes?"
                    ),
                    _("Confirm"),
                    wx.YES_NO | wx.NO_DEFAULT,
                    self,
                )
                == wx.YES
            ):
                for e in entries:
                    autosave.removeRecovery(autosave.getRecoveryDir(), e.recId)

    def mySetIcons(self):
        wx.Image.AddHandler(wx.PNGHandler())

        ib = wx.IconBundle()

        for sz in ("16", "32", "64", "128", "256"):
            ib.AddIcon(wx.Icon(gutil.getBitmap("trelby/resources/icon%s.png" % sz)))

        self.SetIcons(ib)

    # def allocIds(self):

    #     g = globals()

    #     # see OnChangeType
    #     g["idToLTMap"] = {
    #         ID_ELEM_TO_SCENE: screenplay.SCENE,
    #         ID_ELEM_TO_ACTION: screenplay.ACTION,
    #         ID_ELEM_TO_CHARACTER: screenplay.CHARACTER,
    #         ID_ELEM_TO_DIALOGUE: screenplay.DIALOGUE,
    #         ID_ELEM_TO_PAREN: screenplay.PAREN,
    #         ID_ELEM_TO_TRANSITION: screenplay.TRANSITION,
    #         ID_ELEM_TO_SHOT: screenplay.SHOT,
    #         ID_ELEM_TO_ACTBREAK: screenplay.ACTBREAK,
    #         ID_ELEM_TO_NOTE: screenplay.NOTE,
    #     }

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

        self.panel.ctrl.loadFile(filename)
        self.panel.ctrl.updateScreen()
        self.gd.mru.add(filename)

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

    # If we get focus, pass it on to ctrl.
    def OnFocus(self, event):
        self.panel.ctrl.SetFocus()

    def OnMenuHighlight(self, event):
        # default implementation modifies status bar, so we need to
        # override it and do nothing
        pass

    def OnPageChange(self, page):
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

    def OnNewScript(self, event=None):
        self.panel = self.createNewPanel()

    def OnMRUFile(self, event):
        i = event.GetId() - self.gd.mru.getIds()[0]
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
            self.gd.mru.remove(i)

            return

        self.openScript(filename)

    def OnClearRecentFiles(self, event=None):
        self.gd.mru.clear()

    def OnOpen(self, event=None):
        dlg = wx.FileDialog(
            self,
            _("File to open"),
            misc.scriptDir,
            wildcard="Trelby "
            + _("files")
            + " (*.trelby)|*.trelby|"
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

            if not self.tabCtrl.getPage(self.findPage(self.panel)).ctrl.isUntouched():
                self.panel = self.createNewPanel()

            self.panel.ctrl.importFile(dlg.GetPath(), fmt)
            self.panel.ctrl.updateScreen()

        dlg.Destroy()

    def OnCloseScript(self, event=None):
        if not self.panel.ctrl.canBeClosed():
            return

        if self.tabCtrl.getPageCount() > 1:
            self.panel.ctrl.removeRecovery()
            self.tabCtrl.deletePage(self.tabCtrl.getSelectedPageIndex())
        else:
            self.panel.ctrl.createEmptySp()
            self.panel.ctrl.updateScreen()

    def OnSettings(self, event=None):
        self.panel.ctrl.OnSettings()

    # the LoadSettings / SaveSettingsAs keyboard commands. the settings
    # dialog has buttons for these too.
    def OnLoadSettings(self, event=None):
        path = cfgdlg.askSettingsFile(self, self.gd.confFilename, False)
        if not path:
            return

        c = cfgdlg.loadGlobalCfg(path, self)
        if c:
            self.gd.confFilename = path
            self.panel.ctrl.applyGlobalCfg(c, False)

    def OnSaveSettingsAs(self, event=None):
        path = cfgdlg.askSettingsFile(self, self.gd.confFilename, True)
        if not path:
            return

        if gutil.writeToFile(path, self.gd.cfgGl.save(), self):
            self.gd.confFilename = path

    # from the View menu item, which wx has already (un)checked, or its
    # keyboard command
    def OnToggleShowFormatting(self):
        self.gd.showFormatting = not self.gd.showFormatting
        self.menuBar.Check(ID_VIEW_SHOW_FORMATTING, self.gd.showFormatting)
        self.panel.ctrl.Refresh(False)

    # from the View menu item or the toolbar button, which share an id, or
    # the keyboard command
    def OnToggleOutline(self):
        self.setShowOutline(not self.gd.showOutline)

    # show or hide the outline view in all tabs, keeping the View menu item
    # and the toolbar button in sync
    def setShowOutline(self, show):
        self.gd.showOutline = show
        self.menuBar.Check(ID_VIEW_SHOW_OUTLINE, show)
        self.toolBar.ToggleTool(ID_VIEW_SHOW_OUTLINE, show)

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).showOutline(show)

    # names of the controls fillToolBar puts in the toolbar
    TB_CONTROLS = ("elemTypeBar", "formatBar", "alignBar")

    # (re)create the toolbar's tools, with icons at the size set in the
    # global config.
    def fillToolBar(self):
        tb = self.toolBar
        size = wx.Size(self.gd.cfgGl.toolbarIconSize, self.gd.cfgGl.toolbarIconSize)

        # empty space around each icon. wxMSW ignores the toolbar's own
        # margin / packing settings, so it's part of the icons instead.
        pad = 5
        paddedSize = wx.Size(size.width + pad * 2, size.height + pad * 2)

        tb.ClearTools()
        tb.SetToolBitmapSize(paddedSize)

        # ClearTools normally destroys controls along with their tools, but
        # not always, so destroy any that are left. a destroyed wx object
        # is false.
        controls = [getattr(self, name, None) for name in self.TB_CONTROLS]
        controls += getattr(self, "tbDividers", [])

        for c in controls:
            if c:
                c.Destroy()

        self.tbDividers = []

        # height of the controls in the toolbar
        height = max(
            tb.FromDIP(paddedSize.height), tb.GetCharHeight() + tb.FromDIP(12)
        )

        # a vertical line between groups of tools. the toolbar's own
        # separators don't show against its background color.
        def addDivider():
            d = toolbar.MyToolbarDivider(tb, self.getCfgGui, height)
            tb.AddControl(d)
            self.tbDividers.append(d)

        # disabled tools' icons, faded most of the way into the background.
        # wx's own greyed versions barely differ from the normal ones, and
        # on a dark appearance come out lighter.
        disabledColor = gutil.blendColors(
            gutil.svgIconColor(), self.gd.cfgGui.tabBarBgColor, 0.65
        )

        def addTB(id, iconFilename, toolTip, kind=wx.ITEM_NORMAL):
            bitmap = gutil.svgBitmap(iconFilename, size, pad)
            disabledBitmap = gutil.svgBitmap(iconFilename, size, pad, disabledColor)
            tool = tb.AddTool(
                id, "", bitmap, disabledBitmap, kind=kind, shortHelp=toolTip
            )

            # the status bar shows this while the tool is hovered
            tool.SetLongHelp(toolTip)

        addTB(ID_FILE_NEW, "new.svg", _("New file"))
        addTB(ID_FILE_OPEN, "open.svg", _("Open file") + "...")
        addTB(ID_FILE_SAVE, "save.svg", _("Save"))
        addTB(ID_FILE_SAVE_AS, "saveas.svg", _("Save as") + "...")
        addTB(ID_FILE_CLOSE, "close.svg", _("Close file"))

        addDivider()

        addTB(ID_FILE_IMPORT, "import.svg", _("Import file") + "...")
        addTB(ID_FILE_EXPORT, "export.svg", _("Export file"))

        addDivider()

        addTB(ID_EDIT_UNDO, "undo.svg", _("Undo"))
        addTB(ID_EDIT_REDO, "redo.svg", _("Redo"))

        addDivider()

        addTB(ID_EDIT_FIND, "find.svg", _("Find / Replace"))
        addTB(ID_TOOLBAR_VIEWS, "view.svg", _("View mode"))

        addDivider()

        self.elemTypeBar = toolbar.MyElemTypeBar(
            tb,
            -1,
            self.getCfgGui,
            [(lt, label) for lt, id, label, mnemonic, cmd in menus.elemTypes()],
            self.OnElemTypeBar,
            self.getElemTypeToolTip,
            height,
        )
        tb.AddControl(self.elemTypeBar)

        # bold / italic / underline, which go on top of any element type
        addDivider()
        self.formatBar = toolbar.MyFormatBar(
            tb,
            -1,
            self.getCfgGui,
            [(bit, label) for bit, label, name, key in self.getFormatTypes()],
            self.OnFormatBar,
            self.getFormatToolTip,
            height,
        )
        tb.AddControl(self.formatBar)

        # centering, which applies to whole action elements
        addDivider()
        self.alignBar = toolbar.MyFormatBar(
            tb,
            -1,
            self.getCfgGui,
            [(self.ALIGN_CENTER, _("Center"))],
            lambda bit: self.OnAlignBar(),
            lambda bit: self.getAlignToolTip(),
            height,
        )
        tb.AddControl(self.alignBar)

        # at the far right, next to where the outline view appears
        tb.AddStretchableSpace()
        addTB(ID_VIEW_SHOW_OUTLINE, "outline.svg", _("Outline"), wx.ITEM_CHECK)

        tb.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        tb.Realize()

        tb.ToggleTool(ID_VIEW_SHOW_OUTLINE, self.gd.showOutline)

    # the toolbar's format toggles: textfmt bit, label, name, shortcut
    def getFormatTypes(self):
        return [
            (textfmt.BOLD, "B", _("Bold"), "CTRL+B"),
            (textfmt.ITALIC, "I", _("Italic"), "CTRL+I"),
            (textfmt.UNDERLINED, "U", _("Underline"), "CTRL+U"),
        ]

    def OnFormatBar(self, bit):
        scriptactions.toggleFormat(self, self.panel.ctrl, bit)
        self.panel.ctrl.SetFocus()

    def getFormatToolTip(self, bit):
        for itemBit, label, name, key in self.getFormatTypes():
            if itemBit == bit:
                return "%s (%s)" % (name, key)

    # the align bar's item for centering, a bit that's not one of the
    # textfmt ones
    ALIGN_CENTER = 8

    def getAlignToolTip(self):
        if self.alignBar.disabled:
            return _(
                "Centering is only for Action elements. Put the cursor in"
                " an action, or select one, to center it."
            )

        return _(
            "Center this action on the page, e.g. THE END or a title card."
            " Only Action elements can be centered."
        )

    def OnAlignBar(self):
        scriptactions.toggleCentered(self, self.panel.ctrl)
        self.panel.ctrl.SetFocus()

    # show which of bold / italic / underline are on at the cursor or for
    # the selection, and whether the action there is centered (None if
    # centering doesn't apply there)
    def setFormatStatus(self, style, centered):
        self.formatBar.SetValue(style)
        self.alignBar.setDisabled(centered is None)
        self.alignBar.SetValue(self.ALIGN_CENTER if centered else 0)

    def OnElemTypeBar(self, lt):
        self.panel.ctrl.changeType(lt)
        self.panel.ctrl.SetFocus()

    def getElemTypeToolTip(self, lt):
        for itemLt, id, label, mnemonic, cmdName in menus.elemTypes():
            if itemLt == lt:
                break

        s = _("Change element to %s") % label

        for cmd in self.gd.cfgGl.commands:
            if (cmd.name == cmdName) and cmd.keys:
                s += " (%s)" % keys.Key.fromInt(cmd.keys[0]).toStr()

        return s

    # show the current element's type in the toolbar, and what Enter and
    # Tab would change it to in the status bar
    def setElemTypeStatus(self, lt, tabNext, enterNext):
        self.elemTypeBar.SetValue(lt)
        self.statusBar.SetStatusText(
            _("Enter: %s    Tab: %s") % (_(enterNext), _(tabNext)), self.SB_NEXT
        )

    # status bar fields
    SB_SPACER = 0
    SB_HELP = 1
    SB_NEXT = 2
    SB_WORDS = 3
    SB_RUNTIME = 4
    SB_PAGE = 5
    SB_ZOOM = 6

    # the status bar at the bottom of the window. a narrow spacer field
    # keeps the text off the window's left edge. the help field shows
    # whether the script has been autosaved, then come the element types
    # Enter / Tab would create, the script's word count and estimated
    # running time, the current page and the zoom buttons.
    def createStatusBar(self):
        # the fields are set below, once we know their widths
        sb = statusbar.StatusBar(self, self.SB_NEXT)
        self.statusBar = sb

        style = wx.BU_EXACTFIT | wx.BORDER_NONE

        self.zoomOutBtn = wx.Button(sb, -1, "\u2212", style=style)
        self.zoomOutBtn.SetToolTip(_("Zoom out"))
        self.zoomOutBtn.Bind(wx.EVT_BUTTON, partial(self.OnZoomButton, self.OnZoomOut))

        self.zoomLevelBtn = wx.Button(sb, -1, "", style=style)
        self.zoomLevelBtn.SetToolTip(_("Reset zoom"))
        self.zoomLevelBtn.Bind(
            wx.EVT_BUTTON, partial(self.OnZoomButton, self.OnZoomReset)
        )

        self.zoomInBtn = wx.Button(sb, -1, "+", style=style)
        self.zoomInBtn.SetToolTip(_("Zoom in"))
        self.zoomInBtn.Bind(wx.EVT_BUTTON, partial(self.OnZoomButton, self.OnZoomIn))

        self.zoomBtns = (self.zoomOutBtn, self.zoomLevelBtn, self.zoomInBtn)

        # flat buttons don't look clickable, so they get a hand cursor and
        # are highlighted while hovered
        self.zoomHoverBtn = None

        for btn in self.zoomBtns:
            btn.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            btn.Bind(wx.EVT_ENTER_WINDOW, self.OnZoomButtonHover)
            btn.Bind(wx.EVT_LEAVE_WINDOW, self.OnZoomButtonHover)

        # fixed widths, so nothing shifts as the values change
        pad = sb.FromDIP(16)
        btnW = sb.FromDIP(24)
        self.zoomOutBtn.SetSize(btnW, -1)
        self.zoomInBtn.SetSize(btnW, -1)
        self.zoomLevelBtn.SetSize(sb.GetTextExtent("300%")[0] + pad, -1)

        pageW = sb.GetTextExtent(_("Page %d / %d") % (999, 999))[0] + pad
        zoomW = sum(b.GetSize().width for b in self.zoomBtns) + sb.FromDIP(8)
        longest = _("Parenthetical")
        nextW = sb.GetTextExtent(_("Enter: %s    Tab: %s") % (longest, longest))[0]
        wordsW = sb.GetTextExtent(self.formatWordCount(999999))[0] + pad
        runtimeW = sb.GetTextExtent(self.formatRuntime(599))[0] + pad
        widths = [sb.FromDIP(6), -1, nextW + pad, wordsW, runtimeW, pageW, zoomW]
        sb.SetFieldsCount(len(widths), widths)

        sb.Bind(wx.EVT_SIZE, self.OnStatusBarSize)

        self.updateZoomStatus()

        # the status bar may already have its final size, in which case no
        # size event comes
        wx.CallAfter(self.layoutZoomButtons)

    # use the theme's colors for the status bar and the parts of each
    # script's panel not drawn by MyCtrl
    def applyThemeColors(self):
        cfgGui = self.gd.cfgGui

        gutil.setTitleBarColors(self, cfgGui)

        self.statusBar.setColors(
            cfgGui.tabBarBgColor, cfgGui.tabTextColor, cfgGui.tabBorderColor
        )

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).applyTheme(cfgGui)

    def OnStatusBarSize(self, event):
        self.layoutZoomButtons()
        event.Skip()

    # place the zoom buttons centered in their status bar field
    def layoutZoomButtons(self):
        rect = self.statusBar.GetFieldRect(self.SB_ZOOM)
        x = rect.x + (rect.width - sum(b.GetSize().width for b in self.zoomBtns)) // 2

        for btn in self.zoomBtns:
            w = btn.GetSize().width
            btn.SetSize(x, rect.y, w, rect.height)
            x += w

    def OnZoomButton(self, zoomFunc, event):
        zoomFunc()
        self.panel.ctrl.SetFocus()

    def OnZoomButtonHover(self, event):
        btn = event.GetEventObject()

        # moving from one button to the next, the next one's enter event
        # can come before this one's leave event
        if event.Entering():
            self.setZoomButtonHover(btn)
        elif btn is self.zoomHoverBtn:
            self.setZoomButtonHover(None)

        event.Skip()

    # highlight the zoom button hovered (None for none), unless it's
    # disabled
    def setZoomButtonHover(self, hovered):
        sb = self.statusBar
        self.zoomHoverBtn = hovered

        for btn in self.zoomBtns:
            if (btn is hovered) and btn.IsEnabled():
                color = self.gd.cfgGui.tabNonActiveBgColor
            else:
                color = sb.bgColor

            if btn.GetBackgroundColour() != color:
                btn.SetBackgroundColour(color)
                btn.Refresh()

    # page is the label of the current page, pageCnt the number of pages
    def setPageStatus(self, page, pageCnt, locked=False):
        if locked:
            s = _("Page %s / %d (locked)") % (page, pageCnt)
        else:
            s = _("Page %s / %d") % (page, pageCnt)

        self.statusBar.SetStatusText(s, self.SB_PAGE)

    def setLengthStatus(self, wordCnt, pageLength):
        self.statusBar.SetStatusText(self.formatWordCount(wordCnt), self.SB_WORDS)
        self.statusBar.SetStatusText(
            self.formatRuntime(round(pageLength)), self.SB_RUNTIME
        )

    def formatWordCount(self, cnt):
        if cnt == 1:
            return _("1 word")

        return _("%s words") % "{:,}".format(cnt)

    # estimated running time, using the usual rule of thumb of one minute
    # of screen time per script page
    def formatRuntime(self, minutes):
        if minutes < 60:
            return _("Runtime: ~%d min") % minutes

        return _("Runtime: ~%d h %d min") % divmod(minutes, 60)

    def updateZoomStatus(self):
        zoom = self.gd.zoom
        self.zoomLevelBtn.SetLabel("%d%%" % zoom)
        self.zoomOutBtn.Enable(self.gd.getZoomStep(-1) != zoom)
        self.zoomInBtn.Enable(self.gd.getZoomStep(1) != zoom)

        # a button disabled while hovered gets no leave event, and one
        # enabled under the mouse no enter event
        pos = wx.GetMousePosition()
        hovered = [b for b in self.zoomBtns if b.GetScreenRect().Contains(pos)]
        self.setZoomButtonHover(hovered[0] if hovered else None)

    def ShowHideToolbar(self, event=None):
        self.toolBar.Show(self.menuBar.IsChecked(ID_SHOW_HIDE_TOOLBAR))
        self.Layout()

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

    # set zoom level (in percent) for all open scripts
    def setZoom(self, zoom):
        if zoom == self.gd.zoom:
            return

        self.gd.zoom = zoom
        self.updateZoomStatus()

        # zooming scales the screen fonts in gd.cfgGui, which all tabs
        # share, so it's rebuilt once. each tab's page size and mm2p
        # follow from the font sizes, so refreshCache recomputes them.
        self.panel.ctrl.refreshGuiConfig()

        for c in self.getCtrls():
            c.refreshCache()

        c = self.panel.ctrl
        c.makeLineVisible(c.ed.line)
        c.updateScreen()

    def ToggleFullscreen(self, event=None):
        fullScreen = not self.IsFullScreen()

        self.noFSBtn.Show(fullScreen)
        self.statusBar.Show(not fullScreen)

        # FULLSCREEN_ALL only hides the bars the frame manages
        if self.ownMenuBar:
            self.menuBar.Show(not fullScreen)
            self.toolBar.Show(
                not fullScreen and self.menuBar.IsChecked(ID_SHOW_HIDE_TOOLBAR)
            )

        self.ShowFullScreen(fullScreen, wx.FULLSCREEN_ALL)
        self.Layout()
        self.panel.ctrl.SetFocus()

    def OnSpellCheckerDictionaryDlg(self, event=None):
        dlg = spellcheckcfgdlg.SCDictDlg(self, copy.deepcopy(self.gd.scDict), True)

        if dlg.ShowModal() == wx.ID_OK:
            self.gd.scDict = dlg.scDict
            self.gd.saveScDict()

        dlg.Destroy()

    # run the menus.Action with the given name
    def runAction(self, name):
        self.actions[name].run(self)

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
        gutil.writeToFile(self.gd.confFilename, self.gd.cfgGl.save(), self)

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

            gutil.writeToFile(self.gd.stateFilename, self.gd.save(), self)
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
