import wx


# a status bar drawn in the theme's colors. wx.StatusBar can't be used: the
# native one ignores its colors, and in dark mode wx paints it over anything
# we draw. it has the parts of wx.StatusBar's interface we use, and is
# placed at the bottom of the frame's sizer.
#
# it's divided into fields (see SetFieldsCount), whose texts are drawn
# with lines between the fields, except before the first 'unruled' ones.
class StatusBar(wx.Window):
    def __init__(self, parent, unruled):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.unruled = unruled
        self.SetFieldsCount(1, [-1])

        self.bgColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        self.textColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        self.lineColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW)

        # space between a field's edge and its text
        self.margin = self.FromDIP(4)

        # well taller than the text, so it isn't cramped. about the height
        # of the native one.
        self.SetMinSize(wx.Size(-1, self.GetCharHeight() + self.FromDIP(22)))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setColors(self, bg, text, line):
        self.bgColor = bg
        self.textColor = text
        self.lineColor = line

        for w in self.GetChildren():
            w.SetBackgroundColour(bg)
            w.SetForegroundColour(text)

        self.Refresh()

    # divide the bar into count fields of the given widths, where -1 means
    # taking the space the others leave. clears the fields' texts.
    def SetFieldsCount(self, count, widths):
        self.widths = widths
        self.texts = [""] * count
        self.Refresh()

    def SetStatusText(self, text, i):
        if text != self.texts[i]:
            self.texts[i] = text
            self.RefreshRect(self.GetFieldRect(i))

    def GetStatusText(self, i):
        return self.texts[i]

    def GetFieldsCount(self):
        return len(self.widths)

    # the area of field i, below the line along the bar's top
    def GetFieldRect(self, i):
        size = self.GetClientSize()
        fixed = sum(w for w in self.widths if w != -1)
        stretchCnt = self.widths.count(-1)
        stretchW = max(0, size.width - fixed) // max(1, stretchCnt)

        x = sum(stretchW if w == -1 else w for w in self.widths[:i])
        w = self.widths[i]

        return wx.Rect(x, 1, stretchW if w == -1 else w, size.height - 1)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.bgColor))
        dc.Clear()

        dc.SetPen(wx.Pen(self.lineColor))
        dc.DrawLine(0, 0, self.GetClientSize().width, 0)

        dc.SetFont(self.GetFont())
        dc.SetTextForeground(self.textColor)

        pad = self.FromDIP(5)

        for i in range(len(self.widths)):
            rect = self.GetFieldRect(i)

            if i >= self.unruled:
                dc.DrawLine(rect.x, rect.y + pad, rect.x, rect.GetBottom() - pad)

            text = self.texts[i]

            if text:
                text = wx.Control.Ellipsize(
                    text, dc, wx.ELLIPSIZE_END, rect.width - 2 * self.margin
                )
                h = dc.GetTextExtent(text).height
                dc.DrawText(
                    text, rect.x + self.margin, rect.y + (rect.height - h) // 2
                )

    def OnSize(self, event):
        self.Refresh()
        event.Skip()
