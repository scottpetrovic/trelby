# the main window's menus, toolbar buttons and menu keyboard commands, all
# made from one table (makeTable) of Actions: each has the menu item's id
# and label, the code it runs and when it can be used. MyFrame builds the
# menu bar from it (build), binds the items (bind), and runs the keyboard
# commands that are menu commands (commands.Command.isMenu) by name, the
# Action's name being the Command's.

import os

import wx

import trelby.formats as formats
import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.ui.scriptactions as scriptactions
import trelby.textfmt as textfmt
import trelby.translations as translations
from trelby.ui.globaldata import GlobalData
from trelby.ui.ids import *
from trelby.reports.reportframes import (
    genCharacterReport,
    genDialogueChart,
    genLocationReport,
    genSceneReport,
    genScriptReport,
)


# runs a scriptactions function on the current script, as func(frame,
# ctrl, *args)
class OnScript:
    def __init__(self, func, *args):
        self.func = func
        self.args = args

    def __call__(self, frame):
        self.func(frame, frame.panel.ctrl, *self.args)


# runs a MyFrame method, as frame.<method>(*args)
class OnFrame:
    def __init__(self, method, *args):
        self.method = method
        self.args = args

    def __call__(self, frame):
        getattr(frame, self.method)(*self.args)


class Action:
    def __init__(
        self,
        name,
        id,
        label,
        mnemonic,
        run,
        accel=None,
        dots=False,
        canUse=None,
        kind=wx.ITEM_NORMAL,
    ):
        # name of the keyboard command (see commands.py), if there's one
        # for this, or a name of its own
        self.name = name

        # menu / toolbar id, or None for keyboard commands without a menu
        # item
        self.id = id

        # the menu item's label, the letter to underline in it (None for
        # none), its shortcut (e.g. "CTRL-N"), and whether the label ends in
        # "...", which it does if a dialog asks for more before anything
        # happens
        self.label = label
        self.mnemonic = mnemonic
        self.accel = accel
        self.dots = dots

        # OnScript or OnFrame
        self.run = run

        # function(frame, ctrl) returning whether the item is enabled, or
        # None if it always is. wx asks this when a menu is opened, and on
        # some platforms (GTK) also when idle, which keeps the items'
        # shortcuts working, as those of a disabled item don't do anything
        # there. so it has to be quick.
        self.canUse = canUse

        # wx.ITEM_NORMAL, ITEM_CHECK or ITEM_RADIO
        self.kind = kind

    def getMenuLabel(self):
        s = self.label + ("..." if self.dots else "")

        if self.mnemonic:
            s = misc.mnemonic(self.mnemonic, s)

        if self.accel:
            s += "\t" + self.accel

        return s


# a separator in a menu
SEP = None


# a menu: label, mnemonic, and items: Actions, SEPs and submenus. items can
# instead be the name of one filled in by build ("recent" or "language").
# if key is given, build returns the wx.Menu under it.
class Menu:
    def __init__(self, label, mnemonic, items, key=None):
        self.label = label
        self.mnemonic = mnemonic
        self.items = items
        self.key = key


# the element types, in the order the toolbar and the right-click menu show
# them: line type, id of the right-click menu item that changes to it,
# label, mnemonic, and the keyboard command that changes to it
def elemTypes():
    return [
        (screenplay.SCENE, ID_ELEM_TO_SCENE, _("Scene"), "S", "ChangeToScene"),
        (screenplay.ACTION, ID_ELEM_TO_ACTION, _("Action"), "A", "ChangeToAction"),
        (
            screenplay.CHARACTER,
            ID_ELEM_TO_CHARACTER,
            _("Character"),
            "C",
            "ChangeToCharacter",
        ),
        (
            screenplay.PAREN,
            ID_ELEM_TO_PAREN,
            _("Parenthetical"),
            "P",
            "ChangeToParenthetical",
        ),
        (
            screenplay.DIALOGUE,
            ID_ELEM_TO_DIALOGUE,
            _("Dialogue"),
            "D",
            "ChangeToDialogue",
        ),
        (
            screenplay.TRANSITION,
            ID_ELEM_TO_TRANSITION,
            _("Transition"),
            "T",
            "ChangeToTransition",
        ),
        (screenplay.SHOT, ID_ELEM_TO_SHOT, _("Shot"), "o", "ChangeToShot"),
        (
            screenplay.ACTBREAK,
            ID_ELEM_TO_ACTBREAK,
            _("Act break"),
            "b",
            "ChangeToActBreak",
        ),
        (screenplay.NOTE, ID_ELEM_TO_NOTE, _("Note"), "N", "ChangeToNote"),
    ]


# the table: returns (menus, others), where menus is the menu bar's Menus,
# and others the Actions that aren't in it: keyboard commands without a
# menu item, the toolbar's own buttons and the right-click menu's type
# changes
def makeTable():
    def marked(f, c):
        return bool(c.ed.mark)

    hasManual = os.path.exists(misc.getFullPath("trelby/manual.html"))

    def exportAction(f):
        name = "ExportScript" if f.key == "pdf" else "Export" + f.key.capitalize()

        return Action(
            name,
            wx.NewIdRef(),
            f.menuLabel(),
            f.mnemonic,
            OnScript(scriptactions.exportScript, f),
            dots=True,
        )

    def importAction(f):
        name = "ImportScript" if f.key == "text" else "Import" + f.key.capitalize()

        return Action(
            name,
            wx.NewIdRef(),
            f.menuLabel(),
            f.mnemonic,
            OnFrame("OnImportScript", f),
            dots=True,
        )

    exportItems = [exportAction(f) for f in formats.EXPORT_FORMATS]
    exportItems.insert(
        1,
        Action(
            "Watermark",
            ID_FILE_EXPORT_WATERMARK,
            _("Watermarked PDF"),
            "W",
            OnScript(scriptactions.watermark),
            dots=True,
        ),
    )

    fileMenu = Menu(
        _("File"),
        "F",
        [
            Action(
                "NewScript",
                ID_FILE_NEW,
                _("New"),
                "N",
                OnFrame("OnNewScript"),
                "CTRL-N",
            ),
            Action(
                "OpenScript",
                ID_FILE_OPEN,
                _("Open"),
                "O",
                OnFrame("OnOpen"),
                "CTRL-O",
                True,
            ),
            Menu(_("Open Recent"), "R", "recent"),
            Action(
                "SaveScript",
                ID_FILE_SAVE,
                _("Save"),
                "S",
                OnScript(scriptactions.save),
                "CTRL-S",
            ),
            Action(
                "SaveScriptAs",
                ID_FILE_SAVE_AS,
                _("Save As"),
                "A",
                OnScript(scriptactions.saveAs),
                dots=True,
            ),
            Action(
                "CloseScript",
                ID_FILE_CLOSE,
                _("Close"),
                "C",
                OnFrame("OnCloseScript"),
                "CTRL-W",
            ),
            Action(
                "RevertScript",
                ID_FILE_REVERT,
                _("Revert"),
                "v",
                OnScript(scriptactions.revert),
                canUse=lambda f, c: bool(c.fileName) and c.sp.hasChanged,
            ),
            SEP,
            Menu(
                _("Import"),
                "I",
                [importAction(f) for f in formats.IMPORT_FORMATS],
                "import",
            ),
            Menu(_("Export"), "E", exportItems, "export"),
            SEP,
            Action("Quit", ID_FILE_EXIT, _("Exit"), "x", OnFrame("OnExit"), "CTRL-Q"),
        ],
    )

    editMenu = Menu(
        _("Edit"),
        "E",
        [
            Action(
                "Undo",
                ID_EDIT_UNDO,
                _("Undo"),
                "U",
                OnScript(scriptactions.undo),
                "CTRL-Z",
            ),
            Action(
                "Redo",
                ID_EDIT_REDO,
                _("Redo"),
                "R",
                OnScript(scriptactions.redo),
                "CTRL-Y",
            ),
            SEP,
            Action(
                "Cut",
                ID_EDIT_CUT,
                _("Cut"),
                "t",
                OnScript(scriptactions.cut),
                "CTRL-X",
                canUse=marked,
            ),
            Action(
                "Copy",
                ID_EDIT_COPY,
                _("Copy"),
                "C",
                OnScript(scriptactions.copySelection),
                "CTRL-C",
                canUse=marked,
            ),
            Action(
                "Paste",
                ID_EDIT_PASTE,
                _("Paste"),
                "P",
                OnScript(scriptactions.paste),
                "CTRL-V",
                canUse=lambda f, c: bool(c.gd.clipboard),
            ),
            SEP,
            Menu(
                _("Copy (system)"),
                "o",
                [
                    Action(
                        "CopySystemCb",
                        ID_EDIT_COPY_TO_CB,
                        _("Unformatted"),
                        "U",
                        OnScript(scriptactions.copySystem, False),
                        canUse=marked,
                    ),
                    Action(
                        "CopySystemCbFormatted",
                        ID_EDIT_COPY_TO_CB_FMT,
                        _("Formatted"),
                        "F",
                        OnScript(scriptactions.copySystem, True),
                        canUse=marked,
                    ),
                ],
            ),
            Action(
                "PasteSystemCb",
                ID_EDIT_PASTE_FROM_CB,
                _("Paste (system)"),
                "a",
                OnScript(scriptactions.pasteSystem),
            ),
            SEP,
            Action(
                "SelectScene",
                ID_EDIT_SELECT_SCENE,
                _("Select scene"),
                "S",
                OnScript(scriptactions.selectScene),
            ),
            Action(
                "SelectAll",
                ID_EDIT_SELECT_ALL,
                _("Select all"),
                "l",
                OnScript(scriptactions.selectAll),
            ),
            SEP,
            Action(
                "FindAndReplaceDlg",
                ID_EDIT_FIND,
                _("Find && Replace"),
                "F",
                OnScript(scriptactions.find),
                "CTRL-F",
                True,
            ),
            Action(
                "GotoPage",
                ID_EDIT_GOTO_PAGE,
                _("Goto page"),
                "G",
                OnScript(scriptactions.gotoPage),
                "CTRL-G",
                True,
            ),
            Action(
                "GotoScene",
                ID_EDIT_GOTO_SCENE,
                _("Goto scene"),
                "e",
                OnScript(scriptactions.gotoScene),
                "ALT-G",
                True,
                canUse=lambda f, c: c.sp.hasScenes(),
            ),
            SEP,
            Action(
                "ToggleBold",
                ID_EDIT_BOLD,
                _("Bold"),
                "B",
                OnScript(scriptactions.toggleFormat, textfmt.BOLD),
                "CTRL-B",
            ),
            Action(
                "ToggleItalic",
                ID_EDIT_ITALIC,
                _("Italic"),
                "I",
                OnScript(scriptactions.toggleFormat, textfmt.ITALIC),
                "CTRL-I",
            ),
            Action(
                "ToggleUnderline",
                ID_EDIT_UNDERLINE,
                _("Underline"),
                "U",
                OnScript(scriptactions.toggleFormat, textfmt.UNDERLINED),
                "CTRL-U",
            ),
            Action(
                "ToggleCentered",
                ID_EDIT_CENTER,
                _("Center action"),
                "t",
                OnScript(scriptactions.toggleCentered),
                canUse=lambda f, c: c.ed.getCenteredState() is not None,
            ),
            SEP,
            Action(
                "InsertNbsp",
                ID_EDIT_INSERT_NBSP,
                _("Insert non-breaking space"),
                None,
                OnScript(scriptactions.insertNbsp),
            ),
            Action(
                "DualDialogue",
                ID_EDIT_DUAL_DIALOGUE,
                _("Dual dialogue"),
                "i",
                OnScript(scriptactions.dualDialogue),
                "CTRL-D",
                canUse=lambda f, c: c.ed.getDualToggle() is not None,
            ),
            Action(
                "DeleteElements",
                ID_EDIT_DELETE_ELEMENTS,
                _("Delete elements"),
                "D",
                OnScript(scriptactions.deleteElements),
                dots=True,
            ),
            SEP,
            Action(
                "Settings",
                ID_SETTINGS_CHANGE,
                _("Settings"),
                "n",
                OnFrame("OnSettings"),
                dots=True,
            ),
        ],
    )

    def zoomStep(step):
        return lambda f, c: f.gd.getZoomStep(step) != f.gd.zoom

    viewMenu = Menu(
        _("View"),
        "V",
        [
            Action(
                "ViewModeDraft",
                ID_VIEW_STYLE_DRAFT,
                _("Continuous"),
                "C",
                OnFrame("setViewMode", GlobalData.VIEWMODE_DRAFT),
                kind=wx.ITEM_RADIO,
            ),
            Action(
                "ViewModeLayout",
                ID_VIEW_STYLE_LAYOUT,
                _("Page"),
                "P",
                OnFrame("setViewMode", GlobalData.VIEWMODE_LAYOUT),
                kind=wx.ITEM_RADIO,
            ),
            Action(
                "ViewModeSideBySide",
                ID_VIEW_STYLE_SIDE_BY_SIDE,
                _("Side by side"),
                "S",
                OnFrame("setViewMode", GlobalData.VIEWMODE_SIDE_BY_SIDE),
                kind=wx.ITEM_RADIO,
            ),
            SEP,
            Action(
                "ShowHideToolbar",
                ID_SHOW_HIDE_TOOLBAR,
                _("Toolbar"),
                "T",
                OnFrame("ShowHideToolbar"),
                kind=wx.ITEM_CHECK,
            ),
            Action(
                "ToggleOutline",
                ID_VIEW_SHOW_OUTLINE,
                _("Outline"),
                "O",
                OnFrame("OnToggleOutline"),
                kind=wx.ITEM_CHECK,
            ),
            Action(
                "ToggleBeatBoard",
                ID_VIEW_BEAT_BOARD,
                _("Beat board"),
                "B",
                OnFrame("OnToggleBeatBoard"),
                kind=wx.ITEM_CHECK,
            ),
            Action(
                "ToggleShowFormatting",
                ID_VIEW_SHOW_FORMATTING,
                _("Show formatting"),
                "h",
                OnFrame("OnToggleShowFormatting"),
                kind=wx.ITEM_CHECK,
            ),
            SEP,
            Action(
                "ZoomIn",
                ID_VIEW_ZOOM_IN,
                _("Zoom in"),
                "I",
                OnFrame("OnZoomIn"),
                "CTRL-=",
                canUse=zoomStep(1),
            ),
            Action(
                "ZoomOut",
                ID_VIEW_ZOOM_OUT,
                _("Zoom out"),
                "U",
                OnFrame("OnZoomOut"),
                "CTRL--",
                canUse=zoomStep(-1),
            ),
            Action(
                "ZoomReset",
                ID_VIEW_ZOOM_RESET,
                _("Reset zoom"),
                "R",
                OnFrame("OnZoomReset"),
                "CTRL-0",
                canUse=lambda f, c: f.gd.zoom != 100,
            ),
            SEP,
            Action(
                "Fullscreen",
                ID_VIEW_FULL_SCREEN,
                _("Fullscreen"),
                "F",
                OnFrame("ToggleFullscreen"),
                "F11",
            ),
        ],
        "view",
    )

    # everything that is saved in the script file itself, as opposed to
    # the global settings and tools
    scriptMenu = Menu(
        _("Script"),
        "S",
        [
            Action(
                "ScriptSettings",
                ID_SCRIPT_SETTINGS_CHANGE,
                _("Script settings"),
                "S",
                OnScript(scriptactions.scriptSettings),
                dots=True,
            ),
            Action(
                "TitlesDlg",
                ID_SCRIPT_TITLES,
                _("Title pages"),
                "T",
                OnScript(scriptactions.titlesDlg),
                dots=True,
            ),
            Action(
                "HeadersDlg",
                ID_SCRIPT_HEADERS,
                _("Page headers"),
                "H",
                OnScript(scriptactions.headersDlg),
                dots=True,
            ),
            Action(
                "FooterDlg",
                ID_SCRIPT_FOOTER,
                _("Page footer"),
                "F",
                OnScript(scriptactions.footerDlg),
                dots=True,
            ),
            SEP,
            Action(
                "CharacterProfilesDlg",
                ID_SCRIPT_CHARACTER_PROFILES,
                _("Character profiles"),
                "C",
                OnScript(scriptactions.characterProfilesDlg),
                dots=True,
            ),
            Action(
                "LocationsDlg",
                ID_SCRIPT_LOCATIONS,
                _("Locations"),
                "o",
                OnScript(scriptactions.locationsDlg),
                dots=True,
            ),
            Action(
                "WorldBuildingDlg",
                ID_SCRIPT_WORLD_BUILDING,
                _("World building"),
                "W",
                OnScript(scriptactions.worldBuildingDlg),
                dots=True,
            ),
            Action(
                "AutoCompletionDlg",
                ID_SCRIPT_AUTO_COMPLETION,
                _("Auto-completion"),
                "A",
                OnScript(scriptactions.autoCompletionDlg),
                dots=True,
            ),
            Action(
                "SpellCheckerScriptDictionaryDlg",
                ID_SCRIPT_SC_DICT,
                _("Script dictionary"),
                "d",
                OnScript(scriptactions.scriptDictionaryDlg),
                dots=True,
            ),
            SEP,
            Action(
                "LockPages",
                ID_SCRIPT_LOCK_PAGES,
                _("Lock pages"),
                "L",
                OnScript(scriptactions.lockPages),
            ),
            Action(
                "UnlockPages",
                ID_SCRIPT_UNLOCK_PAGES,
                _("Unlock pages"),
                "U",
                OnScript(scriptactions.unlockPages),
                canUse=lambda f, c: c.sp.hasPageLocks(),
            ),
            Action(
                "LockScenes",
                ID_SCRIPT_LOCK_SCENES,
                _("Lock scene numbers"),
                "n",
                OnScript(scriptactions.lockScenes),
            ),
            Action(
                "UnlockScenes",
                ID_SCRIPT_UNLOCK_SCENES,
                _("Unlock scene numbers"),
                "k",
                OnScript(scriptactions.unlockScenes),
                canUse=lambda f, c: c.sp.hasAnySceneLock(),
            ),
        ],
    )

    reportsMenu = Menu(
        _("Reports"),
        "R",
        [
            Action(
                "ReportScript",
                ID_REPORTS_SCRIPT_REP,
                _("Script report"),
                "r",
                OnScript(scriptactions.report, genScriptReport),
            ),
            Action(
                "ReportLocation",
                ID_REPORTS_LOCATION_REP,
                _("Location report"),
                "L",
                OnScript(scriptactions.report, genLocationReport),
                dots=True,
            ),
            Action(
                "ReportScene",
                ID_REPORTS_SCENE_REP,
                _("Scene report"),
                "S",
                OnScript(scriptactions.report, genSceneReport),
                dots=True,
            ),
            Action(
                "ReportCharacter",
                ID_REPORTS_CHARACTER_REP,
                _("Character report"),
                "C",
                OnScript(scriptactions.report, genCharacterReport),
                dots=True,
            ),
            Action(
                "ReportDialogueChart",
                ID_REPORTS_DIALOGUE_CHART,
                _("Dialogue chart"),
                "D",
                OnScript(scriptactions.report, genDialogueChart),
                dots=True,
            ),
        ],
    )

    toolsMenu = Menu(
        _("Tools"),
        "T",
        [
            Action(
                "SpellCheckerDlg",
                ID_TOOLS_SPELL_CHECK,
                _("Spell checker"),
                "S",
                OnScript(scriptactions.spellCheck),
                dots=True,
            ),
            Action(
                "CheckFormatting",
                ID_TOOLS_CHECK_FORMATTING,
                _("Check formatting errors"),
                "F",
                OnScript(scriptactions.checkFormatting),
                dots=True,
            ),
            SEP,
            Action(
                "NameDatabase",
                ID_TOOLS_NAME_DB,
                _("Name database"),
                "N",
                OnScript(scriptactions.nameDatabase),
                dots=True,
            ),
            Action(
                "CharacterMap",
                ID_TOOLS_CHARMAP,
                _("Character map"),
                "C",
                OnScript(scriptactions.characterMap),
                dots=True,
            ),
            SEP,
            Action(
                "CompareScripts",
                ID_TOOLS_COMPARE_SCRIPTS,
                _("Compare scripts"),
                "o",
                OnScript(scriptactions.compareScripts),
                dots=True,
                canUse=lambda f, c: f.tabCtrl.getPageCount() >= 2,
            ),
        ],
    )

    helpMenu = Menu(
        _("Help"),
        "H",
        [
            Action(
                "HelpCommands",
                ID_HELP_COMMANDS,
                _("Commands"),
                "C",
                OnFrame("OnHelpCommands"),
                dots=True,
            ),
            Action(
                "HelpManual",
                ID_HELP_MANUAL,
                _("Manual"),
                "M",
                OnFrame("OnHelpManual"),
                canUse=lambda f, c: hasManual,
            ),
            SEP,
            Action(
                "About",
                ID_HELP_ABOUT,
                _("About"),
                "A",
                OnFrame("OnAbout"),
                dots=True,
            ),
        ],
    )

    menus = [
        fileMenu,
        editMenu,
        viewMenu,
        scriptMenu,
        reportsMenu,
        toolsMenu,
        Menu(_("Language"), "L", "language"),
        helpMenu,
    ]

    others = [
        Action(
            "LoadScriptSettings",
            None,
            None,
            None,
            OnScript(scriptactions.loadScriptSettings),
        ),
        Action(
            "SaveScriptSettingsAs",
            None,
            None,
            None,
            OnScript(scriptactions.saveScriptSettingsAs),
        ),
        Action("LoadSettings", None, None, None, OnFrame("OnLoadSettings")),
        Action("SaveSettingsAs", None, None, None, OnFrame("OnSaveSettingsAs")),
        Action("ScriptNext", None, None, None, OnFrame("selectScript", True)),
        Action("ScriptPrev", None, None, None, OnFrame("selectScript", False)),
        Action(
            "SpellCheckerDictionaryDlg",
            None,
            None,
            None,
            OnFrame("OnSpellCheckerDictionaryDlg"),
        ),
        # the toolbar buttons that pop up a menu
        Action(
            "ToolbarImport",
            ID_FILE_IMPORT,
            None,
            None,
            OnFrame("popupMenu", "import"),
        ),
        Action(
            "ToolbarExport",
            ID_FILE_EXPORT,
            None,
            None,
            OnFrame("popupMenu", "export"),
        ),
        Action(
            "ToolbarViews",
            ID_TOOLBAR_VIEWS,
            None,
            None,
            OnFrame("popupMenu", "view"),
        ),
    ]

    for lt, id, label, mnemonic, cmdName in elemTypes():
        others.append(
            Action(
                "ElemTo" + cmdName[len("ChangeTo") :],
                id,
                label,
                mnemonic,
                OnScript(scriptactions.changeType, lt),
            )
        )

    return menus, others


# return all the Actions in makeTable's results
def allActions(menus, others):
    ret = []

    def add(items):
        for it in items:
            if isinstance(it, Menu):
                if not isinstance(it.items, str):
                    add(it.items)
            elif it is not SEP:
                ret.append(it)

    add(menus)

    return ret + others


# add the menus to the menu bar (a wx.MenuBar or menubar.MyMenuBar). gd is
# the GlobalData, for the recent files and the language. returns {key:
# wx.Menu} for the Menus that have a key.
def build(bar, menus, gd, onLanguage):
    keyed = {}

    def fill(menu, items):
        for it in items:
            if it is SEP:
                menu.AppendSeparator()
            elif isinstance(it, Menu):
                menu.AppendSubMenu(makeMenu(it), misc.mnemonic(it.mnemonic, it.label))
            else:
                menu.Append(it.id, it.getMenuLabel(), kind=it.kind)

    def makeMenu(m):
        menu = wx.Menu()

        if m.items == "recent":
            gd.mru.useMenu(menu)
        elif m.items == "language":
            fillLanguageMenu(menu, gd, onLanguage)
        else:
            fill(menu, m.items)

        if m.key:
            keyed[m.key] = menu

        return menu

    for m in menus:
        bar.Append(makeMenu(m), misc.mnemonic(m.mnemonic, m.label))

    return keyed


# one item per installed translation, each named in its own language,
# after one for the system's language. onLanguage(language) is called when
# one is picked.
def fillLanguageMenu(menu, gd, onLanguage):
    available = translations.getLanguages(translations.getLocaleDir())
    systemLanguage = translations.pickLanguage(
        "", os.environ.get("LANG", ""), available
    )
    chosen = translations.findLanguage(gd.cfgGl.language, available) or ""

    items = [
        ("", _("System default ({})").format(translations.languageName(systemLanguage)))
    ] + [(name, translations.languageName(name)) for name in available]

    for language, label in items:
        item = menu.AppendRadioItem(wx.ID_ANY, label)
        menu.Bind(
            wx.EVT_MENU, lambda event, lang=language: onLanguage(lang), item
        )

        if language == chosen:
            item.Check(True)


# bind the actions that have an id to frame: their menu items and toolbar
# buttons run them, and those with a canUse are enabled only when they can
# be used
# the Actions that work on the script at its cursor, or on how it's shown.
# they do nothing while the beat board is shown in the script's place (see
# MyPanel.showBeatBoard), and their menu items and buttons are greyed out,
# so that e.g. CTRL-X on the board doesn't cut text from the hidden script.
SCRIPT_ONLY = {
    "CheckFormatting",
    "Copy",
    "Cut",
    "DeleteElements",
    "DualDialogue",
    "FindAndReplaceDlg",
    "GotoPage",
    "GotoScene",
    "InsertNbsp",
    "NameDatabase",
    "CharacterMap",
    "Paste",
    "PasteSystemCb",
    "SelectAll",
    "SelectScene",
    "SpellCheckerDlg",
    "ToggleBold",
    "ToggleCentered",
    "ToggleItalic",
    "ToggleOutline",
    "ToggleShowFormatting",
    "ToggleUnderline",
    "ToolbarViews",
    "ViewModeDraft",
    "ViewModeLayout",
    "ViewModeSideBySide",
    "ZoomIn",
    "ZoomOut",
    "ZoomReset",
}


# whether Action a can't be used now because the beat board is shown
def isBlockedByBoard(frame, a):
    panel = getattr(frame, "panel", None)

    return bool(panel) and panel.boardShown and (
        (a.name in SCRIPT_ONLY) or a.name.startswith("ElemTo")
    )


# run Action a, unless the beat board blocks it
def runAction(frame, a):
    if not isBlockedByBoard(frame, a):
        a.run(frame)


def bind(frame, actions):
    for a in actions:
        if a.id is None:
            continue

        frame.Bind(wx.EVT_MENU, lambda event, a=a: runAction(frame, a), id=a.id)

        if a.canUse or (a.name in SCRIPT_ONLY):
            frame.Bind(
                wx.EVT_UPDATE_UI,
                lambda event, a=a: onUpdateUI(frame, event, a),
                id=a.id,
            )


# this can be called while MyFrame.init creates the first tab, before
# frame.panel exists, hence getattr
def onUpdateUI(frame, event, a):
    panel = getattr(frame, "panel", None)

    if panel:
        if isBlockedByBoard(frame, a):
            event.Enable(False)
        elif a.canUse:
            event.Enable(a.canUse(frame, panel.ctrl))
        else:
            event.Enable(True)


# build the editor's right-click menu from the actions ({name: Action}).
# curLt is the type of the element(s) it applies to, or None if they're of
# more than one type. dualState: None if dual dialogue can't be toggled at
# the cursor, otherwise whether the cursor is in a dual dialogue.
# centeredState is likewise for centering action elements. spelling, for a
# misspelled word, is a list of (id, label) items to put first, an id of
# None making the label a disabled item.
def makeRightClickMenu(
    actions,
    curLt,
    withCut,
    dualState=None,
    centeredState=None,
    spelling=None,
    synonyms=None,
):
    def append(menu, name, kind=wx.ITEM_NORMAL):
        a = actions[name]

        return menu.Append(a.id, a.getMenuLabel(), kind=kind)

    # (id, label) items, with None ids for headers
    def appendItems(menu, items):
        for id, label in items:
            if id is None:
                menu.Append(wx.ID_ANY, label).Enable(False)
            else:
                menu.Append(id, label)

    types = elemTypes()
    m = wx.Menu()

    if spelling:
        appendItems(m, spelling)
        m.AppendSeparator()

    if synonyms:
        synonymsMenu = wx.Menu()
        appendItems(synonymsMenu, synonyms)
        m.AppendSubMenu(synonymsMenu, _("Synonyms"))
        m.AppendSeparator()

    if curLt is None:
        header = _("Multiple types")
    else:
        header = next(label for lt, id, label, mnemonic, cmd in types if lt == curLt)

    m.Append(wx.ID_ANY, header).Enable(False)

    switchMenu = wx.Menu()

    for lt, id, label, mnemonic, cmdName in types:
        if lt != curLt:
            append(switchMenu, "ElemTo" + cmdName[len("ChangeTo") :])

    m.AppendSubMenu(switchMenu, _("Switch type"))

    if dualState is not None:
        append(m, "DualDialogue", wx.ITEM_CHECK).Check(dualState)

    if centeredState is not None:
        append(m, "ToggleCentered", wx.ITEM_CHECK).Check(centeredState)

    m.AppendSeparator()
    append(m, "SelectScene")
    m.AppendSeparator()

    if withCut:
        for name in ("ToggleBold", "ToggleItalic", "ToggleUnderline"):
            append(m, name)

        m.AppendSeparator()
        append(m, "Cut")
        append(m, "Copy")

    append(m, "Paste")

    return m
