# the main window's status bar (MainStatusBar), and StatusBar, which it's
# built on.

import time

import wx

import trelby.screenplay.revisions as revisions
import trelby.screenplay.scriptformats as scriptformats
import trelby.writinglog as writinglog


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


def formatWordCount(cnt):
    if cnt == 1:
        return _("1 word")

    return _("%s words") % "{:,}".format(cnt)


# a number of pages, to a tenth of a page: "3", "1.5"
def formatPages(pages):
    return ("%.1f" % pages).rstrip("0").rstrip(".")


# what's been written today across all scripts, for the status bar: the
# words or, if inPages, the pages, out of the daily goal unless it's 0
def formatToday(words, pages, goal, inPages):
    if inPages:
        if goal:
            return _("{} / {} pages today").format(formatPages(pages), goal)

        if formatPages(pages) == "1":
            return _("1 page today")

        return _("{} pages today").format(formatPages(pages))

    if goal:
        return _("{} / {} words today").format(
            "{:,}".format(words), "{:,}".format(goal)
        )

    if words == 1:
        return _("1 word today")

    return _("{} words today").format("{:,}".format(words))


# estimated running time, using the usual rule of thumb of one minute of
# screen time per script page
def formatRuntime(minutes):
    if minutes < 60:
        return _("Runtime: ~%d min") % minutes

    return _("Runtime: ~%d h %d min") % divmod(minutes, 60)


# the main window's status bar. a narrow spacer field keeps the text off the
# window's left edge. the help field shows whether the script has been
# autosaved, then come what's been written today in all scripts (see
# writinglog.py), the element types Enter / Tab would create, the
# script's word count and estimated running time, the current page and the
# zoom buttons, which call onAction(name) with the name of the
# menus.Action to run.
class MainStatusBar(StatusBar):
    # the fields
    SB_SPACER = 0
    SB_HELP = 1
    SB_GOAL = 2
    SB_NEXT = 3
    SB_WORDS = 4
    SB_RUNTIME = 5
    SB_PAGE = 6
    SB_ZOOM = 7

    def __init__(self, parent, gd, onAction):
        StatusBar.__init__(self, parent, self.SB_GOAL)

        self.gd = gd

        style = wx.BU_EXACTFIT | wx.BORDER_NONE

        self.zoomOutBtn = wx.Button(self, -1, "\u2212", style=style)
        self.zoomOutBtn.SetToolTip(_("Zoom out"))
        self.zoomOutBtn.Bind(wx.EVT_BUTTON, lambda event: onAction("ZoomOut"))

        self.zoomLevelBtn = wx.Button(self, -1, "", style=style)
        self.zoomLevelBtn.SetToolTip(_("Reset zoom"))
        self.zoomLevelBtn.Bind(wx.EVT_BUTTON, lambda event: onAction("ZoomReset"))

        self.zoomInBtn = wx.Button(self, -1, "+", style=style)
        self.zoomInBtn.SetToolTip(_("Zoom in"))
        self.zoomInBtn.Bind(wx.EVT_BUTTON, lambda event: onAction("ZoomIn"))

        self.zoomBtns = (self.zoomOutBtn, self.zoomLevelBtn, self.zoomInBtn)

        # flat buttons don't look clickable, so they get a hand cursor and
        # are highlighted while hovered
        self.zoomHoverBtn = None

        for btn in self.zoomBtns:
            btn.SetCursor(wx.Cursor(wx.CURSOR_HAND))
            btn.Bind(wx.EVT_ENTER_WINDOW, self.OnZoomButtonHover)
            btn.Bind(wx.EVT_LEAVE_WINDOW, self.OnZoomButtonHover)

        # fixed widths, so nothing shifts as the values change
        pad = self.FromDIP(16)
        btnW = self.FromDIP(24)
        self.zoomOutBtn.SetSize(btnW, -1)
        self.zoomInBtn.SetSize(btnW, -1)
        self.zoomLevelBtn.SetSize(self.GetTextExtent("300%")[0] + pad, -1)

        pageW = self.GetTextExtent(_("Page %d / %d") % (999, 999))[0] + pad

        # the page field's width, which it grows from to fit "(locked)" or
        # the revision (see showScriptState)
        self.pageW = pageW
        self.pad = pad
        zoomW = sum(b.GetSize().width for b in self.zoomBtns) + self.FromDIP(8)
        longest = _("Parenthetical")
        nextW = self.GetTextExtent(_("Enter: %s    Tab: %s") % (longest, longest))[0]
        wordsW = self.GetTextExtent(formatWordCount(999999))[0] + pad
        runtimeW = self.GetTextExtent(formatRuntime(599))[0] + pad
        # wide enough for a sprint's countdown too (see sprinttimer.py)
        goalW = (
            max(
                self.GetTextExtent(formatToday(99999, 0, 99999, False))[0],
                self.GetTextExtent(_("Sprint paused {}  ·  {}").format(
                    "240:00", _("{} / {} words").format("9,999", "9,999")
                ))[0],
            )
            + pad
        )
        widths = [
            self.FromDIP(6),
            -1,
            goalW,
            nextW + pad,
            wordsW,
            runtimeW,
            pageW,
            zoomW,
        ]
        self.SetFieldsCount(len(widths), widths)

        self.Bind(wx.EVT_SIZE, self.OnMainSize)

        # a click on the goal field starts or stops a writing sprint
        self.onAction = onAction
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

        self.updateZoom()

        # the status bar may already have its final size, in which case no
        # size event comes
        wx.CallAfter(self.layoutZoomButtons)

    def OnMainSize(self, event):
        self.layoutZoomButtons()
        event.Skip()

    def OnLeftDown(self, event):
        if self.GetFieldRect(self.SB_GOAL).Contains(event.GetPosition()):
            self.onAction("ToggleSprint")

        event.Skip()

    # the goal field says what a click on it does
    def OnMotion(self, event):
        if self.GetFieldRect(self.SB_GOAL).Contains(event.GetPosition()):
            tip = _("Written today in all scripts. Click to start or stop a writing sprint.")

            if self.GetToolTipText() != tip:
                self.SetToolTip(tip)
                self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        elif self.GetToolTipText():
            self.UnsetToolTip()
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

        event.Skip()

    # place the zoom buttons centered in their field
    def layoutZoomButtons(self):
        rect = self.GetFieldRect(self.SB_ZOOM)
        x = rect.x + (rect.width - sum(b.GetSize().width for b in self.zoomBtns)) // 2

        for btn in self.zoomBtns:
            w = btn.GetSize().width
            btn.SetSize(x, rect.y, w, rect.height)
            x += w

    def OnZoomButtonHover(self, event):
        btn = event.GetEventObject()

        # moving from one button to the next, the next one's enter event
        # can come before this one's leave event
        if event.Entering():
            self.setZoomButtonHover(btn)
        elif btn is self.zoomHoverBtn:
            self.setZoomButtonHover(None)

        event.Skip()

    # highlight the zoom button hovered (None for none), unless it's
    # disabled
    def setZoomButtonHover(self, hovered):
        self.zoomHoverBtn = hovered

        for btn in self.zoomBtns:
            if (btn is hovered) and btn.IsEnabled():
                color = self.gd.cfgGui.tabNonActiveBgColor
            else:
                color = self.bgColor

            if btn.GetBackgroundColour() != color:
                btn.SetBackgroundColour(color)
                btn.Refresh()

    # show the zoom level, and which ways it can still go
    def updateZoom(self):
        zoom = self.gd.currentZoom()
        self.zoomLevelBtn.SetLabel("%d%%" % zoom)
        self.zoomOutBtn.Enable(self.gd.getZoomStep(-1) != zoom)
        self.zoomInBtn.Enable(self.gd.getZoomStep(1) != zoom)

        # a button disabled while hovered gets no leave event, and one
        # enabled under the mouse no enter event
        pos = wx.GetMousePosition()
        hovered = [b for b in self.zoomBtns if b.GetScreenRect().Contains(pos)]
        self.setZoomButtonHover(hovered[0] if hovered else None)

    def applyTheme(self, cfgGui):
        self.setColors(cfgGui.tabBarBgColor, cfgGui.tabTextColor, cfgGui.tabBorderColor)

    # show the state of the script in the trelbyctrl.MyCtrl ctrl: the
    # element types Enter and Tab would create, its length and the page
    # the cursor is on
    def showScript(self, ctrl):
        sp = ctrl.sp
        cur = ctrl.ed.typeFlow()

        if ctrl.ed.tabMakesNew():
            tabNext = cur.newTypeTab
        else:
            tabNext = cur.nextTypeTab

        # in the script's format's names for them (see scriptformats)
        def label(lt):
            return scriptformats.typeLabel(sp.cfg, lt)

        self.SetStatusText(
            _("Enter: %s    Tab: %s") % (label(cur.newTypeEnter), label(tabNext)),
            self.SB_NEXT,
        )

        page = sp.line2pageLabel(ctrl.ed.line)
        pageCnt = sp.line2page(len(sp.lines) - 1)

        if sp.hasPageLocks():
            s = _("Page %s / %d (locked)") % (page, pageCnt)
        else:
            s = _("Page %s / %d") % (page, pageCnt)

        if sp.revisions.active:
            s += "    " + _("{} revision").format(
                revisions.levelName(sp.revisions.level)
            )

        w = max(self.pageW, self.GetTextExtent(s)[0] + self.pad)

        if w != self.widths[self.SB_PAGE]:
            self.widths[self.SB_PAGE] = w
            self.layoutZoomButtons()
            self.Refresh()

        self.SetStatusText(s, self.SB_PAGE)
        self.SetStatusText(formatWordCount(sp.getWordCount()), self.SB_WORDS)
        self.SetStatusText(formatRuntime(round(sp.getPageLength())), self.SB_RUNTIME)
        self.showToday()

    # show what's been written today in all scripts, against the daily goal
    def showToday(self):
        cfgGl = self.gd.cfgGl
        timer = getattr(getattr(self.gd, "mainFrame", None), "sprint", None)

        if timer and timer.isActive():
            self.SetStatusText(timer.statusText(), self.SB_GOAL)

            return

        today = self.gd.writingLog.dayTotal(writinglog.localDay(time.time()))

        self.SetStatusText(
            formatToday(
                today.shownWords(),
                today.shownPages(),
                cfgGl.dailyGoal,
                cfgGl.dailyGoalPages,
            ),
            self.SB_GOAL,
        )

    # show whether the trelbyctrl.MyCtrl ctrl's script has been autosaved
    def showAutosave(self, ctrl):
        if ctrl.autosaveError is not None:
            s = _("Autosave failed: %s") % ctrl.autosaveError
        elif ctrl.autosaveTime is not None:
            s = _("Recovery copy autosaved at %s") % time.strftime(
                "%H:%M", time.localtime(ctrl.autosaveTime)
            )
        else:
            s = ""

        self.SetStatusText(s, self.SB_HELP)
