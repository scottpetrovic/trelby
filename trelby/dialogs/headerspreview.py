import wx

import trelby.pdf.pml as pml
import trelby.screenplay as screenplay
import trelby.ui.gutil as gutil
import trelby.util as util
from trelby.dialogs.titlespreview import BASELINE, FACE_NAMES

# gap around the page, in pixels
MARGIN = 12

# sample script text shown below the headers, as (element type, text),
# with None for an empty line
SAMPLE_LINES = [
    (screenplay.ACTION, "Mindy runs away from the dinosaur, but trips on the"),
    (screenplay.ACTION, "power cord. The raptor approaches her slowly."),
    None,
    (screenplay.CHARACTER, "MINDY"),
    (screenplay.DIALOGUE, "Nice dinosaur. Good dinosaur. Who's a"),
    (screenplay.DIALOGUE, "good boy?"),
    None,
    (screenplay.ACTION, "The raptor tilts its head, considering this."),
]


# live preview of the top of a script page with the current headers.
# clicking a header string selects it.
class HeadersPreview(wx.Window):
    def __init__(self, parent, ctrl, cfg):
        wx.Window.__init__(self, parent, -1, style=wx.FULL_REPAINT_ON_RESIZE)

        # a page, which is left to right in a right-to-left interface too
        gutil.keepLeftToRight(self)

        self.cfg = cfg
        self.ctrl = ctrl

        # list of (header index, wx.Rect) from the last paint
        self.rects = []

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    # return the index of the header at widget point 'pos', or -1. later
    # headers are drawn on top of earlier ones, so they're checked first.
    def hitTest(self, pos):
        for i, rect in reversed(self.rects):
            if rect.Contains(pos):
                return i

        return -1

    def OnLeftDown(self, event):
        i = self.hitTest(event.GetPosition())

        if i != -1:
            self.ctrl.selectHeader(i)

    def OnMotion(self, event):
        cursor = (
            wx.CURSOR_HAND if self.hitTest(event.GetPosition()) != -1 else wx.CURSOR_ARROW
        )
        self.SetCursor(wx.Cursor(cursor))

    def OnPaint(self, event):
        self.draw(wx.AutoBufferedPaintDC(self))

    def draw(self, dc):
        dc.SetBackground(
            wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_APPWORKSPACE))
        )
        dc.Clear()

        cfg = self.cfg
        ww, wh = self.GetClientSize()

        # the page fills the width and runs off the bottom, since only its
        # top part is of interest
        w = max(1, ww - 2 * MARGIN)
        h = w * cfg.paperHeight / cfg.paperWidth
        ox = MARGIN
        oy = MARGIN

        # pixels per mm
        scale = w / cfg.paperWidth

        gc = wx.GraphicsContext.Create(dc)

        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 60)))
        gc.DrawRectangle(ox + 3, oy + 3, w, h)

        gc.SetPen(wx.Pen(wx.Colour(160, 160, 160)))
        gc.SetBrush(wx.WHITE_BRUSH)
        gc.DrawRectangle(ox, oy, w, h)

        # margin guides
        pen = wx.Pen(wx.Colour(200, 210, 225), 1, wx.PENSTYLE_SHORT_DASH)
        gc.SetPen(pen)

        left = ox + cfg.marginLeft * scale
        right = ox + (cfg.paperWidth - cfg.marginRight) * scale
        top = oy + cfg.marginTop * scale

        gc.StrokeLine(left, oy, left, wh)
        gc.StrokeLine(right, oy, right, wh)
        gc.StrokeLine(ox, top, ox + w, top)

        fs = cfg.fontSize
        sizeMM = util.getTextHeight(fs)
        fontPx = max(1.0, sizeMM * scale)

        self.rects = []

        for i, hs in enumerate(self.ctrl.headers.hdrs):
            self.drawHeader(gc, hs, i, ox, oy, scale, fontPx)

        # sample text below the headers, as it would appear in the script
        gc.SetFont(
            gc.CreateFont(
                fontPx,
                FACE_NAMES[pml.COURIER],
                wx.FONTFLAG_DEFAULT,
                wx.Colour(150, 150, 150),
            )
        )

        y = cfg.marginTop + self.ctrl.headers.getNrOfLines() * sizeMM

        charW = util.getTextWidth(" ", pml.COURIER, fs)

        for it in SAMPLE_LINES:
            if it:
                lt, text = it
                x = cfg.marginLeft + cfg.getType(lt).indent * charW
                self.drawLine(gc, text, ox + x * scale, oy + y * scale, fontPx)

            y += sizeMM

    # draw 'text' with its top at widget y coordinate 'top', lining up the
    # baseline with where the PDF puts it. returns the text's width.
    def drawLine(self, gc, text, x, top, heightPx):
        tw, th, descent, lead = gc.GetFullTextExtent(text)
        gc.DrawText(text, x, top + BASELINE * heightPx - (th - descent))

        return tw

    # draw header string 'hs' (index 'i'), with the page at (ox, oy) and
    # 'scale' pixels per mm, and record where it is in self.rects.
    def drawHeader(self, gc, hs, i, ox, oy, scale, fontPx):
        flags = wx.FONTFLAG_DEFAULT

        if hs.isBold:
            flags |= wx.FONTFLAG_BOLD

        if hs.isItalic:
            flags |= wx.FONTFLAG_ITALIC

        if hs.isUnderlined:
            flags |= wx.FONTFLAG_UNDERLINED

        gc.SetFont(gc.CreateFont(fontPx, FACE_NAMES[pml.COURIER], flags, wx.BLACK))

        text = hs.getText(self.ctrl.pvars)
        x, y = hs.getPos(self.cfg)

        tw = gc.GetTextExtent(text)[0]
        xp = ox + x * scale

        if hs.align == util.ALIGN_CENTER:
            xp -= tw / 2
        elif hs.align == util.ALIGN_RIGHT:
            xp -= tw

        top = oy + y * scale
        hPx = util.getTextHeight(self.cfg.fontSize) * scale

        # make empty strings clickable too
        bw = max(tw, 6)

        rect = wx.Rect(int(xp) - 2, int(top) - 1, int(bw) + 5, int(hPx) + 3)
        self.rects.append((i, rect))

        if i == self.ctrl.hdrIndex:
            gc.SetPen(wx.Pen(wx.Colour(80, 140, 220)))
            gc.SetBrush(wx.Brush(wx.Colour(80, 140, 220, 45)))
            gc.DrawRectangle(rect.x, rect.y, rect.width, rect.height)

        self.drawLine(gc, text, xp, top, hPx)
