import wx

import trelby.gutil as gutil
import trelby.util as util


# return the character blocks the dialog shows, as a list of (name, list
# of (first, last) code point ranges)
def getBlocks():
    return [
        (_("Latin-1"), [(0x20, 0xFF)]),
        (_("Latin Extended-A"), [(0x100, 0x17F)]),
        (_("Latin Extended-B"), [(0x180, 0x24F)]),
        (_("Greek"), [(0x370, 0x3FF)]),
        (_("Cyrillic"), [(0x400, 0x4FF)]),
        (
            _("Punctuation and symbols"),
            # dashes, quotes, bullets, primes and guillemets; currency
            # signs; ℓ, №, ™ and Ω
            [
                (0x2010, 0x2027),
                (0x2030, 0x203E),
                (0x20A0, 0x20C0),
                (0x2113, 0x2113),
                (0x2116, 0x2116),
                (0x2122, 0x2122),
                (0x2126, 0x2126),
            ],
        ),
    ]


# return the valid input characters of the given block, as a string
def blockChars(ranges):
    return "".join(
        chr(i)
        for first, last in ranges
        for i in range(first, last + 1)
        if util.isValidInputChar(i)
    )


class CharMapDlg(wx.Dialog):
    def __init__(self, parent, ctrl):
        wx.Dialog.__init__(self, parent, -1, _("Character map"))

        self.ctrl = ctrl

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.blockCombo = wx.Choice(self, -1)

        for name, ranges in getBlocks():
            self.blockCombo.Append(name, ranges)

        self.blockCombo.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self.OnBlock, id=self.blockCombo.GetId())
        vsizer.Add(self.blockCombo, 0, wx.BOTTOM, 5)

        self.charMap = MyCharMap(self)
        vsizer.Add(self.charMap)

        hsizer.Add(vsizer)

        self.insertButton = wx.Button(self, -1, _(" Insert character "))
        hsizer.Add(self.insertButton, 0, wx.ALL, 10)
        self.Bind(wx.EVT_BUTTON, self.OnInsert, id=self.insertButton.GetId())
        gutil.btnDblClick(self.insertButton, self.OnInsert)

        util.finishWindow(self, hsizer, 0)

    def OnBlock(self, event):
        self.charMap.setChars(
            blockChars(self.blockCombo.GetClientData(self.blockCombo.GetSelection()))
        )

    def OnInsert(self, event):
        if self.charMap.selected:
            self.ctrl.OnKeyChar(util.MyKeyEvent(ord(self.charMap.selected)))


class MyCharMap(wx.Window):
    def __init__(self, parent):
        wx.Window.__init__(self, parent, -1)

        self.cols = 20

        # the most rows any block needs, which the window is sized for
        blocks = getBlocks()
        maxRows = max(self.rowsFor(blockChars(ranges)) for name, ranges in blocks)

        self.setChars(blockChars(blocks[0][1]))

        # offset of grid
        self.offset = 5

        # size of a single character cell
        self.cellSize = 32

        # size of the zoomed-in character boxes
        self.boxSize = 60

        self.smallFont = util.createPixelFont(
            18, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        self.normalFont = util.createPixelFont(
            self.cellSize - 2, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        self.bigFont = util.createPixelFont(
            self.boxSize - 2, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        util.setWH(
            self,
            self.cols * self.cellSize + 2 * self.offset,
            self.offset + maxRows * self.cellSize + self.boxSize + 15,
        )

    def rowsFor(self, chars):
        return (len(chars) + self.cols - 1) // self.cols

    # show 'chars', the valid characters of a block
    def setChars(self, chars):
        self.chars = chars
        self.rows = self.rowsFor(chars)
        self.selected = None

        self.Refresh(False)

    def OnSize(self, event):
        size = self.GetClientSize()
        self.screenBuf = wx.Bitmap(size.width, size.height)

    def OnLeftDown(self, event):
        pos = event.GetPosition()

        x = (pos.x - self.offset) // self.cellSize
        y = (pos.y - self.offset) // self.cellSize

        self.selected = None

        if (x >= 0) and (x < self.cols) and (y >= 0) and (y <= self.rows):
            i = y * self.cols + x
            if i < len(self.chars):
                self.selected = self.chars[i]

        self.Refresh(False)

    def OnMotion(self, event):
        if event.LeftIsDown():
            self.OnLeftDown(event)

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self, self.screenBuf)

        size = self.GetClientSize()
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.SetPen(wx.WHITE_PEN)
        dc.DrawRectangle(0, 0, size.width, size.height)

        dc.SetPen(wx.BLACK_PEN)
        dc.SetTextForeground(wx.BLACK)

        for y in range(self.rows + 1):
            util.drawLine(
                dc,
                self.offset,
                self.offset + y * self.cellSize,
                self.cols * self.cellSize + 1,
                0,
            )

        for x in range(self.cols + 1):
            util.drawLine(
                dc,
                self.offset + x * self.cellSize,
                self.offset,
                0,
                self.rows * self.cellSize,
            )

        dc.SetFont(self.normalFont)

        for y in range(self.rows):
            for x in range(self.cols):
                i = y * self.cols + x
                if i < len(self.chars):
                    util.drawText(
                        dc,
                        self.chars[i],
                        x * self.cellSize + self.offset + self.cellSize // 2 + 1,
                        y * self.cellSize + self.offset + self.cellSize // 2 + 1,
                        util.ALIGN_CENTER,
                        util.VALIGN_CENTER,
                    )

        y = self.offset + self.rows * self.cellSize
        pad = 5

        if self.selected:
            code = ord(self.selected)

            self.drawCharBox(
                dc, _("Selected:"), self.selected, self.offset, y + pad, 75
            )

            c = util.upper(self.selected)
            if c == self.selected:
                c = util.lower(self.selected)
                if c == self.selected:
                    c = None

            if c:
                self.drawCharBox(
                    dc, _("Opposite case:"), c, self.offset + 150, y + pad, 110
                )

            dc.SetFont(self.smallFont)
            dc.DrawText(
                (_("Character code: %d") % code) + (" (U+%04X)" % code), 360, y + pad
            )

            if code == 32:
                dc.DrawText(_("Normal space"), 360, y + pad + 30)
            elif code == 160:
                dc.DrawText(_("Non-breaking space"), 360, y + pad + 30)

        else:
            dc.SetFont(self.smallFont)
            dc.DrawText(_("Click on a character to select it."), self.offset, y + pad)

    def drawCharBox(self, dc, text, char, x, y, xinc):
        dc.SetFont(self.smallFont)
        dc.DrawText(text, x, y)

        boxX = x + xinc

        dc.DrawRectangle(boxX, y, self.boxSize, self.boxSize)

        dc.SetFont(self.bigFont)
        util.drawText(
            dc,
            char,
            boxX + self.boxSize // 2 + 1,
            y + self.boxSize // 2 + 1,
            util.ALIGN_CENTER,
            util.VALIGN_CENTER,
        )
