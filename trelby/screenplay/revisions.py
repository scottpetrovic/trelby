# revisions: marking what has changed in a script once it's in
# production. each round of changes is a revision, named after the color
# of the paper its pages are printed on (White, the original, then Blue,
# Pink, Yellow, ...; see COLORS). while revision mode is on, every edit
# marks the text it changes with the current revision's level, and those
# lines get a revision mark ("*") in the right margin when printed. a
# page's revision is the highest level on it, shown in its header, and
# the pages of the current revision can be printed on their own.
#
# the marks are kept per character, in Line.revs: like Line.fmt, a string
# with one character per character of text, chr(48 + level), "0" being
# unrevised, or None if the line has no marks. edits don't keep it up to
# date themselves: the undo objects call carry() when an edit is done,
# which compares the lines before and after it, gives unchanged text its
# old marks and changed text the current level (see undo.Base). the
# wrapping functions carry the marks along too, for the rewrapping that
# isn't an undoable edit (loading, changed settings).
#
# Revisions (sp.revisions) holds the settings: the current revision, the
# dates the revisions were issued, revision mode and how marks are shown.

import difflib
import re
import time

import trelby.config as config
import trelby.mypickle as mypickle
import trelby.textfmt as textfmt
import trelby.undo as undo
import trelby.util as util
from trelby.screenplay.constants import (
    LB_FORCED,
    LB_LAST,
)

# the standard revision colors, in the order they're used, as (name
# function, color as "rrggbb"). the color is what the marked text is
# highlighted with on screen, so it's a little darker than the paper.
COLORS = [
    (lambda: _("White"), "c8c8c8"),
    (lambda: _("Blue"), "8fb8e6"),
    (lambda: _("Pink"), "f2a7b8"),
    (lambda: _("Yellow"), "f2e35c"),
    (lambda: _("Green"), "9ed69e"),
    (lambda: _("Goldenrod"), "e6b94a"),
    (lambda: _("Buff"), "e8d488"),
    (lambda: _("Salmon"), "f7a08c"),
    (lambda: _("Cherry"), "e0607e"),
]

# after Cherry come Double White, Double Blue, ..., then Triple White...
MAX_LEVEL = 3 * len(COLORS) - 1

DEFAULT_MARK = "*"


# return the name of revision 'level' (0 being the original, White)
def levelName(level):
    name = COLORS[level % len(COLORS)][0]()
    times = level // len(COLORS)

    if times == 1:
        return _("Double {}").format(name)
    elif times >= 2:
        return _("Triple {}").format(name)

    return name


# return the color of revision 'level', as "rrggbb"
def levelColor(level):
    return COLORS[level % len(COLORS)][1]


# return the character Line.revs uses for 'level'
def levelChar(level):
    return chr(48 + level)


# return the highest revision level of line ln's text, 0 if it has no
# marks
def lineLevel(ln):
    if not ln.revs:
        return 0

    return ord(max(ln.revs)) - 48


# whether line ln has text marked with revision 'level'
def lineHasLevel(ln, level):
    return bool(ln.revs) and (levelChar(level) in ln.revs)


# return the revision marks for the text of the lines whose (text, revs)
# pairs are given, joined with the separators given in seps (one fewer
# than the lines, each "" or " "), or None if there are none. a separator
# gets the lower of the levels next to it.
def join(parts, seps):
    if not any(revs for text, revs in parts):
        return None

    ret = []

    for i, (text, revs) in enumerate(parts):
        revs = textfmt.fit(revs, len(text))

        if (i != 0) and seps[i - 1]:
            prev = ret[-1][-1:] if ret and ret[-1] else "0"
            ret.append(min(prev, revs[:1] or "0") * len(seps[i - 1]))

        ret.append(revs)

    return textfmt.compact("".join(ret))


# return revs (a Line.revs string) in the form saved to files: comma-
# separated "start-end:level" items for its marked runs, end being
# exclusive. returns "" if there are no marks.
def encode(revs):
    if not revs:
        return ""

    items = []

    for start, end, level in textfmt.runs(revs, len(revs)):
        if level:
            items.append("%d-%d:%d" % (start, end, level))

    return ",".join(items)


_itemRe = re.compile(r"^(\d+)-(\d+):(\d+)$")


# opposite of encode(), for a text n characters long. invalid items and
# the parts of items past the end of the text are ignored. returns None if
# there are no (valid) marks.
def decode(s, n):
    revs = ["0"] * n

    for item in s.split(","):
        m = _itemRe.match(item.strip())

        if not m:
            continue

        level = int(m.group(3))

        if not (0 <= level <= MAX_LEVEL):
            continue

        for i in range(int(m.group(1)), min(int(m.group(2)), n)):
            revs[i] = levelChar(level)

    return textfmt.compact("".join(revs))


# return the x position (mm) of the revision marks on a page: just past
# the right margin, where they're printed. chX is a character's width.
def markX(cfg, chX):
    return min(
        cfg.paperWidth - cfg.marginRight + 3 * chX, cfg.paperWidth - 2 * chX
    )


# a script's revision settings
# today's date as a revision's date is usually written, in the system's
# short date format
def today():
    return time.strftime("%x")


class Revisions:
    def __init__(self):
        # the current revision's level: 1 for Blue, 2 for Pink, ... (see
        # levelName). 0 until a revision has been started.
        self.level = 0

        # revision mode: whether edits are marked with the current level
        self.active = False

        # the dates the revisions were issued, as free text, by level
        self.dates = {}

        # the character printed in the right margin of revised lines
        self.markChar = DEFAULT_MARK

        # whether each revised page shows its revision above its header
        self.showInHeader = True

        # whether only the current revision's changes get marks; older
        # marks still count for the pages' revisions
        self.currentOnly = False

        # whether turning revision mode on locks the pages and the scene
        # numbers, if they aren't locked yet (see Editor.lockForRevisions),
        # as production scripts are locked before their first revision
        self.autoLock = True

    def __eq__(self, other):
        return isinstance(other, Revisions) and (vars(self) == vars(other))

    # whether there's anything worth saving
    def hasInfo(self):
        return self != Revisions()

    # turn revision mode on or off. turning it on before a revision has
    # been started starts the first one (Blue), dated today, so that it
    # starts marking right away; Revision settings picks another.
    def toggleActive(self):
        self.active = not self.active

        if self.active and not self.level:
            self.level = 1
            self.dates.setdefault(1, today())

    # the level edits are marked with now, or 0 if they aren't
    def markingLevel(self):
        return self.level if self.active else 0

    # what a page of revision 'level' says above its header, e.g. "Blue
    # Rev. 10/17/26", or "" for an unrevised page
    def label(self, level):
        if not level:
            return ""

        date = self.dates.get(level, "")

        return (_("{} Rev.").format(levelName(level)) + " " + date).strip()

    # whether line ln gets a revision mark
    def isMarked(self, ln):
        if self.currentOnly:
            return bool(self.level) and lineHasLevel(ln, self.level)

        return bool(ln.revs)

    def save(self):
        s = "Level:%d\n" % self.level
        s += "Active:%d\n" % int(self.active)
        s += "Mark:%s\n" % self.markChar
        s += "ShowInHeader:%d\n" % int(self.showInHeader)
        s += "CurrentOnly:%d\n" % int(self.currentOnly)
        s += "AutoLock:%d\n" % int(self.autoLock)

        for level in sorted(self.dates):
            s += "Date/%d:%s\n" % (level, self.dates[level])

        return s

    # load from string s. doesn't throw any exceptions, and silently
    # ignores any errors.
    def load(self, s):
        vals = mypickle.Vars.makeVals(s)

        self.level = util.str2int(vals.get("Level", "0"), 0, 0, MAX_LEVEL)
        self.active = bool(self.level) and (vals.get("Active") == "1")
        self.showInHeader = vals.get("ShowInHeader", "1") != "0"
        self.currentOnly = vals.get("CurrentOnly") == "1"
        self.autoLock = vals.get("AutoLock", "1") != "0"

        mark = vals.get("Mark", "").strip()
        self.markChar = mark[:1] or DEFAULT_MARK

        self.dates = {}

        for key, val in vals.items():
            if key.startswith("Date/") and val.strip():
                level = util.str2int(key[5:], 0, 0, MAX_LEVEL)

                if level:
                    self.dates[level] = val.strip()


# a paragraph of a run of lines, for carry(): its type, its text (the
# lines' texts joined like rewrapPara does), the marks of that text, and
# the index of its first line and the offset of each of its lines' text
class _Para:
    def __init__(self, lines, start):
        self.lt = lines[start].lt
        self.start = start
        self.offsets = []

        texts = []
        revs = []
        pos = 0
        i = start

        while True:
            ln = lines[i]
            self.offsets.append(pos)
            texts.append(ln.text)
            revs.append(textfmt.fit(ln.revs, len(ln.text)))
            pos += len(ln.text)
            i += 1

            if (ln.lb in (LB_LAST, LB_FORCED)) or (i >= len(lines)):
                break

            sep = config.lb2str(ln.lb)
            texts.append(sep)
            revs.append("0" * len(sep))
            pos += len(sep)

        self.end = i
        self.text = "".join(texts)
        self.revs = "".join(revs)

    def key(self):
        return (self.lt, self.text)


def _paras(lines):
    ret = []
    i = 0

    while i < len(lines):
        p = _Para(lines, i)
        ret.append(p)
        i = p.end

    return ret


_tokenRe = re.compile(r"\w+|\s+|[^\w\s]")

# blocks with more words than this are compared as a whole, not word by
# word, as the comparison could take too long
MAX_TOKENS = 20000


# return the (start, end) of each word, run of spaces and punctuation
# character in s
def _tokens(s):
    return [m.span() for m in _tokenRe.finditer(s)]


# the lines 'before' have been replaced by the lines 'after' (Line
# objects, changed in place): set the marks of after's text from before's,
# for the text that's still there, and mark the text that's new or changed
# with revision 'level', if it isn't 0. otherwise changed text keeps the
# marks its line already has, e.g. when a scene is moved. a deletion
# marks the character before it (or after, where there's none before), so
# that the line still gets a revision mark. changing a paragraph's type
# marks all of it. the comparison is by paragraph, and then word by word.
def carry(before, after, level):
    mark = levelChar(level) if level else None

    bp = _paras(before)
    ap = _paras(after)

    # the new marks of each of after's paragraphs, as lists of characters,
    # starting from what the lines have now
    res = [list(p.revs) for p in ap]

    # (paragraph, offset) of characters to mark at the end, next to
    # deleted paragraphs
    extra = []

    if (len(bp) == 1) and (len(ap) == 1):
        if bp[0].key() == ap[0].key():
            ops = [("equal", 0, 1, 0, 1)]
        else:
            ops = [("replace", 0, 1, 0, 1)]
    else:
        ops = difflib.SequenceMatcher(
            None, [p.key() for p in bp], [p.key() for p in ap], autojunk=False
        ).get_opcodes()

    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for k in range(i2 - i1):
                res[j1 + k] = list(bp[i1 + k].revs)

        elif tag == "delete":
            if mark:
                _markNeighbor(res, j1, extra)

        else:
            _carryBlock(bp[i1:i2], ap[j1:j2], res, j1, mark, extra)

    for p, c in extra:
        res[p][c] = max(res[p][c], mark)

    for p, revs in zip(ap, res):
        for k, off in enumerate(p.offsets):
            ln = after[p.start + k]
            ln.revs = textfmt.compact("".join(revs[off : off + len(ln.text)]))


# a paragraph was deleted before after's paragraph j: mark the last
# character of the paragraph before it, or if there's none with text, the
# first character of one after it
def _markNeighbor(res, j, extra):
    for p in range(j - 1, -1, -1):
        if res[p]:
            extra.append((p, len(res[p]) - 1))

            return

    for p in range(j, len(res)):
        if res[p]:
            extra.append((p, 0))

            return


# carry() for paragraphs bps replaced by aps, aps starting at after's
# paragraph j0
def _carryBlock(bps, aps, res, j0, mark, extra):
    bText = "\n".join(p.text for p in bps)
    bRevs = "0".join(p.revs for p in bps)
    aText = "\n".join(p.text for p in aps)
    aRevs = list("0".join("".join(res[j0 + k]) for k in range(len(aps))))

    tb = _tokens(bText)
    ta = _tokens(aText)

    if (len(tb) + len(ta)) > MAX_TOKENS:
        ops = [("replace", 0, len(tb), 0, len(ta))]
    else:
        ops = difflib.SequenceMatcher(
            None,
            [bText[a:b] for a, b in tb],
            [aText[a:b] for a, b in ta],
            autojunk=False,
        ).get_opcodes()

    # whether a deletion couldn't be marked within the block
    unmarked = False

    for tag, i1, i2, j1, j2 in ops:
        a0 = ta[j1][0] if j1 < len(ta) else len(aText)
        a1 = ta[j2 - 1][1] if j2 > j1 else a0

        if tag == "equal":
            b0 = tb[i1][0]
            aRevs[a0:a1] = bRevs[b0 : tb[i2 - 1][1]]

        elif not mark:
            pass

        elif tag == "delete":
            if (a0 > 0) and (aText[a0 - 1] != "\n"):
                aRevs[a0 - 1] = mark
            elif (a0 < len(aText)) and (aText[a0] != "\n"):
                aRevs[a0] = mark
            else:
                unmarked = True

        else:
            for c in range(a0, a1):
                if aText[c] != "\n":
                    aRevs[c] = mark

    if mark and (len(bps) == len(aps)):
        off = 0

        for bp, ap in zip(bps, aps):
            if bp.lt != ap.lt:
                aRevs[off : off + len(ap.text)] = mark * len(ap.text)

            off += len(ap.text) + 1

    off = 0

    for k, ap in enumerate(aps):
        res[j0 + k] = aRevs[off : off + len(ap.text)]
        off += len(ap.text) + 1

    if unmarked and not any(c > "0" for c in aRevs):
        _markNeighbor(res, j0 + len(aps), extra)


class RevisionsMixin:
    # whether any line has revision marks
    def hasRevisionMarks(self):
        return any(ln.revs for ln in self.lines)

    # return the revision of page pageNr: the highest level on it, or 0
    def getPageRevision(self, pageNr):
        first, last = self.page2lines(pageNr)

        return max(lineLevel(self.lines[i]) for i in range(first, last + 1))

    # whether page pageNr has text marked with the current revision
    def isPageRevised(self, pageNr):
        level = self.revisions.level

        if not level:
            return False

        first, last = self.page2lines(pageNr)

        return any(lineHasLevel(self.lines[i], level) for i in range(first, last + 1))

    # return the numbers of the pages isPageRevised is True for
    def getRevisedPages(self):
        return [p for p in range(1, len(self.pages)) if self.isPageRevised(p)]


# the Editor's side
class RevisionsEditMixin:
    # remove all revision marks, as one undo step. the pages are all
    # White again afterwards.
    def clearRevisionMarks(self):
        if not self.sp.hasRevisionMarks():
            return

        u = undo.FullCopy(self)

        for ln in self.sp.lines:
            ln.revs = None

        self.sp.markChanged()

        # FullCopy.setAfter carries the marks over from before the edit,
        # which here is exactly what mustn't happen
        u.setAfter(self, carry=False)
        self.undoHistory.add(u)
