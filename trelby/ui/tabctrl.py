# the tab bar above the script: the tabs of the open scripts, the "+"
# button after them for a new script, and the button for leaving
# fullscreen mode.

import wx

import trelby.ui.gutil as gutil
import trelby.ui.icons as icons
import trelby.util as util

TAB_BAR_HEIGHT = 30


# Custom "exit fullscreen" button for our tab bar. Used so that we have
# full control over the button's size.
class MyFSButton(wx.Window):
    def __init__(self, parent, id, getCfgGui):
        wx.Window.__init__(self, parent, id, size=(TAB_BAR_HEIGHT, TAB_BAR_HEIGHT))

        self.getCfgGui = getCfgGui
        self.fsImage = icons.getBitmap("trelby/resources/fullscreen.png")

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnMouseDown)

    def OnPaint(self, event):
        cfgGui = self.getCfgGui()
        dc = wx.PaintDC(self)

        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabNonActiveBgBrush)
        dc.SetPen(cfgGui.tabBorderPen)
        dc.DrawRectangle(0, 0, w, h)

        off = (h - self.fsImage.GetHeight()) // 2
        dc.DrawBitmap(self.fsImage, off, off)

    def OnMouseDown(self, event):
        clickEvent = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
        clickEvent.SetEventObject(self)
        self.GetEventHandler().ProcessEvent(clickEvent)


# our own version of a tab control, which exists for two reasons: it does
# not care where it is physically located, which allows us to combine it
# with other controls on a horizontal row, and it consumes less vertical
# space than wx.Notebook. note that this control is divided into two parts,
# MyTabCtrl and MyTabCtrl2, and both must be created.
class MyTabCtrl(wx.Window):
    def __init__(self, parent, id, getCfgGui):
        style = wx.FULL_REPAINT_ON_RESIZE
        wx.Window.__init__(self, parent, id, style=style)

        self.getCfgGui = getCfgGui

        # pages, i.e., [wx.Window, name] lists. note that 'name' must be an
        # Unicode string.
        self.pages = []

        # index of selected page
        self.selected = -1

        # index of first visible tab
        self.firstTab = 0

        # how much padding to leave horizontally at the ends of the
        # control, and within each tab
        self.paddingX = 10

        # width of a single tab
        self.tabWidth = 150

        # x-pos of the center of a tab's close button, relative to the tab
        self.closeX = self.tabWidth - 18

        # width of the "+" button after the last visible tab, and the size
        # of its hover highlight
        self.newTabWidth = 30
        self.newTabSize = 22

        # whether the mouse is over the "+" button
        self.newTabHover = False

        # function to call when the "+" button is clicked
        self.newTabFunc = None

        # width, height, spacing, y-pos of arrows
        self.arrowWidth = 8
        self.arrowHeight = 13
        self.arrowSpacing = 3
        self.arrowY = 5

        # initialized in OnPaint since we don't know our height yet
        self.font = None

        self.SetMinSize(
            wx.Size(
                self.paddingX * 2
                + self.arrowWidth * 2
                + self.arrowSpacing
                + self.tabWidth
                + self.newTabWidth
                + 5,
                TAB_BAR_HEIGHT,
            )
        )

        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDown)
        self.Bind(wx.EVT_MOTION, self.OnMotion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    # get the ctrl that the tabbed windows should use as a parent
    def getTabParent(self):
        return self.ctrl2

    # get page count
    def getPageCount(self):
        return len(self.pages)

    # get selected page index
    def getSelectedPageIndex(self):
        return self.selected

    # get given page
    def getPage(self, i):
        return self.pages[i][0]

    # MyTabCtrl2 uses this to register itself with us
    def add2(self, ctrl2):
        self.ctrl2 = ctrl2

    # add page
    def addPage(self, page, name):
        self.pages.append([page, name])

        # the new page must be given the correct size and position
        self.setPageSizes()
        page.Move(0, 0)

        self.selectPage(len(self.pages) - 1)

    # set all page's sizes
    def setPageSizes(self):
        size = self.ctrl2.GetClientSize()

        # with the position, since in a right-to-left window a size alone
        # keeps the page's distance from the left edge, not the right
        for p in self.pages:
            p[0].SetSize(0, 0, size.width, size.height)

    # select given page
    def selectPage(self, page):
        self.selected = page

        for i in range(len(self.pages)):
            w = self.pages[i][0]

            if i == self.selected:
                w.Show()
            else:
                w.Hide()

        self.pageChangeFunc(self.selected)
        self.makeSelectedTabVisible()
        self.Refresh(False)

    # delete given page
    def deletePage(self, i):
        self.pages[i][0].Destroy()
        del self.pages[i]

        self.selectPage(util.clamp(i, 0, len(self.pages) - 1))

    # try to change the first visible tag by the given amount.
    def scroll(self, delta):
        newFirstTab = self.firstTab + delta

        if (newFirstTab >= 0) and (newFirstTab < len(self.pages)):
            self.firstTab = newFirstTab
            self.Refresh(False)

    # calculate the maximum number of tabs that we could show with our
    # current size.
    def calcMaxVisibleTabs(self):
        w = self.GetClientSize()[0]

        w -= self.paddingX * 2
        w -= self.arrowWidth * 2 + self.arrowSpacing
        w -= self.newTabWidth

        # leave at least 2 pixels between left arrow and last tab
        w -= 2

        w //= self.tabWidth

        # if by some freak accident we're so small that the above results
        # in w being negative or positive but too small, guard against us
        # ever returning < 1.
        return max(1, w)

    # get last visible tab
    def getLastVisibleTab(self):
        return util.clamp(
            self.firstTab + self.calcMaxVisibleTabs() - 1, maxVal=len(self.pages) - 1
        )

    # x-pos of the "+" button's left edge: right after the last visible tab
    def getNewTabX(self):
        return self.paddingX + (self.getLastVisibleTab() - self.firstTab + 1) * (
            self.tabWidth
        )

    # whether x-pos 'x' is on the "+" button
    def isOnNewTab(self, x):
        nx = self.getNewTabX()

        return (x >= nx) and (x < (nx + self.newTabWidth))

    # make sure selected tab is visible
    def makeSelectedTabVisible(self):
        maxTab = self.getLastVisibleTab()

        # if already visible, no need to do anything
        if (self.selected >= self.firstTab) and (self.selected <= maxTab):
            return

        # otherwise, position the selected tab as far right as possible
        self.firstTab = util.clamp(self.selected - self.calcMaxVisibleTabs() + 1, 0)

    # set text for tab 'i' to 's'
    def setTabText(self, i, s):
        self.pages[i][1] = s
        self.Refresh(False)

    # set function to call when page changes. the function gets a single
    # integer argument, the index of the new page.
    def setPageChangedFunc(self, func):
        self.pageChangeFunc = func

    # set function to call, with no arguments, when the "+" button is
    # clicked
    def setNewTabFunc(self, func):
        self.newTabFunc = func

    def OnMotion(self, event):
        self.setNewTabHover(self.isOnNewTab(event.GetPosition().x))
        event.Skip()

    def OnLeaveWindow(self, event):
        self.setNewTabHover(False)
        event.Skip()

    def setNewTabHover(self, hover):
        if hover == self.newTabHover:
            return

        self.newTabHover = hover

        if hover:
            self.SetToolTip(_("New script"))
        else:
            self.UnsetToolTip()

        self.Refresh(False)

    def OnLeftDown(self, event):
        x = event.GetPosition().x

        if x < self.paddingX:
            return

        if self.isOnNewTab(x):
            if self.newTabFunc:
                self.newTabFunc()

            return

        w = self.GetClientSize()[0]

        # start of left arrow
        lx = (
            w
            - 1
            - self.paddingX
            - self.arrowWidth
            - self.arrowSpacing
            - self.arrowWidth
            + 1
        )

        if x < lx:
            page, pageOffset = divmod(x - self.paddingX, self.tabWidth)
            page += self.firstTab

            if page < len(self.pages):
                hitX = pageOffset >= (self.closeX - self.paddingX)

                if hitX:
                    panel = self.pages[page][0]
                    if not panel.ctrl.canBeClosed():
                        return

                    if self.getPageCount() > 1:
                        self.deletePage(page)
                    else:
                        panel.ctrl.createEmptySp()
                        panel.ctrl.updateScreen()
                else:
                    self.selectPage(page)
        else:
            if x < (lx + self.arrowWidth):
                self.scroll(-1)

            # start of right arrow
            rx = lx + self.arrowWidth + self.arrowSpacing

            if (
                (x >= rx)
                and (x < (rx + self.arrowWidth))
                and (self.getLastVisibleTab() < (len(self.pages) - 1))
            ):
                self.scroll(1)

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDCFactory(self)

        cfgGui = self.getCfgGui()

        w, h = self.GetClientSize()

        dc.SetBrush(cfgGui.tabBarBgBrush)
        dc.SetPen(cfgGui.tabBarBgPen)
        dc.DrawRectangle(0, 0, w, h)

        dc.SetPen(cfgGui.tabBorderPen)
        separatorLineThickness = cfgGui.tabBorderPen.GetWidth()
        dc.DrawLine(0, h - separatorLineThickness, w, h - separatorLineThickness)

        xpos = self.paddingX

        # each tab leaves a gap at its right edge, so tabs don't touch
        tabGap = 3
        tabW = self.tabWidth - tabGap
        radius = 5

        if not self.font:
            self.font = gutil.createPixelFont(
                h // 2, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
            )

        dc.SetFont(self.font)
        textH = dc.GetTextExtent("Ag")[1]

        gc = wx.GraphicsContext.Create(dc)
        borderPen = gc.CreatePen(
            wx.GraphicsPenInfo(cfgGui.tabBorderColor, separatorLineThickness)
        )

        maxTab = self.getLastVisibleTab()

        # the tabs' names, as (name, x, y), drawn once gc is gone: in a
        # right-to-left window, what's drawn on dc while there's a
        # GraphicsContext on it isn't mirrored
        names = []

        for i in range(self.firstTab, maxTab + 1):
            p = self.pages[i]
            selected = i == self.selected

            # the selected tab is taller and covers the separator line, so
            # it joins the script below it
            if selected:
                tabY = 2
                bottom = h
                brush = cfgGui.workspaceBrush
            else:
                tabY = 4
                bottom = h - separatorLineThickness
                brush = cfgGui.tabNonActiveBgBrush

            # outline: up the left side, around the rounded top corners,
            # down the right side; the bottom stays open
            path = gc.CreatePath()
            path.MoveToPoint(xpos + 0.5, bottom)
            path.AddArcToPoint(xpos + 0.5, tabY + 0.5, xpos + tabW / 2, tabY + 0.5, radius)
            path.AddArcToPoint(
                xpos + tabW - 0.5, tabY + 0.5, xpos + tabW - 0.5, bottom, radius
            )
            path.AddLineToPoint(xpos + tabW - 0.5, bottom)

            gc.SetBrush(gc.CreateBrush(brush))
            gc.FillPath(path)
            gc.SetPen(borderPen)
            gc.StrokePath(path)

            textY = tabY + (h - tabY - textH) // 2
            names.append((p[1], xpos, tabY, textY))

            # close button; OnLeftDown takes clicks from paddingX left of
            # its center to the end of the tab
            cx = xpos + self.closeX
            cy = textY + textH / 2
            s = 3.5
            gc.SetPen(
                gc.CreatePen(
                    wx.GraphicsPenInfo(cfgGui.tabTextColor, 1.5).Cap(wx.CAP_ROUND)
                )
            )
            gc.StrokeLine(cx - s, cy - s, cx + s, cy + s)
            gc.StrokeLine(cx - s, cy + s, cx + s, cy - s)

            xpos += self.tabWidth

        # the "+" button after the last tab, with a rounded highlight
        # behind it while the mouse is over it
        cx = xpos + self.newTabWidth / 2
        cy = (4 + h) / 2

        if self.newTabHover:
            hs = self.newTabSize
            gc.SetPen(wx.NullGraphicsPen)
            gc.SetBrush(gc.CreateBrush(cfgGui.tabNonActiveBgBrush))
            gc.DrawRoundedRectangle(cx - hs / 2, cy - hs / 2, hs, hs, radius)

        s = 5
        gc.SetPen(
            gc.CreatePen(wx.GraphicsPenInfo(cfgGui.tabTextColor, 1.5).Cap(wx.CAP_ROUND))
        )
        gc.StrokeLine(cx - s, cy, cx + s, cy)
        gc.StrokeLine(cx, cy - s, cx, cy + s)

        del gc

        dc.SetTextForeground(cfgGui.tabTextColor)

        for name, x, tabY, textY in names:
            # clip the text to fit within the tab, leaving room for the
            # close button
            dc.SetClippingRegion(
                x + self.paddingX, tabY, self.closeX - self.paddingX * 2, h - tabY
            )
            dc.DrawText(name, x + self.paddingX, textY)
            dc.DestroyClippingRegion()

        # start of right arrow
        rx = w - 1 - self.paddingX - self.arrowWidth + 1

        if self.firstTab != 0:
            dc.DestroyClippingRegion()
            dc.SetPen(cfgGui.tabTextPen)

            gutil.drawLine(
                dc, rx - self.arrowSpacing - 1, self.arrowY, 0, self.arrowHeight
            )
            gutil.drawLine(
                dc,
                rx - self.arrowSpacing - 2,
                self.arrowY,
                -self.arrowWidth + 1,
                self.arrowHeight // 2 + 1,
            )
            gutil.drawLine(
                dc,
                rx - self.arrowSpacing - self.arrowWidth,
                self.arrowY + self.arrowHeight // 2,
                self.arrowWidth - 1,
                self.arrowHeight // 2 + 1,
            )

        if maxTab < (len(self.pages) - 1):
            dc.DestroyClippingRegion()
            dc.SetPen(cfgGui.tabTextPen)

            gutil.drawLine(dc, rx, self.arrowY, 0, self.arrowHeight)
            gutil.drawLine(
                dc, rx + 1, self.arrowY, self.arrowWidth - 1, self.arrowHeight // 2 + 1
            )
            gutil.drawLine(
                dc,
                rx + 1,
                self.arrowY + self.arrowHeight - 1,
                self.arrowWidth - 1,
                -(self.arrowHeight // 2 + 1),
            )


# second part of MyTabCtrl
class MyTabCtrl2(wx.Window):
    def __init__(self, parent, id, tabCtrl):
        wx.Window.__init__(self, parent, id)

        # MyTabCtrl
        self.tabCtrl = tabCtrl

        self.tabCtrl.add2(self)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def OnEraseBackground(self, event):
        pass

    def OnSize(self, event):
        self.tabCtrl.setPageSizes()

    # we have an OnPaint handler that does nothing in a feeble attempt in
    # trying to make sure that in the cases when this does get called, as
    # little (useless) work as possible is done.
    def OnPaint(self, event):
        wx.PaintDC(self)
