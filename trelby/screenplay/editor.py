# the editing session on a Screenplay: cursor, selection, scroll
# position, auto-completion list, typing style, undo history and the
# commands that work on them.
#
# TRANSITIONAL: for now this only forwards these names to the Screenplay,
# which still holds the state.

# state that belongs to the editing session
STATE = frozenset(
    (
        "line",
        "column",
        "mark",
        "_topLine",
        "acItems",
        "acSel",
        "acMax",
        "typingStyle",
        "undoHistory",
    )
)

# methods that belong to the editing session
METHODS = frozenset(
    (
        # model
        "cursorAsMark",
        "applyCfg",
        "reformatAll",
        "save",
        "getTopLine",
        "setTopLine",
        "gotoPos",
        "validatePos",
        "_validate",
        # structure, at the cursor
        "getElemFirstIndex",
        "getElemLastIndex",
        "getElemIndexes",
        "getSceneIndexes",
        "isAtEndOfParen",
        # wrapping, keeping the cursor on the same text
        "rewrapPara",
        "rewrapPrevPara",
        "rewrapElem",
        "rewrapElems",
        "reformatRange",
        "rewrapSpeechesAround",
        # centering
        "getActionsForCentering",
        "getCenteredState",
        "toggleCentered",
        # dual dialogue
        "getDualToggle",
        "toggleDualDialogue",
        # locks
        "lockPages",
        "unlockPages",
        "lockScenes",
        "unlockScenes",
        # outline
        "setSceneColor",
        "moveScene",
        "moveSceneTo",
        # editing
        "convertTypeTo",
        "joinLines",
        "splitLine",
        "splitElement",
        "deleteChar",
        "removeElementTypes",
        "renameCharacters",
        # formatting
        "getTypingStyle",
        "getFormatState",
        "toggleFormat",
        # auto-completion
        "clearAutoComp",
        "fillAutoComp",
        "pageScrollAutoComp",
        "offerAutoComp",
        "isAutoCompPartial",
        "acceptAutoComp",
        "getMatchingText",
        # selection
        "getMarkedLines",
        "getMarkedColumns",
        "isLineMarked",
        "getSelectedAsCD",
        "paste",
        "setMark",
        "clearMark",
        "maybeMark",
        "selectWordAt",
        "selectElementAt",
        # commands
        "cmdPost",
        "cmd",
        "cmdChars",
        "tabMakesNew",
        "capitalizeNeeded",
    )
)


class Editor:
    def __init__(self, sp):
        object.__setattr__(self, "sp", sp)

    def __getattr__(self, name):
        if (name in STATE) or (name in METHODS) or name.endswith("Cmd"):
            return getattr(self.sp, name)

        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in STATE:
            setattr(self.sp, name, value)
        else:
            object.__setattr__(self, name, value)
