# drawing a script on screen: the page backgrounds, the text with its
# selection, cursor and formatting marks, the lock icons, the notes beside
# the page, the title page button and the auto-completion list. MyCtrl.OnPaint uses this, with a
# Viewport describing what's shown, laid out by the current view mode
# (viewmode.py).

import wx
from wx.lib.wordwrap import wordwrap

import trelby.config as config
import trelby.ui.gutil as gutil
import trelby.pdf.pml as pml
import trelby.screenplay.revisions as revisions
import trelby.spellcheck as spellcheck
import trelby.textfmt as textfmt
import trelby.textutil as textutil
import trelby.util as util
from trelby.screenplay.notes import Note
from trelby.ui.theming import blendColors

# the notes beside the page: how wide their cards are at most, and at
# least (in DIPs, with an icon instead where there's less room), and how
# many lines of a note's text they show
NOTE_WIDTH = 240
NOTE_MIN_WIDTH = 120
NOTE_LINES = 3

# what's shown in an editor window: the script and its Editor (for the
# cursor, selection and scroll position), the configgui.ConfigGui with the
# screen fonts and colors, the window's size (wx.Size), and the scale:
# mm2p converts mm on paper to pixels, pageW / pageH are a page's size on
# screen in pixels, and chX / chY a character's width and a line's height
# on paper in mm. dip converts device independent pixels to pixels.
#
# the view modes take this in place of a MyCtrl, so it has the parts of
# MyCtrl's interface they use for drawing.
class Viewport:
    def __init__(self, sp, ed, cfgGui, size, mm2p, pageW, pageH, chX, chY, dip):
        self.sp = sp
        self.ed = ed
        self.cfgGui = cfgGui
        self.size = size
        self.mm2p = mm2p
        self.pageW = pageW
        self.pageH = pageH
        self.chX = chX
        self.chY = chY
        self.dip = dip

    # return a Viewport showing sp in a window of the given size, at the
    # scale the view mode vm lays it out at
    @staticmethod
    def make(sp, ed, cfgGui, vm, size, dip):
        # width of one character and height of one line on paper, in mm,
        # at the script's (PDF) font size
        chX = util.getTextWidth(" ", pml.COURIER, sp.cfg.fontSize)
        chY = util.getTextHeight(sp.cfg.fontSize)

        vp = Viewport(sp, ed, cfgGui, size, None, None, None, chX, chY, dip)

        # the scale comes from the screen font, not the paper: the page is
        # drawn as many screen characters wide as the paper holds, so text
        # laid out in mm for the PDF lands on whole character cells. zoom
        # works by scaling the screen fonts.
        pageW = vm.getPageWidth(vp)
        vp.mm2p = pageW / sp.cfg.paperWidth
        vp.pageW = int(pageW)
        vp.pageH = int(vp.mm2p * sp.cfg.paperHeight)

        return vp

    def GetClientSize(self):
        return self.size

    def getCfgGui(self):
        return self.cfgGui


class ScriptPainter:
    # vp is the Viewport, vm the viewmode.ViewMode, cfgGl the global
    # config, and showFormatting whether to show the margins and line
    # break types (View / Show formatting). misspelled words are
    # underlined if scDict, the user's global spell checker dictionary,
    # is given and the main dictionary is loaded. newNoteLine is the first
    # line of a paragraph that gets a blank card after its notes, for a
    # note being written there (see noteeditor.py), or None. readingLines
    # is (first line, last line) of the element being read aloud, which is
    # highlighted, or None.
    def __init__(
        self,
        vp,
        vm,
        cfgGl,
        showFormatting,
        scDict=None,
        newNoteLine=None,
        readingLines=None,
    ):
        self.vp = vp
        self.vm = vm
        self.cfgGl = cfgGl
        self.cfgGui = vp.cfgGui
        self.showFormatting = showFormatting
        self.newNoteLine = newNoteLine
        self.readingLines = readingLines

        self.spellChecker = None

        if scDict and spellcheck.gdict:
            self.spellChecker = spellcheck.SpellChecker(vp.sp, scDict)

        # wx.Rect of the title page button, set by paint
        self.titleButtonRect = None

        # the highlight color of each revision level drawn, by level
        self.revisionColors = {}

        # the note markers drawn, as (wx.Rect, line, index) tuples, set by
        # paint (see drawNoteMarkers)
        self.noteMarkers = []

        # the "resolved" checkboxes on the note cards, as (wx.Rect, line,
        # index) tuples like noteMarkers', the rect a bit bigger than the
        # box to make it easier to click
        self.noteChecks = []

    # draw the script on dc. returns the wx.Rect of the "Manage title
    # page" button above the first page, or None if it's not on screen.
    def paint(self, dc):
        vp = self.vp
        ls = vp.sp.lines

        size = vp.size
        marked = vp.ed.getMarkedLines()
        lineh = self.vm.getLineHeight(vp)
        posX = -1
        cursorY = -1

        # auto-comp FontInfo
        acFi = None

        # list of (font, ([text, ...], [(x, y), ...], [wx.Colour, ...]))
        # tuples, drawn after everything else by ViewMode.drawTexts
        texts = []

        # lists of underline-lines to draw, one for normal text and one
        # for header texts. list objects are (x, y, width) tuples.
        ulines = []
        ulinesHdr = []

        # misspelled words to underline, as (x, y, width) tuples, y being
        # the bottom of the text
        squiggles = []

        strings, dpages = self.vm.getScreen(vp, True, True)

        # key = id() of a wx.Font, which isn't hashable, value = x offset
        # (pixels) of a wide character in a double-width cell (see
        # cellOffset)
        wideOffsets = {}

        dc.SetBrush(self.cfgGui.workspaceBrush)
        dc.SetPen(self.cfgGui.workspacePen)
        dc.DrawRectangle(0, 0, size.width, size.height)

        dc.SetPen(self.cfgGui.tabBorderPen)
        dc.DrawLine(0, 0, 0, size.height)

        if not dpages:
            # draft mode; draw an infinite page
            lx = util.clamp((size.width - vp.pageW) // 2, 0)
            rx = lx + vp.pageW

            dc.SetBrush(self.cfgGui.textBgBrush)
            dc.SetPen(self.cfgGui.textBgPen)
            dc.DrawRectangle(lx, 5, vp.pageW, size.height - 5)

            dc.SetPen(self.cfgGui.pageBorderPen)
            dc.DrawLine(lx, 5, lx, size.height)
            dc.DrawLine(rx, 5, rx, size.height)

        else:
            dc.SetBrush(self.cfgGui.textBgBrush)
            dc.SetPen(self.cfgGui.pageBorderPen)
            for dp in dpages:
                dc.DrawRectangle(dp.x1, dp.y1, dp.x2 - dp.x1 + 1, dp.y2 - dp.y1 + 1)

            dc.SetPen(self.cfgGui.pageShadowPen)
            for dp in dpages:
                # + 2 because DrawLine doesn't draw to end point but stops
                # one pixel short...
                dc.DrawLine(dp.x1 + 1, dp.y2 + 1, dp.x2 + 1, dp.y2 + 1)
                dc.DrawLine(dp.x2 + 1, dp.y1 + 1, dp.x2 + 1, dp.y2 + 2)

        self.titleButtonRect = None

        if dpages and (dpages[0].pageNr == 1):
            self.drawTitleButton(dc, dpages[0])

        for t in strings:
            i = t.line
            y = t.y
            fi = t.fi
            fx = fi.fx

            # width of one character; differs from fx with double-width
            # characters
            cfx = t.getCharPixels()

            if i != -1:
                l = ls[i]

                if self.readingLines and (
                    self.readingLines[0] <= i <= self.readingLines[1]
                ):
                    self.drawReadingLine(dc, t, i, y, lineh, fx)

                if l.revs:
                    self.drawRevised(dc, t, l, y, lineh, cfx)

                if marked and vp.ed.isLineMarked(i, marked):
                    c1, c2 = vp.ed.getMarkedColumns(i, marked)

                    dc.SetPen(self.cfgGui.selectedPen)
                    dc.SetBrush(self.cfgGui.selectedBrush)

                    dc.DrawRectangle(t.x + c1 * cfx, y, (c2 - c1 + 1) * cfx, lineh)

                if self.showFormatting:
                    # a centered line's text doesn't start at its margin
                    lx = int(t.x - vp.sp.getCenterOffset(i) * fx)

                    dc.SetPen(self.cfgGui.bluePen)
                    gutil.drawLine(dc, lx, y, 0, lineh)

                    extraIndent = 1 if vp.sp.needsExtraParenIndent(i) else 0

                    gutil.drawLine(
                        dc,
                        lx + (vp.sp.cfg.getType(l.lt).width - extraIndent) * fx,
                        y,
                        0,
                        lineh,
                    )

                    dc.SetTextForeground(self.cfgGui.redColor)
                    dc.SetFont(self.cfgGui.fonts[pml.NORMAL].font)
                    dc.DrawText(config.lb2char(l.lb), t.x - 10, y)

                if not dpages:
                    if self.cfgGl.pbi == config.PBI_REAL_AND_UNADJ:
                        if vp.sp.line2pageNoAdjust(i) != vp.sp.line2pageNoAdjust(
                            i + 1
                        ):
                            dc.SetPen(self.cfgGui.pagebreakNoAdjustPen)
                            gutil.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                    if self.cfgGl.pbi in (
                        config.PBI_REAL,
                        config.PBI_REAL_AND_UNADJ,
                    ):
                        thisPage = vp.sp.line2page(i)

                        if thisPage != vp.sp.line2page(i + 1):
                            dc.SetPen(self.cfgGui.pagebreakPen)
                            gutil.drawLine(dc, 0, y + lineh - 1, size.width, 0)

                if i == vp.ed.line:
                    posX = t.x
                    cursorY = y
                    acFi = fi
                    dc.SetPen(self.cfgGui.cursorPen)
                    dc.SetBrush(self.cfgGui.cursorBrush)
                    dc.DrawRectangle(t.x + vp.ed.column * cfx, y, cfx, fi.fy)

            if len(t.text) != 0:
                if t.line != -1:
                    color = self.cfgGui.lt2textColor(ls[t.line].lt)
                    uli = ulines
                else:
                    color = self.cfgGui.textHdrColor
                    uli = ulinesHdr

                if t.isUnderlined:
                    uli.append((t.x, y + lineh - 1, len(t.text) * cfx - 1))

                if self.spellChecker and (t.line != -1):
                    cursorCol = vp.ed.column if t.line == vp.ed.line else None

                    # in the page modes the lines are closer than the
                    # font's height
                    bottom = y + min(fi.fy, lineh)

                    for col, n in self.spellChecker.lineErrors(t.line, cursorCol):
                        squiggles.append((t.x + col * cfx, bottom, n * cfx))

                # bold / italic / underlined parts of the text are drawn
                # separately, each in its own font
                #
                # cfgGui.fonts is indexed by the bold / italic bits, which
                # textfmt and pml share, so a run's style bits are added to
                # the element's own font, e.g. italic text in a bold scene
                # heading gets the bold italic font
                if t.fmt:
                    fonts = self.cfgGui.fonts
                    base = fonts.index(fi)

                    parts = []

                    for a, b, style in textfmt.runs(t.fmt, len(t.text)):
                        x = t.x + a * cfx
                        parts.append((fonts[base | (style & 3)].font, a, b, x))

                        if (style & textfmt.UNDERLINED) and not t.isUnderlined:
                            uli.append((x, y + lineh - 1, (b - a) * cfx - 1))
                else:
                    parts = [(fi.font, 0, len(t.text), t.x)]

                for font, a, b, x in parts:
                    if t.charWidth == 1:
                        tl = ([t.text[a:b]], [(x, y)], [color])
                    else:
                        # each character centered in its own cell
                        chars = []
                        coords = []

                        for k in range(a, b):
                            ch = t.text[k]

                            if ch != " ":
                                off = self.cellOffset(
                                    dc, font, ch, fx, cfx, wideOffsets
                                )
                                chars.append(ch)
                                coords.append((t.x + k * cfx + off, y))

                        tl = (chars, coords, [color] * len(chars))

                    texts.append((font, tl))

        if ulines:
            dc.SetPen(self.cfgGui.textPen)

            for ul in ulines:
                gutil.drawLine(dc, ul[0], ul[1], ul[2], 0)

        if ulinesHdr:
            dc.SetPen(self.cfgGui.textHdrPen)

            for ul in ulinesHdr:
                gutil.drawLine(dc, ul[0], ul[1], ul[2], 0)

        for tl in texts:
            self.vm.drawTexts(vp, dc, tl)

        if squiggles:
            dc.SetPen(self.cfgGui.spellErrorPen)

            for x, y, w in squiggles:
                self.drawSquiggle(dc, x, y, w)

        self.drawLocks(dc, strings, dpages, size)
        self.drawRevisionMarks(dc, strings, dpages, size)
        self.drawNoteMarkers(dc, strings, dpages, size)

        if vp.ed.acItems and (cursorY > 0):
            self.drawAutoComp(dc, posX, cursorY, acFi)

        return self.titleButtonRect

    # highlight line i, being read aloud, drawn at t.x, y: a band in a
    # light version of the selection color the width of its element type,
    # with a bar in the cursor color to its left
    def drawReadingLine(self, dc, t, i, y, lineh, fx):
        cfgGui = self.cfgGui
        color = blendColors(cfgGui.selectedColor, cfgGui.textBgColor, 0.5)
        lx = int(t.x - self.vp.sp.getCenterOffset(i) * fx)
        w = self.vp.sp.cfg.getType(self.vp.sp.lines[i].lt).width * fx

        dc.SetPen(wx.Pen(color))
        dc.SetBrush(wx.Brush(color))
        dc.DrawRectangle(lx, y, w, lineh)

        dc.SetPen(cfgGui.cursorPen)
        dc.SetBrush(cfgGui.cursorBrush)
        dc.DrawRectangle(lx - fx, y, max(2, fx // 4), lineh)

    # highlight the revised text of line l, drawn at t.x, y, in the color
    # of each part's revision (see screenplay/revisions.py)
    def drawRevised(self, dc, t, l, y, lineh, cfx):
        n = min(len(t.text), len(l.text))
        dc.SetPen(wx.TRANSPARENT_PEN)

        for a, b, level in textfmt.runs(l.revs[:n], n):
            if level:
                dc.SetBrush(wx.Brush(self.revisionColor(level)))
                dc.DrawRectangle(t.x + a * cfx, y, (b - a) * cfx, lineh)

    # the color revised text of 'level' is highlighted with: the
    # revision's color, faded into the page's
    def revisionColor(self, level):
        color = self.revisionColors.get(level)

        if color is None:
            color = blendColors(
                self.cfgGui.textBgColor,
                wx.Colour("#" + revisions.levelColor(level)),
                0.45,
            )
            self.revisionColors[level] = color

        return color

    # put the revision mark in the right margin of each line that gets
    # one when printed (see screenplay.render), in the color of the
    # line's revision. in draft mode, where there are no pages, the
    # margin is that of the infinite page.
    def drawRevisionMarks(self, dc, strings, dpages, size):
        vp = self.vp
        sp = vp.sp
        rv = sp.revisions
        ls = sp.lines

        markX = int(revisions.markX(sp.cfg, vp.chX) * vp.mm2p)
        draftX = util.clamp((size.width - vp.pageW) // 2, 0)

        dc.SetFont(self.cfgGui.fonts[pml.BOLD].font)
        done = set()

        for t in strings:
            i = t.line

            if (i == -1) or not ls[i].revs or not rv.isMarked(ls[i]):
                continue

            x = draftX

            for dp in dpages:
                if dp.x1 <= t.x <= dp.x2:
                    x = dp.x1

            # the two columns of a dual dialogue share the mark
            if (x, t.y) in done:
                continue

            done.add((x, t.y))

            dc.SetTextForeground(
                blendColors(
                    self.cfgGui.textColor,
                    wx.Colour("#" + revisions.levelColor(revisions.lineLevel(ls[i]))),
                    0.5,
                )
            )
            dc.DrawText(rv.markChar, x + markX, t.y)

    # draw a wavy line w pixels wide from x, its bottom at y
    def drawSquiggle(self, dc, x, y, w):
        # the height of the wave, and the width of each half of it
        h = max(1, self.vp.dip(2))
        step = h

        points = []

        for i in range(w // step + 1):
            points.append(wx.Point(x + i * step, y - (h if i % 2 else 0)))

        if len(points) > 1:
            dc.DrawLines(points)

    # return the x offset (pixels) at which to draw character ch in a
    # double-width cell cfx pixels wide, for it to be centered. fx is the
    # width of a narrow (Latin) character in font. wideOffsets caches the
    # offsets of wide characters, which are all the same width, by font.
    @staticmethod
    def cellOffset(dc, font, ch, fx, cfx, wideOffsets):
        if not textutil.isWideChar(ch):
            return (cfx - fx) // 2

        off = wideOffsets.get(id(font))

        if off is None:
            w = dc.GetFullTextExtent(chr(0x4E2D), font)[0]
            off = max(0, (cfx - w) // 2)
            wideOffsets[id(font)] = off

        return off

    # mark each locked page with a lock icon in its right margin, level
    # with the page number, and each scene heading whose number is locked
    # with one in the left margin, left of the scene number. these are
    # only shown on screen. in draft mode, where there are no pages, a
    # locked page's icon goes on the line it starts at.
    def drawLocks(self, dc, strings, dpages, size):
        vp = self.vp
        cfg = vp.sp.cfg
        ls = vp.sp.lines
        mm2p = vp.mm2p

        h = max(6, self.cfgGui.fonts[pml.NORMAL].fy)
        w = h * 3 // 4
        gap = h // 3

        # x offsets (pixels) of the icons from the left edge of the page
        pageX = int((cfg.paperWidth - cfg.marginRight) * mm2p) + gap

        # the left scene number starts 6 characters left of the margin (see
        # screenplay.render.addSceneNumbers)
        sceneX = int((cfg.marginLeft - 6 * vp.chX) * mm2p) - gap - w

        draftX = util.clamp((size.width - vp.pageW) // 2, 0)

        for dp in dpages:
            if ls[vp.sp.page2lines(dp.pageNr)[0]].pageLock:
                self.drawLock(
                    dc, dp.x1 + pageX, dp.y1 + int(cfg.marginTop * mm2p), h, w
                )

        for t in strings:
            i = t.line

            if i == -1:
                continue

            pageLocked = not dpages and ls[i].pageLock
            sceneLocked = vp.sp.getSceneLock(i)

            if not (pageLocked or sceneLocked):
                continue

            x = draftX

            for dp in dpages:
                if dp.x1 <= t.x <= dp.x2:
                    x = dp.x1

            if pageLocked:
                self.drawLock(dc, x + pageX, t.y, h, w)

            if sceneLocked:
                self.drawLock(dc, x + sceneX, t.y, h, w)

    # show each paragraph's notes just outside the page's right edge, from
    # its first line down: each note as a card with the start of its text,
    # pushed down below the card before it where they'd overlap. where
    # there's no room for the cards, as between the pages in side by side
    # mode or in a narrow window, a note icon marks the paragraph instead.
    # remembers where they are for clicks, as (wx.Rect, line, index)
    # tuples in noteMarkers, index being the note's among the paragraph's
    # notes, or None for an icon, and their "resolved" checkboxes in
    # noteChecks. the blank card for a new note (see newNoteLine) has the
    # index the note will have, and no checkbox.
    def drawNoteMarkers(self, dc, strings, dpages, size):
        vp = self.vp
        ls = vp.sp.lines

        # x offset (pixels) of the notes from the page's right edge
        gap = vp.dip(20)

        # in draft mode, the right edge of the infinite page (see paint)
        draftX = util.clamp((size.width - vp.pageW) // 2, 0) + vp.pageW

        dc.SetFont(self.noteFont())
        lineH = dc.GetTextExtent("Ag").height

        # the bottom of the last card beside each page, by its right edge
        bottoms = {}

        for t in strings:
            i = t.line

            if i == -1:
                continue

            notes = ls[i].notes

            if i == self.newNoteLine:
                notes += (Note(""),)

            if not notes:
                continue

            right = draftX

            for dp in dpages:
                if dp.x1 <= t.x <= dp.x2:
                    right = dp.x2

            # the room up to the next page beside this one, or the window's
            # edge
            end = size.width

            for dp in dpages:
                if (dp.x1 > right) and (dp.y1 <= t.y <= dp.y2):
                    end = min(end, dp.x1)

            x = right + gap
            w = min(vp.dip(NOTE_WIDTH), end - x - vp.dip(10))

            if w < vp.dip(NOTE_MIN_WIDTH):
                self.drawNoteIcon(dc, t.y, right, end, i)

                continue

            y = max(t.y, bottoms.get(right, t.y))

            # a line from the paragraph to its first card, which may have
            # been pushed down
            dc.SetPen(wx.Pen(self.noteColors(False)[1]))
            dc.DrawLine(right + 1, t.y + lineH // 2, x, y + lineH // 2)

            for index, note in enumerate(notes):
                # the blank card for a new note has nothing to resolve
                isNew = index == len(ls[i].notes)

                h, check = self.drawNoteCard(dc, x, y, w, lineH, note, not isNew)
                self.noteMarkers.append((wx.Rect(x, y, w, h), i, index))

                if check:
                    self.noteChecks.append((check, i, index))

                y += h + vp.dip(4)

            bottoms[right] = y

    # the font of the notes' text beside the page
    def noteFont(self):
        return wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

    # the (fill, border, text, bar) colors of a note beside the page, in
    # muted colors so that it stays in the background, faded further into
    # the workspace around the pages if 'faded' (it's resolved)
    def noteColors(self, faded):
        cfgGui = self.cfgGui
        bg = cfgGui.workspaceColor
        fill = blendColors(bg, cfgGui.textBgColor, 0.6)
        colors = [
            fill,
            blendColors(bg, cfgGui.textColor, 0.2),
            blendColors(fill, cfgGui.textColor, 0.75),
            blendColors(bg, cfgGui.accentColor, 0.5),
        ]

        if faded:
            colors = [blendColors(c, bg, 0.5) for c in colors]

        return colors

    # draw a card w pixels wide for note, its top left corner at (x, y),
    # with the start of its text: NOTE_LINES lines of lineH pixels, or one
    # for a resolved note, and if 'check', a checkbox at the right of its
    # first line that marks it resolved. returns (its height, the wx.Rect
    # to click for the checkbox, or None).
    def drawNoteCard(self, dc, x, y, w, lineH, note, check=True):
        vp = self.vp
        fill, border, text, bar = self.noteColors(note.resolved)
        padX = vp.dip(12)
        padY = vp.dip(8)
        box = vp.dip(13)
        tw = w - 2 * padX

        if check:
            tw -= box + padX // 2

        lines = []

        for para in note.text.split("\n"):
            lines += wordwrap(para, tw, dc).split("\n")

        if note.resolved:
            lines = [" ".join(note.text.split())]

        maxLines = 1 if note.resolved else NOTE_LINES

        # what doesn't fit is cut off with an ellipsis
        if len(lines) > maxLines:
            last = " ".join(lines[maxLines - 1 :])
            lines = lines[: maxLines - 1] + [last]

        lines[-1] = wx.Control.Ellipsize(lines[-1], dc, wx.ELLIPSIZE_END, tw)

        h = len(lines) * lineH + 2 * padY

        dc.SetPen(wx.Pen(border))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawRoundedRectangle(x, y, w, h, vp.dip(3))

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(bar))
        dc.DrawRectangle(x + 1, y + 1, vp.dip(3), h - 2)

        dc.SetTextForeground(text)

        for k, s in enumerate(lines):
            dc.DrawText(s, x + padX, y + padY + k * lineH)

        if not check:
            return h, None

        bx = x + w - padX - box
        by = y + padY + (lineH - box) // 2
        self.drawCheckBox(dc, bx, by, box, note.resolved, fill, text, bar)

        hit = wx.Rect(bx, by, box, box)
        hit.Inflate(vp.dip(4), vp.dip(4))

        return h, hit

    # draw a checkbox 'size' pixels square, its top left corner at (x, y),
    # on a card filled with 'fill': a box in the card's text color, or
    # filled with 'bar' (the accent color) and ticked if 'checked'
    def drawCheckBox(self, dc, x, y, size, checked, fill, text, bar):
        vp = self.vp

        dc.SetPen(wx.Pen(bar if checked else text))
        dc.SetBrush(wx.Brush(bar if checked else fill))
        dc.DrawRoundedRectangle(x, y, size, size, vp.dip(2))

        if checked:
            dc.SetPen(wx.Pen(fill, max(1, vp.dip(2))))
            dc.DrawLines(
                [
                    wx.Point(x + size * 3 // 13, y + size * 7 // 13),
                    wx.Point(x + size * 5 // 13, y + size * 9 // 13),
                    wx.Point(x + size * 10 // 13, y + size * 4 // 13),
                ]
            )

    # mark the paragraph starting at line i, whose first line is at y on
    # a page whose right edge is at x 'right', with a note icon just
    # outside the page, or as far inside it if there's no room before x
    # 'end' (the next page or the window's edge)
    def drawNoteIcon(self, dc, y, right, end, i):
        vp = self.vp
        ls = vp.sp.lines

        h = max(6, self.cfgGui.fonts[pml.NORMAL].fy)
        w = h + h // 4
        gap = vp.dip(20)

        x = right + gap

        if x + w + gap > end:
            x = right - gap - w

        self.drawNoteMarker(dc, x, y, w, h, all(n.resolved for n in ls[i].notes))
        self.noteMarkers.append((wx.Rect(x, y, w, h), i, None))

    # draw a speech bubble w pixels wide and h high, its top left corner at
    # (x, y), in muted colors so that it stays in the background: a grey
    # outline filled with a tint of the theme's accent color, faded further
    # into the workspace around the pages if 'faded' (all the notes are
    # resolved)
    def drawNoteMarker(self, dc, x, y, w, h, faded):
        cfgGui = self.cfgGui
        bg = cfgGui.workspaceColor
        fill = blendColors(bg, cfgGui.accentColor, 0.3)
        border = blendColors(bg, cfgGui.textColor, 0.4)
        text = border

        if faded:
            fill, border, text = [
                blendColors(c, bg, 0.6) for c in (fill, border, text)
            ]

        bh = h * 3 // 4
        tail = max(2, h // 4)

        dc.SetPen(wx.Pen(border))
        dc.SetBrush(wx.Brush(fill))
        dc.DrawPolygon(
            [
                wx.Point(x + w // 4, y + bh - 1),
                wx.Point(x + w // 4, y + bh + tail),
                wx.Point(x + w // 4 + tail + 1, y + bh - 1),
            ]
        )
        dc.DrawRoundedRectangle(x, y, w, bh, max(1, h // 6))

        # the "text" in it, two lines
        dc.SetPen(wx.Pen(text, max(1, h // 12)))
        lx = x + w // 4
        lw = w - w // 2

        for k in (1, 2):
            ly = y + bh * k // 3
            gutil.drawLine(dc, lx, ly, lw, 0)

    # draw a padlock w pixels wide and h pixels high, with its top left
    # corner at (x, y)
    def drawLock(self, dc, x, y, h, w):
        color = self.cfgGui.textHdrColor

        bodyH = h // 2 + 1
        bodyY = y + h - bodyH

        # the shackle, whose lower half the body covers
        pw = max(1, h // 8)
        sw = w - 2 * max(1, w // 6)
        sx = x + (w - sw) // 2

        dc.SetPen(wx.Pen(color, pw))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(
            sx, y + pw // 2, sw, (bodyY - y - pw // 2) * 2, sw / 2.0
        )

        dc.SetPen(wx.Pen(color))
        dc.SetBrush(wx.Brush(color))
        dc.DrawRoundedRectangle(x, bodyY, w, bodyH, max(1, h // 10))

        # keyhole, when there's room for one
        if h >= 12:
            kw = max(2, w // 6)
            dc.SetPen(self.cfgGui.textBgPen)
            dc.SetBrush(self.cfgGui.textBgBrush)
            dc.DrawRectangle(x + (w - kw) // 2, bodyY + bodyH // 3, kw, bodyH // 3)

    # draw the button that opens the title pages dialog, centered just
    # above the first page (dp), if there's room for it.
    def drawTitleButton(self, dc, dp):
        dc.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))

        text = _("Manage title page")
        tw, th = dc.GetTextExtent(text)

        bw = tw + 40
        bh = th + 16
        x = (dp.x1 + dp.x2 - bw) // 2
        y = dp.y1 - bh - 8

        if y < 0:
            return

        dc.SetPen(self.cfgGui.pageBorderPen)
        dc.SetBrush(self.cfgGui.textBgBrush)
        dc.DrawRoundedRectangle(x, y, bw, bh, 4)

        dc.SetTextForeground(self.cfgGui.textColor)
        dc.DrawText(text, x + (bw - tw) // 2, y + (bh - th) // 2)

        self.titleButtonRect = wx.Rect(x, y, bw, bh)

    # draw the auto-completion list below the cursor line, or above it if
    # there's no room below. posX is where the line's text starts.
    def drawAutoComp(self, dc, posX, cursorY, fi):
        vp = self.vp
        ac = vp.ed.acItems
        asel = vp.ed.acSel

        # space inside the border, around the items
        pad = vp.dip(6)

        # space around an item's text, inside its highlight
        itemPadX = vp.dip(6)
        itemPadY = vp.dip(3)

        # scroll bar width
        sbw = vp.dip(6)

        radius = vp.dip(4)

        size = vp.size

        dc.SetFont(fi.font)

        show = min(vp.ed.acMax, len(ac))
        doSbw = show < len(ac)

        # the items shown scroll a page (show items) at a time: the page
        # with the selected item, except that the last page is moved back
        # to be a full one
        startPos = (asel // show) * show
        endPos = min(startPos + show, len(ac))
        if endPos == len(ac):
            startPos = max(0, endPos - show)

        textW = 0
        for i in range(len(ac)):
            textW = max(textW, dc.GetTextExtent(ac[i])[0])

        itemW = textW + itemPadX * 2
        itemH = fi.fy + itemPadY * 2
        listH = show * itemH

        w = itemW + pad * 2
        h = listH + pad * 2

        if doSbw:
            w += sbw + pad

        # line the items' text up with the line's text, keeping the box
        # inside the window
        posX -= pad + itemPadX
        posX = max(0, min(posX, size.width - w))

        posY = cursorY + fi.fy + vp.dip(4)

        # if the box doesn't fit on the screen in the normal position, put
        # it above the current line. if it doesn't fit there either,
        # that's just too bad, we don't support window sizes that small.
        if (posY + h) > size.height:
            posY = cursorY - h - vp.dip(4)

        cfgGui = self.cfgGui

        dc.SetPen(cfgGui.autoCompBorderPen)
        dc.SetBrush(cfgGui.autoCompBrush)
        dc.DrawRoundedRectangle(posX, posY, w, h, radius)

        dc.SetTextForeground(cfgGui.autoCompFgColor)

        for i in range(startPos, endPos):
            x = posX + pad
            y = posY + pad + (i - startPos) * itemH

            if i == asel:
                dc.SetPen(cfgGui.autoCompSelPen)
                dc.SetBrush(cfgGui.autoCompSelBrush)
                dc.DrawRoundedRectangle(x, y, itemW, itemH, radius - 1)

            dc.DrawText(ac[i], x + itemPadX, y + itemPadY)

        if doSbw:
            dc.SetPen(cfgGui.autoCompBorderPen)
            dc.SetBrush(cfgGui.autoCompBorderBrush)
            dc.DrawRoundedRectangle(
                posX + w - pad - sbw,
                posY + pad + int((float(startPos) / len(ac)) * listH),
                sbw,
                max(sbw, int((float(show) / len(ac)) * listH)),
                sbw // 2,
            )
