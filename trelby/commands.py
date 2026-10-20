# the keyboard commands (actions in the main program that can be bound to
# keys), their default key bindings, and helpers for editing the bindings.
# the global config (config.ConfigGlobal.commands) holds the list of them.

import copy

import trelby.keys as keys
import trelby.mypickle as mypickle
import trelby.textutil as textutil
from trelby.error import ConfigError

# scrolling  directions
SCROLL_UP = 0
SCROLL_DOWN = 1
SCROLL_CENTER = 2

# CTRL+SHIFT+Space shows or hides the side panel. it used to insert a
# non-breaking space (see config.ConfigGlobal.load).
SIDE_PANEL_KEY = keys.Key(keys.WXK_SPACE, ctrl=True, shift=True).toInt()


# command (an action in the main program)
class Command:
    cvars = None

    def __init__(
        self,
        name,
        desc,
        defKeys=[],
        isMovement=False,
        isFixed=False,
        isMenu=False,
        scrollDirection=SCROLL_CENTER,
    ):

        # name, e.g. "MoveLeft"
        self.name = name

        # textual description
        self.desc = desc

        # default keys (list of serialized keys.Key objects (ints))
        self.defKeys = defKeys

        # is this a movement command
        self.isMovement = isMovement

        # some commands & their keys (Tab, Enter, Quit, etc) are fixed and
        # can't be changed
        self.isFixed = isFixed

        # is this a menu item
        self.isMenu = isMenu

        # which way the command wants to scroll the page
        self.scrollDirection = scrollDirection

        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            v.addList(
                "keys", [], "Keys", mypickle.IntVar("", 0, "", 0, 9223372036854775808)
            )

            v.makeDicts()

        # this is not actually needed but let's keep it for consistency
        self.__class__.cvars.setDefaults(self)

        self.keys = copy.deepcopy(self.defKeys)

    # fixed commands aren't saved, so their keys can't be changed by
    # editing the config file either. a command the user has removed all
    # keys from is saved with the single key 0, since an empty list would
    # load as "not in the file" and get the default keys back (see load).
    def save(self, prefix):
        if self.isFixed:
            return ""

        prefix += "%s/" % self.name

        if len(self.keys) > 0:
            return self.cvars.save(prefix, self)
        else:
            self.keys.append(0)
            s = self.cvars.save(prefix, self)
            self.keys = []

            return s

    def load(self, vals, prefix):
        if self.isFixed:
            return

        prefix += "%s/" % self.name

        tmp = copy.deepcopy(self.keys)
        self.cvars.load(vals, prefix, self)

        if len(self.keys) == 0:
            # we have a new command in the program not found in the old
            # config file
            self.keys = tmp
        elif self.keys[0] == 0:
            self.keys = []

        # weed out invalid bindings: a plain character key (no CTRL or ALT)
        # can't be a command, since it's needed for typing
        tmp2 = self.keys
        self.keys = []

        for k in tmp2:
            k2 = keys.Key.fromInt(k)
            if not k2.isValidInputChar():
                self.keys.append(k)


# return a new list of all the commands, with their default keys. the list
# must be in alphabetical order (see checkOrder).
def defaultCommands():
    return [
        Command(
            "Abort",
            _("Abort something, e.g. selection, auto-completion, etc."),
            [keys.WXK_ESCAPE],
            isFixed=True,
        ),
        Command("About", _("Show the about dialog."), isMenu=True),
        Command(
            "AddNote",
            _("Add a note to the current paragraph."),
            [keys.Key(ord("N"), alt=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "AutoCompletionDlg",
            _("Open the auto-completion dialog."),
            isMenu=True,
        ),
        Command(
            "ChangeToActBreak",
            _("Change current element's style to act break."),
            [keys.Key(ord("B"), alt=True).toInt()],
        ),
        Command(
            "ChangeToAction",
            _("Change current element's style to action."),
            [keys.Key(ord("A"), alt=True).toInt()],
        ),
        Command(
            "ChangeToCharacter",
            _("Change current element's style to character."),
            [keys.Key(ord("C"), alt=True).toInt()],
        ),
        Command(
            "ChangeToDialogue",
            _("Change current element's style to dialogue."),
            [keys.Key(ord("D"), alt=True).toInt()],
        ),
        Command(
            "ChangeToParenthetical",
            _("Change current element's style to parenthetical."),
            [keys.Key(ord("P"), alt=True).toInt()],
        ),
        Command(
            "ChangeToScene",
            _("Change current element's style to" " scene."),
            [keys.Key(ord("S"), alt=True).toInt()],
        ),
        Command("ChangeToShot", _("Change current element's style to shot.")),
        Command(
            "ChangeToTransition",
            _("Change current element's style to transition."),
            [keys.Key(ord("T"), alt=True).toInt()],
        ),
        Command("CharacterMap", _("Open the character map."), isMenu=True),
        Command(
            "CharacterProfilesDlg",
            _("Open the character profiles dialog."),
            isMenu=True,
        ),
        Command(
            "CheckFormatting",
            _("Check the current script for formatting errors."),
            [keys.Key(5, ctrl=True).toInt()],
            isMenu=True,
        ),
        Command(
            "CloseScript",
            _("Close the current script."),
            [keys.Key(23, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command("CompareScripts", _("Compare two scripts."), isMenu=True),
        Command(
            "Copy",
            _("Copy selected text to the internal clipboard."),
            [keys.Key(3, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "CopySystemCb",
            _("Copy selected text to the system's clipboard, unformatted."),
            isMenu=True,
        ),
        Command(
            "CopySystemCbFormatted",
            _("Copy selected text to the system's clipboard, formatted."),
            isMenu=True,
        ),
        Command(
            "Cut",
            _("Cut selected text to internal clipboard."),
            [keys.Key(24, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "Delete",
            _("Delete the character under the cursor, or selected text."),
            [keys.WXK_DELETE],
            isFixed=True,
        ),
        Command(
            "DeleteBackward",
            _("Delete the character behind the cursor."),
            [keys.WXK_BACK, keys.Key(keys.WXK_BACK, shift=True).toInt()],
            isFixed=True,
        ),
        Command(
            "DeleteElements",
            _("Open the 'Delete elements' dialog."),
            isMenu=True,
        ),
        Command(
            "DualDialogue",
            _(
                "Turn dual dialogue on or off for the current speech"
                " and the one before it."
            ),
            [keys.Key(4, ctrl=True).toInt()],
            isMenu=True,
        ),
        Command("ExportScript", _("Export the current script."), isMenu=True),
        Command(
            "FindAndReplaceDlg",
            _("Open the 'Find & Replace' dialog."),
            [keys.Key(6, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "FocusMode",
            _("Toggle focus mode, fading all but the current element or scene."),
            [keys.Key(keys.WXK_F11, shift=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command("FooterDlg", _("Open the page footer dialog."), isMenu=True),
        Command(
            "ForcedLineBreak",
            _("Insert a forced line break."),
            [
                keys.Key(keys.WXK_RETURN, ctrl=True).toInt(),
                keys.Key(keys.WXK_RETURN, shift=True).toInt(),
                # CTRL+Enter under wxMSW
                keys.Key(10, ctrl=True).toInt(),
            ],
            isFixed=True,
        ),
        Command(
            "Fullscreen",
            _("Toggle fullscreen."),
            [keys.Key(keys.WXK_F11).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "GotoPage",
            _("Goto to a given page."),
            [keys.Key(7, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "GotoScene",
            _("Goto to a given scene."),
            [keys.Key(ord("G"), alt=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command("HeadersDlg", _("Open the headers dialog."), isMenu=True),
        Command(
            "HelpCommands",
            _("Show list of commands and their key bindings."),
            isMenu=True,
        ),
        Command("HelpManual", _("Open the manual."), isMenu=True),
        Command("ImportScript", _("Import a script."), isMenu=True),
        Command(
            "InsertNbsp",
            _("Insert non-breaking space."),
            isMenu=True,
        ),
        Command(
            "LoadScriptSettings",
            _("Load script-specific settings."),
            isMenu=True,
        ),
        Command("LoadSettings", _("Load global settings."), isMenu=True),
        Command("LocationsDlg", _("Open the locations dialog."), isMenu=True),
        Command(
            "MoveDown",
            _("Move down."),
            [keys.WXK_DOWN],
            isMovement=True,
            scrollDirection=SCROLL_DOWN,
        ),
        Command(
            "MoveEndOfLine",
            _("Move to the end of the line or finish auto-completion."),
            [keys.WXK_END],
            isMovement=True,
        ),
        Command(
            "MoveEndOfScript",
            _("Move to the end of the script."),
            [keys.Key(keys.WXK_END, ctrl=True).toInt()],
            isMovement=True,
        ),
        Command("MoveLeft", _("Move left."), [keys.WXK_LEFT], isMovement=True),
        Command(
            "MoveNextWord",
            _("Move to start of next word."),
            [keys.Key(keys.WXK_RIGHT, ctrl=True).toInt()],
            isMovement=True,
            isFixed=True,
        ),
        Command(
            "MovePageDown",
            _("Move one page down."),
            [keys.WXK_PAGEDOWN],
            isMovement=True,
        ),
        Command(
            "MovePageUp",
            _("Move one page up."),
            [keys.WXK_PAGEUP],
            isMovement=True,
        ),
        Command(
            "MovePrevWord",
            _("Move to start of previous word."),
            [keys.Key(keys.WXK_LEFT, ctrl=True).toInt()],
            isMovement=True,
            isFixed=True,
        ),
        Command("MoveRight", _("Move right."), [keys.WXK_RIGHT], isMovement=True),
        Command(
            "MoveSceneDown",
            _("Move one scene down."),
            [keys.Key(keys.WXK_DOWN, ctrl=True).toInt()],
            isMovement=True,
        ),
        Command(
            "MoveSceneUp",
            _("Move one scene up."),
            [keys.Key(keys.WXK_UP, ctrl=True).toInt()],
            isMovement=True,
        ),
        Command(
            "MoveStartOfLine",
            _("Move to the start of the line."),
            [keys.WXK_HOME],
            isMovement=True,
        ),
        Command(
            "MoveStartOfScript",
            _("Move to the start of the" " script."),
            [keys.Key(keys.WXK_HOME, ctrl=True).toInt()],
            isMovement=True,
        ),
        Command(
            "MoveUp",
            _("Move up."),
            [keys.WXK_UP],
            isMovement=True,
            scrollDirection=SCROLL_UP,
        ),
        Command(
            "NameDatabase", _("Open the character name database."), isMenu=True
        ),
        Command(
            "NewElement",
            _("Create a new element."),
            [keys.WXK_RETURN],
            isFixed=True,
        ),
        Command(
            "NewScript",
            _("Create a new script."),
            [keys.Key(14, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "OpenScript",
            _("Open a script."),
            [keys.Key(15, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "Paste",
            _("Paste text from the internal clipboard."),
            [keys.Key(22, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "PasteSystemCb",
            _("Paste text from the system's clipboard."),
            isMenu=True,
        ),
        Command(
            "PauseSprint",
            _("Pause or resume the writing sprint."),
            [keys.Key(keys.WXK_F7, shift=True).toInt()],
            isMenu=True,
        ),
        Command(
            "PrintScript",
            _("Print current script."),
            [keys.Key(16, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "Quit",
            _("Quit the program."),
            [keys.Key(17, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ReadAloud",
            _(
                "Read the script aloud from the cursor, or pause / resume reading."
            ),
            [keys.Key(keys.WXK_F5).toInt()],
            isMenu=True,
        ),
        Command(
            "ReadAloudNext",
            _("While reading aloud, go to the next element."),
            [keys.Key(keys.WXK_F6).toInt()],
            isMenu=True,
        ),
        Command(
            "ReadAloudPrev",
            _("While reading aloud, go back to the previous element."),
            [keys.Key(keys.WXK_F6, shift=True).toInt()],
            isMenu=True,
        ),
        Command(
            "ReadAloudStop",
            _("Stop reading aloud."),
            [keys.Key(keys.WXK_F5, shift=True).toInt()],
            isMenu=True,
        ),
        Command(
            "Redo",
            _("Redo a change that was reverted through undo."),
            [keys.Key(25, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ReportCharacter", _("Generate character report."), isMenu=True
        ),
        Command(
            "ReportDialogueChart",
            _("Generate dialogue chart report."),
            isMenu=True,
        ),
        Command("ReportLocation", _("Generate location report."), isMenu=True),
        Command("ReportScene", _("Generate scene report."), isMenu=True),
        Command("ReportScript", _("Generate script report."), isMenu=True),
        Command(
            "RevertScript",
            _("Revert current script to the version on disk."),
            isMenu=True,
        ),
        Command(
            "SaveScript",
            _("Save the current script."),
            [keys.Key(19, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "SaveScriptAs",
            _("Save the current script to a new file."),
            isMenu=True,
        ),
        Command(
            "SaveScriptSettingsAs",
            _("Save script-specific settings to a new file."),
            isMenu=True,
        ),
        Command(
            "SaveSettingsAs",
            _("Save global settings to a new file."),
            isMenu=True,
        ),
        Command(
            "ScriptNext",
            _("Change to next open script."),
            [
                keys.Key(keys.WXK_TAB, ctrl=True).toInt(),
                keys.Key(keys.WXK_PAGEDOWN, ctrl=True).toInt(),
            ],
            isMenu=True,
        ),
        Command(
            "ScriptPrev",
            _("Change to previous open script."),
            [
                keys.Key(keys.WXK_TAB, shift=True, ctrl=True).toInt(),
                keys.Key(keys.WXK_PAGEUP, ctrl=True).toInt(),
            ],
            isMenu=True,
        ),
        Command(
            "ScriptSettings", _("Change script-specific settings."), isMenu=True
        ),
        Command("SelectAll", _("Select the entire script."), isMenu=True),
        Command(
            "SelectScene",
            _("Select the current scene."),
            [keys.Key(1, ctrl=True).toInt()],
            isMenu=True,
        ),
        Command(
            "SetMark",
            _("Set mark at current cursor position."),
        ),
        Command("Settings", _("Change global settings."), isMenu=True),
        Command(
            "SpellCheckerDictionaryDlg",
            _("Open the global spell checker dictionary dialog."),
            isMenu=True,
        ),
        Command(
            "SpellCheckerDlg",
            _("Spell check the script."),
            [keys.Key(keys.WXK_F8).toInt()],
            isMenu=True,
        ),
        Command(
            "SpellCheckerScriptDictionaryDlg",
            _("Open the script-specific spell checker dictionary dialog."),
            isMenu=True,
        ),
        Command(
            "Tab",
            _(
                "Change current element to the next style or create a new element."
            ),
            [keys.WXK_TAB],
            isFixed=True,
        ),
        Command(
            "TabPrev",
            _("Change current element to the previous style."),
            [keys.Key(keys.WXK_TAB, shift=True).toInt()],
            isFixed=True,
        ),
        Command("TitlesDlg", _("Open the titles dialog."), isMenu=True),
        Command(
            "ToggleBeatBoard",
            _("Switch between the script and its beat board."),
            [keys.Key(keys.WXK_SPACE, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ToggleBold",
            _("Make the selected text, or the text typed next, bold or not."),
            [keys.Key(2, ctrl=True).toInt()],
            isMenu=True,
        ),
        Command(
            "ToggleCentered",
            _("Center the current action element, or stop centering it."),
            isMenu=True,
        ),
        Command(
            "ToggleItalic",
            _(
                "Make the selected text, or the text typed next, italic"
                " or not."
            ),
            # CTRL+I comes in as the same key code as CTRL+Tab, so
            # it's only a menu accelerator (see MyFrame), which
            # sees the two apart
            isMenu=True,
        ),
        Command(
            "ToggleNotes",
            _(
                "Show the notes in the side panel, or hide the side panel"
                " if it's showing them."
            ),
            isMenu=True,
        ),
        Command(
            "ToggleOutline",
            _(
                "Show the outline in the side panel, or hide the side panel"
                " if it's showing it."
            ),
            isMenu=True,
        ),
        Command(
            "ToggleReadAloud",
            _(
                "Show the read aloud controls and voices in the side panel, or"
                " hide the side panel if it's showing them."
            ),
            isMenu=True,
        ),
        Command(
            "ToggleShowFormatting",
            _("Toggle 'Show formatting' display."),
            isMenu=True,
        ),
        Command(
            "ToggleSidePanel",
            _("Show or hide the side panel with the outline and the notes."),
            [SIDE_PANEL_KEY],
            isMenu=True,
        ),
        Command(
            "ToggleSprint",
            _("Start a writing sprint, or stop the one going on."),
            [keys.Key(keys.WXK_F7).toInt()],
            isMenu=True,
        ),
        Command(
            "ToggleTypewriter",
            _("Toggle typewriter scrolling, keeping the cursor's line in place."),
            isMenu=True,
        ),
        Command(
            "ToggleUnderline",
            _(
                "Make the selected text, or the text typed next,"
                " underlined or not."
            ),
            [keys.Key(21, ctrl=True).toInt()],
            isMenu=True,
        ),
        Command(
            "Undo",
            _("Undo the last change."),
            [keys.Key(26, ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ViewModeDraft", _("Change view mode to continuous."), isMenu=True
        ),
        Command(
            "ViewModeLayout", _("Change view mode to page."), isMenu=True
        ),
        Command(
            "ViewModeSideBySide",
            _("Change view mode to side by side."),
            isMenu=True,
        ),
        Command("Watermark", _("Export the current script as watermarked PDFs."), isMenu=True),
        Command(
            "WorldBuildingDlg",
            _("Open the world building dialog."),
            isMenu=True,
        ),
        Command(
            "WritingGoals",
            _("Set the daily and weekly writing goals and the sprints' length."),
            isMenu=True,
        ),
        Command(
            "ZoomIn",
            _("Zoom in."),
            [keys.Key(ord("="), ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ZoomOut",
            _("Zoom out."),
            [keys.Key(ord("-"), ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
        Command(
            "ZoomReset",
            _("Reset zoom to 100%."),
            [keys.Key(ord("0"), ctrl=True).toInt()],
            isFixed=True,
            isMenu=True,
        ),
    ]


# raise ConfigError if commands isn't in alphabetical order.
def checkOrder(commands):
    names = [cmd.name for cmd in commands]
    namesSorted = sorted(names)

    if names != namesSorted:
        # for i in range(len(names)):
        #     if names[i] != namesSorted[i]:
        #         print "Got: %s Expected: %s" % (names[i], namesSorted[i])

        # if you get this error, you've put a new command you've added
        # in an incorrect place in the command list. uncomment the
        # above lines to figure out where it should be.
        raise ConfigError(_("Commands not listed in correct order"))


# add SHIFT+Key alias for all keys bound to movement commands, so
# selection-movement works. the aliases are real entries in cmd.keys,
# which removeKey takes out along with the key itself.
def addShiftKeys(commands):
    for cmd in commands:
        if cmd.isMovement:
            nk = []

            for key in cmd.keys:
                k = keys.Key.fromInt(key)
                k.shift = True
                ki = k.toInt()

                if ki not in cmd.keys:
                    nk.append(ki)

            cmd.keys.extend(nk)


# remove key (int) from given cmd
def removeKey(cmd, key):
    cmd.keys.remove(key)

    if cmd.isMovement:
        k = keys.Key.fromInt(key)
        k.shift = True
        ki = k.toInt()

        if ki in cmd.keys:
            cmd.keys.remove(ki)


# get textual description of conflicting keys, or None if no
# conflicts.
def getConflictingKeys(commands):
    bound = {}

    for cmd in commands:
        for key in cmd.keys:
            if key in bound:
                bound[key].append(cmd.name)
            else:
                bound[key] = [cmd.name]

    s = ""
    for k, v in bound.items():
        if len(v) > 1:
            s += "%s:" % keys.Key.fromInt(k).toStr()

            for cmd in v:
                s += " %s" % cmd

            s += "\n"

    if s == "":
        return None
    else:
        return s


# return the commands' key bindings as a dict (key = keys.Key.toInt(),
# value = Command) for resolveKey. fixed menu commands (New, Open, Save,
# Quit...) are left out: their keys are their menu items' accelerators,
# which wx handles before a key reaches the editor.
def makeKeyMap(commands):
    keyMap = {}

    for cmd in commands:
        if not (cmd.isFixed and cmd.isMenu):
            for key in cmd.keys:
                keyMap[key] = cmd

    return keyMap


# work out what a key pressed in the editor does. uc is the key event's
# Unicode character (keys.WXK_NONE if it has none) and keyCode its key
# code. returns (char, cmd): the character to type, or the Command in
# keyMap (see makeKeyMap) the key is bound to. both are None if the key
# does nothing.
def resolveKey(keyMap, uc, keyCode, ctrl=False, alt=False, shift=False):
    if (
        not ctrl
        and not alt
        and (uc != keys.WXK_NONE)
        and textutil.isValidInputChar(uc)
    ):
        return (chr(uc), None)

    # the key code to look up commands with. non-character keys (arrows,
    # Home, PgUp, F-keys...) have no Unicode value, only a key code. key
    # codes above 255 are wx.WXK_ constants, so a character above 255 must
    # not be used as one: "ł" (322) is wx.WXK_INSERT.
    if (uc != keys.WXK_NONE) and (uc < 256):
        kc = uc
    else:
        kc = keyCode

    return (None, keyMap.get(keys.Key(kc, ctrl, alt, shift).toInt()))
