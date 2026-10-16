import wx

from trelby.ui.gutil import blendColors


# a vertical scrollbar drawn in the theme's colors, for the places where a
# native one would ignore them. it has the parts of wx.ScrollBar's interface
# we use, and sends the same events (EVT_COMMAND_SCROLL catches them all):
# EVT_SCROLL_THUMBTRACK while the thumb is dragged and EVT_SCROLL_THUMBRELEASE
# when it's let go, and EVT_SCROLL_PAGEUP / EVT_SCROLL_PAGEDOWN when the
# track above or below the thumb is clicked, repeating while the button is
# held. mouse wheel events are passed on to wheelTarget, the window the
# scrollbar scrolls, if it's set.
class ScrollBar(wx.Window):

    # how long a click on the track is held before paging repeats, and how
    # often it repeats after that, in ms
    REPEAT_DELAY = 300
    REPEAT_INTERVAL = 50

    def __init__(self, parent, wheelTarget=None):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.wheelTarget = wheelTarget

        # same meanings as in wx.ScrollBar.SetScrollbar
        self.pos = 0
        self.thumbSize = 0
        self.range = 0
        self.pageSize = 0

        self.trackColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_SCROLLBAR)
        self.thumbColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW)
        self.thumbHoverColor = self.thumbColor

        # whether the mouse is over the thumb
        self.hover = False

        # while the thumb is dragged, the mouse's distance from its top
        self.dragOffset = None

        # while the button is held down on the track, -1 when paging up and
        # 1 when paging down, and the mouse's y position
        self.pageDir = 0
        self.pageY = 0

        self.margin = self.FromDIP(2)
        self.minThumbHeight = self.FromDIP(24)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize(wx.Size(self.FromDIP(12), -1))

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeave)
        self.Bind(wx.EVT_MOUSE_CAPTURE_LOST, self.OnCaptureLost)
        self.Bind(wx.EVT_MOUSEWHEEL, self.OnMouseWheel)
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

    # it's used with the mouse only, so Tab skips it
    def AcceptsFocusFromKeyboard(self):
        return False

    # draw on a background of color bg, with the thumb in a shade between
    # bg and fg
    def setColors(self, bg, fg):
        self.trackColor = bg
        self.thumbColor = blendColors(bg, fg, 0.3)
        self.thumbHoverColor = blendColors(bg, fg, 0.45)
        self.Refresh()

    def SetScrollbar(self, position, thumbSize, range, pageSize, refresh=True):
        old = (self.pos, self.thumbSize, self.range, self.pageSize)

        self.thumbSize = thumbSize
        self.range = range
        self.pageSize = pageSize
        self.pos = self.clampPos(position)

        if refresh and (old != (self.pos, self.thumbSize, self.range, self.pageSize)):
            self.Refresh()

    def GetThumbPosition(self):
        return self.pos

    def SetThumbPosition(self, position):
        pos = self.clampPos(position)

        if pos != self.pos:
            self.pos = pos
            self.Refresh()

    def GetThumbSize(self):
        return self.thumbSize

    def GetRange(self):
        return self.range

    def GetPageSize(self):
        return self.pageSize

    def maxPos(self):
        return max(0, self.range - self.thumbSize)

    def clampPos(self, pos):
        return max(0, min(pos, self.maxPos()))

    # whether there's anything to scroll, i.e. whether a thumb is shown
    def canScroll(self):
        return (self.thumbSize > 0) and (self.range > self.thumbSize)

    # return the space the thumb moves in, as (top, height)
    def getTrack(self):
        height = self.GetClientSize().height

        return (self.margin, max(0, height - 2 * self.margin))

    # return the thumb's wx.Rect, or None if there's no thumb. its height
    # is the visible part's share of the track (but at least
    # minThumbHeight), and its top moves over the rest of the track in
    # proportion to pos / maxPos.
    def getThumbRect(self):
        if not self.canScroll():
            return None

        top, height = self.getTrack()
        thumbH = max(
            min(self.minThumbHeight, height), height * self.thumbSize // self.range
        )
        y = top + (height - thumbH) * self.pos // self.maxPos()
        width = self.GetClientSize().width

        return wx.Rect(self.margin, y, width - 2 * self.margin, thumbH)

    # return the position that puts the thumb's top at y
    def pos4y(self, y):
        top, height = self.getTrack()
        free = height - self.getThumbRect().height

        if free <= 0:
            return 0

        return self.clampPos(round((y - top) * self.maxPos() / free))

    def sendEvent(self, eventType):
        event = wx.ScrollEvent(eventType, self.GetId(), self.pos, wx.VERTICAL)
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

    # page once towards the mouse, unless the thumb has already reached it
    def page(self):
        rect = self.getThumbRect()

        if rect is None:
            return

        if self.pageDir < 0:
            if self.pageY >= rect.y:
                return

            eventType = wx.wxEVT_SCROLL_PAGEUP
        else:
            if self.pageY < rect.GetBottom():
                return

            eventType = wx.wxEVT_SCROLL_PAGEDOWN

        pos = self.clampPos(self.pos + self.pageDir * max(1, self.pageSize))

        if pos != self.pos:
            self.pos = pos
            self.Refresh()
            self.sendEvent(eventType)

    def setHover(self, hover):
        if hover != self.hover:
            self.hover = hover
            self.Refresh()

    def endMouseAction(self):
        self.timer.Stop()
        self.pageDir = 0

        if self.dragOffset is not None:
            self.dragOffset = None
            self.Refresh()
            self.sendEvent(wx.wxEVT_SCROLL_THUMBRELEASE)

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.trackColor))
        dc.Clear()

        rect = self.getThumbRect()

        if rect is None:
            return

        if self.hover or (self.dragOffset is not None):
            color = self.thumbHoverColor
        else:
            color = self.thumbColor

        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(color))
        gc.DrawRoundedRectangle(
            rect.x, rect.y, rect.width, rect.height, rect.width / 2.0
        )

    def OnSize(self, event):
        self.Refresh()
        event.Skip()

    def OnLeftDown(self, event):
        rect = self.getThumbRect()

        if rect is None:
            return

        y = event.GetPosition().y

        if rect.Contains(event.GetPosition()):
            self.dragOffset = y - rect.y
            self.Refresh()
        else:
            self.pageDir = -1 if y < rect.y else 1
            self.pageY = y
            self.page()
            self.timer.StartOnce(self.REPEAT_DELAY)

        if not self.HasCapture():
            self.CaptureMouse()

    def OnLeftUp(self, event):
        if self.HasCapture():
            self.ReleaseMouse()

        self.endMouseAction()
        self.setHover(self.isOverThumb(event.GetPosition()))

    def OnMotion(self, event):
        if self.dragOffset is not None:
            pos = self.pos4y(event.GetPosition().y - self.dragOffset)

            if pos != self.pos:
                self.pos = pos
                self.Refresh()
                self.sendEvent(wx.wxEVT_SCROLL_THUMBTRACK)
        elif self.pageDir != 0:
            self.pageY = event.GetPosition().y
        else:
            self.setHover(self.isOverThumb(event.GetPosition()))

    def isOverThumb(self, pos):
        rect = self.getThumbRect()

        return (rect is not None) and rect.Contains(pos)

    def OnLeave(self, event):
        if self.dragOffset is None:
            self.setHover(False)

    def OnCaptureLost(self, event):
        self.endMouseAction()

    def OnTimer(self, event):
        if self.pageDir != 0:
            self.page()
            self.timer.StartOnce(self.REPEAT_INTERVAL)

    def OnMouseWheel(self, event):
        if self.wheelTarget:
            self.wheelTarget.GetEventHandler().ProcessEvent(event)

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

        event.Skip()
