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

import trelby
import trelby.autosave as autosave
import trelby.cfgdlg as cfgdlg
import trelby.charmapdlg as charmapdlg
import trelby.commandsdlg as commandsdlg
import trelby.gutil as gutil
import trelby.mcpapp as mcpapp
import trelby.menubar as menubar
import trelby.misc as misc
import trelby.namesdlg as namesdlg
import trelby.screenplay as screenplay
import trelby.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.splash as splash
import trelby.util as util
from trelby.ids import *
from trelby.trelbypanel import MyPanel


class MyFrame(wx.Frame):

    def __init__(self, parent, id, title, gd, myApp):
        wx.Frame.__init__(self, parent, id, title, name="Trelby")

        if misc.isUnix:
            # automatically reaps zombies
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)

        self.clipboard = None
        self.showFormatting = False
        self.gd = gd
        self.myApp = myApp

        self.SetSizeHints(gd.cvars.getMin("width"), gd.cvars.getMin("height"))

        self.Move(gd.posX, gd.posY)
        self.SetSize(wx.Size(gd.width, gd.height))

        util.removeTempFiles(misc.tmpPrefix)

        self.mySetIcons()
        # self.allocIds()

        fileMenu = wx.Menu()
        fileMenu.Append(ID_FILE_NEW, misc.mnemonic("N", _("New") + "\tCTRL-N"))
        fileMenu.Append(ID_FILE_OPEN, misc.mnemonic("O", _("Open") + "...\tCTRL-O"))
        recentMenu = wx.Menu()
        fileMenu.AppendSubMenu(recentMenu, misc.mnemonic("R", _("Open Recent")))
        fileMenu.Append(ID_FILE_SAVE, misc.mnemonic("S", _("Save") + "\tCTRL-S"))
        fileMenu.Append(ID_FILE_SAVE_AS, misc.mnemonic("A", _("Save As") + "..."))
        fileMenu.Append(ID_FILE_CLOSE, misc.mnemonic("C", _("Close\tCTRL-W")))
        fileMenu.Append(ID_FILE_REVERT, misc.mnemonic("v", _("Revert")))
        fileMenu.AppendSeparator()
        importMenu = wx.Menu()
        importMenu.Append(
            ID_FILE_IMPORT_FDX, misc.mnemonic("D", _("Final Draft (FDX)") + "...")
        )
        importMenu.Append(
            ID_FILE_IMPORT_FOUNTAIN, misc.mnemonic("F", _("Fountain") + "...")
        )
        importMenu.Append(ID_FILE_IMPORT_CELTX, misc.mnemonic("C", _("Celtx") + "..."))
        importMenu.Append(
            ID_FILE_IMPORT_ASTX, misc.mnemonic("A", _("Adobe Story (ASTX)") + "...")
        )
        importMenu.Append(
            ID_FILE_IMPORT_FADEIN, misc.mnemonic("I", _("Fade In") + "...")
        )
        importMenu.Append(
            ID_FILE_IMPORT_TEXT, misc.mnemonic("T", _("Formatted Text") + "...")
        )
        fileMenu.AppendSubMenu(importMenu, misc.mnemonic("I", _("Import")))
        exportMenu = wx.Menu()
        exportMenu.Append(ID_FILE_EXPORT_PDF, misc.mnemonic("P", _("PDF") + "..."))
        exportMenu.Append(
            ID_FILE_EXPORT_WATERMARK,
            misc.mnemonic("W", _("Watermarked PDF") + "..."),
        )
        exportMenu.Append(
            ID_FILE_EXPORT_RTF, misc.mnemonic("R", _("Rich Text (RTF)") + "...")
        )
        exportMenu.Append(
            ID_FILE_EXPORT_FDX, misc.mnemonic("D", _("Final Draft (FDX)") + "...")
        )
        exportMenu.Append(ID_FILE_EXPORT_HTML, misc.mnemonic("H", _("HTML") + "..."))
        exportMenu.Append(
            ID_FILE_EXPORT_FOUNTAIN, misc.mnemonic("F", _("Fountain") + "...")
        )
        exportMenu.Append(
            ID_FILE_EXPORT_TEXT, misc.mnemonic("T", _("Formatted Text") + "...")
        )
        fileMenu.AppendSubMenu(exportMenu, misc.mnemonic("E", _("Export")))
        fileMenu.AppendSeparator()
        fileMenu.Append(ID_FILE_EXIT, misc.mnemonic("x", _("Exit") + "\tCTRL-Q"))

        editMenu = wx.Menu()
        editMenu.Append(ID_EDIT_UNDO, misc.mnemonic("U", _("Undo") + "\tCTRL-Z"))
        editMenu.Append(ID_EDIT_REDO, misc.mnemonic("R", _("Redo") + "\tCTRL-Y"))
        editMenu.AppendSeparator()
        editMenu.Append(ID_EDIT_CUT, misc.mnemonic("t", _("Cut") + "\tCTRL-X"))
        editMenu.Append(ID_EDIT_COPY, misc.mnemonic("C", _("Copy") + "\tCTRL-C"))
        editMenu.Append(ID_EDIT_PASTE, misc.mnemonic("P", _("Paste") + "\tCTRL-V"))
        editMenu.AppendSeparator()

        tmp = wx.Menu()
        tmp.Append(ID_EDIT_COPY_TO_CB, misc.mnemonic("U", _("Unformatted")))
        tmp.Append(ID_EDIT_COPY_TO_CB_FMT, misc.mnemonic("F", _("Formatted")))

        editMenu.AppendSubMenu(tmp, misc.mnemonic("o", _("Copy (system)")))
        editMenu.Append(ID_EDIT_PASTE_FROM_CB, misc.mnemonic("a", _("Paste (system)")))
        editMenu.AppendSeparator()
        editMenu.Append(ID_EDIT_SELECT_SCENE, misc.mnemonic("S", _("Select scene")))
        editMenu.Append(ID_EDIT_SELECT_ALL, misc.mnemonic("l", _("Select all")))
        editMenu.AppendSeparator()
        editMenu.Append(
            ID_EDIT_FIND, misc.mnemonic("F", _("Find && Replace") + "...\tCTRL-F")
        )
        editMenu.Append(
            ID_EDIT_GOTO_PAGE, misc.mnemonic("G", _("Goto page") + "...\tCTRL-G")
        )
        editMenu.Append(
            ID_EDIT_GOTO_SCENE, misc.mnemonic("e", _("Goto scene") + "...\tALT-G")
        )
        editMenu.AppendSeparator()
        editMenu.Append(ID_EDIT_INSERT_NBSP, _("Insert non-breaking space"))
        editMenu.Append(
            ID_EDIT_DUAL_DIALOGUE,
            misc.mnemonic("i", _("Dual dialogue") + "\tCTRL-D"),
        )
        editMenu.Append(
            ID_EDIT_DELETE_ELEMENTS, misc.mnemonic("D", _("Delete elements") + "...")
        )
        editMenu.AppendSeparator()
        editMenu.Append(ID_SETTINGS_CHANGE, misc.mnemonic("n", _("Settings") + "..."))

        viewMenu = wx.Menu()
        viewMenu.AppendRadioItem(
            ID_VIEW_STYLE_DRAFT, misc.mnemonic("C", _("Continuous"))
        )
        viewMenu.AppendRadioItem(ID_VIEW_STYLE_LAYOUT, misc.mnemonic("P", _("Page")))
        viewMenu.AppendRadioItem(
            ID_VIEW_STYLE_SIDE_BY_SIDE, misc.mnemonic("S", _("Side by side"))
        )

        if gd.viewMode == gd.VIEWMODE_DRAFT:
            viewMenu.Check(ID_VIEW_STYLE_DRAFT, True)
        elif gd.viewMode == gd.VIEWMODE_LAYOUT:
            viewMenu.Check(ID_VIEW_STYLE_LAYOUT, True)
        else:
            viewMenu.Check(ID_VIEW_STYLE_SIDE_BY_SIDE, True)

        viewMenu.AppendSeparator()
        viewMenu.AppendCheckItem(ID_SHOW_HIDE_TOOLBAR, misc.mnemonic("T", _("Toolbar")))
        viewMenu.Check(ID_SHOW_HIDE_TOOLBAR, True)
        viewMenu.AppendCheckItem(ID_VIEW_SHOW_OUTLINE, misc.mnemonic("O", _("Outline")))
        viewMenu.Check(ID_VIEW_SHOW_OUTLINE, gd.showOutline)
        viewMenu.AppendCheckItem(
            ID_VIEW_SHOW_FORMATTING, misc.mnemonic("h", _("Show formatting"))
        )
        viewMenu.AppendSeparator()
        viewMenu.Append(ID_VIEW_ZOOM_IN, misc.mnemonic("I", _("Zoom in") + "\tCTRL-="))
        viewMenu.Append(
            ID_VIEW_ZOOM_OUT, misc.mnemonic("U", _("Zoom out") + "\tCTRL--")
        )
        viewMenu.Append(
            ID_VIEW_ZOOM_RESET, misc.mnemonic("R", _("Reset zoom") + "\tCTRL-0")
        )
        viewMenu.AppendSeparator()
        viewMenu.Append(
            ID_VIEW_FULL_SCREEN, misc.mnemonic("F", _("Fullscreen") + "\tF11")
        )

        # the script's own page format: the settings that end up in the PDF
        pageMenu = wx.Menu()
        pageMenu.Append(
            ID_SCRIPT_SETTINGS_CHANGE, misc.mnemonic("S", _("Page setup") + "...")
        )
        pageMenu.Append(ID_SCRIPT_HEADERS, misc.mnemonic("H", _("Headers") + "..."))
        pageMenu.Append(ID_SCRIPT_TITLES, misc.mnemonic("T", _("Title pages") + "..."))
        pageMenu.AppendSeparator()
        pageMenu.Append(ID_SCRIPT_PAGINATE, misc.mnemonic("P", _("Paginate")))
        pageMenu.Append(ID_SCRIPT_LOCK_PAGES, misc.mnemonic("L", _("Lock pages")))
        pageMenu.Append(ID_SCRIPT_UNLOCK_PAGES, misc.mnemonic("U", _("Unlock pages")))

        reportsMenu = wx.Menu()
        reportsMenu.Append(
            ID_REPORTS_SCRIPT_REP, misc.mnemonic("r", _("Script report"))
        )
        reportsMenu.Append(
            ID_REPORTS_LOCATION_REP, misc.mnemonic("L", _("Location report") + "...")
        )
        reportsMenu.Append(
            ID_REPORTS_SCENE_REP, misc.mnemonic("S", _("Scene report") + "...")
        )
        reportsMenu.Append(
            ID_REPORTS_CHARACTER_REP, misc.mnemonic("C", _("Character report") + "...")
        )
        reportsMenu.Append(
            ID_REPORTS_DIALOGUE_CHART, misc.mnemonic("D", _("Dialogue chart") + "...")
        )

        toolsMenu = wx.Menu()
        toolsMenu.Append(
            ID_TOOLS_SPELL_CHECK, misc.mnemonic("S", _("Spell checker") + "...")
        )
        toolsMenu.Append(
            ID_SCRIPT_SC_DICT, misc.mnemonic("d", _("Script dictionary") + "...")
        )
        toolsMenu.Append(
            ID_SCRIPT_FIND_ERROR, misc.mnemonic("F", _("Find next error"))
        )
        toolsMenu.AppendSeparator()
        toolsMenu.Append(
            ID_SCRIPT_CHARACTER_PROFILES,
            misc.mnemonic("r", _("Character profiles") + "..."),
        )
        toolsMenu.Append(
            ID_SCRIPT_LOCATIONS, misc.mnemonic("L", _("Locations") + "...")
        )
        toolsMenu.Append(
            ID_SCRIPT_AUTO_COMPLETION, misc.mnemonic("A", _("Auto-completion") + "...")
        )
        toolsMenu.Append(
            ID_TOOLS_NAME_DB, misc.mnemonic("N", _("Name database") + "...")
        )
        toolsMenu.Append(
            ID_TOOLS_CHARMAP, misc.mnemonic("C", _("Character map") + "...")
        )
        toolsMenu.AppendSeparator()
        toolsMenu.Append(
            ID_TOOLS_COMPARE_SCRIPTS, misc.mnemonic("o", _("Compare scripts") + "...")
        )

        helpMenu = wx.Menu()
        helpMenu.Append(ID_HELP_COMMANDS, misc.mnemonic("C", _("Commands") + "..."))
        helpMenu.Append(ID_HELP_MANUAL, misc.mnemonic("M", _("Manual")))
        helpMenu.AppendSeparator()
        helpMenu.Append(ID_HELP_ABOUT, misc.mnemonic("A", _("About") + "..."))

        # Windows' native menu bar has a fixed, cramped height, so there we
        # draw our own, with the toolbar below it in the sizer instead of
        # being managed by the frame
        self.ownMenuBar = misc.isWindows

        if self.ownMenuBar:
            self.menuBar = menubar.MyMenuBar(self, self.getCfgGui)
        else:
            self.menuBar = wx.MenuBar()

        self.menuBar.Append(fileMenu, misc.mnemonic("F", _("File")))
        self.menuBar.Append(editMenu, misc.mnemonic("E", _("Edit")))
        self.menuBar.Append(viewMenu, misc.mnemonic("V", _("View")))
        self.menuBar.Append(pageMenu, misc.mnemonic("P", _("Page")))
        self.menuBar.Append(reportsMenu, misc.mnemonic("R", _("Reports")))
        self.menuBar.Append(toolsMenu, misc.mnemonic("T", _("Tools")))
        self.menuBar.Append(helpMenu, misc.mnemonic("H", _("Help")))

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

        self.noFSBtn = misc.MyFSButton(self, -1, self.getCfgGui)
        self.noFSBtn.SetToolTip(_("Exit fullscreen"))
        self.noFSBtn.Show(False)
        hsizer.Add(self.noFSBtn)

        self.Bind(wx.EVT_BUTTON, self.ToggleFullscreen, id=self.noFSBtn.GetId())

        self.tabCtrl = misc.MyTabCtrl(self, -1, self.getCfgGui)
        hsizer.Add(self.tabCtrl, 1, wx.EXPAND)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        tmp = misc.MyTabCtrl2(self, -1, self.tabCtrl)
        vsizer.Add(tmp, 1, wx.EXPAND)

        vsizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND)

        gd.mru.useMenu(recentMenu)

        self.Bind(wx.EVT_MENU_HIGHLIGHT_ALL, self.OnMenuHighlight)

        self.tabCtrl.setPageChangedFunc(self.OnPageChange)

        self.Bind(wx.EVT_MENU, self.OnNewScript, id=ID_FILE_NEW)
        self.Bind(wx.EVT_MENU, self.OnOpen, id=ID_FILE_OPEN)
        self.Bind(wx.EVT_MENU, self.OnSave, id=ID_FILE_SAVE)
        self.Bind(wx.EVT_MENU, self.OnSaveScriptAs, id=ID_FILE_SAVE_AS)
        for importId, fmt in (
            (ID_FILE_IMPORT_FDX, "fdx"),
            (ID_FILE_IMPORT_FOUNTAIN, "fountain"),
            (ID_FILE_IMPORT_CELTX, "celtx"),
            (ID_FILE_IMPORT_ASTX, "astx"),
            (ID_FILE_IMPORT_FADEIN, "fadein"),
            (ID_FILE_IMPORT_TEXT, "txt"),
        ):
            self.Bind(
                wx.EVT_MENU, partial(self.OnImportScript, fmt=fmt), id=importId
            )
        for exportId, fmt in (
            (ID_FILE_EXPORT_PDF, "pdf"),
            (ID_FILE_EXPORT_RTF, "rtf"),
            (ID_FILE_EXPORT_FDX, "fdx"),
            (ID_FILE_EXPORT_HTML, "html"),
            (ID_FILE_EXPORT_FOUNTAIN, "fountain"),
            (ID_FILE_EXPORT_TEXT, "txt"),
        ):
            self.Bind(
                wx.EVT_MENU, partial(self.OnExportScript, fmt=fmt), id=exportId
            )
        self.Bind(wx.EVT_MENU, self.OnCloseScript, id=ID_FILE_CLOSE)
        self.Bind(wx.EVT_MENU, self.OnRevertScript, id=ID_FILE_REVERT)
        self.Bind(wx.EVT_MENU, self.OnSettings, id=ID_SETTINGS_CHANGE)
        self.Bind(wx.EVT_MENU, self.OnExit, id=ID_FILE_EXIT)
        self.Bind(wx.EVT_MENU, self.OnUndo, id=ID_EDIT_UNDO)
        self.Bind(wx.EVT_MENU, self.OnRedo, id=ID_EDIT_REDO)
        self.Bind(wx.EVT_MENU, self.OnCut, id=ID_EDIT_CUT)
        self.Bind(wx.EVT_MENU, self.OnCopy, id=ID_EDIT_COPY)
        self.Bind(wx.EVT_MENU, self.OnPaste, id=ID_EDIT_PASTE)
        self.Bind(wx.EVT_MENU, self.OnCopySystemCb, id=ID_EDIT_COPY_TO_CB)
        self.Bind(
            wx.EVT_MENU, self.OnCopySystemCbFormatted, id=ID_EDIT_COPY_TO_CB_FMT
        )
        self.Bind(wx.EVT_MENU, self.OnPasteSystemCb, id=ID_EDIT_PASTE_FROM_CB)
        self.Bind(wx.EVT_MENU, self.OnSelectScene, id=ID_EDIT_SELECT_SCENE)
        self.Bind(wx.EVT_MENU, self.OnSelectAll, id=ID_EDIT_SELECT_ALL)
        self.Bind(wx.EVT_MENU, self.OnGotoPage, id=ID_EDIT_GOTO_PAGE)
        self.Bind(wx.EVT_MENU, self.OnGotoScene, id=ID_EDIT_GOTO_SCENE)
        self.Bind(wx.EVT_MENU, self.OnInsertNbsp, id=ID_EDIT_INSERT_NBSP)
        self.Bind(wx.EVT_MENU, self.OnDualDialogue, id=ID_EDIT_DUAL_DIALOGUE)
        self.Bind(wx.EVT_MENU, self.OnFind, id=ID_EDIT_FIND)
        self.Bind(wx.EVT_MENU, self.OnDeleteElements, id=ID_EDIT_DELETE_ELEMENTS)
        self.Bind(wx.EVT_MENU, self.OnViewModeChange, id=ID_VIEW_STYLE_DRAFT)
        self.Bind(wx.EVT_MENU, self.ShowHideToolbar, id=ID_SHOW_HIDE_TOOLBAR)
        self.Bind(wx.EVT_MENU, self.OnViewModeChange, id=ID_VIEW_STYLE_LAYOUT)
        self.Bind(wx.EVT_MENU, self.OnViewModeChange, id=ID_VIEW_STYLE_SIDE_BY_SIDE)
        self.Bind(wx.EVT_MENU, self.OnShowFormatting, id=ID_VIEW_SHOW_FORMATTING)
        self.Bind(wx.EVT_MENU, self.OnShowOutline, id=ID_VIEW_SHOW_OUTLINE)
        self.Bind(wx.EVT_MENU, self.ToggleFullscreen, id=ID_VIEW_FULL_SCREEN)
        self.Bind(wx.EVT_MENU, self.OnZoomIn, id=ID_VIEW_ZOOM_IN)
        self.Bind(wx.EVT_MENU, self.OnZoomOut, id=ID_VIEW_ZOOM_OUT)
        self.Bind(wx.EVT_MENU, self.OnZoomReset, id=ID_VIEW_ZOOM_RESET)

        self.Bind(wx.EVT_MENU, self.OnFindNextError, id=ID_SCRIPT_FIND_ERROR)
        self.Bind(wx.EVT_MENU, self.OnPaginate, id=ID_SCRIPT_PAGINATE)
        self.Bind(wx.EVT_MENU, self.OnLockPages, id=ID_SCRIPT_LOCK_PAGES)
        self.Bind(wx.EVT_MENU, self.OnUnlockPages, id=ID_SCRIPT_UNLOCK_PAGES)
        self.Bind(
            wx.EVT_MENU, self.OnAutoCompletionDlg, id=ID_SCRIPT_AUTO_COMPLETION
        )
        self.Bind(wx.EVT_MENU, self.OnHeadersDlg, id=ID_SCRIPT_HEADERS)
        self.Bind(wx.EVT_MENU, self.OnLocationsDlg, id=ID_SCRIPT_LOCATIONS)
        self.Bind(
            wx.EVT_MENU,
            self.OnCharacterProfilesDlg,
            id=ID_SCRIPT_CHARACTER_PROFILES,
        )
        self.Bind(wx.EVT_MENU, self.OnTitlesDlg, id=ID_SCRIPT_TITLES)
        self.Bind(
            wx.EVT_MENU,
            self.OnSpellCheckerScriptDictionaryDlg,
            id=ID_SCRIPT_SC_DICT,
        )
        self.Bind(wx.EVT_MENU, self.OnScriptSettings, id=ID_SCRIPT_SETTINGS_CHANGE)
        self.Bind(
            wx.EVT_MENU, self.OnReportDialogueChart, id=ID_REPORTS_DIALOGUE_CHART
        )
        self.Bind(wx.EVT_MENU, self.OnReportCharacter, id=ID_REPORTS_CHARACTER_REP)
        self.Bind(wx.EVT_MENU, self.OnReportScript, id=ID_REPORTS_SCRIPT_REP)
        self.Bind(wx.EVT_MENU, self.OnReportLocation, id=ID_REPORTS_LOCATION_REP)
        self.Bind(wx.EVT_MENU, self.OnReportScene, id=ID_REPORTS_SCENE_REP)
        self.Bind(wx.EVT_MENU, self.OnSpellCheckerDlg, id=ID_TOOLS_SPELL_CHECK)
        self.Bind(wx.EVT_MENU, self.OnNameDatabase, id=ID_TOOLS_NAME_DB)
        self.Bind(wx.EVT_MENU, self.OnCharacterMap, id=ID_TOOLS_CHARMAP)
        self.Bind(wx.EVT_MENU, self.OnCompareScripts, id=ID_TOOLS_COMPARE_SCRIPTS)
        self.Bind(wx.EVT_MENU, self.OnWatermark, id=ID_FILE_EXPORT_WATERMARK)
        self.Bind(wx.EVT_MENU, self.OnHelpCommands, id=ID_HELP_COMMANDS)
        self.Bind(wx.EVT_MENU, self.OnHelpManual, id=ID_HELP_MANUAL)
        self.Bind(wx.EVT_MENU, self.OnAbout, id=ID_HELP_ABOUT)

        self.Bind(
            wx.EVT_MENU_RANGE,
            self.OnMRUFile,
            id=gd.mru.getIds()[0],
            id2=gd.mru.getIds()[1],
        )
        self.Bind(wx.EVT_MENU, self.OnClearRecentFiles, id=gd.mru.clearId)

        self.Bind(
            wx.EVT_MENU_RANGE,
            self.OnChangeType,
            id=ID_ELEM_TO_ACTION,
            id2=ID_ELEM_TO_TRANSITION,
        )

        self.Bind(
            wx.EVT_MENU,
            partial(self.OnToolBarMenu, menu=viewMenu),
            id=ID_TOOLBAR_VIEWS,
        )

        self.Bind(
            wx.EVT_MENU,
            partial(self.OnToolBarMenu, menu=importMenu),
            id=ID_FILE_IMPORT,
        )

        self.Bind(
            wx.EVT_MENU,
            partial(self.OnToolBarMenu, menu=exportMenu),
            id=ID_FILE_EXPORT,
        )

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
        self.updateKbdCommands()
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
            ib.AddIcon(wx.Icon(misc.getBitmap("trelby/resources/icon%s.png" % sz)))

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

    def createNewPanel(self):
        newPanel = MyPanel(self.tabCtrl.getTabParent(), -1, self.gd)
        self.tabCtrl.addPage(newPanel, "")
        newPanel.ctrl.setTabText()
        newPanel.ctrl.SetFocus()

        return newPanel

    def setTitle(self, text):
        self.SetTitle("Trelby - %s" % text)

    def setTabText(self, panel, text):
        i = self.findPage(panel)

        if i != -1:
            # strip out ".trelby" suffix from tab names (it's a bit
            # complicated since if we open the same file multiple times,
            # we have e.g. "foo.trelby" and "foo.trelby<2>", so actually
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

    def updateKbdCommands(self):
        self.gd.cfgGl.addShiftKeys()

        if self.gd.cfgGl.getConflictingKeys() != None:
            wx.MessageBox(
                _(
                    "You have at least one key bound to more than one\ncommand. The program will not work correctly until\nyou fix this."
                ),
                _("Warning"),
                wx.OK,
                self,
            )

        self.kbdCommands = {}

        for cmd in self.gd.cfgGl.commands:
            if not (cmd.isFixed and cmd.isMenu):
                for key in cmd.keys:
                    self.kbdCommands[key] = cmd

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
            if not util.isFixedWidth(fi.font):
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
        self.setTitle(self.panel.ctrl.fileNameDisplay)
        self.updateAutosaveStatus()

        # also called when a script is opened or closed
        self.menuBar.Enable(
            ID_TOOLS_COMPARE_SCRIPTS, self.tabCtrl.getPageCount() >= 2
        )

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

    def OnScriptNext(self, event=None):
        self.selectScript(True)

    def OnScriptPrev(self, event=None):
        self.selectScript(False)

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

    def OnSave(self, event=None):
        self.panel.ctrl.OnSave()

    def OnSaveScriptAs(self, event=None):
        self.panel.ctrl.OnSaveScriptAs()

    def OnImportScript(self, event=None, fmt="txt"):
        # (file type description, wildcard pattern) for each import format
        types = {
            "fdx": ("Final Draft XML", "*.fdx"),
            "fountain": ("Fountain", "*.fountain;*.txt"),
            "celtx": ("Celtx", "*.celtx"),
            "astx": ("Adobe Story XML", "*.astx"),
            "fadein": ("Fade In", "*.fadein"),
            "txt": (_("Formatted text"), "*.txt"),
        }
        desc, pattern = types[fmt]

        dlg = wx.FileDialog(
            self,
            _("File to import"),
            misc.scriptDir,
            wildcard="%s %s (%s)|%s|%s|*"
            % (desc, _("files"), pattern, pattern, _("All files")),
            style=wx.FD_OPEN,
        )

        if dlg.ShowModal() == wx.ID_OK:
            misc.scriptDir = dlg.GetDirectory()

            if not self.tabCtrl.getPage(self.findPage(self.panel)).ctrl.isUntouched():
                self.panel = self.createNewPanel()

            self.panel.ctrl.importFile(dlg.GetPath(), fmt)
            self.panel.ctrl.updateScreen()

        dlg.Destroy()

    def OnExportScript(self, event=None, fmt="pdf"):
        self.panel.ctrl.OnExportScript(fmt)

    def OnCloseScript(self, event=None):
        if not self.panel.ctrl.canBeClosed():
            return

        if self.tabCtrl.getPageCount() > 1:
            self.panel.ctrl.removeRecovery()
            self.tabCtrl.deletePage(self.tabCtrl.getSelectedPageIndex())
        else:
            self.panel.ctrl.createEmptySp()
            self.panel.ctrl.updateScreen()

    def OnRevertScript(self, event=None):
        self.panel.ctrl.OnRevertScript()

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

        if util.writeToFile(path, self.gd.cfgGl.save(), self):
            self.gd.confFilename = path

    def OnUndo(self, event=None):
        self.panel.ctrl.OnUndo()

    def OnRedo(self, event=None):
        self.panel.ctrl.OnRedo()

    def OnCut(self, event=None):
        self.panel.ctrl.OnCut()

    def OnCopy(self, event=None):
        self.panel.ctrl.OnCopy()

    def OnCopySystemCb(self, event=None):
        self.panel.ctrl.OnCopySystem(formatted=False)

    def OnCopySystemCbFormatted(self, event=None):
        self.panel.ctrl.OnCopySystem(formatted=True)

    def OnPaste(self, event=None):
        self.panel.ctrl.OnPaste()

    def OnPasteSystemCb(self, event=None):
        self.panel.ctrl.OnPasteSystemCb()

    def OnSelectScene(self, event=None):
        self.panel.ctrl.OnSelectScene()

    def OnSelectAll(self, event=None):
        self.panel.ctrl.OnSelectAll()

    def OnGotoPage(self, event=None):
        self.panel.ctrl.OnGotoPage()

    def OnGotoScene(self, event=None):
        self.panel.ctrl.OnGotoScene()

    def OnFindNextError(self, event=None):
        self.panel.ctrl.OnFindNextError()

    def OnFind(self, event=None):
        self.panel.ctrl.OnFind()

    def OnInsertNbsp(self, event=None):
        self.panel.ctrl.OnInsertNbsp()

    def OnDualDialogue(self, event=None):
        self.panel.ctrl.OnDualDialogue()

    def OnDeleteElements(self, event=None):
        self.panel.ctrl.OnDeleteElements()

    def OnToggleShowFormatting(self, event=None):
        self.menuBar.Check(
            ID_VIEW_SHOW_FORMATTING, not self.menuBar.IsChecked(ID_VIEW_SHOW_FORMATTING)
        )
        self.showFormatting = not self.showFormatting
        self.panel.ctrl.Refresh(False)

    def OnShowFormatting(self, event=None):
        self.showFormatting = self.menuBar.IsChecked(ID_VIEW_SHOW_FORMATTING)
        self.panel.ctrl.Refresh(False)

    def OnToggleOutline(self, event=None):
        self.setShowOutline(not self.gd.showOutline)

    # from the View menu item or the toolbar button, which share an id
    def OnShowOutline(self, event):
        self.setShowOutline(event.IsChecked())

    # show or hide the outline view in all tabs, keeping the View menu item
    # and the toolbar button in sync
    def setShowOutline(self, show):
        self.gd.showOutline = show
        self.menuBar.Check(ID_VIEW_SHOW_OUTLINE, show)
        self.toolBar.ToggleTool(ID_VIEW_SHOW_OUTLINE, show)

        for i in range(self.tabCtrl.getPageCount()):
            self.tabCtrl.getPage(i).showOutline(show)

    def OnViewModeDraft(self):
        self.menuBar.Check(ID_VIEW_STYLE_DRAFT, True)
        self.OnViewModeChange()

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

        # ClearTools normally destroys controls along with their tools
        if getattr(self, "elemTypeBar", None):
            self.elemTypeBar.Destroy()

        def addTB(id, iconFilename, toolTip, kind=wx.ITEM_NORMAL):
            bitmap = gutil.svgBitmap(iconFilename, size, pad)
            tool = tb.AddTool(id, "", bitmap, shortHelp=toolTip, kind=kind)

            # the status bar shows this while the tool is hovered
            tool.SetLongHelp(toolTip)

        addTB(ID_FILE_NEW, "new.svg", _("New file"))
        addTB(ID_FILE_OPEN, "open.svg", _("Open file") + "...")
        addTB(ID_FILE_SAVE, "save.svg", _("Save"))
        addTB(ID_FILE_SAVE_AS, "saveas.svg", _("Save as") + "...")
        addTB(ID_FILE_CLOSE, "close.svg", _("Close file"))

        tb.AddSeparator()

        addTB(ID_FILE_IMPORT, "import.svg", _("Import file") + "...")
        addTB(ID_FILE_EXPORT, "export.svg", _("Export file"))

        tb.AddSeparator()

        addTB(ID_EDIT_UNDO, "undo.svg", _("Undo"))
        addTB(ID_EDIT_REDO, "redo.svg", _("Redo"))

        tb.AddSeparator()

        addTB(ID_EDIT_FIND, "find.svg", _("Find / Replace"))
        addTB(ID_TOOLBAR_VIEWS, "view.svg", _("View mode"))

        tb.AddSeparator()

        height = max(
            tb.FromDIP(paddedSize.height), tb.GetCharHeight() + tb.FromDIP(12)
        )
        self.elemTypeBar = misc.MyElemTypeBar(
            tb,
            -1,
            self.getCfgGui,
            [(lt, label) for lt, label, cmdName in self.getElemTypes()],
            self.OnElemTypeBar,
            self.getElemTypeToolTip,
            height,
        )
        tb.AddControl(self.elemTypeBar)

        # at the far right, next to where the outline view appears
        tb.AddStretchableSpace()
        addTB(ID_VIEW_SHOW_OUTLINE, "outline.svg", _("Outline"), wx.ITEM_CHECK)

        tb.SetBackgroundColour(self.gd.cfgGui.tabBarBgColor)
        tb.Realize()

        tb.ToggleTool(ID_VIEW_SHOW_OUTLINE, self.gd.showOutline)

    # element types in the toolbar's element type group: line type, label,
    # name of the command that changes to it
    def getElemTypes(self):
        return [
            (screenplay.SCENE, _("Scene"), "ChangeToScene"),
            (screenplay.ACTION, _("Action"), "ChangeToAction"),
            (screenplay.CHARACTER, _("Character"), "ChangeToCharacter"),
            (screenplay.PAREN, _("Parenthetical"), "ChangeToParenthetical"),
            (screenplay.DIALOGUE, _("Dialogue"), "ChangeToDialogue"),
            (screenplay.TRANSITION, _("Transition"), "ChangeToTransition"),
            (screenplay.SHOT, _("Shot"), "ChangeToShot"),
            (screenplay.ACTBREAK, _("Act break"), "ChangeToActBreak"),
            (screenplay.NOTE, _("Note"), "ChangeToNote"),
        ]

    def OnElemTypeBar(self, lt):
        self.panel.ctrl.changeType(lt)
        self.panel.ctrl.SetFocus()

    def getElemTypeToolTip(self, lt):
        for itemLt, label, cmdName in self.getElemTypes():
            if itemLt == lt:
                break

        s = _("Change element to %s") % label

        for cmd in self.gd.cfgGl.commands:
            if (cmd.name == cmdName) and cmd.keys:
                s += " (%s)" % util.Key.fromInt(cmd.keys[0]).toStr()

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

    # the status bar at the bottom of the window. a narrow, borderless
    # spacer field keeps the text off the window's left edge. the help field
    # shows the hovered menu item's or toolbar tool's help (wx puts it in
    # the frame's status bar pane, set to SB_HELP below), then come the
    # element types Enter / Tab would create, the script's word count and
    # estimated running time, the current page and the zoom buttons.
    def createStatusBar(self):
        # created with one field, as splitting the still unsized bar into
        # all of them makes wx log SB_GETRECT errors; the rest are added
        # below, along with their widths
        sb = self.CreateStatusBar(1)
        self.statusBar = sb

        # a bit taller than the default, so the text isn't cramped
        sb.SetMinHeight(sb.GetCharHeight() + sb.FromDIP(14))

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

        styles = [wx.SB_NORMAL] * len(widths)
        styles[self.SB_SPACER] = wx.SB_FLAT
        sb.SetStatusStyles(styles)
        self.SetStatusBarPane(self.SB_HELP)

        sb.Bind(wx.EVT_SIZE, self.OnStatusBarSize)

        self.updateZoomStatus()

        # the status bar may already have its final size, in which case no
        # size event comes
        wx.CallAfter(self.layoutZoomButtons)

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

    def ShowHideToolbar(self, event=None):
        self.toolBar.Show(self.menuBar.IsChecked(ID_SHOW_HIDE_TOOLBAR))
        self.Layout()

    def OnViewModeLayout(self):
        self.menuBar.Check(ID_VIEW_STYLE_LAYOUT, True)
        self.OnViewModeChange()

    def OnViewModeSideBySide(self):
        self.menuBar.Check(ID_VIEW_STYLE_SIDE_BY_SIDE, True)
        self.OnViewModeChange()

    def OnViewModeChange(self, event=None):
        if self.menuBar.IsChecked(ID_VIEW_STYLE_DRAFT):
            mode = self.gd.VIEWMODE_DRAFT
        elif self.menuBar.IsChecked(ID_VIEW_STYLE_LAYOUT):
            mode = self.gd.VIEWMODE_LAYOUT
        else:
            mode = self.gd.VIEWMODE_SIDE_BY_SIDE

        self.gd.setViewMode(mode)

        for c in self.getCtrls():
            c.refreshCache()

        c = self.panel.ctrl
        c.makeLineVisible(c.sp.line)
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
        self.panel.ctrl.refreshGuiConfig()

        for c in self.getCtrls():
            c.refreshCache()

        c = self.panel.ctrl
        c.makeLineVisible(c.sp.line)
        c.updateScreen()

    def ToggleFullscreen(self, event=None):
        fullScreen = not self.IsFullScreen()

        self.noFSBtn.Show(fullScreen)

        # FULLSCREEN_ALL only hides the bars the frame manages
        if self.ownMenuBar:
            self.menuBar.Show(not fullScreen)
            self.toolBar.Show(
                not fullScreen and self.menuBar.IsChecked(ID_SHOW_HIDE_TOOLBAR)
            )

        self.ShowFullScreen(fullScreen, wx.FULLSCREEN_ALL)
        self.Layout()
        self.panel.ctrl.SetFocus()

    def OnPaginate(self, event=None):
        self.panel.ctrl.OnPaginate()

    def OnLockPages(self, event=None):
        self.panel.ctrl.OnLockPages()

    def OnUnlockPages(self, event=None):
        self.panel.ctrl.OnUnlockPages()

    def OnAutoCompletionDlg(self, event=None):
        self.panel.ctrl.OnAutoCompletionDlg()

    def OnTitlesDlg(self, event=None):
        self.panel.ctrl.OnTitlesDlg()

    def OnHeadersDlg(self, event=None):
        self.panel.ctrl.OnHeadersDlg()

    def OnLocationsDlg(self, event=None):
        self.panel.ctrl.OnLocationsDlg()

    def OnCharacterProfilesDlg(self, event=None):
        self.panel.ctrl.OnCharacterProfilesDlg()

    def OnSpellCheckerDictionaryDlg(self, event=None):
        dlg = spellcheckcfgdlg.SCDictDlg(self, copy.deepcopy(self.gd.scDict), True)

        if dlg.ShowModal() == wx.ID_OK:
            self.gd.scDict = dlg.scDict
            self.gd.saveScDict()

        dlg.Destroy()

    def OnSpellCheckerScriptDictionaryDlg(self, event=None):
        self.panel.ctrl.OnSpellCheckerScriptDictionaryDlg()

    def OnWatermark(self, event=None):
        self.panel.ctrl.OnWatermark()

    def OnScriptSettings(self, event=None):
        self.panel.ctrl.OnScriptSettings()

    # the LoadScriptSettings / SaveScriptSettingsAs keyboard commands. the
    # page setup dialog has buttons for these too.
    def OnLoadScriptSettings(self, event=None):
        path = cfgdlg.askScriptSettingsFile(self, self.gd.scriptSettingsPath, False)
        if not path:
            return

        c = cfgdlg.loadScriptCfg(path, self)
        if c:
            self.panel.ctrl.applyCfg(c)
            self.gd.scriptSettingsPath = os.path.dirname(path)

    def OnSaveScriptSettingsAs(self, event=None):
        path = cfgdlg.askScriptSettingsFile(self, self.gd.scriptSettingsPath, True)
        if not path:
            return

        if util.writeToFile(path, self.panel.ctrl.sp.saveCfg(), self):
            self.gd.scriptSettingsPath = os.path.dirname(path)

    def OnReportCharacter(self, event=None):
        self.panel.ctrl.OnReportCharacter()

    def OnReportDialogueChart(self, event=None):
        self.panel.ctrl.OnReportDialogueChart()

    def OnReportLocation(self, event=None):
        self.panel.ctrl.OnReportLocation()

    def OnReportScene(self, event=None):
        self.panel.ctrl.OnReportScene()

    def OnReportScript(self, event=None):
        self.panel.ctrl.OnReportScript()

    def OnSpellCheckerDlg(self, event=None):
        self.panel.ctrl.OnSpellCheckerDlg()

    def OnNameDatabase(self, event=None):
        if not namesdlg.readNames(self):
            wx.MessageBox(_("Error opening name database."), _("Error"), wx.OK, self)

            return

        dlg = namesdlg.NamesDlg(self, self.panel.ctrl)
        dlg.ShowModal()
        dlg.Destroy()

    def OnCharacterMap(self, event=None):
        dlg = charmapdlg.CharMapDlg(self, self.panel.ctrl)
        dlg.ShowModal()
        dlg.Destroy()

    def OnCompareScripts(self, event=None):
        self.panel.ctrl.OnCompareScripts()

    def OnChangeType(self, event):
        self.panel.ctrl.OnChangeType(event)

    # build the editor's right-click menu. curLt is the type of the
    # element(s) it applies to, or None if they're of more than one type.
    # dualState: None if dual dialogue can't be toggled at the cursor,
    # otherwise whether the cursor is in a dual dialogue.
    def makeRightClickMenu(self, curLt, withCut, dualState=None):
        types = (
            (ID_ELEM_TO_SCENE, screenplay.SCENE, "S", _("Scene")),
            (ID_ELEM_TO_ACTION, screenplay.ACTION, "A", _("Action")),
            (ID_ELEM_TO_CHARACTER, screenplay.CHARACTER, "C", _("Character")),
            (ID_ELEM_TO_PAREN, screenplay.PAREN, "P", _("Parenthetical")),
            (ID_ELEM_TO_DIALOGUE, screenplay.DIALOGUE, "D", _("Dialogue")),
            (ID_ELEM_TO_TRANSITION, screenplay.TRANSITION, "T", _("Transition")),
            (ID_ELEM_TO_SHOT, screenplay.SHOT, "o", _("Shot")),
            (ID_ELEM_TO_ACTBREAK, screenplay.ACTBREAK, "b", _("Act break")),
            (ID_ELEM_TO_NOTE, screenplay.NOTE, "N", _("Note")),
        )

        m = wx.Menu()

        if curLt is None:
            header = _("Multiple types")
        else:
            header = next(t[3] for t in types if t[1] == curLt)

        m.Append(wx.ID_ANY, header).Enable(False)

        switchMenu = wx.Menu()

        for id, lt, key, name in types:
            if lt != curLt:
                switchMenu.Append(id, misc.mnemonic(key, name))

        m.AppendSubMenu(switchMenu, _("Switch type"))

        if dualState is not None:
            m.AppendCheckItem(ID_EDIT_DUAL_DIALOGUE, _("Dual dialogue")).Check(
                dualState
            )

        m.AppendSeparator()

        m.Append(ID_EDIT_SELECT_SCENE, _("Select scene"))
        m.AppendSeparator()

        if withCut:
            m.Append(ID_EDIT_CUT, _("Cut"))
            m.Append(ID_EDIT_COPY, _("Copy"))

        m.Append(ID_EDIT_PASTE, _("Paste"))

        return m

    def OnHelpCommands(self, event=None):
        dlg = commandsdlg.CommandsDlg(self.gd.cfgGl)
        dlg.Show()

    def OnHelpManual(self, event=None):
        webbrowser.open("file://" + misc.getFullPath("trelby/manual.html"))

    def OnAbout(self, event=None):
        win = splash.SplashWindow(self, -1)
        win.Show()

    def OnToolBarMenu(self, event, menu):
        self.PopupMenu(menu)

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
                self.OnSave()
            elif response == wx.ID_NO:
                discard = True
            elif response == wx.ID_CANCEL:
                doExit = False

        if doExit:
            self.autosaveTimer.Stop()

            # changes the user didn't explicitly discard but that still
            # aren't saved (e.g. other tabs, or a cancelled save) are kept
            # for recovery on the next startup
            for c in self.getCtrls():
                if discard:
                    c.removeRecovery()
                else:
                    c.autosave()

            util.writeToFile(self.gd.stateFilename, self.gd.save(), self)
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
