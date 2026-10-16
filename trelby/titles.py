import trelby.pdf.pml as pml
import trelby.textutil as textutil
import trelby.util as util

# kinds of title strings, in the order they're offered when adding one.
# the kind is a label and a starting template (see makeString); it doesn't
# affect the output.
TITLE = "title"
BYLINE = "byline"
AUTHOR = "author"
BASED_ON = "basedon"
DRAFT = "draft"
CONTACT = "contact"
COPYRIGHT = "copyright"
TEXT = "text"

KINDS = [TITLE, BYLINE, AUTHOR, BASED_ON, DRAFT, CONTACT, COPYRIGHT, TEXT]

# distance of the strings at the bottom of the page from the page edges,
# in mm
EDGE_X = 15.0
BOTTOM_Y = 30.94


# return a new TitleString of the given kind, with placeholder text and
# typical formatting and position for that kind on a page of the given
# size (in mm)
def makeString(kind, paperWidth, paperHeight):
    bottom = paperHeight - BOTTOM_Y

    if kind == TITLE:
        ts = TitleString(
            ["UNTITLED SCREENPLAY"], y=105.0, size=24, isBold=True, font=pml.HELVETICA
        )
    elif kind == BYLINE:
        ts = TitleString(["Written by", "", "Author Name"], y=120.46)
    elif kind == AUTHOR:
        ts = TitleString(["Author Name"], y=137.39)
    elif kind == BASED_ON:
        ts = TitleString(["Based on", "Source Material", "by Original Author"], y=150.0)
    elif kind == DRAFT:
        ts = TitleString(["First Draft", "Month Day, Year"], y=bottom, isCentered=False)
        ts.x = paperWidth - EDGE_X
        ts.isRightJustified = True
    elif kind == CONTACT:
        ts = TitleString(
            ["Name", "Address", "Phone", "Email"], EDGE_X, bottom, isCentered=False
        )
    elif kind == COPYRIGHT:
        ts = TitleString(["Copyright (c) Year"], y=bottom + 17.0, isCentered=False)
        ts.x = paperWidth - EDGE_X
        ts.isRightJustified = True
    else:
        kind = TEXT
        ts = TitleString(["Text"], y=paperHeight / 2.0)

    ts.kind = kind

    return ts


# return a guess at the kind of title string 'ts', for strings saved
# before kinds existed. 'prev' is the kind of the string above it on the
# page, or None.
def guessKind(ts, prev):
    text = " ".join(ts.items).strip().lower()
    first = ts.items[0].strip().lower() if ts.items else ""

    if (first == "by") or first.endswith(" by"):
        return BYLINE

    if text.startswith("based on"):
        return BASED_ON

    if ("draft" in text) or ("revision" in text):
        return DRAFT

    if any(w in text for w in ("copyright", "(c)", "©", "rights reserved", "wga")):
        return COPYRIGHT

    if ("@" in text) or (sum(ch.isdigit() for ch in text) >= 7):
        return CONTACT

    if ts.isCentered and (prev == BYLINE):
        return AUTHOR

    if ts.isCentered and (ts.isBold or (ts.size > 12)):
        return TITLE

    return TEXT


# a script's title pages.
class Titles:

    def __init__(self):
        # list of lists of TitleString objects
        self.pages = []

    # create semi-standard title page
    def addDefaults(self):
        a = []

        y = 105.0
        a.append(
            TitleString(
                ["UNTITLED SCREENPLAY"],
                y=y,
                size=24,
                isBold=True,
                font=pml.HELVETICA,
                kind=TITLE,
            )
        )
        a.append(TitleString(["by", "", "My Name Here"], y=y + 15.46, kind=BYLINE))

        x = 15.0
        y = 240.0
        a.append(
            TitleString(
                ["123/456-7890", "no.such@thing.com"],
                x,
                y + 8.46,
                False,
                kind=CONTACT,
            )
        )

        self.pages.append(a)

    # set the kind of every title string that doesn't have one, by
    # guessing from its text and formatting
    def guessKinds(self):
        for page in self.pages:
            prev = None

            for ts in sorted(page, key=lambda ts: ts.y):
                if ts.kind is None:
                    ts.kind = guessKind(ts, prev)

                prev = ts.kind

    # add title pages to doc.
    def generatePages(self, doc):
        for page in self.pages:
            pg = pml.Page(doc)

            for s in page:
                s.generatePML(pg)

            doc.add(pg)

    # return a (rough) RTF fragment representation of title pages
    def generateRTF(self):
        s = util.String()

        for page in self.pages:
            for p in page:
                s += p.generateRTF()

            s += "\\page\n"

        return str(s)

    # sort the title strings on each page in y,x order (makes editing them
    # easier and RTF output better). strings at the same position keep
    # their order.
    def sort(self):
        for page in self.pages:
            page.sort(key=lambda ts: (ts.y, ts.x))


# a single string displayed on a title page
class TitleString:
    def __init__(
        self,
        items,
        x=0.0,
        y=0.0,
        isCentered=True,
        isBold=False,
        size=12,
        font=pml.COURIER,
        kind=None,
    ):

        # what this string is (one of KINDS), or None if not known, for
        # strings saved before kinds existed
        self.kind = kind

        # list of text strings
        self.items = items

        # position, in mm from the top left corner of the page. y is the
        # top of the first line. x is the left edge, or the right edge if
        # isRightJustified, and is ignored if isCentered.
        self.x = x
        self.y = y

        # size in points
        self.size = size

        # whether this is centered in the horizontal direction
        self.isCentered = isCentered

        # whether this is right-justified (xpos = rightmost edge of last
        # character)
        self.isRightJustified = False

        # style flags
        self.isBold = isBold
        self.isItalic = False
        self.isUnderlined = False

        # font
        self.font = font

    def getStyle(self):
        fl = self.font

        if self.isBold:
            fl |= pml.BOLD

        if self.isItalic:
            fl |= pml.ITALIC

        if self.isUnderlined:
            fl |= pml.UNDERLINED

        return fl

    def getAlignment(self):
        if self.isCentered:
            return util.ALIGN_CENTER
        elif self.isRightJustified:
            return util.ALIGN_RIGHT
        else:
            return util.ALIGN_LEFT

    def setAlignment(self, align):
        if align == util.ALIGN_CENTER:
            self.isCentered = True
            self.isRightJustified = False
        elif align == util.ALIGN_RIGHT:
            self.isCentered = False
            self.isRightJustified = True
        else:
            self.isCentered = False
            self.isRightJustified = False

    def generatePML(self, page):
        y = self.y

        for line in self.items:
            x = self.x

            if self.isCentered:
                x = page.doc.w / 2.0

            page.add(
                pml.TextOp(line, x, y, self.size, self.getStyle(), self.getAlignment())
            )

            y += util.getTextHeight(self.size)

    # return a (rough) RTF fragment representation of this string
    def generateRTF(self):
        s = ""

        for line in self.items:
            tmp = "\\fs%d" % (self.size * 2)

            if self.isCentered:
                tmp += r" \qc"
            elif self.isRightJustified:
                tmp += r" \qr"

            if self.isBold:
                tmp += r" \b"

            if self.isItalic:
                tmp += r" \i"

            if self.isUnderlined:
                tmp += r" \ul"

            s += r"{\pard\plain%s %s}{\par}" % (tmp, textutil.escapeRTF(line))

        return s

    # parse information from s, which must be a string created by __str__,
    # and set object state accordingly. keeps default settings on any
    # errors, does not throw any exceptions.
    #
    # sample of the format:
    # '0.000000,70.000000,24,cb,Helvetica,title,text here'
    #
    # the kind field was empty and ignored before kinds existed.
    def load(self, s):
        a = textutil.fromUTF8(s).split(",", 6)

        if len(a) != 7:
            return

        self.x = util.str2float(a[0], 0.0)
        self.y = util.str2float(a[1], 0.0)
        self.size = util.str2int(a[2], 12, 4, 288)

        (
            self.isCentered,
            self.isRightJustified,
            self.isBold,
            self.isItalic,
            self.isUnderlined,
        ) = util.flags2bools(a[3], "crbiu")

        tmp = {
            "Courier": pml.COURIER,
            "Helvetica": pml.HELVETICA,
            "Times": pml.TIMES_ROMAN,
        }

        self.font = tmp.get(a[4], pml.COURIER)
        self.kind = a[5] if a[5] in KINDS else None
        self.items = textutil.unescapeStrings(a[6])

    def __str__(self):
        s = "%f,%f,%d," % (self.x, self.y, self.size)

        s += util.bools2flags(
            "crbiu",
            self.isCentered,
            self.isRightJustified,
            self.isBold,
            self.isItalic,
            self.isUnderlined,
        )
        s += ","

        if self.font == pml.COURIER:
            s += "Courier"
        elif self.font == pml.HELVETICA:
            s += "Helvetica"
        else:
            s += "Times"

        s += ",%s,%s" % (self.kind or "", textutil.escapeStrings(self.items))

        return s
