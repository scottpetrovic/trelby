import wx

import trelby.pml as pml
import trelby.util as util

# screen fonts that match the metrics of the PDF fonts
FACE_NAMES = {
    pml.COURIER: "Courier New",
    pml.HELVETICA: "Arial",
    pml.TIMES_ROMAN: "Times New Roman",
}

# distance from the top of the text to its baseline in the PDF output, as
# a fraction of the font size (see pdf.PDFTextOp)
BASELINE = 0.843

# gap around the page, in pixels
MARGIN = 12


# live preview of the current title page. renders the actual text, and
# selects a string when it's clicked.
class TitlesPreview(wx.Window):
    def __init__(self, parent, ctrl, cfg):
        wx.Window.__init__(self, parent, -1, style=wx.FULL_REPAINT_ON_RESIZE)

        self.cfg = cfg
        self.ctrl = ctrl

        # list of (string index, wx.Rect) from the last paint, for hit
        # testing
        self.hitRects = []

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

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

    def OnLeftDown(self, event):
        pos = event.GetPosition()

        for i, rect in reversed(self.hitRects):
            if rect.Contains(pos):
                self.ctrl.selectString(i)

                return

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

        self.hitRects = []

        if self.ctrl.pageIndex == -1:
            return

        # pixels per mm
        scale = w / self.cfg.paperWidth

        page = self.ctrl.titles.pages[self.ctrl.pageIndex]

        for i, ts in enumerate(page):
            self.drawString(gc, ts, i, ox, oy, scale)

    # draw title string 'ts' (index 'i' on the page), with the page at
    # (ox, oy) and 'scale' pixels per mm, and record its bounding box in
    # self.hitRects.
    def drawString(self, gc, ts, i, ox, oy, scale):
        flags = wx.FONTFLAG_DEFAULT

        if ts.isBold:
            flags |= wx.FONTFLAG_BOLD

        if ts.isItalic:
            flags |= wx.FONTFLAG_ITALIC

        if ts.isUnderlined:
            flags |= wx.FONTFLAG_UNDERLINED

        sizeMM = util.getTextHeight(ts.size)
        fontPx = max(1.0, sizeMM * scale)

        gc.SetFont(gc.CreateFont(fontPx, FACE_NAMES[ts.font], flags, wx.BLACK))

        # (x, y, width) of each line, and the box around them all
        lines = []
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

            lines.append((line, xp, yp))

            x1 = min(x1, xp)
            x2 = max(x2, xp + tw)
            y1 = min(y1, oy + y * scale)
            y2 = max(y2, oy + (y + sizeMM) * scale)

            y += sizeMM

        if not lines:
            return

        # make empty strings clickable too
        if x2 - x1 < 6:
            x1 -= 3
            x2 = x1 + 6

        rect = wx.Rect(int(x1) - 2, int(y1) - 1, int(x2 - x1) + 5, int(y2 - y1) + 3)
        self.hitRects.append((i, rect))

        if i == self.ctrl.tsIndex:
            gc.SetPen(wx.Pen(wx.Colour(80, 140, 220)))
            gc.SetBrush(wx.Brush(wx.Colour(80, 140, 220, 45)))
            gc.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

        for line, xp, yp in lines:
            gc.DrawText(line, xp, yp)
