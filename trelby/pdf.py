import uuid
from typing import AnyStr, Dict, Optional, Tuple

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

import trelby.pml as pml
import trelby.pml as util
import trelby.textfmt as textfmt

# PDF transform matrixes where key is the angle from x-axis
# in counter-clockwise direction.
#
# these are the (a, b, c, d) of a PDF text matrix (cos, sin, -sin, cos).
# the 45 degree one isn't normalized (cos 45 = 0.707, not 1), so text at
# that angle (the watermarks) comes out sqrt(2) times its nominal size.
TRANSFORM_MATRIX = {
    45: (1, 1, -1, 1),
    90: (0, 1, -1, 0),
}


# users should only use this.
def generate(doc: "pml.Document") -> bytes:
    tmp = PDFExporter(doc)
    return tmp.generate()


# return the characters in doc's text that its fonts can't show, sorted
# and without duplicates, as a string. the standard PDF fonts (used when
# no TrueType font is set for a style) only have the WinAnsi (cp1252)
# characters. reportlab draws others with a fallback font: Greek letters
# come out in the proportional Symbol font, most others as black boxes.
def unsupportedChars(doc: "pml.Document") -> str:
    chars = set()

    for page in doc.pages:
        for op in page.ops:
            if not isinstance(op, pml.TextOp) or op.text.isascii():
                continue

            if op.fmt and (op.angle is None):
                runs = [
                    (a, b, op.flags | (style & (pml.BOLD | pml.ITALIC)))
                    for a, b, style in textfmt.runs(op.fmt, len(op.text))
                ]
            else:
                runs = [(0, len(op.text), op.flags)]

            for a, b, flags in runs:
                if (flags & 15) in doc.fonts:
                    continue

                for ch in op.text[a:b]:
                    if isWinAnsi(ch):
                        continue

                    # double-width text uses CJK_FONT for these
                    if (op.charWidth != 1) and isInCJKFont(ch):
                        continue

                    chars.add(ch)

    return "".join(sorted(chars))


# return True if ch is in the WinAnsi encoding of the standard PDF fonts
def isWinAnsi(ch: str) -> bool:
    try:
        ch.encode("cp1252")
    except UnicodeEncodeError:
        return False

    return True


# the font double-width characters that the standard PDF fonts don't have
# are drawn in: one of the Adobe Asian fonts, which PDF viewers have or
# substitute, so it isn't embedded. it covers Simplified Chinese (the
# Adobe-GB1 character collection), and with it most Traditional Chinese
# and Japanese characters, but not Korean Hangul.
CJK_FONT = "STSong-Light"


# return True if ch is in CJK_FONT. Adobe-GB1 is roughly the GBK encoding.
def isInCJKFont(ch: str) -> bool:
    try:
        ch.encode("gbk")
    except UnicodeEncodeError:
        return False

    return True


# An abstract base class for all PDF drawing operations.
class PDFDrawOp:

    # draw the PML object pmlOp on the reportlab canvas. pe = PDFExporter,
    # which has the coordinate conversions and font lookup.
    def draw(
        self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas: Canvas
    ) -> None:
        raise Exception(_("draw not implemented"))


class PDFTextOp(PDFDrawOp):
    def draw(self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas) -> None:
        if not isinstance(pmlOp, pml.TextOp):
            raise Exception(
                _("PDFTextOp is only compatible with pml.TextOp, got ")
                + type(pmlOp).__name__
            )

        # we need to adjust y position since PDF uses baseline of text as
        # the y pos, but pml uses top of the text as y pos. The Adobe
        # standard Courier family font metrics give 157 units in 1/1000
        # point units as the Descender value, thus giving (1000 - 157) =
        # 843 units from baseline to top of text.

        # http://partners.adobe.com/asn/tech/type/ftechnotes.jsp contains
        # the "Font Metrics for PDF Core 14 Fonts" document.

        x = pe.x(pmlOp.x)
        y = pe.y(pmlOp.y) - 0.843 * pmlOp.size

        newFont = pe.getFontForFlags(pmlOp.flags)
        canvas.setFont(newFont, pmlOp.size)

        # rotated text is written as raw PDF operators, since reportlab's
        # drawString can't rotate. the font comes from the setFont call
        # above: it emits a Tf operator, and the font is part of the PDF
        # graphics state, so it carries over into this text object.
        if pmlOp.angle is not None:
            matrix = TRANSFORM_MATRIX.get(pmlOp.angle)

            if matrix:
                canvas.addLiteral(
                    "BT\n"
                    "%f %f %f %f %f %f Tm\n"
                    "(%s) Tj\n"
                    "ET\n"
                    % (
                        matrix[0],
                        matrix[1],
                        matrix[2],
                        matrix[3],
                        x,
                        y,
                        pe.escapeStr(pmlOp.text),
                    )
                )  # TODO: Doing this with addLiteral, non-latin characters won't work in watermarks. There must be a better way to do this with reportlab, that we do it this way is for historical reasons and because no one took the time to change it
            else:
                # unsupported angle, don't print it.
                pass
        elif pmlOp.charWidth != 1:
            self.drawCells(pmlOp, pe, canvas, x, y)
        elif pmlOp.fmt:
            # bold / italic / underlined parts of the text are drawn
            # separately, each in its own font
            partX = x

            for a, b, style in textfmt.runs(pmlOp.fmt, len(pmlOp.text)):
                part = pmlOp.text[a:b]
                flags = pmlOp.flags | (style & (pml.BOLD | pml.ITALIC))

                if style & textfmt.UNDERLINED:
                    flags |= pml.UNDERLINED

                font = pe.getFontForFlags(flags)
                canvas.setFont(font, pmlOp.size)
                canvas.drawString(partX, y, part)

                w = canvas.stringWidth(part, font, pmlOp.size)

                if flags & pml.UNDERLINED:
                    self.underline(canvas, partX, y, w, pmlOp.size)

                partX += w
        else:
            canvas.drawString(x, y, pmlOp.text)

        # formatted and double-width text underlines its runs itself
        # (above, and in drawCells), so the whole text is only underlined
        # here for plain and rotated text
        if (pmlOp.flags & pml.UNDERLINED) and (
            (pmlOp.angle is not None) or not (pmlOp.fmt or (pmlOp.charWidth != 1))
        ):
            undLen = canvas.stringWidth(pmlOp.text, newFont, pmlOp.size)
            self.underline(canvas, x, y, undLen, pmlOp.size)

        # create bookmark for table of contents if applicable
        if pmlOp.toc:
            bookmarkKey = (
                uuid.uuid4().hex
            )  # we need a unique key to link the bookmark in toc – TODO: generate a more speaking one
            canvas.bookmarkHorizontal(bookmarkKey, pe.x(pmlOp.x), pe.y(pmlOp.y))
            canvas.addOutlineEntry(pmlOp.toc.text, bookmarkKey)


    # draw a text with double-width characters (see pml.TextOp), starting
    # at (x, y) in PDF coordinates: each character centered in its own
    # cell. characters the style's font doesn't have are drawn in the
    # Chinese CID font, if they're in it (see isInCJKFont).
    def drawCells(self, pmlOp, pe, canvas, x, y):
        size = pmlOp.size

        # Courier characters are 600/1000 of the font size wide
        cellW = pmlOp.charWidth * 0.6 * size

        if pmlOp.fmt:
            runs = textfmt.runs(pmlOp.fmt, len(pmlOp.text))
        else:
            runs = [(0, len(pmlOp.text), 0)]

        for a, b, style in runs:
            flags = pmlOp.flags | (style & (pml.BOLD | pml.ITALIC))

            if style & textfmt.UNDERLINED:
                flags |= pml.UNDERLINED

            font = pe.getFontForFlags(flags)
            hasCustomFont = (flags & 15) in pe.doc.fonts

            for i in range(a, b):
                ch = pmlOp.text[i]

                if ch == " ":
                    continue

                chFont = font

                if not hasCustomFont and not isWinAnsi(ch) and isInCJKFont(ch):
                    chFont = pe.getCJKFont()

                w = canvas.stringWidth(ch, chFont, size)
                canvas.setFont(chFont, size)
                canvas.drawString(x + i * cellW + (cellW - w) / 2.0, y, ch)

            if flags & pml.UNDERLINED:
                self.underline(canvas, x + a * cellW, y, (b - a) * cellW, size)

    # underline text of width w drawn at (x, y) in the given font size
    @staticmethod
    def underline(canvas, x, y, w, size):
        # all standard PDF fonts have the underline line 100 units below
        # baseline with a thickness of 50
        undY = y - 0.1 * size
        canvas.setLineWidth(0.05 * size)

        canvas.line(x, undY, x + w, undY)


class PDFLineOp(PDFDrawOp):
    def draw(self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas):
        if not isinstance(pmlOp, pml.LineOp):
            raise Exception(
                _("PDFLineOp is only compatible with pml.LineOp, got ")
                + type(pmlOp).__name__
            )

        points = pmlOp.points
        numberOfPoints = len(points)

        if numberOfPoints < 2:
            print(_("LineOp contains only {} points").format(numberOfPoints))

            return

        canvas.setLineWidth(pe.mm2points(pmlOp.width))

        lines = []
        for i in range(0, numberOfPoints - 1):
            lines.append(pe.xy(points[i]) + pe.xy(points[i + 1]))

        if pmlOp.isClosed:
            lines.append(pe.xy(points[i + 1]) + pe.xy(points[0]))

        canvas.lines(lines)


class PDFRectOp(PDFDrawOp):
    def draw(self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas) -> None:
        if not isinstance(pmlOp, pml.RectOp):
            raise Exception(
                _("PDFRectOp is only compatible with pml.RectOp, got ")
                + type(pmlOp).__name__
            )

        if pmlOp.lw != -1:
            canvas.setLineWidth(pe.mm2points(pmlOp.lw))

        canvas.rect(
            pe.x(pmlOp.x),
            pe.y(pmlOp.y) - pe.mm2points(pmlOp.height),
            pe.mm2points(pmlOp.width),
            pe.mm2points(pmlOp.height),
            pmlOp.fillType == pml.NO_FILL or pmlOp.fillType == pml.STROKE_FILL,
            pmlOp.fillType == pml.FILL or pmlOp.fillType == pml.STROKE_FILL,
        )


class PDFQuarterCircleOp(PDFDrawOp):
    def draw(self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas) -> None:
        if not isinstance(pmlOp, pml.QuarterCircleOp):
            raise Exception(
                _(
                    "PDFQuarterCircleOp is only compatible with pml.QuarterCircleOp, got "
                )
                + type(pmlOp).__name__
            )

        sX = pmlOp.flipX and -1 or 1
        sY = pmlOp.flipY and -1 or 1

        # The traditional constant is: 0.552284749
        # however, as described here:
        # http://spencermortensen.com/articles/bezier-circle/,
        # this has a maximum radial drift of 0.027253%.
        # The constant calculated by Spencer Mortensen
        # has a max. drift of 0.019608% which is 28% better.
        A = pmlOp.radius * 0.551915024494

        canvas.setLineWidth(pe.mm2points(pmlOp.width))
        canvas.bezier(
            pe.x(pmlOp.x - pmlOp.radius * sX),
            pe.y(pmlOp.y),
            pe.x(pmlOp.x - pmlOp.radius * sX),
            pe.y(pmlOp.y - A * sY),
            pe.x(pmlOp.x - A * sX),
            pe.y(pmlOp.y - pmlOp.radius * sY),
            pe.x(pmlOp.x),
            pe.y(pmlOp.y - pmlOp.radius * sY),
        )


class PDFArbitraryOp(PDFDrawOp):
    def draw(self, pmlOp: "pml.DrawOp", pageNr: int, pe: "PDFExporter", canvas) -> None:
        if not isinstance(pmlOp, pml.PDFOp):
            raise Exception(
                _("PDFArbitraryOp is only compatible with pml.PDFOp, got ")
                + type(pmlOp).__name__
            )

        canvas.addLiteral("%s\n" % pmlOp.cmds)


# used for keeping track of used fonts. only 'name' is used now; 'number'
# and 'pdfObj', like PDFObject and PDFExporter.genStream / _widthsStr, are
# left over from when Trelby wrote the PDF file structure itself, which
# reportlab does now.
class FontInfo:
    def __init__(self, name: str):
        self.name: str = name

        # font number (the name in the /F PDF command), or -1 if not used
        self.number: int = -1

        # PDFObject that contains the /Font object for this font, or None
        self.pdfObj: Optional[PDFObject] = None


# one object in a PDF file
class PDFObject:
    def __init__(self, nr: int, data: str = ""):
        # PDF object number
        self.nr: int = nr

        # all data between 'obj/endobj' tags, excluding newlines
        self.data: str = data

    # write object to canvas.
    def write(self, canvas: Canvas) -> None:
        code = "%d 0 obj\n" % self.nr
        code += self.data
        code += "\nendobj\n"
        canvas.addLiteral(code)


class PDFExporter:
    # see genWidths
    _widthsStr: Optional[str] = None

    def __init__(self, doc: "pml.Document"):
        self.doc: pml.Document = doc
        # fast lookup of font information
        self.fonts: Dict[int, FontInfo] = {
            pml.COURIER: FontInfo("Courier"),
            pml.COURIER | pml.BOLD: FontInfo("Courier-Bold"),
            pml.COURIER | pml.ITALIC: FontInfo("Courier-Oblique"),
            pml.COURIER | pml.BOLD | pml.ITALIC: FontInfo("Courier-BoldOblique"),
            pml.HELVETICA: FontInfo("Helvetica"),
            pml.HELVETICA | pml.BOLD: FontInfo("Helvetica-Bold"),
            pml.HELVETICA | pml.ITALIC: FontInfo("Helvetica-Oblique"),
            pml.HELVETICA | pml.BOLD | pml.ITALIC: FontInfo("Helvetica-BoldOblique"),
            pml.TIMES_ROMAN: FontInfo("Times-Roman"),
            pml.TIMES_ROMAN | pml.BOLD: FontInfo("Times-Bold"),
            pml.TIMES_ROMAN | pml.ITALIC: FontInfo("Times-Italic"),
            pml.TIMES_ROMAN | pml.BOLD | pml.ITALIC: FontInfo("Times-BoldItalic"),
        }

    # generate PDF document and return it as a string
    def generate(self) -> bytes:
        doc = self.doc
        canvas = Canvas(
            "",
            pdfVersion=(1, 5),
            pagesize=(self.mm2points(doc.w), self.mm2points(doc.h)),
            initialFontName=self.getFontForFlags(pml.NORMAL),
        )

        # set PDF info
        version = self.doc.version
        canvas.setCreator("Trelby " + version)
        canvas.setProducer("Trelby " + version)
        if self.doc.uniqueId:
            canvas.setKeywords(self.doc.uniqueId)

        numberOfPages: int = len(doc.pages)

        # draw pages
        for i in range(numberOfPages):
            pg = self.doc.pages[i]
            for op in pg.ops:
                op.pdfOp.draw(op, i, self, canvas)

            if i < numberOfPages - 1:
                canvas.showPage()

        if doc.showTOC:
            canvas.showOutline()

        return canvas.getpdfdata()

    # generate a stream object's contents. 's' is all data between
    # 'stream/endstream' tags, excluding newlines.
    def genStream(self, s, isFontStream=False) -> str:
        compress = False

        # embedded TrueType font program streams for some reason need a
        # Length1 entry that records the uncompressed length of the stream
        if isFontStream:
            lenStr = "/Length1 %d\n" % len(s)
        else:
            lenStr = ""

        filterStr = " "
        if compress:
            s = s.encode("zlib")
            filterStr = "/Filter /FlateDecode\n"

        return (
            "<< /Length %d\n%s%s>>\n"
            "stream\n"
            "%s\n"
            "endstream" % (len(s), lenStr, filterStr, s)
        )

    # get font name to use for given flags. also registers the font in reportlabs if it does not yet exist.
    def getFontForFlags(self, flags: int) -> str:
        # the "& 15" gets rid of the underline flag
        fontInfo = self.fonts.get(flags & 15)

        if not fontInfo:
            raise Exception(_("PDF.getfontNr: invalid flags {}").format(flags))

        # the "& 15" gets rid of the underline flag
        customFontInfo = self.doc.fonts.get(flags & 15)

        # user fonts can only be set for the Courier styles (keys 0 - 3),
        # so Helvetica and Times text always uses the standard fonts
        if not customFontInfo:
            return fontInfo.name

        # reportlab's font registry is global to the process, so a name is
        # only registered (and its file read) once; pointing the same name
        # at a different file has no effect until Trelby is restarted.
        if not customFontInfo.name in pdfmetrics.getRegisteredFontNames():
            if not customFontInfo.fontFileName:
                raise Exception(
                    _('Font name "{}" is not known and no font file name provided. Please provide a file name for this font in the settings or use the default font.').format(
                        customFontInfo.name
                    )
                )
            pdfmetrics.registerFont(
                TTFont(customFontInfo.name, customFontInfo.fontFileName)
            )

        return customFontInfo.name

    # get the name of CJK_FONT, registering it with reportlab if needed
    def getCJKFont(self) -> str:
        if CJK_FONT not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(UnicodeCIDFont(CJK_FONT))

        return CJK_FONT

    # escape string
    def escapeStr(self, s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # convert mm to points (1/72 inch).
    def mm2points(self, mm: float) -> float:
        # 2.834 = 72 / 25.4
        return mm * 2.83464567

    # convert x coordinate
    def x(self, x: float) -> float:
        return self.mm2points(x)

    # convert y coordinate. PML measures y down from the top of the page,
    # PDF up from the bottom.
    def y(self, y: float) -> float:
        return self.mm2points(self.doc.h - y)

    # convert xy, which is (x, y) pair, into PDF coordinates
    def xy(self, xy: Tuple[float, float]) -> Tuple[float, float]:
        x = self.x(xy[0])
        y = self.y(xy[1])

        return (x, y)
