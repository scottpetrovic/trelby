import functools
from typing import List

import wx

import trelby.checkboxitem as checkboxitem
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.reportwindow as reportwindow
import trelby.screenplay as screenplay
import trelby.textutil as textutil
import trelby.util as util


# colors (r, g, b, each 0-1) for the page content bars and their legend.
# the speaking bars in the chart use the dialogue color.
OTHER_COLOR = (1.0, 1.0, 1.0)
CHARACTER_COLOR = (0.106, 0.686, 0.478)
DIALOGUE_COLOR = (0.922, 0.408, 0.204)
ACTION_COLOR = (0.165, 0.471, 0.839)

# background color for every other row of the chart
ROW_COLOR = (0.933, 0.957, 0.988)


# return a pml.PDFOp that sets the fill color to 'color', an (r, g, b) tuple
def fillColor(color):
    return pml.PDFOp("%.3f %.3f %.3f rg" % color)


def genDialogueChart(mainFrame, sp, scriptName):
    reportwindow.show(DialogueChartFrame, mainFrame, sp, scriptName)


class DialogueChartFrame(reportwindow.ReportFrame):
    def __init__(self, parent, sp, scriptName):
        # (label, compare function) for each sort order
        self.sorts = [
            (_("Sorted by: First appearance"), cmpFirst),
            (_("Sorted by: Last appearance"), cmpLast),
            (_("Sorted by: Number of lines spoken"), cmpCount),
            (_("Sorted by: Name"), cmpName),
        ]

        self.allChars = True
        self.doc = None

        reportwindow.ReportFrame.__init__(self, parent, sp, scriptName, (1100, 800))

    def getName(self):
        return _("Dialogue Chart")

    def makeReport(self):
        self.chart = DialogueChart(self.sp, 1 if self.allChars else 10)

    def createControls(self, panel):
        self.allCharsCb = wx.CheckBox(panel, -1, _("Characters with < 10 lines"))
        self.allCharsCb.SetValue(self.allChars)
        self.Bind(wx.EVT_CHECKBOX, self.OnAllChars, id=self.allCharsCb.GetId())
        self.optionsSizer.Add(
            self.allCharsCb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.sortChoice = wx.Choice(panel, -1, choices=[s[0] for s in self.sorts])
        self.sortChoice.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, lambda e: self.update(), id=self.sortChoice.GetId())
        self.optionsSizer.Add(self.sortChoice, 0, wx.ALIGN_CENTER_VERTICAL)

        self.view = reportwindow.PageView(panel)
        self.contentSizer.Add(self.view, 1, wx.EXPAND)

    def OnAllChars(self, event):
        self.allChars = self.allCharsCb.GetValue()
        self.makeReport()
        self.update()

    def updateView(self):
        if not self.chart.cinfo:
            self.doc = None

            if self.allChars:
                msg = _("No characters speaking found.")
            else:
                msg = _("No characters with 10 or more lines found.")

            self.view.setDoc(None, msg)
        else:
            label, func = self.sorts[self.sortChoice.GetSelection()]
            self.doc = self.chart.generateDoc([checkboxitem.CheckBoxItem(label, cdata=func)])
            self.view.setDoc(self.doc)

        self.hasContents = self.doc is not None

    def getPDF(self):
        return pdf.generate(self.doc)


class DialogueChart:
    def __init__(self, sp, minLines):

        self.sp = sp

        ls = sp.lines

        # PageInfo's for each page, 0-indexed. (sp.pages has a dummy
        # entry at index 0, and sp.line2page is 1-based.)
        self.pages = []

        for i in range(len(sp.pages) - 1):
            self.pages.append(PageInfo())

        # map of CharInfo objects. key = name, value = CharInfo.
        tmpCinfo = {}

        # the speaker of the dialogue lines that follow: set by the last
        # line of a character element, kept over parentheticals, and
        # reset by any other element type
        name = "UNKNOWN"

        for i in range(len(ls)):
            pgNr = sp.line2page(i) - 1
            pi = self.pages[pgNr]
            line = ls[i]

            pi.addLine(line.lt)

            if (line.lt == screenplay.CHARACTER) and (line.lb == screenplay.LB_LAST):
                name = textutil.upper(line.text)

            elif line.lt == screenplay.DIALOGUE:
                pi.addLineToSpeaker(name)

                ci = tmpCinfo.get(name)

                if ci:
                    ci.addLine(pgNr)
                else:
                    tmpCinfo[name] = CharInfo(name, pgNr)

            elif line.lt != screenplay.PAREN:
                name = "UNKNOWN"

        # CharInfo's.
        self.cinfo = []
        for v in list(tmpCinfo.values()):
            if v.lineCnt >= minLines:
                self.cinfo.append(v)

        # start Y of page markers
        self.pageY = 20.0

        # where dialogue density bars start and how tall they are
        self.barY = 30.0
        self.barHeight = 15.0

        # chart Y pos
        self.chartY = 50.0

        # how much to leave empty on each side (mm)
        self.margin = 10.0

        # try point sizes 10,9,8,7,6 until all characters fit on the page
        # (if 6 is still too big, too bad)
        #
        # the chart is printed in landscape (see generateDoc), so the
        # page's height is the paper's width, and vice versa for chartWidth
        # below
        size = 10
        while 1:
            # character font size in points
            self.charFs = size

            # how many mm in Y direction for each character
            self.charY = util.getTextHeight(self.charFs)

            # height of chart
            self.chartHeight = len(self.cinfo) * self.charY

            if size <= 6:
                break

            if (self.chartY + self.chartHeight) <= (sp.cfg.paperWidth - self.margin):
                break

            size -= 1

        # calculate maximum length of character name, and start position
        # of chart from that

        maxLen = 0
        for ci in self.cinfo:
            maxLen = max(maxLen, len(ci.name))
        maxLen = max(10, maxLen)

        charX = util.getTextWidth(" ", pml.COURIER, self.charFs)

        # chart X pos
        self.chartX = self.margin + maxLen * charX + 3

        # width of chart
        self.chartWidth = sp.cfg.paperHeight - self.chartX - self.margin

        # page contents bar legends' size and position
        self.legendWidth = 23.0
        self.legendHeight = 23.0
        self.legendX = self.margin + 2.0
        self.legendY = self.barY + self.barHeight - self.legendHeight

        # margin from legend border to first item
        self.legendMargin = 2.0

        # spacing from one legend item to next
        self.legendSpacing = 5.0

        # spacing from one legend item to next
        self.legendSize = 4.0

    # return a pml.Document with a page for each selected sort order in
    # 'cbil'.
    def generateDoc(self, cbil: List[checkboxitem.CheckBoxItem]) -> pml.Document:
        doc = pml.Document(self.sp.cfg.paperHeight, self.sp.cfg.paperWidth)

        for it in cbil:
            if it.selected:
                self.cinfo = sorted(self.cinfo, key=functools.cmp_to_key(it.cdata))
                doc.add(self.generatePage(it.text, doc))

        return doc

    def generate(self, cbil: List[checkboxitem.CheckBoxItem]) -> bytes:
        return pdf.generate(self.generateDoc(cbil))

    def generatePage(self, title, doc):
        pg = pml.Page(doc)

        pg.add(
            pml.TextOp(
                title,
                doc.w / 2.0,
                self.margin,
                18,
                pml.BOLD | pml.ITALIC | pml.UNDERLINED,
                util.ALIGN_CENTER,
            )
        )

        # the x axis is the script's pages, each getting an equal-width
        # column of the chart. colors are set with pml.PDFOps, which stay in
        # effect until changed, so each colored part resets to black after.
        pageCnt = len(self.pages)
        mmPerPage = max(0.1, self.chartWidth / pageCnt)

        pg.add(pml.TextOp("Page:", self.chartX - 1.0, self.pageY - 5.0, 10))

        # draw backround for every other row. this needs to be done before
        # drawing the grid.
        for i in range(len(self.cinfo)):
            y = self.chartY + i * self.charY

            if (i % 2) == 1:
                pg.add(fillColor(ROW_COLOR))
                pg.add(pml.RectOp(self.chartX, y, self.chartWidth, self.charY))
                pg.add(pml.PDFOp("0.0 g"))

        # line width to use
        lw = 0.25

        pg.add(pml.PDFOp("0.5 G"))

        # dashed pattern
        pg.add(pml.PDFOp("[2 2] 0 d"))

        # draw grid and page markers
        for i in range(pageCnt):
            if (i == 0) or ((i + 1) % 10) == 0:
                x = self.chartX + i * mmPerPage
                pg.add(
                    pml.TextOp(
                        self.sp.getPageLabel(i + 1),
                        x,
                        self.pageY,
                        10,
                        align=util.ALIGN_CENTER,
                    )
                )
                if i != 0:
                    pg.add(pml.genLine(x, self.chartY, 0, self.chartHeight, lw))

        pg.add(
            pml.RectOp(
                self.chartX,
                self.chartY,
                self.chartWidth,
                self.chartHeight,
                pml.NO_FILL,
                lw,
            )
        )

        pg.add(pml.PDFOp("0.0 G"))

        # restore normal line pattern
        pg.add(pml.PDFOp("[] 0 d"))

        # legend for page content bars
        pg.add(
            pml.RectOp(
                self.legendX,
                self.legendY,
                self.legendWidth,
                self.legendHeight,
                pml.NO_FILL,
                lw,
            )
        )

        self.drawLegend(pg, 0, OTHER_COLOR, "Other", lw)
        self.drawLegend(pg, 1, CHARACTER_COLOR, "Character", lw)
        self.drawLegend(pg, 2, DIALOGUE_COLOR, "Dialogue", lw)
        self.drawLegend(pg, 3, ACTION_COLOR, "Action", lw)

        # page content bars: each page's share of action, dialogue and
        # character lines, stacked up from the bottom of the bar. the rest
        # (other line types) is left white.
        for i in range(pageCnt):
            x = self.chartX + i * mmPerPage
            y = self.barY + self.barHeight
            pi = self.pages[i]
            tlc = pi.getTotalLineCount()

            pg.add(fillColor(ACTION_COLOR))
            pct = util.safeDivInt(pi.getLineCount(screenplay.ACTION), tlc)
            barH = self.barHeight * pct
            pg.add(pml.RectOp(x, y - barH, mmPerPage, barH))
            y -= barH

            pg.add(fillColor(DIALOGUE_COLOR))
            pct = util.safeDivInt(pi.getLineCount(screenplay.DIALOGUE), tlc)
            barH = self.barHeight * pct
            pg.add(pml.RectOp(x, y - barH, mmPerPage, barH))
            y -= barH

            pg.add(fillColor(CHARACTER_COLOR))
            pct = util.safeDivInt(pi.getLineCount(screenplay.CHARACTER), tlc)
            barH = self.barHeight * pct
            pg.add(pml.RectOp(x, y - barH, mmPerPage, barH))
            y -= barH

        pg.add(pml.PDFOp("0.0 g"))

        # rectangle around page content bars
        pg.add(
            pml.RectOp(
                self.chartX, self.barY, self.chartWidth, self.barHeight, pml.NO_FILL, lw
            )
        )

        for i in range(len(self.cinfo)):
            y = self.chartY + i * self.charY
            ci = self.cinfo[i]

            pg.add(
                pml.TextOp(
                    ci.name,
                    self.margin,
                    y + self.charY / 2.0,
                    self.charFs,
                    valign=util.VALIGN_CENTER,
                )
            )

            pg.add(fillColor(DIALOGUE_COLOR))

            # a bar for each page the character speaks on, as tall (within
            # the row, centered) as their share of a full page of lines
            for i in range(pageCnt):
                pi = self.pages[i]
                cnt = pi.getSpeakerLineCount(ci.name)

                if cnt > 0:
                    h = self.charY * (float(cnt) / self.sp.cfg.linesOnPage)

                    pg.add(
                        pml.RectOp(
                            self.chartX + i * mmPerPage,
                            y + (self.charY - h) / 2.0,
                            mmPerPage,
                            h,
                        )
                    )

            pg.add(pml.PDFOp("0.0 g"))

        return pg

    # draw a single legend for page content bars
    def drawLegend(self, pg, pos, color, name, lw):
        x = self.legendX + self.legendMargin
        y = self.legendY + self.legendMargin + pos * self.legendSpacing

        pg.add(fillColor(color))

        pg.add(pml.RectOp(x, y, self.legendSize, self.legendSize, pml.STROKE_FILL, lw))

        pg.add(pml.PDFOp("0.0 g"))

        pg.add(pml.TextOp(name, x + self.legendSize + 2.0, y, 6))


# keeps track of information for one page
class PageInfo:
    def __init__(self):
        # how many lines of each type this page contains. key = line type,
        # value = int. note that if value would be 0, this doesn't have
        # the key at all, so use the helper functions below.
        self.lineCounts = {}

        # total line count
        self.totalLineCount = -1

        # how many lines each character speaks on this page. key =
        # character name, value = int. note that if someone doesn't speak
        # they have no entry.
        self.speakers = {}

    # add one line of given type.
    def addLine(self, lt):
        self.lineCounts[lt] = self.getLineCount(lt) + 1

    # get total number of lines.
    def getTotalLineCount(self):
        if self.totalLineCount == -1:
            self.totalLineCount = sum(iter(self.lineCounts.values()), 0)

        return self.totalLineCount

    # get number of lines of given type.
    def getLineCount(self, lt):
        return self.lineCounts.get(lt, 0)

    # add one dialogue line for given speaker.
    def addLineToSpeaker(self, name):
        self.speakers[name] = self.getSpeakerLineCount(name) + 1

    # get number of lines of dialogue for given character.
    def getSpeakerLineCount(self, name):
        return self.speakers.get(name, 0)


# keeps track of each character's dialogue lines.
class CharInfo:
    def __init__(self, name, firstPage):
        self.name = name
        self.firstPage = firstPage
        self.lastPage = firstPage
        self.lineCnt = 1

    # add a line at given page.
    def addLine(self, page):
        self.lastPage = page
        self.lineCnt += 1


def cmpfunc(a, b):
    return (a > b) - (a < b)


def cmpCount(c1, c2):
    ret = cmpfunc(c2.lineCnt, c1.lineCnt)

    if ret != 0:
        return ret
    else:
        return cmpFirst(c1, c2)


def cmpCountThenName(c1, c2):
    ret = cmpfunc(c2.lineCnt, c1.lineCnt)

    if ret != 0:
        return ret
    else:
        return cmpName(c1, c2)


def cmpFirst(c1, c2):
    ret = cmpfunc(c1.firstPage, c2.firstPage)

    if ret != 0:
        return ret
    else:
        return cmpLastRev(c1, c2)


def cmpLast(c1, c2):
    ret = cmpfunc(c1.lastPage, c2.lastPage)

    if ret != 0:
        return ret
    else:
        return cmpName(c1, c2)


def cmpLastRev(c1, c2):
    ret = cmpfunc(c2.lastPage, c1.lastPage)

    if ret != 0:
        return ret
    else:
        return cmpCountThenName(c1, c2)


def cmpName(c1, c2):
    return cmpfunc(c1.name, c2.name)
