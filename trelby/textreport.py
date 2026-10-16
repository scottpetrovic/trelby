# Common code for the text-based reports (scene, location, character and
# script reports). Each report lays out its contents once, in format(),
# against the TextFormatter interface; that is then rendered either to a
# PDF (pml.TextFormatter) or to HTML for showing in a report window
# (HtmlFormatter).

import html
from typing import List, Optional

import trelby.pdf as pdf
import trelby.pml as pml
import trelby.util as util


class TextReport:
    # page margin (mm) and default font size used for the report
    margin = 15.0
    fontSize = 12

    # lay out the report's contents into 'tf', a pml.TextFormatter or an
    # HtmlFormatter.
    def format(self, tf) -> None:
        raise NotImplementedError

    def generate(self) -> bytes:
        tf = pml.TextFormatter(
            self.sp.cfg.paperWidth, self.sp.cfg.paperHeight, self.margin, self.fontSize
        )
        self.format(tf)

        return pdf.generate(tf.doc)

    # return the report as an HTML fragment (no <html>/<body>), or "" if
    # it has no contents.
    def generateHtml(self) -> str:
        hf = HtmlFormatter(self.margin, self.fontSize)
        self.format(hf)

        return hf.getHtml()


# the same interface as pml.TextFormatter, but produces HTML suitable for
# wx.html.HtmlWindow. text is set in a fixed-width font, with spaces kept,
# so that the column alignment the reports use is preserved. there are no
# pages, and wrapped text is left for the window to wrap.
class HtmlFormatter:
    def __init__(self, margin: float, fontSize: int):
        self.margin: float = margin
        self.fontSize: int = fontSize

        self.parts: List[str] = []

        # vertical space (mm) to add before the next text. consecutive
        # spaces are merged, as the blank lines would otherwise add up.
        self.space: float = 0.0

    # add blank vertical space, unless we're at the top
    def addSpace(self, mm: float) -> None:
        if self.parts:
            self.space = max(self.space, mm)

    # add any pending space. wx.html can't do exact heights, so this is a
    # blank line in a font size that roughly matches.
    def flushSpace(self) -> None:
        if self.space >= 2.0:
            size = "-2" if self.space < 4.0 else "-1"
            self.parts.append('<font size="%s">&nbsp;<br></font>' % size)

        self.space = 0.0

    def addText(
        self,
        text: str,
        x: Optional[float] = None,
        fs: Optional[int] = None,
        style: int = pml.NORMAL,
    ) -> None:
        if fs is None:
            fs = self.fontSize

        # turn an x position past the margin into leading spaces
        if x is not None:
            spaceW = util.getTextWidth(" ", pml.COURIER, fs)
            text = " " * max(0, round((x - self.margin) / spaceW)) + text

        s = html.escape(text).replace(" ", "&nbsp;")
        self.flushSpace()
        self.parts.append(self.styled(s, fs, style) + "<br>")

    def addWrappedText(self, text: str, indent: str) -> None:
        self.flushSpace()
        self.parts.append(html.escape(text) + "<br>")

    def styled(self, s: str, fs: int, style: int) -> str:
        if style & pml.BOLD:
            s = "<b>%s</b>" % s

        if style & pml.ITALIC:
            s = "<i>%s</i>" % s

        if style & pml.UNDERLINED:
            s = "<u>%s</u>" % s

        if fs > self.fontSize:
            s = '<font size="+1">%s</font>' % s
        elif fs < self.fontSize:
            s = '<font size="-1">%s</font>' % s

        return s

    def getHtml(self) -> str:
        if not self.parts:
            return ""

        return "<tt>%s</tt>" % "".join(self.parts)
