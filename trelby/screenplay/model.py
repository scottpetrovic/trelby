# the Screenplay class, the document: a script's lines and everything
# stored with them (title pages, headers, config, character profiles...)
# and the page breaks worked out from them. editing it at a cursor, with
# undo, is done through an Editor (editor.py).
#
# most of its methods come from the mixins it's made of, one module per
# area (structure, wrapping, pagination...); see __init__.py for the map.
# what's here is the state itself and the few methods that don't belong
# to any one area.

import copy

import trelby.screenplay.autocompletion as autocompletion
import trelby.screenplay.beatboard as beatboard
import trelby.screenplay.characterprofiles as characterprofiles
import trelby.config as config
import trelby.screenplay.headers as headers
import trelby.screenplay.locations as locations
import trelby.screenplay.revisions as revisions
import trelby.screenplay.tableread as tableread
import trelby.screenplay.fileformat as fileformat
import trelby.spellcheck as spellcheck
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.screenplay.titles as titles
import trelby.util as util
import trelby.screenplay.worldbuilding as worldbuilding
from trelby.screenplay.line import Line
from trelby.screenplay.breakdown import BreakdownMixin
from trelby.screenplay.centering import CenteringMixin
from trelby.screenplay.constants import (
    LB_LAST,
    LB_NONE,
    SCENE,
)
from trelby.screenplay.dualdialogue import DualDialogueMixin
from trelby.screenplay.locks import LocksMixin
from trelby.screenplay.notes import NotesMixin
from trelby.screenplay.pagination import PaginationMixin
from trelby.screenplay.revisions import RevisionsMixin
from trelby.screenplay.sceneoutline import OutlineMixin
from trelby.screenplay.structure import StructureMixin
from trelby.screenplay.wrapping import WrappingMixin


class Screenplay(
    StructureMixin,
    WrappingMixin,
    CenteringMixin,
    DualDialogueMixin,
    PaginationMixin,
    LocksMixin,
    OutlineMixin,
    NotesMixin,
    BreakdownMixin,
    RevisionsMixin,
):
    def __init__(self, cfgGl):
        self.autoCompletion = autocompletion.AutoCompletion()
        self.headers = headers.Headers()
        self.footer = headers.Footer()
        self.locations = locations.Locations()
        self.titles = titles.Titles()
        self.scDict = spellcheck.Dict()
        self.characterProfiles = characterprofiles.CharacterProfiles()
        self.worldBuilding = worldbuilding.WorldBuilding()
        self.beatBoard = beatboard.BeatBoard()

        # the voices chosen by hand for reading the script aloud
        self.readAloud = tableread.VoiceSettings()

        # the revision settings: the current revision, revision mode...
        self.revisions = revisions.Revisions()

        self.lines = [Line(LB_LAST, SCENE)]

        self.cfgGl = cfgGl
        self.cfg = config.Config()

        # pagination: pages[n] is the last line on page n (1-based) and
        # pages[0] is -1. pagesNoAdjust is the same, but without the
        # adjustments made to avoid things like dangling scene headings.
        # pageLabels[n] is the label printed on page n, which differs from
        # n once pages are locked (see paginate).
        self.pages = [-1, 0]
        self.pagesNoAdjust = [-1, 0]
        self.pageLabels = ["", "1"]

        # True if script has had changes done to it after
        # load/save/creation.
        self.hasChanged = False

        # how many times it's been marked changed, which goes up with every
        # edit, so that watchers can tell whether it has changed since they
        # last looked (see writingsession.py)
        self.changeCount = 0

    def isModified(self):
        if not self.hasChanged:
            return False

        # nothing of value is ever lost by not saving a completely empty
        # script, and it's annoying getting warnings about unsaved changes
        # on those, so don't do that

        return (len(self.lines) > 1) or bool(self.lines[0].text)

    def markChanged(self, state=True):
        self.hasChanged = state

        if state:
            self.changeCount += 1

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
        sp.footer = copy.deepcopy(self.footer)
        sp.locations = copy.deepcopy(self.locations)
        sp.titles = copy.deepcopy(self.titles)
        sp.scDict = copy.deepcopy(self.scDict)
        sp.characterProfiles = copy.deepcopy(self.characterProfiles)
        sp.worldBuilding = copy.deepcopy(self.worldBuilding)
        sp.beatBoard = copy.deepcopy(self.beatBoard)
        sp.readAloud = copy.deepcopy(self.readAloud)
        sp.revisions = copy.deepcopy(self.revisions)

        sp.lines = [ln.copy() for ln in self.lines]

        # pagination starts out fresh, so a caller that needs page numbers
        # from the copy must paginate it first.
        return sp

    # return the script as the contents of a .trelby file (see
    # fileformat). the cursor position saved in it is cfg.cursorLine /
    # cursorColumn, which Editor.save sets from the editor's cursor.
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
            return textutil.upper(line.text)

        return line.text

    # return (line, column) moved to the nearest valid cursor position
    def clampPos(self, line, column):
        line = util.clamp(line, 0, len(self.lines) - 1)

        return (line, util.clamp(column, 0, len(self.lines[line].text)))

    # check script for internal consistency. raises an AssertionError on
    # errors. ONLY MEANT TO BE USED IN TEST CODE.
    def _validate(self):
        # type of previous line, or None when a new element starts
        prevType = None

        # there must be at least one line
        assert len(self.lines) > 0

        for ln in self.lines:
            tcfg = self.cfg.getType(ln.lt)

            # lines should not contain invalid characters
            assert ln.text == textutil.toInputStr(ln.text)

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

            # and so do revision marks
            if ln.revs is not None:
                assert len(ln.revs) == len(ln.text)
                assert ln.revs == textfmt.compact(ln.revs)
                assert max(ln.revs) <= revisions.levelChar(revisions.MAX_LEVEL)

            if prevType:
                assert ln.lt == prevType

            if ln.lb == LB_LAST:
                prevType = None
            else:
                prevType = ln.lt
