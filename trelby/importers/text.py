# formatted text files, like Trelby's own text export: the element types
# are told apart by their indent.
#
# importing one has two steps, with the GUI's ImportDlg between them,
# where the user can change the guesses: guessIndents guesses each indent
# level's line type, and parse converts the lines, with the line types
# given in the options (or the guesses).

import re

import trelby.screenplay as screenplay
import trelby.textutil as textutil
from trelby.importers.common import ImportFailed, ImportResult, checkNotEmpty
from trelby.line import Line

# whether parse takes bytes rather than str
BINARY = False

# special linetype that means that indent contains action and scene lines,
# and scene lines are the ones that begin with "EXT." or "INT."
SCENE_ACTION = -2

# special linetype that means don't import those lines; useful for page
# numbers etc
IGNORE = -3

TAB_WIDTH = 4


# information about one indent level in imported text files.
class Indent:
    def __init__(self, indent):

        # indent level, i.e. spaces at the beginning
        self.indent = indent

        # lines with this indent, leading spaces removed
        self.lines = []

        # assigned line type, or -1 if not assigned yet.
        self.lt = -1

        # how many of the lines start with "EXT." or "INT."
        self.sceneStart = 0

        # how many of the lines have "CUT TO:" or "DISSOLVE TO:"
        self.trans = 0

        # how many of the lines have a form of "^ +\(.*)$", i.e. are most
        # likely parentheticals
        self.paren = 0


class Options:
    def __init__(self, lineTypes=None):
        # dict of indent -> line type (a screenplay line type, SCENE_ACTION
        # or IGNORE) for the indents not to use the guess for
        self.lineTypes = lineTypes or {}


# return the Indents of data's lines, with their line types guessed
def guessIndents(data):
    return list(_analyze(data)[1].values())


# convert data, with the line types guessed or given in options.
# the result always has at least one line.
def parse(data, options=None):
    options = options or Options()

    lines, indDict = _analyze(data)

    for indent, lt in options.lineTypes.items():
        indDict[indent].lt = lt

    return ImportResult(_convert(lines, indDict))


# return data's lines (tabs expanded, trailing spaces removed, and blank
# lines empty), and a dict of indent level -> Indent, with the line types
# guessed
def _analyze(data):
    checkNotEmpty(data)

    data = textutil.fixNL(data)
    lines = data.split("\n")

    # key = indent level, value = Indent
    indDict = {}

    for i in range(len(lines)):
        s = textutil.toInputStr(lines[i].rstrip().expandtabs(TAB_WIDTH))

        # don't count empty lines towards indentation statistics
        if s.strip() == "":
            lines[i] = ""

            continue

        cnt = textutil.countInitial(s, " ")

        ind = indDict.get(cnt)
        if not ind:
            ind = Indent(cnt)
            indDict[cnt] = ind

        tmp = s.upper()

        if textutil.multiFind(tmp, ["EXT.", "INT."]):
            ind.sceneStart += 1

        if textutil.multiFind(tmp, ["CUT TO:", "DISSOLVE TO:"]):
            ind.trans += 1

        if re.match(r"^ +\(.*\)$", tmp):
            ind.paren += 1

        ind.lines.append(s.lstrip())
        lines[i] = s

    if len(indDict) == 0:
        raise ImportFailed(_("File contains only empty lines."))

    _guessTypes(indDict)

    return lines, indDict


# guess each indent level's type. the order matters: each setType only
# looks at the levels not assigned yet, so e.g. dialogue is the most-used
# level once scene/action has been taken.
def _guessTypes(indDict):
    # scene/action indent
    _setType(SCENE_ACTION, indDict, lambda v: v.sceneStart)

    # indent with most lines is dialogue in non-pure-action scripts
    _setType(screenplay.DIALOGUE, indDict, lambda v: len(v.lines))

    # remaining indent with lines is character most likely
    _setType(screenplay.CHARACTER, indDict, lambda v: len(v.lines))

    # transitions
    _setType(screenplay.TRANSITION, indDict, lambda v: v.trans)

    # parentheticals
    _setType(screenplay.PAREN, indDict, lambda v: v.paren)

    # some text files have this type of parens:
    #
    #        JOE
    #      (smiling and
    #       hopping along)
    #
    # this handles them.
    parenIndent = _findIndent(indDict, lambda v: v.lt == screenplay.PAREN)
    if parenIndent != -1:
        paren2Indent = _findIndent(
            indDict, lambda v, var: (v.lt == -1) and (v.indent == var), parenIndent + 1
        )

        if paren2Indent != -1:
            indDict[paren2Indent].lt = screenplay.PAREN

    # set line type to ACTION for any indents not recognized
    for v in indDict.values():
        if v.lt == -1:
            v.lt = screenplay.ACTION


# return lines (as from _analyze) as Lines, with the line types in indDict
def _convert(lines, indDict):
    ret = []

    # consecutive lines of the same type are taken to be one paragraph
    # wrapped in the source, so they're joined with LB_SPACE (rewrapped
    # later by reformatAll). a blank line or a change of type ends the
    # element.
    for i in range(len(lines)):
        s = lines[i]
        cnt = textutil.countInitial(s, " ")
        s = s.lstrip()
        sUp = s.upper()

        if s:
            lt = indDict[cnt].lt

            if lt == IGNORE:
                continue

            if lt == SCENE_ACTION:
                if s.startswith("EXT.") or s.startswith("INT."):
                    lt = screenplay.SCENE
                else:
                    lt = screenplay.ACTION

            if ret and (ret[-1].lt != lt):
                ret[-1].lb = screenplay.LB_LAST

            if lt == screenplay.CHARACTER:
                if sUp.endswith("(CONT'D)"):
                    s = sUp[:-8].rstrip()

            elif lt == screenplay.PAREN:
                if s == "(continuing)":
                    s = ""

            if s:
                line = Line(screenplay.LB_SPACE, lt, s)
                ret.append(line)

        elif ret:
            ret[-1].lb = screenplay.LB_LAST

    if len(ret) == 0:
        ret.append(Line(screenplay.LB_LAST, screenplay.ACTION))

    # make sure the last line ends an element
    ret[-1].lb = screenplay.LB_LAST

    return ret


# go through indents, find the one with maximum value in something, and
# set its linetype to given lt.
def _setType(lt, indDict, func):
    maxCount = 0
    found = -1

    for v in indDict.values():
        # don't touch indents already set
        if v.lt != -1:
            continue

        val = func(v)

        if val > maxCount:
            maxCount = val
            found = v.indent

    if found != -1:
        indDict[found].lt = lt


# go through indents calling func(it, *vars) on each. return indent count
# for the indent func returns True, or -1 if it returns False for each.
def _findIndent(indDict, func, *vars):
    for v in indDict.values():
        if func(v, *vars):
            return v.indent

    return -1
