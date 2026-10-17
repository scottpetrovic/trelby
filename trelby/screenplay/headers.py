# a script's page headers and page footer, and the variables they can
# contain (${PAGE} etc., see VARIABLES).

import trelby.pdf.pml as pml
import trelby.screenplay.titles as titles
import trelby.textutil as textutil
import trelby.util as util

# the variables a header or footer string can contain, as (name,
# description function). the title page ones come from its strings of
# that kind, see titleVars.
VARIABLES = [
    ("PAGE", lambda: _("page number")),
    ("PAGES", lambda: _("number of pages")),
    ("TITLE", lambda: _("title")),
    ("AUTHOR", lambda: _("author")),
    ("DRAFT", lambda: _("draft")),
    ("DRAFTDATE", lambda: _("draft date")),
    ("REVISION", lambda: _("page's revision")),
]


# return the non-empty strings in 'items' joined into one line: with
# 'sep' between them if given, otherwise with ", ", or " " around a lone
# "&" or "and" (["Jane Doe", "&", "John Smith"] -> "Jane Doe & John
# Smith").
def joinItems(items, sep=None):
    res = ""
    prev = None

    for s in items:
        s = s.strip()

        if not s:
            continue

        if not res:
            res = s
        elif sep is not None:
            res += sep + s
        elif (s.lower() in ("&", "and")) or (prev.lower() in ("&", "and")):
            res += " " + s
        else:
            res += ", " + s

        prev = s

    return res


# return the title page variables for 'tp' (a titles.Titles), as a
# {name: text} dict. each comes from the first title string of its kind
# (the topmost on the first page that has one), and is empty if there's
# none. the author falls back on the byline's
# lines after the "by" one, and the draft date is the draft string's last
# line with a digit in it, or its last line if it has more than one
# (like the "Month Day, Year" placeholder).
def titleVars(tp):
    first = {}

    # strings saved before kinds existed get the kind the title pages
    # dialog would guess for them, going down the page like guessKinds
    for page in tp.pages:
        prev = None

        for ts in sorted(page, key=lambda ts: ts.y):
            kind = ts.kind or titles.guessKind(ts, prev)
            first.setdefault(kind, ts)
            prev = kind

    def items(kind):
        ts = first.get(kind)

        return [s.strip() for s in ts.items if s.strip()] if ts else []

    author = items(titles.AUTHOR)

    if not author:
        author = items(titles.BYLINE)

        for i, s in enumerate(author):
            low = s.lower()

            if (low == "by") or low.endswith(" by"):
                author = author[i + 1 :]

                break

    draft = items(titles.DRAFT)
    dated = [s for s in draft if any(ch.isdigit() for ch in s)]

    if dated:
        draftDate = dated[-1]
    elif len(draft) > 1:
        draftDate = draft[-1]
    else:
        draftDate = ""

    return {
        "TITLE": joinItems(items(titles.TITLE), " "),
        "AUTHOR": joinItems(author),
        "DRAFT": joinItems(draft),
        "DRAFTDATE": draftDate,
    }


# return the variables for page 'pageNr' (a 1-based index into sp.pages)
# of script 'sp', as a {name: text} dict. 'tvars' is titleVars(sp.titles),
# for callers doing many pages.
def pageVars(sp, pageNr, tvars=None):
    v = dict(titleVars(sp.titles) if tvars is None else tvars)
    v["PAGE"] = sp.getPageLabel(pageNr)
    v["PAGES"] = sp.getPageLabel(len(sp.pages) - 1)
    v["REVISION"] = sp.revisions.label(sp.getPageRevision(pageNr))

    return v


# return 'text' with the variables in 'pvars' ({name: text}) filled in.
# anything else in ${...} is left as it is.
def expand(text, pvars):
    if "${" not in text:
        return text

    for name, val in pvars.items():
        text = text.replace("${%s}" % name, val)

    return text


# return the x position (in mm) of a string with alignment 'align' on
# the page: its left edge, center or right edge
def alignX(align, cfg):
    if align == util.ALIGN_LEFT:
        return cfg.marginLeft
    elif align == util.ALIGN_CENTER:
        return (cfg.marginLeft + (cfg.paperWidth - cfg.marginRight)) / 2.0
    else:
        return cfg.paperWidth - cfg.marginRight


# a script's headers.
class Headers:

    def __init__(self):
        # list of HeaderString objects
        self.hdrs = []

        # how many empty lines after the headers
        self.emptyLinesAfter = 1

    # create standard headers
    def addDefaults(self):
        h = HeaderString()
        h.text = "${PAGE}."
        h.align = util.ALIGN_RIGHT
        h.line = 1

        self.hdrs.append(h)

    # return how many header lines there are. includes number of empty
    # lines after possible headers.
    def getNrOfLines(self):
        nr = 0

        for h in self.hdrs:
            nr = max(nr, h.line)

        if nr > 0:
            nr += self.emptyLinesAfter

        return nr

    # add headers to given page, with the variables in 'pvars' (see
    # pageVars) filled in.
    def generatePML(self, page, pvars, cfg):
        for h in self.hdrs:
            h.generatePML(page, pvars, cfg)


# a single header string
class HeaderString:
    def __init__(self):

        # which line, 1-based
        self.line = 1

        # x offset, in characters
        self.xoff = 0

        # contents of string
        self.text = ""

        # whether this is centered in the horizontal direction
        self.align = util.ALIGN_CENTER

        # style flags
        self.isBold = False
        self.isItalic = False
        self.isUnderlined = False

    # return (x, y) of the string on the page, in mm. x is the left edge,
    # center or right edge depending on the alignment, and y the top.
    def getPos(self, cfg):
        x = alignX(self.align, cfg)
        fs = cfg.fontSize

        if self.xoff != 0:
            x += util.getTextWidth(" ", pml.COURIER, fs) * self.xoff

        y = cfg.marginTop + (self.line - 1) * util.getTextHeight(fs)

        return (x, y)

    # return the text with the variables in 'pvars' (see pageVars) filled
    # in
    def getText(self, pvars):
        return expand(self.text, pvars)

    def generatePML(self, page, pvars, cfg):
        fl = 0

        if self.isBold:
            fl |= pml.BOLD

        if self.isItalic:
            fl |= pml.ITALIC

        if self.isUnderlined:
            fl |= pml.UNDERLINED

        x, y = self.getPos(cfg)

        page.add(pml.TextOp(self.getText(pvars), x, y, cfg.fontSize, fl, self.align))

    # parse information from s, which must be a string created by __str__,
    # and set object state accordingly. keeps default settings on any
    # errors, does not throw any exceptions.
    #
    # sample of the format: '1,0,r,,${PAGE}.'
    def load(self, s):
        a = textutil.fromUTF8(s).split(",", 4)

        if len(a) != 5:
            return

        self.line = util.str2int(a[0], 1, 1, 5)
        self.xoff = util.str2int(a[1], 0, -100, 100)

        l, c, self.isBold, self.isItalic, self.isUnderlined = util.flags2bools(
            a[2], "lcbiu"
        )

        if l:
            self.align = util.ALIGN_LEFT
        elif c:
            self.align = util.ALIGN_CENTER
        else:
            self.align = util.ALIGN_RIGHT

        self.text = a[4]

    def __str__(self):
        s = "%d,%d," % (self.line, self.xoff)

        if self.align == util.ALIGN_LEFT:
            s += "l"
        elif self.align == util.ALIGN_CENTER:
            s += "c"
        else:
            s += "r"

        s += util.bools2flags("biu", self.isBold, self.isItalic, self.isUnderlined)

        s += ",,%s" % self.text

        return s


# a script's page footer: one line in the bottom margin, in three parts
# aligned to the left margin, the middle and the right margin. it takes
# no room from the script's lines, and isn't printed on the title pages.
class Footer:
    # (attribute, alignment, file key) of the three parts
    PARTS = [
        ("left", util.ALIGN_LEFT, "Footer-Left"),
        ("center", util.ALIGN_CENTER, "Footer-Center"),
        ("right", util.ALIGN_RIGHT, "Footer-Right"),
    ]

    def __init__(self):
        self.left = ""
        self.center = ""
        self.right = ""

        # whether it's printed on the script's first page too (which
        # never has headers)
        self.showOnFirstPage = True

    def __eq__(self, other):
        return isinstance(other, Footer) and (vars(self) == vars(other))

    def isEmpty(self):
        return not (self.left or self.center or self.right)

    # return whether it's printed on page 'pageNr' (1-based)
    def isOnPage(self, pageNr):
        return not self.isEmpty() and ((pageNr != 1) or self.showOnFirstPage)

    # return the y position of the top of the footer on the page, in mm:
    # centered in the bottom margin, or if the margin is too small for
    # that, at the bottom of the page, but never above the bottom of the
    # script's lines.
    @staticmethod
    def getY(cfg):
        chY = util.getTextHeight(cfg.fontSize)
        y = cfg.paperHeight - max(cfg.marginBottom + chY, 2 * chY) / 2.0

        return max(y, cfg.marginTop + cfg.linesOnPage * chY)

    # return whether the bottom margin has room for the footer
    @staticmethod
    def fits(cfg):
        return cfg.marginBottom >= util.getTextHeight(cfg.fontSize)

    # return [(text, alignment)] of the non-empty parts, with the
    # variables in 'pvars' (see pageVars) filled in
    def getTexts(self, pvars):
        res = []

        for attr, align, key in self.PARTS:
            text = getattr(self, attr)

            if text:
                res.append((expand(text, pvars), align))

        return res

    # add the footer to page 'page'
    def generatePML(self, page, pvars, cfg):
        y = self.getY(cfg)

        for text, align in self.getTexts(pvars):
            page.add(pml.TextOp(text, alignX(align, cfg), y, cfg.fontSize, 0, align))

    # return the footer's lines in the script file, or "" if it's empty
    def save(self):
        if self.isEmpty():
            return ""

        s = ""

        for attr, align, key in self.PARTS:
            s += "#%s %s\n" % (key, getattr(self, attr))

        s += "#Footer-First-Page %d\n" % self.showOnFirstPage

        return s

    # set what file key 'key' says to 'val'. returns whether the key is
    # one of the footer's.
    def load(self, key, val):
        for attr, align, k in self.PARTS:
            if key == k:
                setattr(self, attr, textutil.toInputStr(textutil.fromUTF8(val)))

                return True

        if key == "Footer-First-Page":
            self.showOnFirstPage = val.strip() != "0"

            return True

        return False
