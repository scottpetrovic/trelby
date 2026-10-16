# The dialogue chart: who speaks on which page, one row per character,
# with a bar above showing each page's mix of action, dialogue and
# character lines. DialogueChart collects the data from a script, and
# generateDoc lays it out as a landscape pml.Document. Its window is
# reports.DialogueChartFrame.

from typing import List, Optional

import trelby.pml as pml
import trelby.screenplay as screenplay
import trelby.screenplay.speeches as speeches
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


# the orders the characters can be sorted in: (name, label function, sort
# key for a CharInfo). ties are broken down to the name, which is unique.
SORTS = [
    (
        "first",
        lambda: _("Sorted by: First appearance"),
        lambda ci: (ci.firstPage, -ci.lastPage, -ci.lineCnt, ci.name),
    ),
    (
        "last",
        lambda: _("Sorted by: Last appearance"),
        lambda ci: (ci.lastPage, ci.name),
    ),
    (
        "count",
        lambda: _("Sorted by: Number of lines spoken"),
        lambda ci: (-ci.lineCnt, ci.firstPage, -ci.lastPage, ci.name),
    ),
    (
        "name",
        lambda: _("Sorted by: Name"),
        lambda ci: ci.name,
    ),
]

_sorts = {name: (label, key) for name, label, key in SORTS}


# the chart's data: what's on each page, and who speaks where
class DialogueChart:
    def __init__(self, sp):
        ls = sp.lines

        # PageInfo's for each page, 0-indexed. (sp.pages has a dummy
        # entry at index 0, and sp.line2page is 1-based.)
        self.pages = [PageInfo(sp.getPageLabel(i + 1)) for i in range(len(sp.pages) - 1)]

        for i in range(len(ls)):
            self.pages[sp.line2page(i) - 1].addLine(ls[i].lt)

        # key = name, value = CharInfo
        chars = {}

        # who speaks is worked out in screenplay/speeches.py
        for speech in speeches.iterSpeeches(sp):
            name = speech.name

            for i in speech.dialogue:
                pgNr = sp.line2page(i) - 1
                self.pages[pgNr].addLineToSpeaker(name)

                ci = chars.get(name)

                if ci:
                    ci.addLine(pgNr)
                else:
                    chars[name] = CharInfo(name, pgNr)

        # CharInfo's, in order of first appearance
        self.cinfo = list(chars.values())

    # return the CharInfos of characters with at least 'minLines' lines
    # of dialogue, sorted in the order named 'sort' (see SORTS)
    def getChars(self, minLines=1, sort="first"):
        chars = [ci for ci in self.cinfo if ci.lineCnt >= minLines]

        return sorted(chars, key=_sorts[sort][1])


# return a pml.Document with a page for each sort order named in 'sorts'
# (see SORTS), showing the characters with at least 'minLines' lines, or
# None if there are none. cfg is the script's config, for the paper size
# and lines per page.
def generateDoc(chart, cfg, sorts, minLines=1) -> Optional[pml.Document]:
    if not chart.getChars(minLines):
        return None

    doc = pml.Document(cfg.paperHeight, cfg.paperWidth)

    for name in sorts:
        label, key = _sorts[name]
        chars = chart.getChars(minLines, name)
        doc.add(ChartLayout(cfg, chars).generatePage(label(), chart.pages, chars, doc))

    return doc


# the positions and sizes (mm) of the chart's parts, for the given
# config and characters
class ChartLayout:
    def __init__(self, cfg, chars):
        self.linesOnPage = cfg.linesOnPage

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
            self.chartHeight = len(chars) * self.charY

            if size <= 6:
                break

            if (self.chartY + self.chartHeight) <= (cfg.paperWidth - self.margin):
                break

            size -= 1

        # calculate maximum length of character name, and start position
        # of chart from that

        maxLen = 0
        for ci in chars:
            maxLen = max(maxLen, len(ci.name))
        maxLen = max(10, maxLen)

        charX = util.getTextWidth(" ", pml.COURIER, self.charFs)

        # chart X pos
        self.chartX = self.margin + maxLen * charX + 3

        # width of chart
        self.chartWidth = cfg.paperHeight - self.chartX - self.margin

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

    # return a pml.Page titled 'title', for the PageInfos 'pages' and the
    # CharInfos 'chars', in that order
    def generatePage(
        self, title: str, pages: List["PageInfo"], chars: List["CharInfo"], doc
    ) -> pml.Page:
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
        pageCnt = len(pages)
        mmPerPage = max(0.1, self.chartWidth / pageCnt)

        pg.add(pml.TextOp("Page:", self.chartX - 1.0, self.pageY - 5.0, 10))

        # draw backround for every other row. this needs to be done before
        # drawing the grid.
        for i in range(len(chars)):
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
                        pages[i].label,
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
            pi = pages[i]
            tlc = pi.getTotalLineCount()

            for lt, color in (
                (screenplay.ACTION, ACTION_COLOR),
                (screenplay.DIALOGUE, DIALOGUE_COLOR),
                (screenplay.CHARACTER, CHARACTER_COLOR),
            ):
                pg.add(fillColor(color))
                pct = util.safeDivInt(pi.getLineCount(lt), tlc)
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

        for i in range(len(chars)):
            y = self.chartY + i * self.charY
            ci = chars[i]

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
                cnt = pages[i].getSpeakerLineCount(ci.name)

                if cnt > 0:
                    h = self.charY * (float(cnt) / self.linesOnPage)

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
    def __init__(self, label):
        # the page's label, e.g. "16" or "15A"
        self.label = label

        # how many lines of each type this page contains. key = line type,
        # value = int. note that if value would be 0, this doesn't have
        # the key at all, so use the helper functions below.
        self.lineCounts = {}

        # how many lines each character speaks on this page. key =
        # character name, value = int. note that if someone doesn't speak
        # they have no entry.
        self.speakers = {}

    # add one line of given type.
    def addLine(self, lt):
        self.lineCounts[lt] = self.getLineCount(lt) + 1

    # get total number of lines.
    def getTotalLineCount(self):
        return sum(self.lineCounts.values())

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
