# controls drawn in the main toolbar.

import wx

import trelby.textfmt as textfmt


# toolbar control showing the element types as a group of toggle buttons,
# with the current element's type selected. 'items' is a list of (lt,
# label) tuples; clicking one calls onSelect(lt). getToolTip(lt) returns
# the tooltip for an item.
class MyElemTypeBar(wx.Control):
    def __init__(self, parent, id, getCfgGui, items, onSelect, getToolTip, height):
        wx.Control.__init__(self, parent, id, style=wx.BORDER_NONE)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.getCfgGui = getCfgGui
        self.items = items
        self.onSelect = onSelect
        self.getToolTip = getToolTip

        # line type of the current element, and indexes of the selected
        # and hovered items (-1 = none)
        self.curLt = None
        self.selected = -1
        self.hover = -1

        # if True, the items are greyed out and clicking them does
        # nothing. unlike a disabled window, this still shows tooltips,
        # which can say why.
        self.disabled = False

        self.font = self.GetFont()
        self.boldFont = self.font.Bold()

        # every item is as wide as its label in bold, so selecting one
        # doesn't shift the others
        padX = self.FromDIP(10)
        self.margin = self.FromDIP(2)

        self.rects = []
        x = self.margin

        for lt, label in items:
            w = self.GetFullTextExtent(label, self.boldFont)[0] + padX * 2
            self.rects.append(wx.Rect(x, self.margin, w, height - self.margin * 2))
            x += w

        size = wx.Size(x + self.margin, height)
        self.SetMinSize(size)
        self.SetSize(size)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)

    def AcceptsFocus(self):
        return False

    def SetValue(self, lt):
        if lt == self.curLt:
            return

        self.curLt = lt
        self.selected = -1

        for i, (itemLt, label) in enumerate(self.items):
            if itemLt == lt:
                self.selected = i

        self.Refresh(False)

    # whether item i is shown highlighted
    def isSelected(self, i):
        return i == self.selected

    # font to draw item i's label in
    def itemFont(self, i, selected):
        return self.boldFont if selected else self.font

    def itemAt(self, pos):
        for i, rect in enumerate(self.rects):
            if rect.Contains(pos):
                return i

        return -1

    def OnLeftDown(self, event):
        i = self.itemAt(event.GetPosition())

        if (i != -1) and not self.disabled:
            self.onSelect(self.items[i][0])

    def OnMotion(self, event):
        i = self.itemAt(event.GetPosition())

        if i != self.hover:
            self.hover = i
            self.SetToolTip(self.getToolTip(self.items[i][0]) if i != -1 else "")
            self.Refresh(False)

    def OnLeave(self, event):
        if self.hover != -1:
            self.hover = -1
            self.Refresh(False)

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()

        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        radius = self.FromDIP(4)
        group = wx.Rect(0, 0, w, h).Deflate(self.margin - 1)

        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(cfgGui.tabBorderPen)
        dc.DrawRoundedRectangle(group, radius)


        inset = self.FromDIP(2)

        for i, rect in enumerate(self.rects):
            label = self.items[i][1]

            # Deflate works in place, and self.rects is also used for
            # hit testing, so deflate a copy
            fillRect = wx.Rect(rect).Deflate(inset)

            if self.isSelected(i):
                dc.SetBrush(cfgGui.accentBrush)
                dc.SetPen(cfgGui.accentPen)
                dc.DrawRoundedRectangle(fillRect, radius - 1)
                dc.SetTextForeground(cfgGui.accentTextColor)
                dc.SetFont(self.itemFont(i, True))
            else:
                if (i == self.hover) and not self.disabled:
                    dc.SetBrush(cfgGui.tabNonActiveBgBrush)
                    dc.SetPen(cfgGui.tabNonActiveBgPen)
                    dc.DrawRoundedRectangle(fillRect, radius - 1)

                if not self.disabled:
                    dc.SetTextForeground(cfgGui.tabTextColor)
                else:
                    dc.SetTextForeground(
                        wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
                    )

                dc.SetFont(self.itemFont(i, False))

            tw, th = dc.GetTextExtent(label)
            dc.DrawText(
                label, rect.x + (rect.width - tw) // 2, rect.y + (rect.height - th) // 2
            )

            # divider between two items that are both unhighlighted
            if (
                (i > 0)
                and not self.isSelected(i - 1)
                and not self.isSelected(i)
                and (self.hover not in (i - 1, i))
            ):
                dc.SetPen(cfgGui.tabBorderPen)
                dy = rect.height // 4
                dc.DrawLine(rect.x, rect.y + dy, rect.x, rect.bottom - dy + 1)


# a vertical line between groups of tools in the toolbar
class MyToolbarDivider(wx.Control):
    def __init__(self, parent, getCfgGui, height):
        wx.Control.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.getCfgGui = getCfgGui

        size = wx.Size(self.FromDIP(13), height)
        self.SetMinSize(size)
        self.SetSize(size)

        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def AcceptsFocus(self):
        return False

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()

        dc = wx.AutoBufferedPaintDC(self)
        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        # halfway between the group borders and the text, so that it
        # stands out in both light and dark themes
        a = cfgGui.tabBorderColor
        b = cfgGui.tabTextColor
        color = wx.Colour(
            (a.Red() + b.Red()) // 2,
            (a.Green() + b.Green()) // 2,
            (a.Blue() + b.Blue()) // 2,
        )

        # a filled rectangle rather than a line, for an exact width
        lw = self.FromDIP(2)
        dy = h // 5
        dc.SetBrush(wx.Brush(color))
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.DrawRectangle((w - lw) // 2, dy, lw, h - dy * 2)


# the toolbar's bold / italic / underline toggles, drawn like the element
# type bar but with any number of items on at once. items are (bit, label)
# tuples, where bit is textfmt.BOLD etc., and each label is drawn in the
# style it stands for. onSelect(bit) is called when one is clicked.
class MyFormatBar(MyElemTypeBar):
    def __init__(self, parent, id, getCfgGui, items, onSelect, getToolTip, height):
        MyElemTypeBar.__init__(
            self, parent, id, getCfgGui, items, onSelect, getToolTip, height
        )

        # bits that are on
        self.style = 0

        self.fonts = {
            textfmt.BOLD: self.boldFont,
            textfmt.ITALIC: self.font.Italic(),
            textfmt.UNDERLINED: self.font.Underlined(),
        }

    def SetValue(self, style):
        if style == self.style:
            return

        self.style = style
        self.Refresh(False)

    # grey the items out or not (see MyElemTypeBar.disabled)
    def setDisabled(self, disabled):
        if disabled == self.disabled:
            return

        self.disabled = disabled
        self.Refresh(False)

        # the tooltip can depend on it
        if self.hover != -1:
            self.SetToolTip(self.getToolTip(self.items[self.hover][0]))

    def isSelected(self, i):
        return not self.disabled and bool(self.style & self.items[i][0])

    def itemFont(self, i, selected):
        return self.fonts.get(self.items[i][0], self.font)
