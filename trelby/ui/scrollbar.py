import wx

from trelby.ui.theming import blendColors


# a scrollbar drawn in the theme's colors, for the places where a native
# one would ignore them. it's vertical unless orient is wx.HORIZONTAL; the
# comments below speak of the vertical one, whose ups are a horizontal
# one's lefts. it has the parts of wx.ScrollBar's interface
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

    def __init__(self, parent, wheelTarget=None, orient=wx.VERTICAL):
        wx.Window.__init__(self, parent, -1, style=wx.BORDER_NONE)

        self.wheelTarget = wheelTarget
        self.vertical = orient != wx.HORIZONTAL

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
        # 1 when paging down, and the mouse's y position (see along)
        self.pageDir = 0
        self.pageY = 0

        self.margin = self.FromDIP(2)
        self.minThumbHeight = self.FromDIP(24)

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        thickness = self.FromDIP(12)
        self.SetMinSize(
            wx.Size(thickness, -1) if self.vertical else wx.Size(-1, thickness)
        )

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

    # the coordinate of point p (a wx.Point or wx.Size) along the
    # scrollbar: y for a vertical one, x for a horizontal one
    def along(self, p):
        return p.y if self.vertical else p.x

    # and across it
    def across(self, p):
        return p.x if self.vertical else p.y

    # return the space the thumb moves in, as (top, height)
    def getTrack(self):
        height = self.along(self.GetClientSize())

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
        width = self.across(self.GetClientSize()) - 2 * self.margin

        if self.vertical:
            return wx.Rect(self.margin, y, width, thumbH)
        else:
            return wx.Rect(y, self.margin, thumbH, width)

    # the thumb's top and height, or None if there's no thumb
    def getThumbSpan(self):
        rect = self.getThumbRect()

        if rect is None:
            return None

        if self.vertical:
            return (rect.y, rect.height)
        else:
            return (rect.x, rect.width)

    # return the position that puts the thumb's top at y
    def pos4y(self, y):
        top, height = self.getTrack()
        free = height - self.getThumbSpan()[1]

        if free <= 0:
            return 0

        return self.clampPos(round((y - top) * self.maxPos() / free))

    def sendEvent(self, eventType):
        event = wx.ScrollEvent(
            eventType,
            self.GetId(),
            self.pos,
            wx.VERTICAL if self.vertical else wx.HORIZONTAL,
        )
        event.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(event)

    # page once towards the mouse, unless the thumb has already reached it
    def page(self):
        span = self.getThumbSpan()

        if span is None:
            return

        if self.pageDir < 0:
            if self.pageY >= span[0]:
                return

            eventType = wx.wxEVT_SCROLL_PAGEUP
        else:
            if self.pageY < span[0] + span[1] - 1:
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
            rect.x,
            rect.y,
            rect.width,
            rect.height,
            self.across(rect.GetSize()) / 2.0,
        )

        # the drawing reaches dc's buffer when gc goes, and the buffer the
        # screen when dc goes, so gc must go first
        del gc
        del dc

    def OnSize(self, event):
        self.Refresh()
        event.Skip()

    def OnLeftDown(self, event):
        rect = self.getThumbRect()

        if rect is None:
            return

        y = self.along(event.GetPosition())
        top = self.getThumbSpan()[0]

        if rect.Contains(event.GetPosition()):
            self.dragOffset = y - top
            self.Refresh()
        else:
            self.pageDir = -1 if y < top else 1
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
            pos = self.pos4y(self.along(event.GetPosition()) - self.dragOffset)

            if pos != self.pos:
                self.pos = pos
                self.Refresh()
                self.sendEvent(wx.wxEVT_SCROLL_THUMBTRACK)
        elif self.pageDir != 0:
            self.pageY = self.along(event.GetPosition())
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
