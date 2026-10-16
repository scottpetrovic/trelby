# PDF files made by screenwriting programs (with text in them, not scanned
# pages). the text is read with its positions, the page furniture is taken
# out (page numbers and other repeated headers and footers, (MORE) and the
# character's (CONT'D) on the next page, CONTINUED lines, scene numbers),
# and what's left is turned into formatted text, one line per line on the
# page, indented by its distance from the page's left edge in characters.
# that is then imported like a text file (importers/text.py), with the
# same two steps: guessIndents guesses each indent level's line type for
# the GUI's ImportDlg, and parse converts the lines with the line types in
# the options.
#
# leading pages that look like title pages (mostly centered text, no scene
# headings) become the script's title pages.
#
# reading PDF files needs pypdf, an optional dependency (the "pdf" extra),
# imported only when a file is read.

import copy
import functools
import io
import re
import statistics

import trelby.importers.text as text
import trelby.screenplay.titles as titles
from trelby.importers.common import (
    ImportFailed,
    ImportResult,
    checkLines,
    checkNotEmpty,
)

# whether parse takes bytes rather than str
BINARY = True

# a character's width in Courier, as a fraction of the font size. the
# indents are counted in characters of the body text's font size.
COURIER_WIDTH = 0.6

MM_PER_POINT = 25.4 / 72.0

# the distance from a line's baseline to its top in pml (and so in the
# title page strings' y), as a fraction of the font size
ASCENT = 0.843

# a page number on its own: "12", "12.", "- 12 -", "Page 12", "12 of 90"
PAGE_NUMBER_RE = re.compile(
    r"^(page\s*)?[-(]?\s*\d+\s*[.)]?\s*-?(\s*(of|/)\s*\d+)?$", re.IGNORECASE
)

# scene continued markers at the top and bottom of pages, with or without
# scene numbers: "CONTINUED:", "12 CONTINUED: (2) 12", "(CONTINUED)"
CONTINUED_RE = re.compile(
    r"^(\S{1,6}\s+)?\(?CONTINUED\)?:?(\s*\(\d+\))?(\s+\S{1,6})?$", re.IGNORECASE
)

MORE_RE = re.compile(r"^\(\s*MORE\s*\)$", re.IGNORECASE)

# a character's continuation mark, at the end of the name
CONTD_RE = re.compile(
    r"\s*\(\s*(CONT['’]?D|CONT\.?|CONTINUING|CONTINUED)\s*\)$", re.IGNORECASE
)

# a scene number: "12", "12A", "A12", "12.", "*12*"
SCENE_NUMBER = r"\*?[A-Z]?\d+[A-Z]{0,3}\.?\*?"

# a line with scene numbers on one or both sides, separated by 2 or more
# spaces
SCENE_NUMBERS_RE = re.compile(
    r"^(%s\s{2,})?(.*?)(\s{2,}%s)?$" % (SCENE_NUMBER, SCENE_NUMBER)
)

# how scene headings start
SCENE_PREFIXES = (
    "INT.",
    "EXT.",
    "INT ",
    "EXT ",
    "INT/",
    "EXT/",
    "I/E",
    "E/I",
    "EST.",
    "INT--",
    "EXT--",
)


class Options:
    def __init__(self, lineTypes=None):
        # dict of indent -> line type, as in text.Options
        self.lineTypes = lineTypes or {}


# return the Indents of data's lines, with their line types guessed, as
# text.guessIndents does
def guessIndents(data):
    return text.guessIndents(_convertPDF(data).text)


# convert data, with the line types guessed or given in options. the
# result always has at least one line.
def parse(data, options=None):
    options = options or Options()
    conv = _convertPDF(data)

    result = text.parse(
        conv.text, text.Options(options.lineTypes, sceneLines=conv.sceneLines)
    )

    # a copy, since the conversion is cached
    return ImportResult(result.lines, copy.deepcopy(conv.titlePages) or None)


# a PDF converted to formatted text: the text, the indexes of its lines
# that are scene headings even though they don't start with INT. / EXT.,
# and the title pages (lists of titles.TitleString), if any
class Converted:
    def __init__(self, text, sceneLines, titlePages):
        self.text = text
        self.sceneLines = sceneLines
        self.titlePages = titlePages


# a line of text on a page. x and right are its left and right edges, y
# its baseline from the top of the page, all in points.
class PLine:
    def __init__(self, x, y, right, text, size, bold, font):
        self.x = x
        self.y = y
        self.right = right
        self.text = text
        self.size = size
        self.bold = bold
        self.font = font


class Page:
    def __init__(self, width, height, lines):
        self.width = width
        self.height = height

        # PLines from the top down
        self.lines = lines


# a line of the formatted text: indent in characters and text, or a blank
# line (text ""). heading is whether it should be a scene heading.
class Row:
    def __init__(self, indent=0, text="", heading=False, right=0):
        self.indent = indent
        self.text = text
        self.heading = heading

        # right edge in characters
        self.right = right


# converting is done once for both of the import's steps (guessIndents and
# parse), which get the same data
@functools.lru_cache(maxsize=2)
def _convertPDF(data):
    checkNotEmpty(data)

    pages = _readPages(data)

    if not any(pg.lines for pg in pages):
        raise ImportFailed(
            _(
                "The PDF file contains no text. Scanned scripts (pictures of"
                " pages) can't be imported."
            )
        )

    allLines = [ln for pg in pages for ln in pg.lines]

    # the body text's font size, by the number of characters
    sizes = {}
    for ln in allLines:
        sizes[ln.size] = sizes.get(ln.size, 0) + len(ln.text)

    size = max(sizes, key=sizes.get)
    cw = size * COURIER_WIDTH

    lineHeight = _lineHeight(pages, size)

    titleCount = _countTitlePages(pages, cw)
    titlePages = [_titlePage(pg, cw, lineHeight) for pg in pages[:titleCount]]
    pages = pages[titleCount:]

    _removeFurniture(pages, lineHeight)

    rows = _makeRows(pages, cw, lineHeight)
    _alignTransitions(rows)

    while rows and not rows[-1].text:
        rows.pop()

    checkLines(rows)

    s = "\n".join((" " * r.indent + r.text) if r.text else "" for r in rows)
    sceneLines = frozenset(i for i, r in enumerate(rows) if r.heading)

    return Converted(s, sceneLines, titlePages)


# return the pages of the PDF file in data
def _readPages(data):
    try:
        import pypdf
    except ImportError:
        raise ImportFailed(
            _(
                "Importing PDF files needs the pypdf Python module, which"
                " isn't installed. Install it with: pip install pypdf"
            )
        )

    try:
        reader = pypdf.PdfReader(io.BytesIO(data))

        if reader.is_encrypted and not reader.decrypt(""):
            raise ImportFailed(_("The PDF file is password protected."))

        return [_readPage(page) for page in reader.pages]
    except ImportFailed:
        raise
    except Exception as e:
        # pypdf raises all sorts of errors on broken files
        raise ImportFailed(_("Error reading PDF file: {}").format(e))


# a text fragment, as pypdf's text visitor gives them
class _Frag:
    def __init__(self, x, y, text, size, font):
        self.x = x
        self.y = y
        self.text = text
        self.size = size
        self.font = font


def _readPage(page):
    box = page.mediabox
    left = float(box.left)
    bottom = float(box.bottom)
    width = float(box.width)
    height = float(box.height)

    frags = []

    # by the font dictionary's id
    fonts = {}

    def visit(s, cm, tm, fontDict, fontSize):
        if not s.strip():
            return

        # tm * cm
        a = tm[0] * cm[0] + tm[1] * cm[2]
        b = tm[0] * cm[1] + tm[1] * cm[3]
        d = tm[2] * cm[1] + tm[3] * cm[3]
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]

        # only horizontal text
        if abs(b) > 0.01 * abs(a) or a <= 0 or d <= 0:
            return

        sz = round(fontSize * d, 1)
        font = fonts.get(id(fontDict))
        if font is None:
            font = fonts[id(fontDict)] = _Font(fontDict)

        # the visitor is called once per line, ending in a newline, but
        # more lines may come in one call
        for i, part in enumerate(s.split("\n")):
            fx = x - left
            fy = height - (y - bottom) + i * sz

            # text outside the page isn't shown (some programs put the
            # previous page's last line just above the top edge)
            if part.strip() and (0 <= fx < width) and (0 < fy <= height):
                frags.append(_Frag(fx, fy, part, sz, font))

    page.extract_text(visitor_text=visit)

    return Page(width, height, _joinFrags(frags))


# a font's name and character widths
class _Font:
    def __init__(self, fontDict):
        name = ""
        self.widths = None

        if fontDict:
            name = str(fontDict.get("/BaseFont", ""))

            try:
                first = int(fontDict["/FirstChar"])
                widths = [float(w) for w in fontDict["/Widths"]]
                self.widths = (first, widths)
            except Exception:
                pass

        # "/ABCDEF+Courier-Bold" -> "Courier-Bold"
        self.name = name.lstrip("/").split("+")[-1]

        self.bold = "bold" in self.name.lower()

        self.mono = any(m in self.name.lower() for m in ("courier", "mono"))

    # the width of s in this font at the given size
    def width(self, s, size):
        if self.mono or not self.name:
            return len(s) * size * COURIER_WIDTH

        from reportlab.pdfbase import pdfmetrics

        if self.name in pdfmetrics.standardFonts:
            return pdfmetrics.stringWidth(s, self.name, size)

        if self.widths:
            first, widths = self.widths
            total = 0.0

            for ch in s:
                i = ord(ch) - first
                total += widths[i] if 0 <= i < len(widths) else 500.0

            return total * size / 1000.0

        return len(s) * size * COURIER_WIDTH


# join the fragments on each line, giving the page's lines from the top
# down
def _joinFrags(frags):
    lines = []

    for f in frags:
        for ln in lines:
            if abs(ln[0].y - f.y) < f.size * 0.3:
                ln.append(f)
                break
        else:
            lines.append([f])

    ret = []

    for ln in lines:
        # fragments starting at the same place continue the one before
        # (pypdf gives the position of the text operator, not of each
        # piece of text it shows)
        runs = []
        for f in ln:
            if runs and abs(runs[-1][0].x - f.x) < 0.01:
                runs[-1].append(f)
            else:
                runs.append([f])

        runs.sort(key=lambda r: r[0].x)

        s = ""
        end = None
        bold = True

        for run in runs:
            x = run[0].x
            cw = run[0].size * COURIER_WIDTH

            if end is not None:
                gap = (x - end) / cw

                if gap > 0.5:
                    s += " " * max(1, round(gap))
                elif gap > 0.2 and not s.endswith(" "):
                    s += " "
            else:
                start = x
                end = x

            for f in run:
                # pypdf sometimes puts a space before a line's text
                if f is run[0]:
                    f.text = f.text.lstrip()

                s += f.text
                end = max(end, x) + f.font.width(f.text, f.size)
                x = end
                bold = bold and f.font.bold

        first = runs[0][0]
        s = s.strip()

        if s:
            ret.append(PLine(start, first.y, end, s, first.size, bold, first.font))

    ret.sort(key=lambda ln: ln.y)

    return ret


# the distance between the lines of a paragraph: the most common distance
# between consecutive lines that's about the font size (in a script with
# little dialogue, the distance between paragraphs could be more common)
def _lineHeight(pages, size):
    gaps = {}

    for pg in pages:
        for a, b in zip(pg.lines, pg.lines[1:]):
            if (a.size == size) and (b.size == size):
                g = round(b.y - a.y, 1)

                if size * 0.8 <= g <= size * 1.5:
                    gaps[g] = gaps.get(g, 0) + 1

    if not gaps:
        return size

    return max(gaps, key=gaps.get)


# return how many of the leading pages are title pages: mostly centered
# text and no scene headings. at least one page is left for the script.
def _countTitlePages(pages, cw):
    n = 0

    while n < len(pages) - 1:
        pg = pages[n]
        lines = pg.lines

        if not lines or any(_isSceneHeading(ln.text) for ln in lines):
            break

        centered = sum(1 for ln in lines if _isCentered(ln, pg, cw))

        if centered * 2 < len(lines):
            break

        n += 1

    return n


def _isCentered(ln, pg, cw):
    return abs((ln.x + ln.right) / 2 - pg.width / 2) < cw


# turn a title page's lines into TitleStrings: lines close together with
# the same alignment go in the same string
def _titlePage(pg, cw, lineHeight):
    ret = []
    prev = None
    kind = None

    for ln in pg.lines:
        if _isCentered(ln, pg, cw):
            align = "c"
        elif abs(ln.right - pg.width + ln.x) < cw and ln.x > pg.width / 2:
            # right-aligned as far from the right edge as the left margin
            align = "r"
        elif ln.x > pg.width / 2:
            align = "r"
        else:
            align = "l"

        gap = ln.y - prev.y if prev else None

        if (
            ret
            and (prev.size == ln.size)
            and (align == ret[-1].align)
            and gap < ln.size / 12.0 * lineHeight * 2.5
            and ((align != "l") or abs(ln.x - prev.x) < cw)
            and ((align != "r") or abs(ln.right - prev.right) < cw)
        ):
            ts = ret[-1]

            # blank lines between
            for _i in range(round(gap / (ln.size / 12.0 * lineHeight)) - 1):
                ts.items.append("")

            ts.items.append(ln.text)
        else:
            ts = titles.TitleString(
                [ln.text],
                y=(ln.y - ln.size * ASCENT) * MM_PER_POINT,
                isCentered=(align == "c"),
                isBold=ln.bold,
                size=round(ln.size),
                font=_pmlFont(ln.font),
            )
            ts.align = align

            if align == "l":
                ts.x = ln.x * MM_PER_POINT
            elif align == "r":
                ts.isRightJustified = True
                ts.x = ln.right * MM_PER_POINT

            ret.append(ts)

        prev = ln

    for ts in ret:
        del ts.align
        ts.kind = titles.guessKind(ts, kind)
        kind = ts.kind

    return ret


def _pmlFont(font):
    import trelby.pdf.pml as pml

    name = font.name.lower()

    if "helvetica" in name or "arial" in name or "sans" in name:
        return pml.HELVETICA

    if "times" in name or "serif" in name:
        return pml.TIMES_ROMAN

    return pml.COURIER


# take the page furniture off the pages: page numbers and other headers and
# footers repeated on many pages (lines at the top or bottom, apart from
# the rest), and CONTINUED lines. scene numbers, (MORE) and the
# character's name repeated on the next page are left for _makeRows.
def _removeFurniture(pages, lineHeight):
    # lines at the top or bottom of a page, apart from the rest
    def edgeLines(pg):
        lines = pg.lines
        ret = []

        for i in range(min(2, len(lines))):
            nxt = lines[i + 1] if i + 1 < len(lines) else None

            if nxt is None or (nxt.y - lines[i].y) > lineHeight * 1.5:
                ret.append(lines[i])
            else:
                break

        for i in range(len(lines) - 1, max(len(lines) - 3, -1), -1):
            prv = lines[i - 1] if i > 0 else None

            if (prv is None or (lines[i].y - prv.y) > lineHeight * 1.5) and (
                lines[i] not in ret
            ):
                ret.append(lines[i])
            else:
                break

        return ret

    def normalize(s):
        return re.sub(r"\d+", "#", re.sub(r"\s+", " ", s)).upper()

    counts = {}
    for pg in pages:
        for s in {normalize(ln.text) for ln in edgeLines(pg)}:
            counts[s] = counts.get(s, 0) + 1

    repeated = {
        s for s, n in counts.items() if n >= max(3, len(pages) / 2) and "MORE" not in s
    }

    for pg in pages:
        drop = set()

        for ln in edgeLines(pg):
            if (normalize(ln.text) in repeated) or PAGE_NUMBER_RE.match(ln.text):
                drop.add(id(ln))

        # CONTINUED among the first and last two lines
        lines = pg.lines
        for ln in lines[:2] + lines[-2:]:
            if CONTINUED_RE.match(ln.text):
                drop.add(id(ln))

        pg.lines = [ln for ln in lines if id(ln) not in drop]


# turn the pages into rows of formatted text: indents in characters from
# the left edge, blank rows where there's space between lines, and the
# furniture that's left taken out
def _makeRows(pages, cw, lineHeight):
    rows = []

    # whether the previous page ended with (MORE), and the last character
    # name before that
    more = False
    lastName = None
    prevLast = None

    for pg in pages:
        lines = list(pg.lines)

        if more and lines:
            # the character's name repeated, usually with (CONT'D)
            s = lines[0].text

            if _isCaps(s) and (
                CONTD_RE.search(s) or _baseName(s) == lastName
            ):
                lines = lines[1:]

        pageRows = []
        prev = None
        endsWithMore = False

        for i, ln in enumerate(lines):
            s = ln.text

            if MORE_RE.match(s):
                if i == len(lines) - 1:
                    endsWithMore = True

                continue

            x = ln.x
            s, skipped = _stripSceneNumbers(s)
            x += skipped * cw

            if prev is not None and (ln.y - prev.y) > lineHeight * 1.5:
                pageRows.append(Row())

            indent = max(0, round(x / cw))

            if _isCaps(s) and CONTD_RE.search(s):
                s = CONTD_RE.sub("", s)

            if _isCaps(s) and len(s) < 40:
                lastName = _baseName(s)

            pageRows.extend(_splitDual(indent, s, round(ln.right / cw)))
            prev = ln

        if pageRows:
            first = pageRows[0]

            # a paragraph going on from the previous page, or dialogue
            # after (MORE), joins up; otherwise there's a new paragraph
            if rows and not (
                more
                or (
                    prevLast
                    and prevLast.indent == first.indent
                    and (
                        not re.search(r"[.!?:\"')]$", prevLast.text)
                        or first.text[:1].islower()
                    )
                )
            ):
                rows.append(Row())

            rows.extend(pageRows)
            prevLast = pageRows[-1]

        more = endsWithMore

    rows = _orderDual(rows)
    _markHeadings(rows)

    return rows


# remove scene numbers from either end of s. return the rest and how many
# characters were taken off the start.
def _stripSceneNumbers(s):
    m = SCENE_NUMBERS_RE.match(s)

    if not m or not (m.group(1) or m.group(3)) or not m.group(2):
        return s, 0

    rest = m.group(2)

    # numbers on the right only, on scene headings only, since an action
    # line might end in a number after spaces
    if not m.group(1) and not _isSceneHeading(rest):
        return s, 0

    return rest, len(m.group(1) or "")


# rows for a line of text, which may be two columns of dual dialogue, far
# apart: a row for each column, marked for _orderDual
def _splitDual(indent, s, right):
    m = re.match(r"^(.*?\S)\s{4,}(\S.*)$", s)

    if not m or _isSceneHeading(s):
        return [Row(indent, s, right=right)]

    left = Row(indent, m.group(1), right=indent + len(m.group(1)))
    left.dual = True

    rightRow = Row(indent + len(s) - len(m.group(2)), m.group(2), right=right)
    rightRow.dual = True

    return [left, rightRow]


# put dual dialogue's columns one after the other: in each run of rows
# without a blank row with one split by _splitDual, the rows at or right
# of the right column's indent go after the others. the columns are
# narrower than normal dialogue, so their rows get the indents the
# character, parenthetical and dialogue rows elsewhere have.
def _orderDual(rows):
    indents = _dialogueIndents(rows)
    ret = []
    i = 0

    while i < len(rows):
        j = i

        while j < len(rows) and rows[j].text:
            j += 1

        block = rows[i:j]
        dual = [r for r in block if getattr(r, "dual", False)]

        if dual and len(dual) >= 2:
            col = min(r.indent for r in dual[1::2])
            leftRows = [r for r in block if r.indent < col - 1]
            rightRows = [r for r in block if r.indent >= col - 1]

            ret.extend(_reindentColumn(leftRows, indents))

            if leftRows and rightRows:
                ret.append(Row())

            ret.extend(_reindentColumn(rightRows, indents))
        else:
            ret.extend(block)

        if j < len(rows):
            ret.append(rows[j])

        i = j + 1

    return ret


# return the most common indents of character names, parentheticals and
# dialogue outside dual dialogue, as a dict with the keys "name",
# "paren" and "dialogue", for the ones found
def _dialogueIndents(rows):
    counts = {"name": {}, "paren": {}, "dialogue": {}}

    for i in range(1, len(rows) - 1):
        r = rows[i]

        if not r.text or getattr(r, "dual", False):
            continue

        prev, nxt = rows[i - 1], rows[i + 1]

        if not prev.text and nxt.text and _isCaps(r.text) and len(r.text) < 40:
            key = "name"
        elif prev.text and r.text.startswith("("):
            key = "paren"
        elif prev.text and _isCaps(prev.text) and (prev.indent > r.indent):
            key = "dialogue"
        else:
            continue

        counts[key][r.indent] = counts[key].get(r.indent, 0) + 1

    return {k: max(c, key=c.get) for k, c in counts.items() if c}


# give a column of dual dialogue the indents in 'indents' (as returned by
# _dialogueIndents): its first row is the name, rows from one starting
# with "(" to one ending with ")" parentheticals, and the rest dialogue.
# without all three indents, the column is left as it is.
def _reindentColumn(rows, indents):
    if len(indents) < 3:
        return rows

    inParen = False

    for i, r in enumerate(rows):
        if i == 0:
            r.indent = indents["name"]
        elif inParen or r.text.startswith("("):
            r.indent = indents["paren"] + (1 if inParen else 0)
            inParen = not r.text.endswith(")")
        else:
            r.indent = indents["dialogue"]

    return rows


# mark the rows that are scene headings without starting with INT. or
# EXT.: ones starting with the other usual prefixes, and lines in capitals
# on their own at the leftmost indent, like "LATER" or "MAP OF THE WORLD",
# but not "FADE IN:" or "BANG!"
def _markHeadings(rows):
    indents = {}
    for r in rows:
        if r.text:
            indents[r.indent] = indents.get(r.indent, 0) + 1

    if not indents:
        return

    total = sum(indents.values())
    left = min(i for i, n in indents.items() if n * 20 >= total)

    for i, r in enumerate(rows):
        if not r.text or r.indent != left:
            continue

        alone = ((i == 0) or not rows[i - 1].text) and (
            (i == len(rows) - 1) or not rows[i + 1].text
        )

        if _isSceneHeading(r.text) or (
            alone
            and _isCaps(r.text)
            and ":" not in r.text
            and r.text[-1].isalnum()
        ):
            r.heading = True


# give right-aligned transitions ("CUT TO:" ending at the right margin)
# the same indent, so they're one indent level
def _alignTransitions(rows):
    cands = []

    for i, r in enumerate(rows):
        alone = ((i == 0) or not rows[i - 1].text) and (
            (i == len(rows) - 1) or not rows[i + 1].text
        )

        if alone and r.text and _isCaps(r.text) and r.text.endswith((":", ".")):
            cands.append(r)

    if len(cands) < 2:
        return

    edge = statistics.median(r.right for r in cands)
    aligned = [r for r in cands if abs(r.right - edge) <= 1]

    if len({r.indent for r in aligned}) < 2:
        return

    # right-aligned ones are well right of the leftmost text
    leftmost = min(r.indent for r in rows if r.text)
    aligned = [r for r in aligned if r.indent > leftmost + 10]

    if len(aligned) < 2:
        return

    indent = min(r.indent for r in aligned)

    for r in aligned:
        r.indent = indent


def _isSceneHeading(s):
    return s.upper().startswith(SCENE_PREFIXES)


# whether s has letters, all in capitals
def _isCaps(s):
    return (s.upper() == s) and any(ch.isalpha() for ch in s)


# a character's name without what's in parentheses after it
def _baseName(s):
    return re.sub(r"\s*\(.*$", "", s).strip()
