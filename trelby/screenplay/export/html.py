# HTML export.

from lxml import etree

import trelby.textfmt as textfmt
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    NOTE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.export.text import getDualTextRows


# generate HTML output and return it as a string, optionally including
# notes.
def generateHtml(sp, includeNotes=True):
    ls = sp.lines

    # We save space by shorter class names in html.
    htmlMap = {
        ACTION: "ac",
        CHARACTER: "ch",
        DIALOGUE: "di",
        PAREN: "pa",
        SCENE: "sc",
        SHOT: "sh",
        TRANSITION: "tr",
        NOTE: "nt",
        ACTBREAK: "ab",
    }

    # html header for files
    htmlHeader = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Exported Screenplay</title>
<style type="text/css">
body {background: #ffffff; color: #000000; text-align: center;}
pre, p {font: 12px/14px Courier, "Courier New", monospace !important;}
pre {text-align: left !important; letter-spacing: 0 !important; margin-top: 0px !important; margin-bottom: 0px !important;}
p {text-align: center;}
.title, .footer {margin: 15px;}
.spcenter {margin: 0 auto; width: 500px;}
.sc, .ab {font-weight: bold !important;}
.nt {color: blue; font-style: italic !important;}
</style>
</head>
<body>
"""
    htmlFooter = """<p class = "footer">***<br>
Generated with <a href="http://www.trelby.org">Trelby</a>.</p>
</body>
</html>"""

    content = etree.Element("div")
    content.set("class", "spcenter")

    # title pages
    for page in sp.titles.pages:
        for ts in page:
            for s in ts.items:
                para = etree.SubElement(content, "p")
                para.set("class", "title")
                para.text = s

        para = etree.SubElement(content, "p")
        para.set("class", "title")
        para.text = "***"

    dualLines = sp.getDualLines(0, len(ls) - 1)

    for i in range(len(ls)):
        line = ls[i]
        dual = dualLines.get(i)

        if not includeNotes and (line.lt == NOTE):
            continue

        # dual dialogues are output whole at their first line
        if dual and (i != dual[1]):
            continue

        tcfg = sp.cfg.getType(line.lt)
        text = sp.getExportText(i)

        if text and sp.needsExtraParenIndent(i):
            text = " " + text

        text = " " * (tcfg.indent + int(sp.getCenterOffset(i))) + text

        # do we need space before this line?
        lineSpaces = sp.getSpacingBefore(i) // 10

        for num in range(lineSpaces):
            para = etree.SubElement(content, "pre")
            para.set("class", htmlMap[line.lt])
            para.text = " "

        if dual:
            for lt, s in getDualTextRows(sp, *dual[1:]):
                para = etree.SubElement(content, "pre")
                para.set("class", htmlMap[lt])
                para.text = s or " "

            continue

        # and now the line text, with bold / italic / underlined runs
        # in spans
        para = etree.SubElement(content, "pre")
        para.set("class", htmlMap[line.lt])

        # text has the indent in front of the line's own text
        pad = len(text) - len(line.text)
        fmt = "0" * pad + line.getFmt() if line.fmt else None
        prev = None

        for a, b, style in textfmt.runs(fmt, len(text)):
            part = str(text[a:b])

            if style:
                prev = etree.SubElement(para, "span")
                prev.set(
                    "style",
                    ";".join(
                        css
                        for bit, css in (
                            (textfmt.BOLD, "font-weight:bold"),
                            (textfmt.ITALIC, "font-style:italic"),
                            (textfmt.UNDERLINED, "text-decoration:underline"),
                        )
                        if style & bit
                    ),
                )
                prev.text = part
            elif prev is None:
                para.text = part
            else:
                prev.tail = part

        if not text:
            para.text = ""

    bodyText = etree.tostring(content, encoding="UTF-8", pretty_print=True).decode()

    return htmlHeader + bodyText + htmlFooter
