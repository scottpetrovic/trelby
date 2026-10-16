# -*- coding: iso-8859-1 -*-

import trelby.commands as commands
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay.render as render
import trelby.util as util

# Number of lines the smooth scroll will try to search. 15-20 is a good
# number to use with the layout mode margins we have.
MAX_JUMP_DISTANCE = 17

# extra space (pixels) above the first page, for the button that opens
# the title pages dialog (drawn by MyCtrl.OnPaint)
TITLE_BUTTON_H = 44


# a piece of text on screen.
class TextString:
    def __init__(self, line, text, x, y, fi, isUnderlined, fmt=None, charWidth=1):

        # if this object is a screenplay line, this is the index of the
        # corresponding line in the Screenplay.lines list. otherwise this
        # is -1 (used for stuff like CONTINUED: etc).
        self.line = line

        # x,y coordinates in pixels from widget's topleft corner
        self.x = x
        self.y = y

        # text and its config.FontInfo and underline status
        self.text = text
        self.fi = fi
        self.isUnderlined = isUnderlined

        # format string for bold / italic / underlined parts of the text
        # (see textfmt), or None
        self.fmt = fmt

        # how many columns each character takes up (see pml.TextOp)
        self.charWidth = charWidth

    # return the width of one character in pixels
    def getCharPixels(self):
        return self.fi.fx * self.charWidth


# a page shown on screen.
class DisplayPage:
    def __init__(self, pageNr, x1, y1, x2, y2):

        # page number (1-based index in Screenplay.pages)
        self.pageNr = pageNr

        # coordinates in pixels
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2


# caches pml.Pages for operations that repeatedly construct them over and
# over again without the page contents changing.
class PageCache:
    def __init__(self, ctrl):
        self.ctrl = ctrl

        # cached pages. key = pageNr, value = pml.Page
        self.pages = {}

    def getPage(self, pager, pageNr):
        pg = self.pages.get(pageNr)

        if not pg:
            pg = render.generatePMLPage(self.ctrl.sp, pager, pageNr, False, False)
            self.pages[pageNr] = pg

        return pg


# View Mode, i.e. a way of displaying the script on screen. this is an
# abstract superclass.
class ViewMode:

    # get a description of what the current screen contains. returns
    # (texts, dpages), where texts = [TextString, ...], dpages =
    # [DisplayPage, ...]. dpages is empty if draft mode is in use, which
    # callers test with "if not dpages". doExtra has same meaning as for
    # render.generatePMLPage. pageCache, if given, is used in layout mode to
    # cache PML pages. it should only be given when doExtra = False as the cached
    # pages aren't accurate down to that level.
    #
    # partial lines (some of the the text is clipped off-screen) are only
    # included in the results if 'partials' is True.
    #
    # lines in 'texts' have to be in monotonically increasing order, and
    # this has to always return at least one line.
    def getScreen(self, ctrl, doExtra, partials=False, pageCache=None):
        raise Exception("getScreen " + _("not implemented"))

    # return height for one line on screen
    def getLineHeight(self, ctrl):
        raise Exception("getLineHeight " + _("not implemented"))

    # return width of one page in (floating point) pixels
    def getPageWidth(self, ctrl):
        raise Exception("getPageWidth " + _("not implemented"))

    # see MyCtrl.OnPaint for what tl is. note: this is only a default
    # implementation, feel free to override this.
    def drawTexts(self, ctrl, dc, tl):
        dc.SetFont(tl[0])
        dc.DrawTextList(tl[1][0], tl[1][1], tl[1][2])

    # determine what (line, col) is at position (x, y) (screen
    # coordinates) and return that, or (None, None) if (x, y) points
    # outside a page.
    def pos2linecol(self, ctrl, x, y):
        raise Exception("pos2linecol " + _("not implemented"))

    # make line, which is not currently visible, visible. texts =
    # self.getScreen(ctrl, False)[0].
    def makeLineVisible(self, ctrl, line, texts, direction=commands.SCROLL_CENTER):
        raise Exception("makeLineVisible " + _("not implemented"))

    # handle page up (dir == -1) or page down (dir == 1) command. cursor
    # is guaranteed to be visible when this is called, and auto-completion
    # to be off. cs = CommandState. texts and dpages are the usual.
    def pageCmd(self, ctrl, cs, dir, texts, dpages):
        raise Exception("pageCmd " + _("not implemented"))

    # semi-generic implementation, for use by Draft and Layout modes.
    def pos2linecolGeneric(self, ctrl, x, y):
        sel = None
        lineh = self.getLineHeight(ctrl)
        texts = self.getScreen(ctrl, False, True)[0]

        for t in texts:
            if t.line == -1:
                continue

            sel = t

            if (t.y + lineh) > y:
                break

        if sel == None:
            return (None, None)

        # the two columns of a dual dialogue share rows, so use the
        # rightmost line on the row that starts left of x
        for t in texts:
            if (t.line != -1) and (t.y == sel.y) and (sel.x < t.x <= x):
                sel = t

        line = sel.line
        l = ctrl.sp.lines[line]

        column = util.clamp(int((x - sel.x) / sel.getCharPixels()), 0, len(l.text))

        return (line, column)

    # semi-generic implementation, for use by Draft and Layout modes.
    #
    # with recenterOnScroll off, the MoveUp / MoveDown commands (the only
    # ones with a direction) scroll just far enough, so the screen moves
    # smoothly. otherwise, or if the line is too far away for that, the
    # line is put in the middle of the screen.
    def makeLineVisibleGeneric(self, ctrl, line, texts, direction, jumpAhead):
        if not ctrl.sp.cfgGl.recenterOnScroll and (direction != commands.SCROLL_CENTER):
            if self._makeLineVisibleHelper(ctrl, line, direction, jumpAhead):
                return

        # smooth scrolling not in operation (or failed), recenter screen
        ctrl.ed.setTopLine(max(0, int(line - (len(texts) * 0.5))))

        if not ctrl.isLineVisible(line):
            ctrl.ed.setTopLine(line)

    # helper function for makeLineVisibleGeneric. moves the top line in
    # 'direction' until line is visible, by 1 line at first and then by
    # jumpAhead more lines each try (each try lays out the screen again,
    # which is slower in layout mode, so it uses bigger steps). returns
    # False, leaving the top line moved, if it isn't visible within
    # MAX_JUMP_DISTANCE lines.
    def _makeLineVisibleHelper(self, ctrl, line, direction, jumpAhead):
        startLine = ctrl.ed.getTopLine()
        sign = 1 if (direction == commands.SCROLL_DOWN) else -1
        i = 1

        while not ctrl.isLineVisible(line):
            ctrl.ed.setTopLine(startLine + i * sign)
            i += jumpAhead

            if i > MAX_JUMP_DISTANCE:
                return False

        return True

    # semi-generic implementation, for use by Draft and Layout modes.
    #
    # page down puts the last line on screen at the top, with the cursor
    # on it. page up puts the cursor on the top line, then scrolls back one
    # line at a time for as long as that line stays on screen, so it ends
    # up at the bottom. (if the top line is also the last one on screen,
    # the window is too small for that, so it just goes back 5 lines.)
    def pageCmdGeneric(self, ctrl, cs, dir, texts, dpages):
        if dir > 0:
            line = texts[-1].line
            ctrl.ed.line = line
            ctrl.ed.setTopLine(line)
        else:
            tl = ctrl.ed.getTopLine()
            if tl == texts[-1].line:
                ctrl.ed.setTopLine(tl - 5)
            else:
                ctrl.ed.line = tl

                pc = PageCache(ctrl)

                while 1:
                    tl = ctrl.ed.getTopLine()
                    if tl == 0:
                        break

                    texts = self.getScreen(ctrl, False, False, pc)[0]
                    lastLine = texts[-1].line

                    if ctrl.ed.line > lastLine:
                        # line scrolled off screen, back up one line
                        ctrl.ed.setTopLine(tl + 1)
                        break

                    ctrl.ed.setTopLine(tl - 1)

            cs.needsVisifying = False


# Draft view mode. No fancy page break layouts, just text lines on a plain
# background.
class ViewModeDraft(ViewMode):

    def getScreen(self, ctrl, doExtra, partials=False, pageCache=None):
        cfg = ctrl.sp.cfg
        cfgGui = ctrl.getCfgGui()

        width, height = ctrl.GetClientSize()
        ls = ctrl.sp.lines
        y = 15
        i = ctrl.ed.getTopLine()

        marginLeft = int(ctrl.mm2p * cfg.marginLeft)
        cox = util.clamp((width - ctrl.pageW) // 2, 0)
        fyd = cfgGui.fontYdelta
        length = len(ls)

        texts = []

        while (y < height) and (i < length):
            # spacing is in tenths of a line
            y += int((ctrl.sp.getSpacingBefore(i) / 10.0) * fyd)

            if y >= height:
                break

            if not partials and ((y + fyd) > height):
                break

            l = ls[i]
            tcfg = cfg.getType(l.lt)

            if tcfg.screen.isCaps:
                text = util.upper(l.text)
            else:
                text = l.text

            fi = cfgGui.tt2fi(tcfg.screen)

            extraIndent = 1 if ctrl.sp.needsExtraParenIndent(i) else 0
            extraIndent += ctrl.sp.getCenterOffset(i)

            texts.append(
                TextString(
                    i,
                    text,
                    int(cox + marginLeft + (tcfg.indent + extraIndent) * fi.fx),
                    y,
                    fi,
                    tcfg.screen.isUnderlined,
                    l.fmt,
                    cfg.getCharWidth(),
                )
            )

            y += fyd
            i += 1

        return (texts, [])

    def getLineHeight(self, ctrl):
        return ctrl.getCfgGui().fontYdelta

    def getPageWidth(self, ctrl):
        # this is not really used for much in draft mode, as it has no
        # concept of page width, but it's safer to return something
        # anyway.
        return (ctrl.sp.cfg.paperWidth / ctrl.chX) * ctrl.getCfgGui().fonts[
            pml.NORMAL
        ].fx

    def pos2linecol(self, ctrl, x, y):
        return self.pos2linecolGeneric(ctrl, x, y)

    def makeLineVisible(self, ctrl, line, texts, direction=commands.SCROLL_CENTER):
        self.makeLineVisibleGeneric(ctrl, line, texts, direction, jumpAhead=1)

    def pageCmd(self, ctrl, cs, dir, texts, dpages):
        self.pageCmdGeneric(ctrl, cs, dir, texts, dpages)


# Layout view mode. Pages are shown with the actual layout they would
# have.
class ViewModeLayout(ViewMode):

    def getScreen(self, ctrl, doExtra, partials=False, pageCache=None):
        cfgGui = ctrl.getCfgGui()
        textOp = pml.TextOp

        texts = []
        dpages = []

        width, height = ctrl.GetClientSize()

        # gap between pages (pixels)
        pageGap = 10
        pager = mypager.Pager(ctrl.sp.cfg)

        mm2p = ctrl.mm2p
        fontY = cfgGui.fonts[pml.NORMAL].fy

        cox = util.clamp((width - ctrl.pageW) // 2, 0)

        y = 0
        topLine = ctrl.ed.getTopLine()
        pageNr = ctrl.sp.line2page(topLine)

        # the pager tracks the current scene's number as it lays out a page,
        # so start it with that of the scene the page begins in
        if doExtra and ctrl.sp.cfg.pdfShowSceneNumbers:
            pager.scene = ctrl.sp.getSceneNumber(ctrl.sp.page2lines(pageNr)[0] - 1)

        # find out starting place (if something bugs, render.generatePMLPage
        # below could return None, but it shouldn't happen...)
        #
        # y is the screen position of the top of topLine's page: if topLine
        # is the page's first line, the whole page is shown, below a gap
        # (and the title page button on page 1), otherwise the page starts
        # above the screen so that topLine is at the very top
        if pageCache:
            pg = pageCache.getPage(pager, pageNr)
        else:
            pg = render.generatePMLPage(ctrl.sp, pager, pageNr, False, doExtra)

        topOfPage = True
        for op in pg.ops:
            if not isinstance(op, textOp) or (op.line == -1):
                continue

            if op.line == topLine:
                if not topOfPage:
                    y = -int(op.y * mm2p)
                else:
                    y = pageGap

                    if pageNr == 1:
                        y += TITLE_BUTTON_H

                break
            else:
                topOfPage = False

        # create pages, convert them to display format, repeat until
        # script ends or we've filled the display.

        done = False
        while 1:
            if done or (y >= height):
                break

            if not pg:
                pageNr += 1
                if pageNr >= len(ctrl.sp.pages):
                    break

                # we'd have to go back an arbitrary number of pages to
                # get an accurate number for this in the worst case,
                # so disable it altogether.
                pager.sceneContNr = 0

                if pageCache:
                    pg = pageCache.getPage(pager, pageNr)
                else:
                    pg = render.generatePMLPage(ctrl.sp, pager, pageNr, False, doExtra)
                if not pg:
                    break

            dp = DisplayPage(pageNr, cox, y, cox + ctrl.pageW, y + ctrl.pageH)
            dpages.append(dp)

            pageY = y

            for op in pg.ops:
                if not isinstance(op, textOp):
                    continue

                ypos = int(pageY + op.y * mm2p)

                # above the screen, on a page that starts above it
                if ypos < 0:
                    continue

                y = max(y, ypos)

                # keep going, since the right-hand column of a dual
                # dialogue comes after the left one but starts higher up
                if (ypos >= height) or (not partials and ((ypos + fontY) > height)):
                    done = True
                    continue

                texts.append(
                    TextString(
                        op.line,
                        op.text,
                        int(cox + op.x * mm2p),
                        ypos,
                        cfgGui.fonts[op.flags & 3],
                        op.flags & pml.UNDERLINED,
                        op.fmt,
                        op.charWidth,
                    )
                )

            y = pageY + ctrl.pageH + pageGap
            pg = None

        # if user has inserted new text causing the script to overflow
        # the last page, we need to make the last page extra-long on
        # the screen.
        if dpages and texts and (pageNr >= (len(ctrl.sp.pages) - 1)):

            lastY = texts[-1].y + fontY
            if lastY >= dpages[-1].y2:
                dpages[-1].y2 = lastY + 10

        return (texts, dpages)

    def getLineHeight(self, ctrl):
        # the + 1.0 avoids occasional non-consecutive backgrounds for
        # lines.
        return int(ctrl.chY * ctrl.mm2p + 1.0)

    # the paper's width in characters (of the PDF font) times the screen
    # font's character width, so that the screen font's characters line up
    # with where the PDF puts them (see MyCtrl.refreshCache)
    def getPageWidth(self, ctrl):
        return (ctrl.sp.cfg.paperWidth / ctrl.chX) * ctrl.getCfgGui().fonts[
            pml.NORMAL
        ].fx

    def pos2linecol(self, ctrl, x, y):
        return self.pos2linecolGeneric(ctrl, x, y)

    def makeLineVisible(self, ctrl, line, texts, direction=commands.SCROLL_CENTER):
        self.makeLineVisibleGeneric(ctrl, line, texts, direction, jumpAhead=3)

    def pageCmd(self, ctrl, cs, dir, texts, dpages):
        self.pageCmdGeneric(ctrl, cs, dir, texts, dpages)


# Side by side view mode. Pages are shown with the actual layout they
# would have, as many pages at a time as fit on the screen, complete pages
# only, in a single row.
class ViewModeSideBySide(ViewMode):

    def getScreen(self, ctrl, doExtra, partials=False, pageCache=None):
        cfgGui = ctrl.getCfgGui()
        textOp = pml.TextOp

        texts = []
        dpages = []

        width, height = ctrl.GetClientSize()

        mm2p = ctrl.mm2p

        # gap between pages (+ screen left edge)
        pageGap = 10

        # how many pages fit on screen
        pageCnt = max(1, (width - pageGap) // (ctrl.pageW + pageGap))

        pager = mypager.Pager(ctrl.sp.cfg)

        topLine = ctrl.ed.getTopLine()
        pageNr = ctrl.sp.line2page(topLine)

        if doExtra and ctrl.sp.cfg.pdfShowSceneNumbers:
            pager.scene = ctrl.sp.getSceneNumber(ctrl.sp.page2lines(pageNr)[0] - 1)

        pagesDone = 0

        # top of the row of pages
        sy = pageGap
        if pageNr == 1:
            sy += TITLE_BUTTON_H

        while 1:
            if (pagesDone >= pageCnt) or (pageNr >= len(ctrl.sp.pages)):
                break

            # we'd have to go back an arbitrary number of pages to get an
            # accurate number for this in the worst case, so disable it
            # altogether.
            pager.sceneContNr = 0

            if pageCache:
                pg = pageCache.getPage(pager, pageNr)
            else:
                pg = render.generatePMLPage(ctrl.sp, pager, pageNr, False, doExtra)
            if not pg:
                break

            sx = pageGap + pagesDone * (ctrl.pageW + pageGap)

            dp = DisplayPage(pageNr, sx, sy, sx + ctrl.pageW, sy + ctrl.pageH)
            dpages.append(dp)

            for op in pg.ops:
                if not isinstance(op, textOp):
                    continue

                texts.append(
                    TextString(
                        op.line,
                        op.text,
                        int(sx + op.x * mm2p),
                        int(sy + op.y * mm2p),
                        cfgGui.fonts[op.flags & 3],
                        op.flags & pml.UNDERLINED,
                        op.fmt,
                        op.charWidth,
                    )
                )

            pageNr += 1
            pagesDone += 1

        return (texts, dpages)

    def getLineHeight(self, ctrl):
        # the + 1.0 avoids occasional non-consecutive backgrounds for
        # lines.
        return int(ctrl.chY * ctrl.mm2p + 1.0)

    def getPageWidth(self, ctrl):
        return (ctrl.sp.cfg.paperWidth / ctrl.chX) * ctrl.getCfgGui().fonts[
            pml.NORMAL
        ].fx

    def pos2linecol(self, ctrl, x, y):
        lineh = self.getLineHeight(ctrl)
        ls = ctrl.sp.lines

        sel = None

        for t in self.getScreen(ctrl, False)[0]:
            if t.line == -1:
                continue

            # above or to the left
            if (x < t.x) or (y < t.y):
                continue

            # below
            if y > (t.y + lineh - 1):
                continue

            # to the right
            w = t.getCharPixels() * (len(ls[t.line].text) + 1)
            if x > (t.x + w - 1):
                continue

            sel = t
            break

        if sel == None:
            return (None, None)

        line = sel.line
        l = ls[line]

        column = util.clamp(int((x - sel.x) / sel.getCharPixels()), 0, len(l.text))

        return (line, column)

    # the screen always starts at the top of the top line's page, so this
    # shows line's page first
    def makeLineVisible(self, ctrl, line, texts, direction=commands.SCROLL_CENTER):
        ctrl.ed.setTopLine(line)

    # move a screenful of pages back or forward
    def pageCmd(self, ctrl, cs, dir, texts, dpages):
        if dir < 0:
            pageNr = dpages[0].pageNr - len(dpages)
        else:
            pageNr = dpages[-1].pageNr + 1

        line = ctrl.sp.page2lines(pageNr)[0]

        ctrl.ed.line = line
        ctrl.ed.setTopLine(line)
        cs.needsVisifying = False
