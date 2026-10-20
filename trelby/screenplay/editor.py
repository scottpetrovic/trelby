# the editing session on a script: an Editor holds a Screenplay (sp, the
# document) and everything about editing it that isn't saved with it:
# the cursor, the selection, the scroll position, the auto-completion
# list, the typing style and the undo history. the commands the editor
# runs, and every undoable edit, are Editor methods.
#
# most of its methods come from the Editor-side mixins, one module per
# area (commands, textinput, selection...; see __init__.py for the map).
# what's here is the state itself, the cursor helpers, and the wrapping
# functions that keep the cursor on the same text.

import copy

import trelby.util as util
from trelby.screenplay.autocomp import AutoCompletionMixin
from trelby.screenplay.beatboard import BeatBoardEditMixin
from trelby.screenplay.centering import CenteringEditMixin
from trelby.screenplay.commands import CommandsMixin
from trelby.screenplay.constants import PAREN
from trelby.screenplay.datatypes import Mark
from trelby.screenplay.dualdialogue import DualDialogueEditMixin
from trelby.screenplay.editing import EditingMixin
from trelby.screenplay.formatting import FormattingMixin
from trelby.screenplay.locks import LocksEditMixin
from trelby.screenplay.notes import NotesEditMixin
from trelby.screenplay.revisions import RevisionsEditMixin
from trelby.screenplay.sceneoutline import OutlineEditMixin
from trelby.screenplay.search import SearchEditMixin
from trelby.screenplay.selection import SelectionMixin
from trelby.screenplay.textinput import TextInputMixin
from trelby.screenplay.undohistory import UndoHistory


class Editor(
    CenteringEditMixin,
    DualDialogueEditMixin,
    LocksEditMixin,
    OutlineEditMixin,
    BeatBoardEditMixin,
    NotesEditMixin,
    RevisionsEditMixin,
    EditingMixin,
    FormattingMixin,
    SearchEditMixin,
    AutoCompletionMixin,
    SelectionMixin,
    CommandsMixin,
    TextInputMixin,
):
    def __init__(self, sp):
        self.sp = sp

        # cursor position: line and column. starts where it was when the
        # script was saved (see save).
        self.line = sp.cfg.cursorLine
        self.column = sp.cfg.cursorColumn
        self.validatePos()

        # first line shown on screen. use getTopLine/setTopLine to access
        # this.
        self._topLine = 0

        # how many pixels further down than usual the screen is drawn from
        # the top line, negative for up. only typewriter scrolling (see
        # viewmode.ViewMode.scrollLineTo) sets it, to keep the cursor's
        # line at the same height.
        self.topOffset = 0

        # Mark object if selection active, or None.
        self.mark = None

        # list of active auto-completion strings
        self.acItems = None

        # selected auto-completion item (only valid when acItems contains
        # something)
        self.acSel = -1

        # max nr of auto comp items displayed at once
        self.acMax = 10

        # (line, column, style): the style (see textfmt) to type text in
        # at that cursor position, set by toggling bold etc. with nothing
        # selected, or None. see getTypingStyle.
        self.typingStyle = None

        # see undohistory.py
        self.undoHistory = UndoHistory()

    def cursorAsMark(self):
        return Mark(self.line, self.column)

    # return the script as the contents of a .trelby file, with the
    # cursor position in it
    def save(self) -> bytes:
        self.sp.cfg.cursorLine = self.line
        self.sp.cfg.cursorColumn = self.column

        return self.sp.save()

    # apply new config.
    #
    # a new config can change the width of every element, and undo
    # objects refer to line numbers in the old wrapping, so the undo
    # history is thrown away (reformatAll insists on that).
    def applyCfg(self, cfg):
        self.undoHistory.clear()

        self.sp.cfg = copy.deepcopy(cfg)
        self.sp.cfg.recalc()
        self.reformatAll()
        self.sp.paginate()

        self.sp.markChanged()

    # get topLine, clamping it to the valid range in the process.
    def getTopLine(self):
        self._topLine = util.clamp(self._topLine, 0, len(self.sp.lines) - 1)

        return self._topLine

    # set topLine, clamping it to the valid range.
    def setTopLine(self, line):
        self._topLine = util.clamp(line, 0, len(self.sp.lines) - 1)

    # move to line,col, and if mark is True, set mark there
    def gotoPos(self, line, col, mark=False):
        self.clearAutoComp()

        self.line = line
        self.column = col

        if mark and not self.mark:
            self.setMark(line, col)

    # make sure current line and column are within the valid bounds.
    def validatePos(self):
        self.line, self.column = self.sp.clampPos(self.line, self.column)

    def getElemFirstIndex(self):
        return self.sp.getElemFirstIndexFromLine(self.line)

    def getElemLastIndex(self):
        return self.sp.getElemLastIndexFromLine(self.line)

    def getElemIndexes(self):
        return self.sp.getElemIndexesFromLine(self.line)

    def getSceneIndexes(self):
        return self.sp.getSceneIndexesFromLine(self.line)

    # returns True if we're at second-to-last character of PAREN element,
    # and last character is ")"
    def isAtEndOfParen(self):
        ls = self.sp.lines

        return (
            self.sp.isLastLineOfElem(self.line)
            and (ls[self.line].lt == PAREN)
            and (ls[self.line].text[self.column :] == ")")
        )

    # the Screenplay's wrapping functions (see wrapping.py), keeping the
    # cursor on the same text. rewrapPara and rewrapElem default to the
    # paragraph / element the cursor is in.

    def reformatAll(self):
        # doing a reformatAll while we have undo history will completely
        # break undo, so that can't be allowed.
        assert self.undoHistory.isEmpty()

        self.sp.reformatAll(self)

    def reformatRange(self, par1, par2):
        self.sp.reformatRange(par1, par2, self)

    def rewrapPara(self, line1=-1):
        if line1 == -1:
            line1 = self.sp.getParaFirstIndexFromLine(self.line)

        return self.sp.rewrapPara(line1, self)

    def rewrapElem(self, line=-1):
        if line == -1:
            line = self.getElemFirstIndex()

        self.sp.rewrapElem(line, self)

    def rewrapElems(self, line, count):
        self.sp.rewrapElems(line, count, self)

    def rewrapSpeechesAround(self, line1, line2):
        self.sp.rewrapSpeechesAround(line1, line2, self)

    # rewraps paragraph previous to current one.
    def rewrapPrevPara(self):
        line = self.sp.getParaFirstIndexFromLine(self.line)

        if line == 0:
            return

        line = self.sp.getParaFirstIndexFromLine(line - 1)
        self.rewrapPara(line)

    # check the script and the editing state for internal consistency.
    # raises an AssertionError on errors. ONLY MEANT TO BE USED IN TEST
    # CODE.
    def _validate(self):
        # cursor position must be valid
        assert self.line >= 0
        assert self.line < len(self.sp.lines)
        assert self.column >= 0
        assert self.column <= len(self.sp.lines[self.line].text)

        self.sp._validate()
