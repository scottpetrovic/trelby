# the Screenplay class: a script's lines and everything stored with them
# (title pages, headers, config, character profiles...), plus the editing
# state (cursor, selection, scroll position, auto-completion list, undo
# history).
#
# most of its methods come from the mixins it's made of, one module per
# area (structure, wrapping, pagination, commands...); see __init__.py
# for the map. what's here is the state itself and the few methods that
# don't belong to any one area.

import copy

import trelby.autocompletion as autocompletion
import trelby.characterprofiles as characterprofiles
import trelby.config as config
import trelby.headers as headers
import trelby.locations as locations
import trelby.screenplay.fileformat as fileformat
import trelby.spellcheck as spellcheck
import trelby.textfmt as textfmt
import trelby.titles as titles
import trelby.util as util
import trelby.worldbuilding as worldbuilding
from trelby.line import Line
from trelby.screenplay.autocomp import AutoCompletionMixin
from trelby.screenplay.centering import CenteringMixin
from trelby.screenplay.commands import CommandsMixin
from trelby.screenplay.constants import (
    LB_LAST,
    LB_NONE,
    SCENE,
)
from trelby.screenplay.datatypes import Mark
from trelby.screenplay.dualdialogue import DualDialogueMixin
from trelby.screenplay.editing import EditingMixin
from trelby.screenplay.formatting import FormattingMixin
from trelby.screenplay.locks import LocksMixin
from trelby.screenplay.pagination import PaginationMixin
from trelby.screenplay.sceneoutline import OutlineMixin
from trelby.screenplay.selection import SelectionMixin
from trelby.screenplay.structure import StructureMixin
from trelby.screenplay.textinput import TextInputMixin
from trelby.screenplay.undohistory import UndoHistory
from trelby.screenplay.wrapping import WrappingMixin


class Screenplay(
    StructureMixin,
    WrappingMixin,
    CenteringMixin,
    DualDialogueMixin,
    PaginationMixin,
    LocksMixin,
    OutlineMixin,
    EditingMixin,
    FormattingMixin,
    AutoCompletionMixin,
    SelectionMixin,
    CommandsMixin,
    TextInputMixin,
):
    def __init__(self, cfgGl):
        self.autoCompletion = autocompletion.AutoCompletion()
        self.headers = headers.Headers()
        self.locations = locations.Locations()
        self.titles = titles.Titles()
        self.scDict = spellcheck.Dict()
        self.characterProfiles = characterprofiles.CharacterProfiles()
        self.worldBuilding = worldbuilding.WorldBuilding()

        self.lines = [Line(LB_LAST, SCENE)]

        self.cfgGl = cfgGl
        self.cfg = config.Config()

        # cursor position: line and column
        self.line = 0
        self.column = 0

        # first line shown on screen. use getTopLine/setTopLine to access
        # this.
        self._topLine = 0

        # Mark object if selection active, or None.
        self.mark = None

        # pagination: pages[n] is the last line on page n (1-based) and
        # pages[0] is -1. pagesNoAdjust is the same, but without the
        # adjustments made to avoid things like dangling scene headings.
        # pageLabels[n] is the label printed on page n, which differs from
        # n once pages are locked (see paginate).
        self.pages = [-1, 0]
        self.pagesNoAdjust = [-1, 0]
        self.pageLabels = ["", "1"]

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

        # True if script has had changes done to it after
        # load/save/creation.
        self.hasChanged = False

        # see undohistory.py
        self.undoHistory = UndoHistory()

    def isModified(self):
        if not self.hasChanged:
            return False

        # nothing of value is ever lost by not saving a completely empty
        # script, and it's annoying getting warnings about unsaved changes
        # on those, so don't do that

        return (len(self.lines) > 1) or bool(self.lines[0].text)

    def markChanged(self, state=True):
        self.hasChanged = state

    def cursorAsMark(self):
        return Mark(self.line, self.column)

    # we implement our own custom deepcopy because it's 8-10x faster than
    # the generic one (times reported by cmdSpeedTest using a 119-page
    # screenplay):
    #
    # ╭─────────────────────────────┬─────────┬────────╮
    # │                             │ Generic │ Custom │
    # ├─────────────────────────────┼─────────┼────────┤
    # │ Intel Core Duo T2050 1.6GHz │  0.173s │ 0.020s │
    # │ Intel i5-2400 3.1GHz        │  0.076s │ 0.007s │
    # ╰─────────────────────────────┴─────────┴────────╯
    def __deepcopy__(self, memo):
        sp = Screenplay(self.cfgGl)
        sp.cfg = copy.deepcopy(self.cfg)

        sp.autoCompletion = copy.deepcopy(self.autoCompletion)
        sp.headers = copy.deepcopy(self.headers)
        sp.locations = copy.deepcopy(self.locations)
        sp.titles = copy.deepcopy(self.titles)
        sp.scDict = copy.deepcopy(self.scDict)
        sp.characterProfiles = copy.deepcopy(self.characterProfiles)
        sp.worldBuilding = copy.deepcopy(self.worldBuilding)

        sp.lines = [ln.copy() for ln in self.lines]

        # "open PDF on current page" breaks on scripts we're removing
        # notes from before printing if we don't copy these
        sp.line = self.line
        sp.column = self.column

        # everything else (pagination, undo history, selection,
        # auto-completion) starts out fresh, so a caller that needs page
        # numbers from the copy must paginate it first.
        return sp

    # apply new config.
    #
    # a new config can change the width of every element, and undo
    # objects refer to line numbers in the old wrapping, so the undo
    # history is thrown away (reformatAll insists on that).
    def applyCfg(self, cfg):
        self.undoHistory.clear()

        self.cfg = copy.deepcopy(cfg)
        self.cfg.recalc()
        self.reformatAll()
        self.paginate()

        self.markChanged()

    # return the script as the contents of a .trelby file (see fileformat)
    def save(self) -> bytes:
        return fileformat.save(self)

    # parse the contents of a .trelby file (see fileformat). returns
    # (Screenplay, message), where message is a string of warnings about
    # unknown or invalid data, or "".
    @staticmethod
    def load(s, cfgGl):
        return fileformat.load(s, cfgGl)

    # return script config as a string.
    def saveCfg(self):
        return self.cfg.save()

    # return line i's text for export, upper-cased if its type's export
    # style says so
    def getExportText(self, i):
        line = self.lines[i]

        if self.cfg.getType(line.lt).export.isCaps:
            return util.upper(line.text)

        return line.text

    # get topLine, clamping it to the valid range in the process.
    def getTopLine(self):
        self._topLine = util.clamp(self._topLine, 0, len(self.lines) - 1)

        return self._topLine

    # set topLine, clamping it to the valid range.
    def setTopLine(self, line):
        self._topLine = util.clamp(line, 0, len(self.lines) - 1)

    # move to line,col, and if mark is True, set mark there
    def gotoPos(self, line, col, mark=False):
        self.clearAutoComp()

        self.line = line
        self.column = col

        if mark and not self.mark:
            self.setMark(line, col)

    # make sure current line and column are within the valid bounds.
    def validatePos(self):
        self.line = util.clamp(self.line, 0, len(self.lines) - 1)
        self.column = util.clamp(self.column, 0, len(self.lines[self.line].text))

    # check script for internal consistency. raises an AssertionError on
    # errors. ONLY MEANT TO BE USED IN TEST CODE.
    def _validate(self):
        # type of previous line, or None when a new element starts
        prevType = None

        # there must be at least one line
        assert len(self.lines) > 0

        # cursor position must be valid
        assert self.line >= 0
        assert self.line < len(self.lines)
        assert self.column >= 0
        assert self.column <= len(self.lines[self.line].text)

        for ln in self.lines:
            tcfg = self.cfg.getType(ln.lt)

            # lines should not contain invalid characters
            assert ln.text == util.toInputStr(ln.text)

            # lines shouldn't be longer than the type's maximum width,
            # unless the extra characters are all spaces
            assert len(ln.text.rstrip(" ")) <= (tcfg.width // self.cfg.getCharWidth())

            # lines with LB_NONE linebreaks that end in a space should be
            # LB_SPACE instead
            if ln.lb == LB_NONE:
                assert not ln.text.endswith(" ")

            # format strings go with the text exactly, and are None if
            # there's no formatting
            if ln.fmt is not None:
                assert len(ln.fmt) == len(ln.text)
                assert ln.fmt == textfmt.compact(ln.fmt)
                assert not ln.fmt.strip("01234567")

            if prevType:
                assert ln.lt == prevType

            if ln.lb == LB_LAST:
                prevType = None
            else:
                prevType = ln.lt
