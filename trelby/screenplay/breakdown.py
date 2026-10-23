# the script breakdown: tagging what each scene needs for production
# (cast, props, vehicles, wardrobe...) so that it can be listed per scene
# and per element, for scheduling and budgeting.
#
# a tag is attached to a paragraph, like a note (see notes.py), and kept
# in Line.tags on its first line, so it stays with that text as the script
# is edited, and goes away when all of the paragraph's text is deleted.
# rewrapPara, joining, splitting, cut and paste, undo and the file carry
# them like notes. a tag names a breakdown element, a category and a name
# ("props", "Revolver"), and has the text it was made from ("his gun"),
# which is highlighted wherever it's found in the paragraph. a tag with no
# text is an element the scene needs that its text doesn't mention; those
# go on the scene heading.
#
# an element is the same one wherever it's tagged if its category and
# name match, ignoring case and extra spaces (elementKey). the speaking
# characters can be counted as cast without being tagged (the reports'
# and the panel's castSpeakers), so a breakdown starts with the cast
# filled in.

import re
from dataclasses import dataclass, replace

import trelby.config as config
import trelby.textutil as textutil
import trelby.undo as undo
import trelby.screenplay.speeches as speeches
from trelby.screenplay.constants import ACTBREAK, LB_FORCED, LB_LAST, SCENE


# a breakdown category: its key (saved in files), label (a function, since
# the categories are made before the translations are loaded) and color
# ("rrggbb"), which is the industry's usual one where there is one (cast
# red, extras green, stunts orange, props violet...)
@dataclass(frozen=True)
class Category:
    key: str
    label: object
    color: str


CAST = "cast"

CATEGORIES = [
    Category(CAST, lambda: _("Cast"), "e53935"),
    Category("extras", lambda: _("Extras"), "43a047"),
    Category("stunts", lambda: _("Stunts"), "fb8c00"),
    Category("vehicles", lambda: _("Vehicles"), "ec407a"),
    Category("props", lambda: _("Props"), "8e24aa"),
    Category("sfx", lambda: _("Special effects"), "1e88e5"),
    Category("vfx", lambda: _("Visual effects"), "00acc1"),
    Category("wardrobe", lambda: _("Wardrobe"), "00897b"),
    Category("makeup", lambda: _("Makeup / hair"), "c0a000"),
    Category("animals", lambda: _("Animals"), "8d6e63"),
    Category("music", lambda: _("Music"), "3949ab"),
    Category("sound", lambda: _("Sound"), "6d4c41"),
    Category("setdressing", lambda: _("Set dressing"), "7cb342"),
    Category("equipment", lambda: _("Special equipment"), "546e7a"),
    Category("misc", lambda: _("Miscellaneous"), "9e9e9e"),
]

_BY_KEY = {c.key: c for c in CATEGORIES}

# the category of tags whose category isn't known (a newer version's)
UNKNOWN = "misc"


# the Category with the given key, or Miscellaneous's
def category(key):
    return _BY_KEY.get(key) or _BY_KEY[UNKNOWN]


def isCategory(key):
    return key in _BY_KEY


# an element's name with its spaces tidied up
def cleanName(name):
    return " ".join(name.split())


# what tells elements apart: names differing only in case or spaces are
# the same element
def elementKey(category, name):
    return (category, textutil.lower(cleanName(name)))


# one tag. it's an immutable value, so lines and undo objects can share
# them.
@dataclass(frozen=True)
class Tag:
    # the category's key
    category: str

    # the element's name
    name: str

    # the paragraph's text the tag was made from, highlighted wherever
    # it's found in the paragraph, or "" for none
    text: str = ""

    @property
    def key(self):
        return elementKey(self.category, self.name)

    def replace(self, **changes):
        return replace(self, **changes)


# the spans of 'text' (a paragraph's text) that the tags' texts are found
# at, as (start, end, Tag) tuples, end exclusive, in order. each tag's
# text is found wherever it is a whole word or words, ignoring case.
def findSpans(text, tags):
    ret = []

    for tag in tags:
        s = tag.text.strip()

        if not s:
            continue

        pattern = r"(?<!\w)%s(?!\w)" % re.escape(s)

        for mo in re.finditer(pattern, text, re.IGNORECASE):
            ret.append((mo.start(), mo.end(), tag))

    ret.sort(key=lambda span: (span[0], span[1]))

    return ret


# the parts of a scene heading: (INT. / EXT., the place, the time of day),
# e.g. ("INT.", "MOTEL ROOM", "NIGHT"). a part that isn't there is "".
_HEADING_RE = re.compile(
    r"^((?:INT\.?\s*/\s*EXT|EXT\.?\s*/\s*INT|I\s*/\s*E|INT|EXT|EST)(?![^\W\d_])\.?)"
    r"\s*(.*)$",
    re.IGNORECASE,
)


def splitHeading(heading):
    heading = " ".join(heading.split())
    intExt = ""

    mo = _HEADING_RE.match(heading)

    if mo:
        intExt = textutil.upper("".join(mo.group(1).split()))

        if not intExt.endswith("."):
            intExt += "."

        heading = mo.group(2)

    place, sep, time = heading.rpartition(" - ")

    if not sep:
        place, time = heading, ""

    return (intExt, place.strip(), textutil.upper(time.strip()))


# a length in eighths of a page as the industry writes it: "1 3/8", "5/8",
# "2"
def eighthsText(eighths):
    whole, rest = divmod(eighths, 8)

    if not rest:
        return str(whole)

    if not whole:
        return "%d/8" % rest

    return "%d %d/8" % (whole, rest)


# one scene's breakdown
@dataclass
class SceneBreakdown:
    # the scene's first and last line
    start: int
    end: int

    # its number ("" if it hasn't got one) and heading, and the heading's
    # parts (see splitHeading)
    number: str
    heading: str
    intExt: str
    place: str
    time: str

    # its length in eighths of a page, at least 1, and the label of the
    # page it starts on
    eighths: int
    page: str

    # the elements: category key -> names, in the order they're tagged
    # (cast first by who speaks first)
    elements: dict

    def names(self, category):
        return self.elements.get(category, [])


# an element and the scenes it's in
@dataclass
class ElementInfo:
    category: str
    name: str

    # the first lines of the scenes it's in, in order
    scenes: list

    # whether it's tagged anywhere, as opposed to only a speaking
    # character counted as cast
    tagged: bool


# the Screenplay's side: finding tags and working out the breakdown
class BreakdownMixin:
    # return the tags of the paragraph containing line i
    def getParaTags(self, i):
        first = self.getParaFirstIndexFromLine(i)
        last = self.getParaLastIndexFromLine(i)

        ret = ()

        for k in range(first, last + 1):
            ret += self.lines[k].tags

        return ret

    # a list of (line, index, Tag) of every tag in the script, in order,
    # line being the one it's on and index its index in that line's tags
    def getAllTags(self):
        return [
            (i, k, tag)
            for i, ln in enumerate(self.lines)
            for k, tag in enumerate(ln.tags)
        ]

    def hasTags(self):
        return any(ln.tags for ln in self.lines)

    # the highlighted spans of line i's text, as (start column, end
    # column, Tag) tuples, end exclusive
    def getLineTagSpans(self, i):
        tags = self.getParaTags(i)

        if not tags:
            return []

        ls = self.lines
        first = self.getParaFirstIndexFromLine(i)
        last = self.getParaLastIndexFromLine(i)

        text = ""
        lineStart = 0

        for k in range(first, last + 1):
            if k == i:
                lineStart = len(text)

            text += ls[k].text

            if k != last:
                text += config.lb2str(ls[k].lb)

        lineEnd = lineStart + len(ls[i].text)
        ret = []

        for a, b, tag in findSpans(text, tags):
            a = max(a, lineStart)
            b = min(b, lineEnd)

            if a < b:
                ret.append((a - lineStart, b - lineStart, tag))

        return ret

    # the tags at column col of line i, whose text is highlighted there,
    # as (line, index, Tag): line is the paragraph's first line and index
    # the tag's index among the paragraph's tags
    def getTagsAt(self, i, col):
        first = self.getParaFirstIndexFromLine(i)
        tags = self.getParaTags(i)
        ret = []

        for a, b, tag in self.getLineTagSpans(i):
            if a <= col < b:
                index = tags.index(tag)

                if (first, index, tag) not in ret:
                    ret.append((first, index, tag))

        return ret

    # the parts of the script the breakdown is split into, as (first line,
    # last line): each scene, and the part before the first scene heading
    # or after an act break (but not the act break itself) if something
    # is tagged in it, a bare FADE IN: not being worth a breakdown
    def getBreakdownScenes(self):
        ret = []
        line = 0

        while line < len(self.lines):
            start, end = self.getSceneIndexesFromLine(line)
            line = end + 1

            if self.lines[start].lt == ACTBREAK:
                start = self.getElemLastIndexFromLine(start) + 1

                if start > end:
                    continue

            if (self.lines[start].lt != SCENE) and not any(
                self.lines[k].tags for k in range(start, end + 1)
            ):
                continue

            ret.append((start, end))

        return ret

    # the elements in lines start - end, as a dict of category key ->
    # names in the order they're tagged. speakers is a list of the
    # characters speaking in those lines, put first in the cast, or None.
    def getElements(self, start, end, speakers=None):
        ret = {}
        seen = set()

        def add(category, name):
            key = elementKey(category, name)

            if key not in seen:
                seen.add(key)
                ret.setdefault(category, []).append(cleanName(name))

        for name in speakers or []:
            add(CAST, name)

        for i in range(start, end + 1):
            for tag in self.lines[i].tags:
                add(tag.category if isCategory(tag.category) else UNKNOWN, tag.name)

        return ret

    # the speaking characters of each part of the script, as a dict of
    # the part's first line -> names in the order they first speak. the
    # parts are those of getBreakdownScenes.
    def getSceneSpeakers(self):
        scenes = self.getBreakdownScenes()
        ret = {start: [] for start, end in scenes}
        starts = sorted(ret)

        for speech in speeches.iterSpeeches(self):
            k = _sceneOf(starts, speech.charLine)

            if (k is not None) and (speech.name not in ret[k]):
                ret[k].append(speech.name)

        return ret

    # a SceneBreakdown for each part of the script (see
    # getBreakdownScenes). if castSpeakers, the speaking characters are
    # counted as cast. uses the last pagination for the page lengths.
    def getBreakdown(self, castSpeakers=True):
        speakers = self.getSceneSpeakers() if castSpeakers else {}
        ret = []

        for start, end in self.getBreakdownScenes():
            isScene = self.lines[start].lt == SCENE
            heading = speeches.sceneName(self, start) if isScene else ""
            intExt, place, time = splitHeading(heading)

            ret.append(
                SceneBreakdown(
                    start,
                    end,
                    self.getSceneNumber(start) if isScene else "",
                    heading,
                    intExt,
                    place,
                    time,
                    self.getEighths(start, end),
                    self.line2pageLabel(start),
                    self.getElements(start, end, speakers.get(start)),
                )
            )

        return ret

    # every element and the scenes it's in, as ElementInfos, sorted by
    # category (in CATEGORIES' order) and then name. castSpeakers is as
    # for getBreakdown.
    def getElementList(self, castSpeakers=True):
        found = {}
        order = [c.key for c in CATEGORIES]
        speakers = self.getSceneSpeakers() if castSpeakers else {}

        for start, end in self.getBreakdownScenes():
            for name in speakers.get(start, []):
                _addElement(found, CAST, name, start, False)

            for i in range(start, end + 1):
                for tag in self.lines[i].tags:
                    cat = tag.category if isCategory(tag.category) else UNKNOWN
                    _addElement(found, cat, tag.name, start, True)

        return sorted(
            found.values(),
            key=lambda e: (order.index(e.category), textutil.lower(e.name)),
        )

    # the length of lines start - end in eighths of a page, rounded to
    # the nearest eighth and at least one: the lines they take up (with
    # the spacing between elements, as paginate counts them) out of a
    # page's
    def getEighths(self, start, end):
        ls = self.lines
        ct = self.cfg.types
        units = 0

        for i in range(start, end + 1):
            units += 10

            if i > start:
                if ls[i - 1].lb == LB_LAST:
                    units += ct[ls[i].lt].beforeSpacing
                else:
                    units += ct[ls[i].lt].intraSpacing

        perPage = max(1, self.cfg.linesOnPage * 10)

        return max(1, round(units * 8 / perPage))

    # lines del1 - del2 are about to be deleted. the tags on them whose
    # paragraph goes on after del2 (its text isn't all deleted) are moved
    # to line del2 + 1, which stays in that paragraph. (see
    # NotesMixin.moveNotesForward)
    def moveTagsForward(self, del1, del2):
        ls = self.lines

        if del2 + 1 >= len(ls):
            return

        moved = ()

        for i in range(del1, del2 + 1):
            if ls[i].tags and not any(
                ls[k].lb in (LB_LAST, LB_FORCED) for k in range(i, del2 + 1)
            ):
                moved += ls[i].tags

        if moved:
            ls[del2 + 1].tags = moved + ls[del2 + 1].tags


# the start of the part (of the sorted starts) that line is in, or None if
# it's before them all
def _sceneOf(starts, line):
    ret = None

    for s in starts:
        if s > line:
            break

        ret = s

    return ret


def _addElement(found, category, name, scene, tagged):
    key = elementKey(category, name)
    e = found.get(key)

    if not e:
        e = found[key] = ElementInfo(category, cleanName(name), [], False)

    if scene not in e.scenes:
        e.scenes.append(scene)

    e.tagged = e.tagged or tagged


# the Editor's side: tagging, each edit one undo step. the cursor stays
# where it is.
class BreakdownEditMixin:
    # set the tags of the paragraph containing line
    def _setParaTags(self, line, tags):
        u = undo.SinglePara(self, undo.CMD_MISC, line)

        ls = self.sp.lines
        first = self.sp.getParaFirstIndexFromLine(line)

        for k in range(first, self.sp.getParaLastIndexFromLine(line) + 1):
            ls[k].tags = ()

        ls[first].tags = tuple(tags)
        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

    # tag the paragraph containing line as having the element (category,
    # name), made from its text 'text' ("" for none). returns False if
    # the paragraph already has that tag, or name is empty.
    def addTag(self, line, category, name, text=""):
        name = cleanName(name)
        text = text.strip()

        if not name:
            return False

        tags = self.sp.getParaTags(line)
        new = Tag(category, name, text)

        if any(
            (t.key == new.key) and (textutil.lower(t.text) == textutil.lower(text))
            for t in tags
        ):
            return False

        self._setParaTags(line, tags + (new,))

        return True

    # remove the tag at 'index' of the paragraph containing line
    def removeTag(self, line, index):
        tags = list(self.sp.getParaTags(line))
        del tags[index]
        self._setParaTags(line, tags)

    # add the element (category, name) to the scene containing line,
    # without any text, on its heading (the first line of the part, see
    # getBreakdownScenes). returns False if it's already there.
    def addSceneElement(self, line, category, name):
        start = self.sceneStart(line)

        if any(
            t.key == elementKey(category, name)
            for i in range(start, self.sp.getSceneIndexesFromLine(line)[1] + 1)
            for t in self.sp.lines[i].tags
        ):
            return False

        return self.addTag(start, category, name)

    # the first line of the part of the script line is in, as
    # getBreakdownScenes has it
    def sceneStart(self, line):
        sp = self.sp
        start, end = sp.getSceneIndexesFromLine(line)

        if sp.lines[start].lt == ACTBREAK:
            start = min(sp.getElemLastIndexFromLine(start) + 1, end)

        return start

    # change the tags in lines start - end (all of them by default) that
    # f(tag) returns something else for: a new Tag, or None to remove it.
    # one undo step. returns whether anything was changed.
    def changeTags(self, f, start=0, end=None):
        ls = self.sp.lines

        if end is None:
            end = len(ls) - 1

        changes = {}

        for i in range(start, end + 1):
            if not ls[i].tags:
                continue

            new = []

            for t in ls[i].tags:
                nt = f(t)

                if nt is not None:
                    new.append(nt)

            new = tuple(new)

            if new != ls[i].tags:
                changes[i] = new

        if not changes:
            return False

        u = undo.AnyDifference(self)

        for i, tags in changes.items():
            ls[i].tags = tags

        self.sp.markChanged()

        u.setAfter(self)
        self.undoHistory.add(u)

        return True

    # rename the element (category, name) to (newCategory, newName)
    # everywhere it's tagged
    def renameElement(self, category, name, newCategory, newName):
        newName = cleanName(newName)

        if not newName:
            return False

        key = elementKey(category, name)

        return self.changeTags(
            lambda t: (
                t.replace(category=newCategory, name=newName) if t.key == key else t
            )
        )

    # remove the element (category, name) from the scene containing line,
    # or from the whole script if line is None
    def removeElement(self, category, name, line=None):
        key = elementKey(category, name)

        if line is None:
            start, end = 0, None
        else:
            start, end = self.sp.getSceneIndexesFromLine(line)

        return self.changeTags(
            lambda t: None if t.key == key else t, start, end
        )

    # the selected text, if it's all in one paragraph, for tagging: (the
    # paragraph's first line, the text with its line breaks as typed),
    # or None if nothing is selected, the selection runs into another
    # paragraph, or it's only spaces
    def getSelectedTagText(self):
        marked = self.getMarkedLines()

        if not marked:
            return None

        sp = self.sp
        first = sp.getParaFirstIndexFromLine(marked[0])

        if sp.getParaFirstIndexFromLine(marked[1]) != first:
            return None

        ls = sp.lines
        text = ""

        for i in range(marked[0], marked[1] + 1):
            c1, c2 = self.getMarkedColumns(i, marked)
            text += ls[i].text[c1 : c2 + 1]

            if (i != marked[1]) and (c2 + 1 >= len(ls[i].text)):
                text += config.lb2str(ls[i].lb)

        text = " ".join(text.split())

        return (first, text) if text else None
