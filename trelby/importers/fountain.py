# Fountain files. http://fountain.io

import copy
import re

import trelby.config as config
import trelby.screenplay as screenplay
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.titles as titles
from trelby.importers.common import ImportResult, checkNotEmpty
from trelby.line import Line

# whether parse takes bytes rather than str
BINARY = False

BONEYARD_RE = re.compile("/\\*.*?\\*/", flags=re.DOTALL)

TAB_WIDTH = 4

# in Fountain, a line of just two spaces is a blank line that doesn't end
# the element. two trailing spaces are also used here as a marker on title
# page lines that go into the script, which keeps the first pass from
# taking them for scene headings or character names.
TWOSPACE = "  "

# a title page line "Key: value", or "Key:" followed by indented lines
KEYWORD_RE = re.compile(r"^([A-Za-z][^:]+:)")

# a title page value's continuation line: begins with 3 or more spaces
CONTINUE_RE = re.compile(r"^\s\s\s+")

# the title page keys that replace a string of the script's title page,
# and the kind of string they replace (one is added if there isn't one)
TITLE_KINDS = {
    "Title:": titles.TITLE,
    "Author:": titles.BYLINE,
    "Authors:": titles.BYLINE,
    "Contact:": titles.CONTACT,
}


class Options:
    def __init__(
        self,
        titlePage=True,
        titlesAsAction=False,
        markup=True,
        sectionsAsNotes=True,
        titlePages=None,
        paperSize=config.PAPER_SIZES["A4"],
    ):
        # whether the title page lines go to the title page, and whether
        # they go into the script as action. with neither, they're
        # dropped.
        self.titlePage = titlePage
        self.titlesAsAction = titlesAsAction

        # whether bold, italic and underline markup becomes formatting
        self.markup = markup

        # whether sections and synopses become notes, or are dropped
        self.sectionsAsNotes = sectionsAsNotes

        # the script's title pages, which the imported titles are put on
        # (a copy of them is). None means the default title page.
        self.titlePages = titlePages

        # the paper size (width, height) in mm, for placing any title
        # strings that have to be added
        self.paperSize = paperSize


# parse data, a Fountain file's contents. the result's title pages are the
# options' (or the default) title pages, with the imported titles on them
# if options.titlePage.
def parse(data, options=None):
    options = options or Options()

    checkNotEmpty(data)

    # pre-process data - fix newlines, remove boneyard.
    data = textutil.fixNL(data)
    data = BONEYARD_RE.sub("", data)
    prelines = [textutil.cleanInput(l) for l in data.split("\n")]

    titlePages = _copyTitlePages(options.titlePages)
    prelines = _takeTitles(prelines, options, titlePages)

    lines = []

    for l in prelines:
        if l != TWOSPACE:
            lines.append(textutil.toInputStr(l.expandtabs(TAB_WIDTH)))
        else:
            lines.append(TWOSPACE)

    lns = _identifyLines(lines, options)
    ret = _joinElements(lns)

    return ImportResult(ret, titlePages or None)


# return a copy of pages (None: the default title page), with every
# string's kind set
def _copyTitlePages(pages):
    t = titles.Titles()

    if pages is None:
        t.addDefaults()
    else:
        t.pages = copy.deepcopy(pages)

    t.guessKinds()

    return t.pages


# handle the title page lines at the start of prelines, if there are any,
# as the options say: put them on titlePages (changed in place), and / or
# keep them in the script. return the script's lines.
def _takeTitles(prelines, options, titlePages):
    # First check if title lines are present:
    c = 0
    while c < len(prelines):
        if prelines[c] != "":
            c = c + 1
        else:
            break

    # prelines[0:c] are the first bunch of lines, that could be titles,
    # and prelines[c] is the blank line after them (prelines[c + 1:] is
    # the script proper). if the title lines run to the end of the file,
    # c == len(prelines).
    # Our check for title is simple:
    #   - the line does not start with 'fade'
    #   - the first line has a single ':'
    if c == 0:
        return prelines

    l = textutil.toInputStr(prelines[0].expandtabs(TAB_WIDTH).lstrip().lower())
    if l.startswith("fade") or (l.count(":") != 1):
        return prelines

    # these are title lines. Now do what the user requested.
    if options.titlePage:
        gatheredTitles, rejects = _gatherTitles(prelines[:c])
        _addTitles(titlePages, gatheredTitles, options.paperSize)

        # user might request that titles go into both title page & script
        if not options.titlesAsAction:
            return rejects + prelines[c + 1 :]

    if options.titlesAsAction:
        # add TWOSPACE to all the title lines.
        return [s + TWOSPACE for s in prelines[:c]] + prelines[c:]

    # remove these lines
    return prelines[c + 1 :]


# return the title page lines' (key, list of value lines), and the lines
# that aren't title lines, which go into the script (marked with
# TWOSPACE)
def _gatherTitles(lines):
    gatheredTitles = []
    rejects = []
    titleIdx = 0

    while titleIdx < len(lines):
        l = lines[titleIdx]
        match = [ll.strip() for ll in KEYWORD_RE.split(l)]

        if len(match) == 3:  # keyword line
            if match[2] == "":
                follows = []
                titleIdx += 1  # gather indented lines
                while titleIdx < len(lines) and CONTINUE_RE.match(lines[titleIdx]):
                    follows.append(lines[titleIdx].strip("_* \t"))
                    titleIdx += 1
                titleIdx -= 1
                gatheredTitles.append([match[1], follows])
            else:
                gatheredTitles.append([match[1], [match[2].strip("_* \t")]])
        else:
            rejects.append(l + TWOSPACE)

        titleIdx += 1

    return gatheredTitles, rejects


# put the gathered titles on the first of titlePages (changed in place,
# and given a page if it has none). Title, Author and Contact replace the
# text of the page's string of that kind (see TITLE_KINDS). other keys
# become new strings: Credit / Source centered, going down the page from
# y = 150 (mm from the top), the rest left-aligned, going up from y = 220.
# (the left-aligned ones are at x = 0, the page's edge.)
def _addTitles(titlePages, gatheredTitles, paperSize):
    if not titlePages:
        titlePages.append([])

    page = titlePages[0]

    leftY = 220.0
    centreY = 150.0

    for key, items in gatheredTitles:
        kind = TITLE_KINDS.get(key)

        if kind:
            if kind == titles.BYLINE:
                items = ["by", ""] + items

            ts = next((ts for ts in page if ts.kind == kind), None)

            if not ts:
                ts = titles.makeString(kind, *paperSize)
                page.append(ts)

            ts.items = items

            continue

        if key == "Credit:" or key == "Source:":
            centred = True
            thisY = centreY
            centreY += 5
        else:
            centred = False
            thisY = leftY
            leftY -= 5

        if len(items) == 1:
            newItems = [key + " " + items[0]]
        else:
            newItems = [key] + items

        page.append(titles.TitleString(newItems, y=thisY, isCentered=centred))


# first pass - identify linetypes. each source line (but skipped
# sections / synopses) becomes a Line of its own with LB_FORCED, blank
# lines included (as empty actions); the second pass groups them into
# elements. the checks rely on Fountain's blank-line rules, e.g. a
# character name has a blank line before it and none after it, and a
# transition has blank lines on both sides.
def _identifyLines(lines, options):
    lns = []
    skipone = False

    def isPrevEmpty():
        return bool(lns) and lns[-1].text == ""

    def isPrevType(ltype):
        return lns and lns[-1].lt == ltype

    # looks ahead to check if next line exists and is empty
    def isNextEmpty(i):
        return i + 1 < len(lines) and lines[i + 1] == ""

    def getPrevType():
        if lns:
            return lns[-1].lt
        else:
            return screenplay.ACTION

    for i in range(len(lines)):
        if skipone:
            skipone = False
            continue

        s = lines[i]
        sl = s.lstrip()
        # mark as ACTION by default.
        line = Line(screenplay.LB_FORCED, screenplay.ACTION, s)

        # Start testing lines for element type. Go in order:
        # Scene Character, Paren, Dialog, Transition, Note.

        if s == "" or _isPageBreak(s):
            # do nothing - import as action.
            pass

        elif _isCentered(s.strip()):
            # an action, but centered. for now every centered line has the
            # flag, so that the second pass can tell where they start and
            # end.
            line.centered = True
            line.text = s.strip()[1:-1].strip()

        elif s == TWOSPACE:
            line.lt = getPrevType()

        elif _isScene(s):
            line.lt = screenplay.SCENE
            if sl.startswith("."):
                line.text = sl[1:]
            else:
                line.text = sl

        elif _isTransition(sl) and isPrevEmpty() and isNextEmpty(i):
            line.lt = screenplay.TRANSITION
            if line.text.startswith(">"):
                line.text = sl[1:].lstrip()

        elif s.isupper() and isPrevEmpty() and not isNextEmpty(i):
            line.lt = screenplay.CHARACTER
            if s.endswith(TWOSPACE):
                line.lt = screenplay.ACTION

        elif _isParen(sl) and (
            isPrevType(screenplay.CHARACTER) or isPrevType(screenplay.DIALOGUE)
        ):
            line.lt = screenplay.PAREN

        elif (
            isPrevType(screenplay.CHARACTER)
            or isPrevType(screenplay.DIALOGUE)
            or isPrevType(screenplay.PAREN)
        ):
            line.lt = screenplay.DIALOGUE

        elif _isNote(sl):
            line.lt = screenplay.NOTE
            line.text = sl.strip("[]")

        elif _isSection(s) or _isSynopsis(s):
            if not options.sectionsAsNotes:
                if isNextEmpty(i):
                    skipone = True
                continue

            line.lt = screenplay.NOTE
            line.text = sl.lstrip("=#")

        if line.text == TWOSPACE:
            pass

        elif line.lt != screenplay.ACTION:
            line.text = line.text.lstrip()

        else:
            line.text = line.text.rstrip()

        if options.markup:
            line.text, line.fmt = textfmt.fromMarkup(line.text)

        # "^" after a character name makes it the right-hand column of a
        # dual dialogue
        if line.lt == screenplay.CHARACTER and line.text.rstrip().endswith("^"):
            line.setText(line.text.rstrip()[:-1].rstrip(), line.fmt)
            line.dual = True

        lns.append(line)

    return lns


# second pass - remove unneeded empty lines, and fix the linebreaks.
# consecutive lines of the same type (and centering) stay one element, and
# a change of type ends it. a blank line ends the open element and is
# dropped, or if none is open (e.g. right after another blank line), it's
# kept as an empty line, which the next blank line ends. so runs of blank
# lines still leave some space.
def _joinElements(lns):
    ret = []

    def isLastLBForced():
        return ret and ret[-1].lb == screenplay.LB_FORCED

    def makeLastLBLast():
        if ret:
            ret[-1].lb = screenplay.LB_LAST

    def isRetPrevType(t):
        return ret and ret[-1].lt == t

    for ln in lns:
        if ln.text == "":
            if isLastLBForced():
                makeLastLBLast()
            else:
                ret.append(ln)

        elif not isRetPrevType(ln.lt) or (ret[-1].centered != ln.centered):
            makeLastLBLast()
            ret.append(ln)

        else:
            ret.append(ln)

    makeLastLBLast()

    # the centered flag only goes on the first line of an element
    for i in range(1, len(ret)):
        if ret[i - 1].lb != screenplay.LB_LAST:
            ret[i].centered = False

    return ret


def _isParen(s):
    return s.startswith("(") and s.endswith(")")


def _isScene(s):
    if s.endswith(TWOSPACE):
        return False
    if s.startswith(".") and not s.startswith(".."):
        return True
    tmp = s.upper()
    if (
        re.match(r"^(INT|EXT|EST)[ .]", tmp)
        or re.match(r"^(INT\.?/EXT\.?)[ .]", tmp)
        or re.match(r"^I/E[ .]", tmp)
    ):
        return True
    return False


def _isTransition(s):
    return (s.isupper() and s.endswith("TO:")) or (
        s.startswith(">") and not s.endswith("<")
    )


def _isCentered(s):
    return s.startswith(">") and s.endswith("<")


def _isPageBreak(s):
    return s.startswith("===") and s.lstrip("=") == ""


def _isNote(s):
    return s.startswith("[[") and s.endswith("]]")


def _isSection(s):
    return s.startswith("#")


def _isSynopsis(s):
    return s.startswith("=") and not s.startswith("==")
