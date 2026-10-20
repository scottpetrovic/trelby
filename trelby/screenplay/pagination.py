# pagination: deciding where each page ends (sp.pages), what each page is
# called (sp.pageLabels), and mapping between lines and pages.

import trelby.screenplay.pagelock as pagelock
import trelby.util as util
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    LB_LAST,
    PAREN,
    SCENE,
    SHOT,
)


class PaginationMixin:
    # return the script's length in pages, with the last page counted as
    # the fraction of it that is filled. uses the last pagination, like
    # the page numbers do.
    def getPageLength(self):
        pageCnt = len(self.pages) - 1

        if pageCnt < 1:
            return 0.0

        ls = self.lines
        ct = self.cfg.types
        last = len(ls) - 1

        # self.pages can point to lines that no longer exist
        start = util.clamp(self.pages[-2] + 1, 0, last)

        # in tenths of a line, like paginate
        units = 10

        if pageCnt > 1:
            units += self.headers.getNrOfLines() * 10

        for i in range(start + 1, last + 1):
            units += 10

            if ls[i - 1].lb == LB_LAST:
                units += ct[ls[i].lt].beforeSpacing
            else:
                units += ct[ls[i].lt].intraSpacing

        return (pageCnt - 1) + min(1.0, units / (self.cfg.linesOnPage * 10))

    # paginate the script. if pages are locked (some lines have a
    # pageLock), each locked page starts at its line no matter what, which
    # splits the script into segments that are paginated independently: if
    # a segment no longer fits on its page, the rest goes onto A-pages
    # (15A, 15B, ...), and if it has gotten shorter, the page just ends
    # early.
    def paginate(self):
        # sfdlksjf = util.TimerDev("paginate")

        self.pages = [-1]
        self.pagesNoAdjust = [-1]
        self.pageLabels = [""]

        length = len(self.lines)
        locks = self.getPageLocks()

        self.initDualPagination()

        # the lines that start a page of their own
        self.pageStarts = set()

        if self.cfg.pbActNewPage:
            self.pageStarts.update(i for i in range(1, length) if self.isActStart(i))

        if self.cfg.pbSceneNewPage:
            self.pageStarts.update(self.getScenePageStarts())

        if not locks:
            self.paginateRange(0, length - 1)
            self.pageLabels.extend(str(p) for p in range(1, len(self.pages)))

        else:
            if locks[0][0] != 0:
                cnt = self.paginateRange(0, locks[0][0] - 1)
                self.pageLabels.extend(pagelock.labelsBefore(locks[0][1], cnt))

            for i, (line, label) in enumerate(locks):
                if i + 1 < len(locks):
                    end, nextLabel = locks[i + 1][0] - 1, locks[i + 1][1]
                else:
                    end, nextLabel = length - 1, None

                cnt = self.paginateRange(line, end)
                self.pageLabels.extend(pagelock.segmentLabels(label, nextLabel, cnt))

    # set up what paginateRange needs to know about dual dialogues, for
    # paginate to call before it:
    #
    # dualBlockAt: {line: (first, right, last)} for each line of a dual
    # dialogue except its last one, i.e. the lines a page must not end on.
    #
    # dualCost: {line: (first, cost)} for each line of a right-hand
    # column. when the whole dual dialogue is on one page (it starts after
    # the previous page break), 'cost' is how much height the line adds,
    # in the same units as in paginateRange; together they add whatever
    # the right column is taller than the left one, if anything.
    # the first lines of the scene headings that start a new page when
    # each scene does (Config.pbSceneNewPage): every scene but the
    # script's first, unless an act heading comes right before it, which
    # already starts the page.
    def getScenePageStarts(self):
        ls = self.lines
        ret = []
        seen = False

        for i, ln in enumerate(ls):
            if (ln.lt != SCENE) or ((i > 0) and (ls[i - 1].lb != LB_LAST)):
                continue

            if seen and (i > 0) and (ls[i - 1].lt not in (SCENE, ACTBREAK)):
                ret.append(i)

            seen = True

        return ret

    def initDualPagination(self):
        self.dualBlockAt = {}
        self.dualCost = {}

        ls = self.lines
        ct = self.cfg.types

        def height(first, last):
            h = 10

            for i in range(first + 1, last + 1):
                h += 10

                if ls[i - 1].lb == LB_LAST:
                    h += ct[ls[i].lt].beforeSpacing
                else:
                    h += ct[ls[i].lt].intraSpacing

            return h

        blocks = {v[1:] for v in self.getDualLines(0, len(ls) - 1).values()}

        for first, right, last in blocks:
            for i in range(first, last):
                self.dualBlockAt[i] = (first, right, last)

            for i in range(right, last):
                self.dualCost[i] = (first, 0)

            extra = height(right, last) - height(first, right - 1)
            self.dualCost[last] = (first, max(0, extra))

    # paginate lines start - end (inclusive), appending to self.pages and
    # self.pagesNoAdjust as if 'start' was the first line of the script
    # and 'end' the last one, except that line 0 is the only one that
    # starts a page without headers. returns the number of pages added.
    def paginateRange(self, start, end):
        ls = self.lines
        cfg = self.cfg

        oldCnt = len(self.pages)
        length = end + 1
        lastBreak = start - 1

        # fast aliases for stuff
        lbl = LB_LAST
        ct = cfg.types
        hdrLines = self.headers.getNrOfLines()
        dualBlockAt = self.dualBlockAt
        dualCost = self.dualCost
        pageStarts = self.pageStarts

        # each iteration makes one page, starting at line i. heights are
        # in tenths of a line, like the spacing settings: lp is the room on
        # the page for script lines, and pageLines how much of it lines
        # i.. take.
        i = start
        while 1:
            lp = cfg.linesOnPage * 10

            if i != 0:
                lp -= hdrLines * 10

                # decrease by 2 if we have to put a "CONTINUED:" on top of
                # this page.
                if cfg.sceneContinueds and not self.isFirstLineOfScene(i):
                    lp -= 20

                # decrease by 1 if we have to put a "WHOEVER (cont'd)" on
                # top of this page.
                if self.needsMore(i - 1):
                    lp -= 10

            # just a safeguard
            lp = max(50, lp)

            pageLines = 0
            if i < length:
                pageLines = 10

                # advance i until it points to the last line to put on
                # this page (before adjustments)

                while i < (length - 1):

                    if (i + 1) in pageStarts:
                        break

                    dual = dualCost.get(i + 1)

                    if dual and (dual[0] > lastBreak):
                        pageLines += dual[1]
                    else:
                        pageLines += 10
                        if ls[i].lb == lbl:
                            pageLines += ct[ls[i + 1].lt].beforeSpacing
                        else:
                            pageLines += ct[ls[i + 1].lt].intraSpacing

                    if pageLines > lp:
                        break

                    i += 1

            if i >= (length - 1):
                if pageLines != 0:
                    self.pages.append(length - 1)
                    self.pagesNoAdjust.append(length - 1)

                break

            self.pagesNoAdjust.append(i)

            # don't split a dual dialogue between pages. if it starts at
            # the top of the page and still doesn't fit, it's split
            # between its columns, or failing that, like a normal speech.
            block = dualBlockAt.get(i)

            if block:
                first, right, last = block

                if first > (lastBreak + 1):
                    i = first - 1
                elif i >= right:
                    i = right - 1

            line = ls[i]

            if line.lt == SCENE:
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == SHOT:
                i = self.removeDanglingElement(i, SHOT, lastBreak)
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == ACTION:
                if line.lb != LB_LAST:
                    first = self.getElemFirstIndexFromLine(i)

                    if first > (lastBreak + 1):
                        linesOnThisPage = i - first + 1
                        if linesOnThisPage < cfg.pbActionLines:
                            i = first - 1

                        i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt == CHARACTER:
                i = self.removeDanglingElement(i, CHARACTER, lastBreak)
                i = self.removeDanglingElement(i, SCENE, lastBreak)

            elif line.lt in (DIALOGUE, PAREN):

                # if the speech continues on the next page, this page ends
                # with (MORE), for which lp has no room yet. walking
                # backwards: a parenthetical moves to the next page, and
                # then the dialogue before it can end this one. a dialogue
                # element that started on this page keeps at least
                # pbDialogueLines lines here, plus one given up for (MORE)
                # unless moving something off already freed a line, or
                # else moves to the next page too. one that started at the
                # top of the page (or earlier) just gives up a line for
                # (MORE). if all that leaves the character name at the
                # bottom, it moves as well, with a scene heading above it.
                if line.lb != LB_LAST or self.getTypeOfNextElem(i) in (DIALOGUE, PAREN):

                    cutDialogue = False
                    cutParen = False
                    while 1:
                        oldI = i
                        line = ls[i]

                        if line.lt == PAREN:
                            i = self.removeDanglingElement(i, PAREN, lastBreak)
                            cutParen = True

                        elif line.lt == DIALOGUE:
                            if cutParen:
                                break

                            first = self.getElemFirstIndexFromLine(i)

                            if first > (lastBreak + 1):
                                linesOnThisPage = i - first + 1

                                # do we need to reserve one line for (MORE)
                                reserveLine = not (cutDialogue or cutParen)

                                val = cfg.pbDialogueLines
                                if reserveLine:
                                    val += 1

                                if linesOnThisPage < val:
                                    i = first - 1
                                    cutDialogue = True
                                else:
                                    if reserveLine:
                                        i -= 1
                                    break
                            else:
                                # leave space for (MORE)
                                i -= 1
                                break

                        elif line.lt == CHARACTER:
                            i = self.removeDanglingElement(i, CHARACTER, lastBreak)
                            i = self.removeDanglingElement(i, SCENE, lastBreak)

                            break

                        else:
                            break

                        if i == oldI:
                            break

            # don't leave an act heading at the bottom of a page, with
            # the act itself starting on the next one
            if ls[i].lt == ACTBREAK:
                first = self.getElemFirstIndexFromLine(i)

                if (first > (lastBreak + 1)) and self.isActStart(first):
                    i = first - 1

            # make sure no matter how buggy the code above is, we always
            # advance at least one line per page
            i = max(i, lastBreak + 1)

            self.pages.append(i)
            lastBreak = i

            i += 1

        return len(self.pages) - oldCnt

    # used by paginateRange, with 'line' being the line it's about to end
    # a page on: if it's of type lt, return the last line before its
    # element, so that the element goes to the next page instead of
    # dangling at the bottom of this one. otherwise 'line' is returned
    # as it is. never goes back past the page's first line, lastBreak + 1.
    def removeDanglingElement(self, line, lt, lastBreak):
        ls = self.lines
        startLine = line

        while 1:
            if line < (lastBreak + 2):
                break

            ln = ls[line]

            if ln.lt != lt:
                break

            # only remove one element at most, to avoid generating
            # potentially thousands of pages in degenerate cases when
            # script only contains scenes or characters or something like
            # that.
            if (line != startLine) and (ln.lb == LB_LAST):
                break

            line -= 1

        return line

    def line2page(self, line):
        return self.line2pageReal(line, self.pages)

    def line2pageNoAdjust(self, line):
        return self.line2pageReal(line, self.pagesNoAdjust)

    # return the page (1-based) that 'line' is on, given p, a list of each
    # page's last line in the format of self.pages: binary search for the
    # first page whose last line is >= line. lines past the end are on the
    # last page.
    def line2pageReal(self, line, p):
        lo = 1
        hi = len(p) - 1

        while lo != hi:
            mid = (lo + hi) // 2

            if line <= p[mid]:
                hi = mid
            else:
                lo = mid + 1

        return lo

    # return (startLine, endLine) for given page number (1-based). if
    # pageNr is out of bounds, it is clamped to the valid range. if
    # pagination is out of date and the lines no longer exist, they are
    # clamped to the valid range as well.
    def page2lines(self, pageNr):
        pageNr = util.clamp(pageNr, 1, len(self.pages) - 1)
        last = len(self.lines) - 1

        return (
            util.clamp(self.pages[pageNr - 1] + 1, 0, last),
            util.clamp(self.pages[pageNr], 0, last),
        )

    # return the label of the given page (1-based index into self.pages),
    # e.g. "16" or "15A". pageNr is clamped to the valid range.
    def getPageLabel(self, pageNr):
        return self.pageLabels[util.clamp(pageNr, 1, len(self.pageLabels) - 1)]

    # return the label of the page the given line is on
    def line2pageLabel(self, line):
        return self.getPageLabel(self.line2page(line))

    # return the page number (1-based index into self.pages) of the page
    # with the given label (case-insensitive), or -1 if there's none.
    def label2page(self, label):
        label = pagelock.normalize(label)

        for p in range(1, len(self.pageLabels)):
            if self.pageLabels[p] == label:
                return p

        return -1

    # return a list of all page labels, in order.
    def getPageNumbers(self):
        return self.pageLabels[1:]
