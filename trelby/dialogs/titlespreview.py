import wx

import trelby.pdf.pml as pml
import trelby.ui.gutil as gutil
import trelby.util as util
from trelby.ui.textedit import TextEdit

# screen fonts that match the metrics of the PDF fonts other than Courier,
# which is the bundled font the PDFs use (gutil.courierFace)
FACE_NAMES = {
    pml.HELVETICA: "Arial",
    pml.TIMES_ROMAN: "Times New Roman",
}


# the screen font face for the given pml font family
def faceName(font):
    if font == pml.COURIER:
        return gutil.courierFace()

    return FACE_NAMES[font]

# distance from the top of the text to its baseline in the PDF output, as
# a fraction of the font size (see pdf.PDFTextOp)
BASELINE = 0.843

# gap around the page, in pixels
MARGIN = 12

# caret blink interval, in milliseconds
BLINK_MS = 530


# layout of one drawn line of a title string, for hit testing and drawing
# the caret and selection
class LineLayout:
    def __init__(self, x, top, bottom, offsets):
        self.x = x
        self.top = top
        self.bottom = bottom

        # x offset from self.x of each caret position on the line, so
        # there's one more of these than there are characters
        self.offsets = offsets

    # column closest to widget x coordinate 'x'
    def colAt(self, x):
        x -= self.x

        return min(range(len(self.offsets)), key=lambda i: abs(self.offsets[i] - x))


# live preview of the current title page. renders the actual text, selects
# a string when it's clicked, and edits the selected string's text in
# place.
class TitlesPreview(wx.Window):
    def __init__(self, parent, ctrl, cfg):
        wx.Window.__init__(
            self, parent, -1, style=wx.FULL_REPAINT_ON_RESIZE | wx.WANTS_CHARS
        )

        # a page, which is left to right in a right-to-left interface too
        gutil.keepLeftToRight(self)

        self.cfg = cfg
        self.ctrl = ctrl

        # list of (string index, wx.Rect, [LineLayout]) from the last
        # paint
        self.layouts = []

        # TextEdit for the selected string, or None
        self.edit = None

        self.caretOn = True
        self.dragging = False

        self.blinkTimer = wx.Timer(self)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_CHAR, self.OnChar)
        self.Bind(wx.EVT_SET_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnFocus)
        self.Bind(wx.EVT_TIMER, self.OnBlink, self.blinkTimer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    # start editing the currently selected string, with the caret at the
    # end of it. call whenever the selection changes.
    def resetEdit(self):
        ts = self.getString()
        self.edit = TextEdit(ts.items) if ts else None
        self.showCaret()

    # select all of the selected string's text, so that typing replaces it
    def selectAllText(self):
        if self.edit:
            self.edit.selectAll()
            self.showCaret()

    def getString(self):
        if (self.ctrl.pageIndex == -1) or (self.ctrl.tsIndex == -1):
            return None

        return self.ctrl.titles.pages[self.ctrl.pageIndex][self.ctrl.tsIndex]

    def getLayout(self, i):
        for idx, rect, lines in self.layouts:
            if idx == i:
                return lines

        return None

    # caret position in the selected string closest to widget point 'pos'
    def posAt(self, pos):
        lines = self.getLayout(self.ctrl.tsIndex)

        if not lines:
            return (0, 0)

        line = len(lines) - 1

        for i, ll in enumerate(lines):
            if pos.y < ll.bottom:
                line = i

                break

        return (line, lines[line].colAt(pos.x))

    # restart the caret blink so that it's visible, and repaint
    def showCaret(self):
        self.caretOn = True

        if self.HasFocus():
            self.blinkTimer.Start(BLINK_MS)

        self.Refresh()

    # the text was changed: store it and update the rest of the dialog
    def textChanged(self):
        self.getString().items = list(self.edit.lines)
        self.ctrl.onTextEdited()
        self.showCaret()

        # paint now, so that the layout used by up/down and clicks is
        # current
        self.Update()

    def OnFocus(self, event):
        if self.HasFocus():
            self.showCaret()
        else:
            self.blinkTimer.Stop()
            self.Refresh()

        event.Skip()

    def OnBlink(self, event):
        self.caretOn = not self.caretOn
        self.Refresh()

    def OnDestroy(self, event):
        self.blinkTimer.Stop()
        event.Skip()

    # return the index of the string at widget point 'pos', or -1. later
    # strings are drawn on top of earlier ones, so they're checked first.
    def hitTest(self, pos):
        for i, rect, lines in reversed(self.layouts):
            if rect.Contains(pos):
                return i

        return -1

    def OnLeftDown(self, event):
        self.SetFocus()

        pos = event.GetPosition()
        i = self.hitTest(pos)

        if i == -1:
            return

        if i != self.ctrl.tsIndex:
            self.ctrl.selectString(i)
            self.edit.setCaret(self.posAt(pos))
        else:
            self.edit.setCaret(self.posAt(pos), event.ShiftDown())

        self.dragging = True
        self.CaptureMouse()
        self.showCaret()

    def OnLeftDClick(self, event):
        pos = event.GetPosition()

        if self.edit and (self.hitTest(pos) == self.ctrl.tsIndex):
            self.edit.selectWord(self.posAt(pos))
            self.showCaret()

    def OnLeftUp(self, event):
        self.stopDrag()

    def OnCaptureLost(self, event):
        self.dragging = False

    def stopDrag(self):
        if self.dragging:
            self.dragging = False

            if self.HasCapture():
                self.ReleaseMouse()

    def OnMotion(self, event):
        pos = event.GetPosition()

        if self.dragging and self.edit and event.LeftIsDown():
            self.edit.setCaret(self.posAt(pos), True)
            self.showCaret()

        cursor = wx.CURSOR_IBEAM if self.hitTest(pos) != -1 else wx.CURSOR_ARROW
        self.SetCursor(wx.Cursor(cursor))

    def OnKeyDown(self, event):
        if not self.edit:
            event.Skip()

            return

        kc = event.GetKeyCode()
        shift = event.ShiftDown()
        ctrl = event.ControlDown() and not event.AltDown()
        ed = self.edit

        if kc == wx.WXK_TAB:
            self.Navigate(not shift)

            return
        elif kc in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT):
            ed.moveLeft(shift, ctrl)
        elif kc in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT):
            ed.moveRight(shift, ctrl)
        elif kc in (wx.WXK_UP, wx.WXK_NUMPAD_UP):
            self.moveVertical(-1, shift)
        elif kc in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN):
            self.moveVertical(1, shift)
        elif kc in (wx.WXK_HOME, wx.WXK_NUMPAD_HOME):
            ed.moveHome(shift, ctrl)
        elif kc in (wx.WXK_END, wx.WXK_NUMPAD_END):
            ed.moveEnd(shift, ctrl)
        elif kc == wx.WXK_BACK:
            ed.backspace()
            self.textChanged()

            return
        elif kc in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            ed.delete()
            self.textChanged()

            return
        elif kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            ed.insert("\n")
            self.textChanged()

            return
        elif ctrl and (kc == ord("A")):
            ed.selectAll()
        elif ctrl and (kc == ord("C")):
            self.copy()

            return
        elif ctrl and (kc == ord("X")):
            if self.copy():
                ed.deleteSelection()
                self.textChanged()

            return
        elif ctrl and (kc == ord("V")):
            self.paste()

            return
        else:
            event.Skip()

            return

        self.showCaret()

    def OnChar(self, event):
        uc = event.GetUnicodeKey()

        # AltGr shows up as Ctrl+Alt on Windows
        if (
            not self.edit
            or (uc == wx.WXK_NONE)
            or (uc < 32)
            or (event.ControlDown() != event.AltDown())
        ):
            event.Skip()

            return

        self.edit.insert(chr(uc))
        self.textChanged()

    # move the caret 'delta' lines up or down, keeping its x position
    def moveVertical(self, delta, extend):
        ed = self.edit
        line, col = ed.caret
        target = line + delta

        if target < 0:
            ed.moveHome(extend, True)

            return

        if target >= len(ed.lines):
            ed.moveEnd(extend, True)

            return

        lines = self.getLayout(self.ctrl.tsIndex)

        if lines and (len(lines) == len(ed.lines)):
            x = lines[line].x + lines[line].offsets[col]
            col = lines[target].colAt(x)

        ed.setCaret((target, col), extend)

    # copy the selected text to the clipboard. returns True if there was
    # something to copy.
    def copy(self):
        s = self.edit.getSelectedText()

        if not s or not wx.TheClipboard.Open():
            return False

        wx.TheClipboard.SetData(wx.TextDataObject(s))
        wx.TheClipboard.Close()

        return True

    def paste(self):
        if not wx.TheClipboard.Open():
            return

        data = wx.TextDataObject()
        ok = wx.TheClipboard.GetData(data)
        wx.TheClipboard.Close()

        if ok:
            self.edit.insert(data.GetText())
            self.textChanged()

    # return (x, y, w, h) of the page in widget coordinates
    def getPageRect(self):
        ww, wh = self.GetClientSize()
        ww = max(1, ww - 2 * MARGIN)
        wh = max(1, wh - 2 * MARGIN)

        aspect = self.cfg.paperWidth / self.cfg.paperHeight

        h = wh
        w = aspect * wh

        if w > ww:
            w = ww
            h = ww / aspect

        x = MARGIN + (ww - w) / 2
        y = MARGIN + (wh - h) / 2

        return (int(x), int(y), int(w), int(h))

    def OnPaint(self, event):
        self.draw(wx.AutoBufferedPaintDC(self))

    def draw(self, dc):
        dc.SetBackground(
            wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_APPWORKSPACE))
        )
        dc.Clear()

        ox, oy, w, h = self.getPageRect()

        gc = wx.GraphicsContext.Create(dc)

        # page with a drop shadow
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 60)))
        gc.DrawRectangle(ox + 3, oy + 3, w, h)

        gc.SetPen(wx.Pen(wx.Colour(160, 160, 160)))
        gc.SetBrush(wx.WHITE_BRUSH)
        gc.DrawRectangle(ox, oy, w, h)

        self.layouts = []

        if self.ctrl.pageIndex == -1:
            return

        # pixels per mm
        scale = w / self.cfg.paperWidth

        page = self.ctrl.titles.pages[self.ctrl.pageIndex]

        for i, ts in enumerate(page):
            self.drawString(gc, ts, i, ox, oy, scale)

    # draw title string 'ts' (index 'i' on the page), with the page at
    # (ox, oy) and 'scale' pixels per mm, and record its layout in
    # self.layouts.
    def drawString(self, gc, ts, i, ox, oy, scale):
        flags = wx.FONTFLAG_DEFAULT

        if ts.isBold:
            flags |= wx.FONTFLAG_BOLD

        if ts.isItalic:
            flags |= wx.FONTFLAG_ITALIC

        if ts.isUnderlined:
            flags |= wx.FONTFLAG_UNDERLINED

        # the font is ts.size points (sizeMM mm) high, as in the PDF, which
        # at 'scale' pixels per mm gives the pixel size CreateFont wants.
        # the layout mirrors TitleString.generatePML.
        sizeMM = util.getTextHeight(ts.size)
        fontPx = max(1.0, sizeMM * scale)

        gc.SetFont(gc.CreateFont(fontPx, faceName(ts.font), flags, wx.BLACK))

        # (text, x, y) of each line, and the box around them all
        lines = []
        layout = []
        x1 = y1 = 1e9
        x2 = y2 = -1e9

        pageW = self.cfg.paperWidth * scale

        y = ts.y

        for line in ts.items:
            tw, th, descent, lead = gc.GetFullTextExtent(line)

            if ts.isCentered:
                xp = pageW / 2 - tw / 2
            else:
                xp = ts.x * scale

                if ts.isRightJustified:
                    xp -= tw

            xp += ox

            # line up the baseline with where the PDF puts it
            baseline = oy + (y + BASELINE * sizeMM) * scale
            yp = baseline - (th - descent)

            top = oy + y * scale
            bottom = oy + (y + sizeMM) * scale

            lines.append((line, xp, yp))
            layout.append(
                LineLayout(xp, top, bottom, [0.0] + gc.GetPartialTextExtents(line))
            )

            x1 = min(x1, xp)
            x2 = max(x2, xp + tw)
            y1 = min(y1, top)
            y2 = max(y2, bottom)

            y += sizeMM

        if not lines:
            return

        # make empty strings clickable too
        if x2 - x1 < 6:
            x1 -= 3
            x2 = x1 + 6

        rect = wx.Rect(int(x1) - 2, int(y1) - 1, int(x2 - x1) + 5, int(y2 - y1) + 3)
        self.layouts.append((i, rect, layout))

        isSelected = i == self.ctrl.tsIndex

        if isSelected:
            gc.SetPen(wx.Pen(wx.Colour(80, 140, 220)))
            gc.SetBrush(wx.Brush(wx.Colour(80, 140, 220, 45)))
            gc.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

            self.drawSelection(gc, layout)

        for line, xp, yp in lines:
            gc.DrawText(line, xp, yp)

        if isSelected:
            self.drawCaret(gc, layout, fontPx)

    # the layout comes from the string's items, the caret and selection
    # from self.edit, which is only replaced by resetEdit. they're only
    # drawn if the two have the same lines, in case they're out of step.
    def drawSelection(self, gc, layout):
        ed = self.edit

        if not ed or not ed.hasSelection() or (len(layout) != len(ed.lines)):
            return

        (l1, c1), (l2, c2) = ed.getSelection()

        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(wx.Colour(80, 140, 220, 110)))

        for line in range(l1, l2 + 1):
            ll = layout[line]
            start = ll.offsets[c1] if line == l1 else 0.0

            if line == l2:
                end = ll.offsets[c2]
            else:
                # show the selected line break
                end = ll.offsets[-1] + (ll.bottom - ll.top) / 3

            gc.DrawRectangle(ll.x + start, ll.top, end - start, ll.bottom - ll.top)

    def drawCaret(self, gc, layout, fontPx):
        ed = self.edit

        if (
            not ed
            or not self.caretOn
            or not self.HasFocus()
            or (len(layout) != len(ed.lines))
        ):
            return

        line, col = ed.caret
        ll = layout[line]
        x = ll.x + ll.offsets[col]

        gc.SetPen(wx.Pen(wx.BLACK, max(1, int(fontPx / 16))))
        gc.StrokeLine(x, ll.top, x, ll.bottom)
