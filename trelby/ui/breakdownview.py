# the breakdown tab of the side panel (see sidepanel.py): what the scene at
# the cursor needs for production, by category, or every element in the
# script with how many scenes it's in (see screenplay/breakdown.py).
#
# things are tagged from the script's right-click menu (Tag as), and the +
# button adds an element the scene's text doesn't mention. double-clicking
# an element goes to it (in the whole script view, to the next scene it's
# in), Delete removes it from the scene (or the script), and the
# right-click menu renames it, changes its category or removes it. every
# change is an undoable edit of the script, done through MyCtrl.

import wx
from wx.lib.wordwrap import wordwrap

import trelby.dialogs.breakdowndlg as breakdowndlg
import trelby.screenplay.breakdown as breakdown
import trelby.screenplay.speeches as speeches
import trelby.textutil as textutil
import trelby.ui.gutil as gutil
import trelby.ui.icons as icons
from trelby.screenplay.constants import SCENE
from trelby.ui.scrollbar import ScrollBar
from trelby.ui.theming import blendColors

# the kinds of rows: the scene's heading, a category, an element in it,
# and a message
HEADING, CATEGORY, ELEMENT, MESSAGE = list(range(4))

# what's shown: the scene at the cursor, or the whole script
SCOPE_SCENE, SCOPE_SCRIPT = list(range(2))


# one row of the list. text is what's shown; detail is shown dimmed below
# a heading or right of an element. category is the category's key, and
# name the element's name (for ELEMENT rows). tagged is whether the element
# is tagged (in the scene, in the scene view), as opposed to a speaking
# character counted as cast. scenes is the first lines of the scenes it's
# in (in the whole script view).
class Row:
    def __init__(
        self, kind, text, detail="", category=None, name=None, tagged=True, scenes=()
    ):
        self.kind = kind
        self.text = text
        self.detail = detail
        self.category = category
        self.name = name
        self.tagged = tagged
        self.scenes = list(scenes)

    def key(self):
        return (self.kind, self.category, self.name)

    def __eq__(self, other):
        return isinstance(other, Row) and (
            (self.kind, self.text, self.detail, self.category, self.name)
            + (self.tagged, self.scenes)
            == (other.kind, other.text, other.detail, other.category, other.name)
            + (other.tagged, other.scenes)
        )


# the part of the script (see Screenplay.getBreakdownScenes) the given line
# is in, as (first line, last line)
def sceneOf(sp, line):
    start, end = sp.getSceneIndexesFromLine(line)

    for s, e in sp.getBreakdownScenes():
        if start <= s <= end:
            return (s, e)

    return (start, end)


# the rows for the scene at line
def sceneRows(sp, line, castSpeakers):
    start, end = sceneOf(sp, line)
    sb = None

    for b in sp.getBreakdown(castSpeakers):
        if b.start == start:
            sb = b

            break

    if sb and sb.heading:
        heading = sb.heading

        if sb.number:
            heading = sb.number + "  " + heading
    else:
        heading = _("Before the first scene")

    info = []

    if sb:
        info.append(_("Page {}").format(sb.page))
        info.append(
            _("{} pages").format(breakdown.eighthsText(sb.eighths))
            if sb.eighths > 8
            else _("{} page").format(breakdown.eighthsText(sb.eighths))
        )

    rows = [Row(HEADING, heading, " · ".join(info))]

    tagged = {t.key for i in range(start, end + 1) for t in sp.lines[i].tags}
    elements = sb.elements if sb else {}

    for c in breakdown.CATEGORIES:
        names = elements.get(c.key, [])

        if not names:
            continue

        rows.append(Row(CATEGORY, c.label(), str(len(names)), c.key))

        for name in names:
            isTagged = breakdown.elementKey(c.key, name) in tagged
            rows.append(
                Row(
                    ELEMENT,
                    name,
                    "" if isTagged else _("speaks"),
                    c.key,
                    name,
                    isTagged,
                    [start],
                )
            )

    if len(rows) == 1:
        rows.append(
            Row(
                MESSAGE,
                _(
                    "Nothing tagged in this scene. Select words in the script, "
                    "right-click them and pick Tag as, or add something the "
                    "text doesn't mention with the + button."
                ),
            )
        )

    return rows


# the rows for the whole script
def scriptRows(sp, castSpeakers):
    rows = []
    current = None
    elements = sp.getElementList(castSpeakers)

    for e in elements:
        if e.category != current:
            current = e.category
            count = sum(1 for x in elements if x.category == current)
            rows.append(
                Row(
                    CATEGORY,
                    breakdown.category(current).label(),
                    str(count),
                    current,
                )
            )

        n = len(e.scenes)
        detail = _("1 scene") if n == 1 else _("{} scenes").format(n)
        rows.append(
            Row(ELEMENT, e.name, detail, e.category, e.name, e.tagged, e.scenes)
        )

    if not rows:
        rows.append(
            Row(
                MESSAGE,
                _(
                    "Nothing tagged yet. Select words in the script, right-click "
                    "them and pick Tag as."
                ),
            )
        )

    return rows


class BreakdownList(wx.VListBox):
    def __init__(self, parent):
        wx.VListBox.__init__(self, parent, -1, style=wx.BORDER_NONE)

        # Rows shown
        self.rows = []

        self.normalFont = self.GetFont()
        self.boldFont = self.normalFont.Bold()
        self.smallFont = self.normalFont.Smaller()
        self.smallBoldFont = self.smallFont.Bold()

        # the theme's accent color, for the selection (see
        # BreakdownPanel.applyTheme)
        self.highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        self.pad = self.FromDIP(wx.Size(8, 4))
        self.indent = self.FromDIP(22)
        self.swatch = self.FromDIP(10)
        self.lineHeight = self.GetFullTextExtent("Ag", self.normalFont)[1]
        self.smallHeight = self.GetFullTextExtent("Ag", self.smallFont)[1]

        # the message rows' text wrapped to fit the list, for wrapWidth
        self.wrapCache = {}
        self.wrapWidth = None

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setRows(self, rows):
        self.rows = rows
        self.wrapCache = {}

        # also makes the list re-measure all rows
        self.SetItemCount(len(rows))
        self.Refresh()

    def textWidth(self):
        return max(1, self.GetClientSize().width - 2 * self.pad.x)

    def wrapped(self, n):
        width = self.textWidth()

        if width != self.wrapWidth:
            self.wrapCache = {}
            self.wrapWidth = width

        lines = self.wrapCache.get(n)

        if lines is None:
            dc = wx.ClientDC(self)
            dc.SetFont(self.normalFont)
            lines = wordwrap(self.rows[n].text, width, dc).split("\n")
            self.wrapCache[n] = lines

        return lines

    def OnMeasureItem(self, n):
        kind = self.rows[n].kind

        if kind == HEADING:
            h = self.lineHeight + self.smallHeight + self.pad.y * 3
        elif kind == CATEGORY:
            h = self.smallHeight + self.pad.y * 2 + self.FromDIP(6)
        elif kind == MESSAGE:
            h = len(self.wrapped(n)) * self.lineHeight + self.pad.y * 4
        else:
            h = self.lineHeight + self.pad.y * 2

        return h

    def isSelectable(self, n):
        return 0 <= n < len(self.rows) and self.rows[n].kind == ELEMENT

    def getRowColor(self, n):
        bg = self.GetBackgroundColour()

        if self.IsSelected(n) and self.isSelectable(n):
            return blendColors(bg, self.highlight, 0.2 if self.HasFocus() else 0.1)

        return bg

    def OnDrawBackground(self, dc, rect, n):
        fill = self.getRowColor(n)

        if fill != self.GetBackgroundColour():
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRectangle(rect)

        if self.rows[n].kind == HEADING:
            dc.SetPen(wx.Pen(blendColors(fill, self.GetForegroundColour(), 0.12)))
            y = rect.GetBottom()
            dc.DrawLine(rect.GetLeft(), y, rect.GetRight() + 1, y)

    def OnDrawItem(self, dc, rect, n):
        row = self.rows[n]
        bg = self.getRowColor(n)
        fg = self.GetForegroundColour()
        dim = blendColors(fg, bg, 0.45)
        x = rect.x + self.pad.x
        right = rect.GetRight() - self.pad.x
        y = rect.y + self.pad.y

        if row.kind == HEADING:
            dc.SetFont(self.boldFont)
            dc.SetTextForeground(fg)
            self.drawText(dc, row.text, x, y, right - x)

            dc.SetFont(self.smallFont)
            dc.SetTextForeground(dim)
            self.drawText(dc, row.detail, x, y + self.lineHeight + self.pad.y, right - x)

        elif row.kind == CATEGORY:
            y = rect.GetBottom() - self.pad.y - self.smallHeight
            color = wx.Colour("#" + breakdown.category(row.category).color)

            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(color))
            sy = y + (self.smallHeight - self.swatch) // 2
            dc.DrawRoundedRectangle(x, sy, self.swatch, self.swatch, self.FromDIP(2))

            dc.SetFont(self.smallFont)
            dc.SetTextForeground(dim)
            dw = dc.GetTextExtent(row.detail).width
            dc.DrawText(row.detail, right - dw, y)

            dc.SetFont(self.smallBoldFont)
            dc.SetTextForeground(fg)
            tx = x + self.swatch + self.pad.x
            self.drawText(
                dc, textutil.upper(row.text), tx, y, right - dw - self.pad.x - tx
            )

        elif row.kind == MESSAGE:
            dc.SetFont(self.normalFont)
            dc.SetTextForeground(dim)
            y += self.pad.y

            for s in self.wrapped(n):
                dc.DrawText(s, x, y)
                y += self.lineHeight

        else:
            dc.SetFont(self.smallFont)
            dc.SetTextForeground(dim)
            dw = dc.GetTextExtent(row.detail).width if row.detail else 0

            if dw:
                dc.DrawText(
                    row.detail, right - dw, y + (self.lineHeight - self.smallHeight) // 2
                )

            dc.SetFont(self.normalFont)
            dc.SetTextForeground(fg if row.tagged else dim)
            tx = x + self.indent
            self.drawText(dc, row.text, tx, y, right - dw - self.pad.x - tx)

    # draw s at x, y, cut off with an ellipsis to fit in width
    def drawText(self, dc, s, x, y, width):
        if width <= 0:
            return

        if dc.GetTextExtent(s).width > width:
            s = wx.Control.Ellipsize(s, dc, wx.ELLIPSIZE_END, width)

        dc.DrawText(s, x, y)

    def OnSize(self, event):
        event.Skip()

        if self.textWidth() != self.wrapWidth:
            self.wrapCache = {}
            self.RefreshAll()


class BreakdownPanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms
    REFRESH_DELAY = 300

    # the add button (in self.tools) is made in toolParent, as in the
    # outline (see outline.OutlinePanel)
    def __init__(self, parent, scriptPanel, toolParent=None):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # Rows shown
        self.rows = []

        # SCOPE_SCENE or SCOPE_SCRIPT
        self.scope = SCOPE_SCENE

        # whether the speaking characters are counted as cast
        self.castSpeakers = True

        # True while we change the list's selection ourselves
        self.updating = False

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.tools = wx.Panel(toolParent or self, -1)
        hdr = wx.BoxSizer(wx.HORIZONTAL)

        bitmap = icons.svgBitmap("addscene.svg", wx.Size(16, 16))
        self.addBtn = wx.BitmapButton(self.tools, -1, bitmap, style=wx.BORDER_NONE)
        self.addBtn.SetToolTip(_("Add something to the scene at the cursor"))
        hdr.Add(self.addBtn, 0, wx.ALL, self.FromDIP(2))
        self.tools.SetSizer(hdr)

        if toolParent is None:
            vsizer.Add(self.tools, 0, wx.ALIGN_RIGHT)

        self.scopeChoice = wx.Choice(
            self, -1, choices=[_("This scene"), _("Whole script")]
        )
        self.scopeChoice.SetSelection(self.scope)
        vsizer.Add(self.scopeChoice, 0, wx.EXPAND | wx.ALL, self.FromDIP(6))

        # as in the notes, the list's native scrollbar is hidden past the
        # right edge of listHolder, and scrollBar stands in for it
        self.listHolder = wx.Window(self, -1, style=wx.BORDER_NONE)

        # the rows show the script's text, which is left to right in a
        # right-to-left interface too
        gutil.keepLeftToRight(self.listHolder)

        self.list = BreakdownList(self.listHolder)
        self.scrollBar = ScrollBar(self, self.list)

        lsizer = wx.BoxSizer(wx.HORIZONTAL)
        lsizer.Add(self.listHolder, 1, wx.EXPAND)
        lsizer.Add(self.scrollBar, 0, wx.EXPAND)
        vsizer.Add(lsizer, 1, wx.EXPAND)

        self.SetSizer(vsizer)

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.listHolder.Bind(wx.EVT_SIZE, self.OnListHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.scopeChoice.Bind(wx.EVT_CHOICE, self.OnScope)
        self.list.Bind(wx.EVT_SIZE, self.OnListSize)
        self.list.Bind(wx.EVT_IDLE, self.OnListIdle)
        self.list.Bind(wx.EVT_LISTBOX, self.OnItemSelected)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnItemActivated)
        self.list.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.list.Bind(wx.EVT_SET_FOCUS, self.OnListFocus)
        self.list.Bind(wx.EVT_KILL_FOCUS, self.OnListFocus)
        self.addBtn.Bind(wx.EVT_BUTTON, self.OnAddBtn)

    def getCtrl(self):
        return self.scriptPanel.ctrl

    # use the colors of the theme in the given configgui.ConfigGui, like
    # the notes: the button like the tab bar, and the list like the page
    def applyTheme(self, cfgGui):
        self.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.SetForegroundColour(cfgGui.tabTextColor)

        for w in (self.tools, self.addBtn):
            w.SetBackgroundColour(cfgGui.tabBarBgColor)
            w.SetForegroundColour(cfgGui.tabTextColor)

        self.tools.Refresh()

        self.list.SetBackgroundColour(cfgGui.textBgColor)
        self.list.SetForegroundColour(cfgGui.textColor)
        self.list.highlight = cfgGui.accentColor
        self.listHolder.SetBackgroundColour(cfgGui.textBgColor)
        self.scrollBar.setColors(cfgGui.textBgColor, cfgGui.textColor)

        self.Refresh()

    # size the list to fill listHolder plus its native scrollbar's width,
    # as in the notes
    def layoutList(self):
        lc = self.list
        size = self.listHolder.GetClientSize()
        sbWidth = lc.GetSize().width - lc.GetClientSize().width
        rect = wx.Rect(0, 0, size.width + sbWidth, size.height)

        if lc.GetRect() != rect:
            lc.SetSize(rect)

        self.updateScrollBar()

    # make scrollBar match the list's native scrollbar, and show it only
    # when the list can scroll
    def updateScrollBar(self):
        lc = self.list
        thumb = lc.GetScrollThumb(wx.VERTICAL)

        self.scrollBar.SetScrollbar(
            lc.GetScrollPos(wx.VERTICAL), thumb, lc.GetScrollRange(wx.VERTICAL), thumb
        )

        show = self.scrollBar.canScroll()

        if show != self.scrollBar.IsShown():
            self.scrollBar.Show(show)
            self.Layout()

    def OnListHolderSize(self, event):
        self.layoutList()

    def OnListSize(self, event):
        event.Skip()
        self.layoutList()

    def OnListIdle(self, event):
        event.Skip()
        self.updateScrollBar()

    def OnScroll(self, event):
        self.list.ScrollToRow(self.scrollBar.GetThumbPosition())

    # refresh the list once things have been quiet for a moment
    def scheduleRefresh(self):
        if self.IsShown():
            self.timer.StartOnce(self.REFRESH_DELAY)

    # refresh the list right away
    def refresh(self):
        self.timer.Stop()

        if not self.IsShown():
            return

        ctrl = self.getCtrl()

        if self.scope == SCOPE_SCENE:
            rows = sceneRows(ctrl.sp, ctrl.ed.line, self.castSpeakers)
        else:
            rows = scriptRows(ctrl.sp, self.castSpeakers)

        self.setRows(rows)

    # show 'rows', keeping the selected element selected
    def setRows(self, rows):
        if rows == self.rows:
            return

        sel = self.getSelected()
        self.rows = rows

        self.updating = True

        try:
            self.list.setRows(rows)
            self.select(sel.key() if sel else None)
        finally:
            self.updating = False

    # the selected element's Row, or None
    def getSelected(self):
        idx = self.list.GetSelection()

        if self.list.isSelectable(idx):
            return self.rows[idx]

        return None

    # select the row with the given key, or nothing
    def select(self, key):
        idx = next((i for i, r in enumerate(self.rows) if r.key() == key), -1)

        if idx != self.list.GetSelection():
            self.list.SetSelection(idx)

    def setScope(self, scope):
        if scope != self.scope:
            self.scope = scope
            self.scopeChoice.SetSelection(scope)
            self.refresh()

    def OnScope(self, event):
        self.setScope(self.scopeChoice.GetSelection())

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

        event.Skip()

    def OnListFocus(self, event):
        event.Skip()
        self.list.Refresh()

    # only elements can be selected; a click on another row selects
    # nothing
    def OnItemSelected(self, event):
        if self.updating:
            return

        if not self.list.isSelectable(self.list.GetSelection()):
            self.updating = True

            try:
                self.list.SetSelection(-1)
            finally:
                self.updating = False

    def OnItemActivated(self, event):
        row = self.getSelected()

        if row:
            self.goTo(row)

    def OnKeyDown(self, event):
        kc = event.GetKeyCode()
        row = self.getSelected()

        if (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)) and row:
            self.goTo(row)
        elif (kc == wx.WXK_F2) and row:
            self.rename(row)
        elif (kc in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE)) and row:
            if self.scope == SCOPE_SCENE:
                self.removeFromScene(row)
            else:
                self.removeFromScript(row)
        elif kc == wx.WXK_ESCAPE:
            self.getCtrl().SetFocus()
        else:
            event.Skip()

    # put the cursor on where the element is: in the scene view, the first
    # paragraph of the scene tagged with it (or where the character first
    # speaks), and in the whole script view, the next scene it's in after
    # the cursor's, going round to the first
    def goTo(self, row):
        ctrl = self.getCtrl()
        sp = ctrl.sp

        if self.scope == SCOPE_SCENE:
            start = sceneOf(sp, ctrl.ed.line)[0]
        else:
            cur = sceneOf(sp, ctrl.ed.line)[0]
            later = [s for s in row.scenes if s > cur]
            start = (later or row.scenes or [None])[0]

            if start is None:
                return

        line = self.findLine(sp, row, start)
        ctrl.showLine(line)
        ctrl.SetFocus()

    # the first line in the scene starting at 'start' tagged with the
    # element, or for a speaking character counted as cast, where they
    # first speak there, or else the scene's first line
    def findLine(self, sp, row, start):
        end = sceneOf(sp, start)[1]
        key = breakdown.elementKey(row.category, row.name)

        for i in range(start, end + 1):
            if any(t.key == key for t in sp.lines[i].tags):
                return i

        if row.category == breakdown.CAST:
            for speech in speeches.iterSpeeches(sp):
                if (start <= speech.charLine <= end) and (
                    breakdown.elementKey(breakdown.CAST, speech.name) == key
                ):
                    return speech.charLine

        return start

    def sceneHeading(self):
        ctrl = self.getCtrl()
        start = sceneOf(ctrl.sp, ctrl.ed.line)[0]

        if ctrl.sp.lines[start].lt == SCENE:
            return textutil.upper(ctrl.sp.getElemText(start))

        return _("Before the first scene")

    def addElement(self):
        ctrl = self.getCtrl()
        res = breakdowndlg.askElement(
            self,
            _("Add to scene"),
            self.sceneHeading(),
            ctrl.sp,
            breakdown.CATEGORIES[1].key,
        )

        if res:
            ctrl.addSceneElement(ctrl.ed.line, *res)
            self.setScope(SCOPE_SCENE)
            self.refresh()
            self.select((ELEMENT, res[0], breakdown.cleanName(res[1])))

    def rename(self, row):
        if not row.tagged:
            return

        ctrl = self.getCtrl()
        res = breakdowndlg.askElement(
            self, _("Rename"), None, ctrl.sp, row.category, row.name
        )

        if res and (res != (row.category, row.name)):
            ctrl.renameElement(row.category, row.name, *res)
            self.refresh()

    def changeCategory(self, row, category):
        if category != row.category:
            self.getCtrl().renameElement(row.category, row.name, category, row.name)
            self.refresh()

    def removeFromScene(self, row):
        if row.tagged:
            ctrl = self.getCtrl()
            ctrl.removeElement(row.category, row.name, ctrl.ed.line)
            self.refresh()

    def removeFromScript(self, row):
        if not row.tagged:
            return

        if (
            wx.MessageBox(
                _('Remove "{}" from every scene it\'s tagged in?').format(row.name),
                _("Remove"),
                wx.YES_NO | wx.NO_DEFAULT,
                self,
            )
            == wx.YES
        ):
            self.getCtrl().removeElement(row.category, row.name)
            self.refresh()

    def OnContextMenu(self, event):
        lc = self.list
        pos = event.GetPosition()

        # from the keyboard: use the selected row
        if pos == wx.DefaultPosition:
            idx = lc.GetSelection()
            pos = wx.Point(0, 0)

            if idx != -1:
                rect = lc.GetItemRect(idx)
                pos = wx.Point(rect.x + lc.pad.x, rect.GetBottom())
        else:
            pos = lc.ScreenToClient(pos)
            idx = lc.VirtualHitTest(pos.y)

            if lc.isSelectable(idx):
                lc.SetSelection(idx)

        row = self.rows[idx] if lc.isSelectable(idx) else None

        menu = wx.Menu()
        ids = {}

        def item(key, label, m=menu, enable=True):
            ids[key] = wx.NewIdRef()
            m.Append(ids[key], label).Enable(enable)

        if row:
            item("goto", _("Go to"))
            item("rename", _("Rename..."), enable=row.tagged)

            catMenu = wx.Menu()

            for c in breakdown.CATEGORIES:
                ids["cat-" + c.key] = wx.NewIdRef()
                catMenu.AppendRadioItem(ids["cat-" + c.key], c.label()).Check(
                    c.key == row.category
                )

            menu.AppendSubMenu(catMenu, _("Category")).Enable(row.tagged)

            if self.scope == SCOPE_SCENE:
                item("remove", _("Remove from this scene"), enable=row.tagged)

            item("removeAll", _("Remove from the script..."), enable=row.tagged)

            if not row.tagged:
                menu.AppendSeparator()
                menu.Append(
                    wx.ID_ANY, _("Counted as cast because they speak here")
                ).Enable(False)

            menu.AppendSeparator()

        item("add", _("Add to this scene..."))
        menu.AppendSeparator()

        ids["speakers"] = wx.NewIdRef()
        menu.AppendCheckItem(
            ids["speakers"], _("Count speaking characters as cast")
        ).Check(self.castSpeakers)

        actions = self.scriptPanel.gd.mainFrame.actions
        menu.AppendCheckItem(
            actions["ToggleShowTags"].id, _("Highlight tags in the script")
        ).Check(self.scriptPanel.gd.showTags)

        try:
            sel = lc.GetPopupMenuSelectionFromUser(menu, pos)
        finally:
            menu.Destroy()

        chosen = next((k for k, v in ids.items() if int(v) == sel), None)

        if sel == int(actions["ToggleShowTags"].id):
            self.scriptPanel.gd.mainFrame.OnToggleShowTags()
        elif chosen == "goto":
            self.goTo(row)
        elif chosen == "rename":
            self.rename(row)
        elif chosen and chosen.startswith("cat-"):
            self.changeCategory(row, chosen[4:])
        elif chosen == "remove":
            self.removeFromScene(row)
        elif chosen == "removeAll":
            self.removeFromScript(row)
        elif chosen == "add":
            self.addElement()
        elif chosen == "speakers":
            self.castSpeakers = not self.castSpeakers
            self.refresh()

    def OnAddBtn(self, event):
        self.addElement()
