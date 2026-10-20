# Word (DOCX) export, written with the standard library: a zip of
# WordprocessingML parts. like the RTF export, each element type is a
# paragraph style with the script's indents, widths, spacing and text
# styles, so the document stays editable in Word, which does its own
# pagination. on top of that:
#
#  - the title pages are their own section, each string a frame at its
#    position on the page.
#  - the script is a second section whose page numbers start at 1, with
#    the headers on every page but its first and the footer (on the
#    first page too if the script says so). ${PAGE} and ${PAGES} become
#    Word's PAGE and SECTIONPAGES fields, so they follow Word's
#    pagination (without Trelby's locked page labels like "12A"), and
#    ${REVISION} is left out, as which page has what revision depends on
#    Trelby's pagination.
#  - lines that start a page in Trelby because of the script's settings
#    (acts, and scenes if they start new pages) start one in Word too.
#  - dual dialogue is a two-column table without borders.
#
# notes, revision marks and scene numbers aren't exported.

import io
import zipfile

import trelby.config as config
import trelby.error as error
import trelby.pdf.pml as pml
import trelby.screenplay.headers as headers
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.util as util
from trelby.screenplay.constants import (
    ACTION,
    CHARACTER,
    DIALOGUE,
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    LB_SPACE,
    PAREN,
    SCENE,
    TRANSITION,
)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"

WML = "application/vnd.openxmlformats-officedocument.wordprocessingml."

# the fonts title strings can be in, and Courier's (see fontinfo's
# Courier Prime, which Word shows as Courier New where it's not
# installed)
FONTS = {
    pml.COURIER: "Courier Prime",
    pml.TIMES_ROMAN: "Times New Roman",
    pml.HELVETICA: "Arial",
}

# element types kept on the same page as the element after them
KEEP_NEXT = (SCENE, CHARACTER, PAREN)

# how much wider than their text title strings' frames are, in mm
FRAME_SLACK = 2.0

# the gap between dual dialogue's columns, in characters, as in
# config.getDualIndentWidth
DUAL_GAP = 2


# generate a DOCX file and return it as bytes.
def generateDocx(sp):
    w = _Writer(sp)
    body = w.titleSection() + w.script() + w.scriptSectPr()

    parts = [
        ("[Content_Types].xml", w.contentTypes()),
        ("_rels/.rels", _RELS),
        ("word/document.xml", _xmlDoc("document", "<w:body>%s</w:body>" % body)),
        ("word/styles.xml", w.styles()),
        ("word/fontTable.xml", _fontTable()),
        ("word/settings.xml", _SETTINGS),
        ("word/_rels/document.xml.rels", w.documentRels()),
    ]

    for name, xml in w.headerParts:
        parts.append(("word/" + name, xml))

    out = io.BytesIO()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts:
            z.writestr(name, xml.encode("UTF-8"))

    return out.getvalue()


class _Writer:
    def __init__(self, sp):
        self.sp = sp
        self.cfg = sp.cfg

        fs = self.cfg.fontSize

        # a character's width and a line's height, in twips (Courier's
        # characters are 0.6 of the font size wide)
        self.charW = fs * 12
        self.lineH = fs * 20

        # the page's text width, in twips
        self.textW = round(
            util.mm2twips(
                self.cfg.paperWidth - self.cfg.marginLeft - self.cfg.marginRight
            )
        )

        # the header and footer parts: [(file name, xml)], and their
        # relationship ids by file name
        self.headerParts = []
        self.relIds = {}

    def twips(self, mm):
        return round(util.mm2twips(mm))

    # --- the title pages

    # return the title pages' paragraphs, ending with their section's
    # properties, or "" if there are none
    def titleSection(self):
        pages = self.sp.titles.pages

        if not pages:
            return ""

        s = ""

        for i, page in enumerate(pages):
            for ts in sorted(page, key=lambda ts: (ts.y, ts.x)):
                s += self.titleString(ts)

            # the page's frames are anchored to this paragraph, which
            # ends the page, or the section on the last one
            if i < (len(pages) - 1):
                s += '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
            else:
                cfg = self.cfg
                side = self.twips(min(cfg.marginLeft, cfg.marginRight))

                s += "<w:p><w:pPr><w:sectPr>%s%s</w:sectPr></w:pPr></w:p>" % (
                    self.pgSz(),
                    '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d"'
                    ' w:header="0" w:footer="0" w:gutter="0"/>'
                    % (
                        self.twips(cfg.marginTop),
                        side,
                        self.twips(cfg.marginBottom),
                        side,
                    ),
                )

        return s

    # return title string ts as paragraphs in a frame at its position
    def titleString(self, ts):
        lines = list(ts.items)

        if not lines:
            return ""

        y = self.twips(ts.y)

        # Word gives a frame without a width what's left of the column
        # right of it, so the others get their text's width, plus some
        # slack for Word's rounding
        style = ts.getStyle()
        width = max(util.getTextWidth(line, style, ts.size) for line in lines)
        width += FRAME_SLACK

        if ts.isCentered:
            frame = 'w:xAlign="center"'
            jc = "center"
        elif ts.isRightJustified:
            x = max(0.0, ts.x - width)
            frame = 'w:x="%d" w:w="%d"' % (
                self.twips(x),
                self.twips(ts.x) - self.twips(x),
            )
            jc = "right"
        else:
            frame = 'w:x="%d" w:w="%d"' % (self.twips(ts.x), self.twips(width))
            jc = "left"

        pPr = (
            '<w:pPr><w:framePr w:wrap="around" w:hAnchor="page"'
            ' w:vAnchor="page" %s w:y="%d"/>'
            '<w:spacing w:before="0" w:after="0" w:line="%d" w:lineRule="exact"/>'
            '<w:ind w:left="0" w:right="0"/><w:jc w:val="%s"/></w:pPr>'
            % (frame, y, ts.size * 20, jc)
        )

        font = FONTS.get(ts.font, FONTS[pml.COURIER])
        rPr = _rPr(
            font=font,
            size=ts.size,
            bold=ts.isBold,
            italic=ts.isItalic,
            underlined=ts.isUnderlined,
        )

        return "".join(
            "<w:p>%s%s</w:p>" % (pPr, _run(line, rPr) if line else "")
            for line in lines
        )

    # --- the script

    # return the script's paragraphs
    def script(self):
        sp = self.sp
        ls = sp.lines
        dualLines = sp.getDualLines(0, len(ls) - 1)
        pageStarts = getattr(sp, "pageStarts", set())

        s = ""
        i = 0

        while i < len(ls):
            dual = dualLines.get(i)

            if dual:
                col, first, right, last = dual
                s += self.dualTable(first, right, last)
                i = last + 1

                continue

            last = sp.getElemLastIndexFromLine(i)
            s += self.paragraph(i, last, (i == 0) or (i in pageStarts))
            i = last + 1

        if s.endswith("</w:tbl>"):
            s += "<w:p/>"

        return s

    # return the element on lines first - last as a paragraph, starting a
    # page if 'pageStart'. 'ind' is its (left, right) indents in twips
    # when it's not its style's.
    def paragraph(self, first, last, pageStart, ind=None):
        sp = self.sp
        ls = sp.lines

        pPr = '<w:pStyle w:val="%s"/>' % _styleId(ls[first].lt)

        # the script's first page starts with a section break, which needs
        # no page break. Word drops the space before an element at the top
        # of a page, as Trelby does, only where it breaks the page itself.
        if pageStart and first:
            pPr += "<w:pageBreakBefore/>"

        if pageStart:
            pPr += '<w:spacing w:before="0"/>'

        if ind:
            pPr += '<w:ind w:left="%d" w:right="%d"/>' % ind

        if sp.hasCenteredFlag(first):
            pPr += '<w:jc w:val="center"/>'

        isCaps = sp.cfg.getType(ls[first].lt).export.isCaps
        s = ""

        for i in range(first, last + 1):
            ln = ls[i]
            text = textutil.upper(ln.text) if isCaps else ln.text

            for a, b, style in textfmt.runs(ln.fmt, len(text)):
                s += _run(
                    text[a:b],
                    _rPr(
                        bold=bool(style & textfmt.BOLD),
                        italic=bool(style & textfmt.ITALIC),
                        underlined=bool(style & textfmt.UNDERLINED),
                    ),
                )

            lb = ln.lb

            if lb in (LB_SPACE, LB_NONE):
                if config.lb2str(lb):
                    s += _run(config.lb2str(lb))
            elif lb == LB_FORCED:
                s += "<w:r><w:br/></w:r>"
            elif lb != LB_LAST:
                raise error.MiscError(
                    _("Unknown line break style {} in generateDocx").format(lb)
                )

        return "<w:p><w:pPr>%s</w:pPr>%s</w:p>" % (pPr, s)

    # return the dual dialogue on lines first - last, its right speech
    # starting at line 'right', as a table of two columns at the action's
    # indent, each element indented in its column as in the PDF
    def dualTable(self, first, right, last):
        sp = self.sp
        cfg = self.cfg
        cw = self.charW

        action = cfg.getType(ACTION)
        colWidth = (action.width - DUAL_GAP) // 2

        # the left column includes the gap
        widths = [(colWidth + DUAL_GAP) * cw, colWidth * cw]

        cells = []

        for col, (start, end) in enumerate(((first, right - 1), (right, last)), 1):
            colX = action.indent + (0 if col == 1 else colWidth + DUAL_GAP)
            cellW = widths[col - 1]
            s = ""
            i = start

            while i <= end:
                elemLast = sp.getElemLastIndexFromLine(i)
                x, width = cfg.getDualIndentWidth(sp.lines[i].lt, col)
                left = (x - colX) * cw
                ind = (left, max(0, cellW - left - width * cw - cw // 2))

                s += self.paragraph(i, elemLast, False, ind)
                i = elemLast + 1

            cells.append(
                '<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/></w:tcPr>%s</w:tc>'
                % (cellW, s)
            )

        # (two dual dialogues in a row become one table of two rows)
        return (
            "<w:tbl><w:tblPr>"
            '<w:tblW w:w="%d" w:type="dxa"/>'
            '<w:tblInd w:w="%d" w:type="dxa"/>'
            '<w:tblLayout w:type="fixed"/>'
            '<w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
            '<w:left w:w="0" w:type="dxa"/>'
            '<w:bottom w:w="0" w:type="dxa"/>'
            '<w:right w:w="0" w:type="dxa"/></w:tblCellMar>'
            '<w:tblLook w:val="0000"/>'
            "</w:tblPr>"
            '<w:tblGrid><w:gridCol w:w="%d"/><w:gridCol w:w="%d"/></w:tblGrid>'
            '<w:tr><w:trPr><w:cantSplit/></w:trPr>%s</w:tr></w:tbl>'
            % (
                sum(widths),
                action.indent * cw,
                widths[0],
                widths[1],
                "".join(cells),
            )
        )

    # return the script section's properties, with its headers and footer
    def scriptSectPr(self):
        cfg = self.cfg
        refs = ""

        hdr = self.headerXml()
        ftr = self.footerXml()

        if hdr:
            refs += self.addPart(
                "header", "default", "header1.xml", _hdrFtr("hdr", hdr)
            )

        if ftr:
            refs += self.addPart(
                "footer", "default", "footer1.xml", _hdrFtr("ftr", ftr)
            )

        # the first page never has headers, and has the footer only if
        # the script says so. a first page header or footer left out is
        # empty, as the title pages have none to inherit, whereas an empty
        # one would take a line.
        if ftr and self.sp.footer.showOnFirstPage:
            refs += self.addPart("footer", "first", "footer2.xml", _hdrFtr("ftr", ftr))

        chH = util.getTextHeight(cfg.fontSize)
        footerY = headers.Footer.getY(cfg)

        return (
            "<w:sectPr>%s%s"
            '<w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d"'
            ' w:header="%d" w:footer="%d" w:gutter="0"/>'
            '<w:pgNumType w:start="1"/>%s</w:sectPr>'
            % (
                refs,
                self.pgSz(),
                self.twips(cfg.marginTop),
                self.twips(cfg.marginRight),
                self.twips(cfg.marginBottom),
                self.twips(cfg.marginLeft),
                self.twips(cfg.marginTop),
                self.twips(max(0, cfg.paperHeight - footerY - chH)),
                "<w:titlePg/>" if (hdr or ftr) else "",
            )
        )

    def pgSz(self):
        return '<w:pgSz w:w="%d" w:h="%d"/>' % (
            self.twips(self.cfg.paperWidth),
            self.twips(self.cfg.paperHeight),
        )

    # add a header or footer part, returning its reference for the
    # section
    def addPart(self, kind, type, name, xml):
        rid = "rId%d" % (len(self.headerParts) + 10)
        self.headerParts.append((name, xml))
        self.relIds[name] = (rid, kind)

        return '<w:%sReference w:type="%s" r:id="%s"/>' % (kind, type, rid)

    # return the headers' paragraphs, or "" if there are none
    def headerXml(self):
        hdrs = self.sp.headers

        if not hdrs.hdrs:
            return ""

        lines = []

        for nr in range(1, hdrs.getNrOfLines() + 1):
            parts = [
                (h.text, h.align, h.isBold, h.isItalic, h.isUnderlined)
                for h in hdrs.hdrs
                if h.line == nr
            ]
            lines.append(self.alignedLine(parts))

        return "".join(lines)

    # return the footer's paragraphs, or "" if it's empty
    def footerXml(self):
        ftr = self.sp.footer

        if ftr.isEmpty():
            return ""

        parts = [
            (getattr(ftr, attr), align, False, False, False)
            for attr, align, key in ftr.PARTS
            if getattr(ftr, attr)
        ]

        return self.alignedLine(parts)

    # return a paragraph with parts (text, alignment, bold, italic,
    # underlined) at the left margin, the middle and the right margin,
    # with tab stops between them
    def alignedLine(self, parts):
        rank = {util.ALIGN_LEFT: 0, util.ALIGN_CENTER: 1, util.ALIGN_RIGHT: 2}
        tvars = headers.titleVars(self.sp.titles)
        s = ""
        pos = 0

        for text, align, bold, italic, underlined in sorted(
            parts, key=lambda p: rank[p[1]]
        ):
            # tab to the part's stop, unless the line is already past it
            while pos < rank[align]:
                s += "<w:r><w:tab/></w:r>"
                pos += 1

            s += self.fieldRuns(
                text, tvars, _rPr(bold=bold, italic=italic, underlined=underlined)
            )

        return (
            "<w:p><w:pPr>"
            '<w:tabs><w:tab w:val="center" w:pos="%d"/>'
            '<w:tab w:val="right" w:pos="%d"/></w:tabs>'
            '<w:spacing w:before="0" w:after="0" w:line="%d" w:lineRule="exact"/>'
            '<w:ind w:left="0" w:right="0"/>'
            "</w:pPr>%s</w:p>" % (self.textW // 2, self.textW, self.lineH, s)
        )

    # return the runs for header or footer text, with the title page
    # variables filled in and ${PAGE} / ${PAGES} as fields
    def fieldRuns(self, text, tvars, rPr):
        text = headers.expand(text, tvars).replace("${REVISION}", "")
        fields = {"${PAGE}": "PAGE", "${PAGES}": "SECTIONPAGES"}
        s = ""

        while text:
            at = [(text.find(k), k) for k in fields if text.find(k) != -1]

            if not at:
                s += _run(text, rPr)

                break

            pos, key = min(at)

            if pos:
                s += _run(text[:pos], rPr)

            s += (
                '<w:r>%s<w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r>%s<w:instrText xml:space="preserve"> %s </w:instrText></w:r>'
                '<w:r>%s<w:fldChar w:fldCharType="separate"/></w:r>'
                "%s"
                '<w:r>%s<w:fldChar w:fldCharType="end"/></w:r>'
                % (rPr, rPr, fields[key], rPr, _run("1", rPr), rPr)
            )
            text = text[pos + len(key) :]

        return s

    # --- the other parts

    def styles(self):
        cfg = self.cfg
        fs = cfg.fontSize
        cw = self.charW
        s = ""

        s += (
            "<w:docDefaults><w:rPrDefault>%s</w:rPrDefault>"
            "<w:pPrDefault><w:pPr>"
            '<w:spacing w:before="0" w:after="0" w:line="%d" w:lineRule="exact"/>'
            "</w:pPr></w:pPrDefault></w:docDefaults>"
            % (_rPr(font=FONTS[pml.COURIER], size=fs), self.lineH)
        )

        s += (
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
            '<w:name w:val="Normal"/><w:qFormat/></w:style>'
        )

        for ti in config.getTIs():
            t = cfg.getType(ti.lt)
            tt = t.export

            left = t.indent * cw
            right = self.textW - (t.indent + t.width) * cw - cw // 2

            # beforeSpacing and intraSpacing are in tenths of a line
            pPr = (
                "%s"
                '<w:spacing w:before="%d" w:after="0" w:line="%d"'
                ' w:lineRule="exact"/>'
                '<w:ind w:left="%d" w:right="%d"/>'
                % (
                    "<w:keepNext/>" if ti.lt in KEEP_NEXT else "",
                    t.beforeSpacing * self.lineH // 10,
                    self.lineH + t.intraSpacing * self.lineH // 10,
                    left,
                    right,
                )
            )

            s += (
                '<w:style w:type="paragraph" w:customStyle="1" w:styleId="%s">'
                '<w:name w:val="%s"/><w:basedOn w:val="Normal"/>'
                '<w:next w:val="%s"/><w:qFormat/>'
                "<w:pPr>%s</w:pPr>%s</w:style>"
                % (
                    _styleId(ti.lt),
                    _escape(ti.name),
                    _styleId(_nextType(ti.lt)),
                    pPr,
                    _rPr(
                        bold=tt.isBold,
                        italic=tt.isItalic,
                        underlined=tt.isUnderlined,
                    ),
                )
            )

        return _xmlDoc("styles", s)

    def contentTypes(self):
        s = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types">'
            '<Default Extension="rels" ContentType="application/'
            'vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml"'
            ' ContentType="%sdocument.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="%sstyles+xml"/>'
            '<Override PartName="/word/fontTable.xml"'
            ' ContentType="%sfontTable+xml"/>'
            '<Override PartName="/word/settings.xml"'
            ' ContentType="%ssettings+xml"/>' % (WML, WML, WML, WML)
        )

        for name, xml in self.headerParts:
            kind = self.relIds[name][1]
            s += '<Override PartName="/word/%s" ContentType="%s%s+xml"/>' % (
                name,
                WML,
                kind,
            )

        return s + "</Types>"

    def documentRels(self):
        rels = [
            ("rId1", "styles", "styles.xml"),
            ("rId2", "fontTable", "fontTable.xml"),
            ("rId3", "settings", "settings.xml"),
        ]

        for name, xml in self.headerParts:
            rid, kind = self.relIds[name]
            rels.append((rid, kind, name))

        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="%s">%s</Relationships>'
            % (
                REL_NS,
                "".join(
                    '<Relationship Id="%s" Type="%s%s" Target="%s"/>'
                    % (rid, DOC_REL, kind, target)
                    for rid, kind, target in rels
                ),
            )
        )


# the element type that usually follows type lt, for the styles' "next"
def _nextType(lt):
    return {
        SCENE: ACTION,
        CHARACTER: DIALOGUE,
        PAREN: DIALOGUE,
        DIALOGUE: CHARACTER,
        TRANSITION: SCENE,
    }.get(lt, ACTION)


def _styleId(lt):
    return config.lt2ti(lt).name.replace(" ", "")


# return run properties with the given font, size (points) and styles
def _rPr(font=None, size=None, bold=False, italic=False, underlined=False):
    s = ""

    if font:
        s += (
            '<w:rFonts w:ascii="%s" w:hAnsi="%s" w:cs="%s" w:eastAsia="%s"/>'
            % ((font,) * 4)
        )

    if bold:
        s += "<w:b/>"

    if italic:
        s += "<w:i/>"

    if size:
        s += '<w:sz w:val="%d"/><w:szCs w:val="%d"/>' % (size * 2, size * 2)

    if underlined:
        s += '<w:u w:val="single"/>'

    return "<w:rPr>%s</w:rPr>" % s if s else ""


# return a run of text
def _run(text, rPr=""):
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rPr, _escape(text))


# return text escaped for XML, without the control characters XML can't
# have
def _escape(s):
    s = "".join(ch for ch in s if (ch >= " ") or (ch in "\t\n\r"))

    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _xmlDoc(root, content):
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:%s xmlns:w="%s" xmlns:r="%s">%s</w:%s>' % (root, W_NS, R_NS, content, root)
    )


def _hdrFtr(root, content):
    return _xmlDoc(root, content)


def _fontTable():
    s = ""

    for name, family, pitch, alt in (
        (FONTS[pml.COURIER], "modern", "fixed", "Courier New"),
        (FONTS[pml.TIMES_ROMAN], "roman", "variable", None),
        (FONTS[pml.HELVETICA], "swiss", "variable", None),
    ):
        s += '<w:font w:name="%s">%s<w:family w:val="%s"/><w:pitch w:val="%s"/>' % (
            name,
            '<w:altName w:val="%s"/>' % alt if alt else "",
            family,
            pitch,
        )
        s += "</w:font>"

    return _xmlDoc("fonts", s)


_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="%s">'
    '<Relationship Id="rId1" Type="%sofficeDocument" Target="word/document.xml"/>'
    "</Relationships>" % (REL_NS, DOC_REL)
)

_SETTINGS = _xmlDoc(
    "settings",
    '<w:defaultTabStop w:val="720"/><w:compat>'
    '<w:compatSetting w:name="compatibilityMode"'
    ' w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>'
    "</w:compat>",
)
