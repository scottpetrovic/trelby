# the notes sidebar: the script's notes (see screenplay/notes.py), one card
# each, in script order. a card shows where its note is (the page and the
# scene, and the start of the paragraph it's on) above the note's text.
#
# selecting a card puts the cursor on the note's paragraph, which the
# script view highlights while the list has the focus. double-click, Enter
# or F2 edits a note in place (Ctrl+Enter or clicking elsewhere finishes,
# Esc cancels), Space marks it resolved or not, and Delete deletes it.
# Edit / Add note (Alt+N) adds one to the paragraph at the cursor. every
# change is an undoable edit of the script, done through MyCtrl.

import bisect

import wx
from wx.lib.wordwrap import wordwrap

import trelby.config as config
import trelby.textutil as textutil
import trelby.ui.gutil as gutil
import trelby.ui.icons as icons
import trelby.ui.widgets as widgets
from trelby.screenplay.notes import Note
from trelby.screenplay.constants import LB_FORCED, LB_LAST
from trelby.ui.scrollbar import ScrollBar
from trelby.ui.theming import blendColors

# how many lines the text field has at least while a note is edited
EDIT_LINES = 4

# how many characters of the paragraph are shown on a card
SNIPPET_LENGTH = 100


# one card of the list: the note at index 'index' of the notes of the
# paragraph starting at 'line', or a new note being written (index None),
# which isn't in the script until it's finished. context and snippet say
# where the note is.
class NoteItem:
    def __init__(self, line, index, note, context, snippet):
        self.line = line
        self.index = index
        self.note = note
        self.context = context
        self.snippet = snippet

    def key(self):
        return (self.line, self.index)

    def __eq__(self, other):
        return isinstance(other, NoteItem) and (
            (self.line, self.index, self.note, self.context, self.snippet)
            == (other.line, other.index, other.note, other.context, other.snippet)
        )


# return what a card for a note on the paragraph starting at 'line' shows
# about where it is: (context, snippet), the snippet being None for a note
# on a scene heading or act break, which the context already shows.
# starts is sp.getOutlineStarts().
def describe(sp, line, starts):
    page = sp.line2pageLabel(line)
    context = _("Page {}").format(page)

    k = bisect.bisect_right(starts, line) - 1

    if k >= 0:
        heading = sp.getElemText(starts[k])

        if sp.cfg.getType(sp.lines[starts[k]].lt).screen.isCaps:
            heading = textutil.upper(heading)

        context += " · " + heading

        if starts[k] == line:
            return context, None

    ls = sp.lines
    s = ""
    i = line

    while len(s) < SNIPPET_LENGTH:
        s += ls[i].text

        if ls[i].lb in (LB_LAST, LB_FORCED):
            break

        s += config.lb2str(ls[i].lb)
        i += 1

    return context, " ".join(s.split())[:SNIPPET_LENGTH]


# return a NoteItem for each of the script's notes, leaving out resolved
# ones unless showResolved is True
def getItems(sp, showResolved):
    starts = sp.getOutlineStarts()
    ret = []

    for line, index, note in sp.getAllNotes():
        if note.resolved and not showResolved:
            continue

        context, snippet = describe(sp, line, starts)
        ret.append(NoteItem(line, index, note, context, snippet))

    return ret


# what the panel says when there are no notes
def emptyMessage():
    return _(
        "No notes yet. Use Edit / Add note (Alt+N) to add one to the "
        "paragraph at the cursor."
    )


# the list of cards
class NotesList(wx.VListBox):
    def __init__(self, parent):
        wx.VListBox.__init__(self, parent, -1, style=wx.BORDER_NONE)

        # NoteItems shown
        self.items = []

        # index of the card whose note is being edited, which is made tall
        # enough for the text field, or None
        self.editRow = None

        self.normalFont = self.GetFont()
        self.italicFont = self.normalFont.Italic()
        self.smallFont = self.normalFont.Smaller()

        # the theme's accent color, for the selection (see
        # NotesPanel.applyTheme)
        self.highlight = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)

        # the color of the bar at the left of each card, like the note
        # markers in the script
        self.barColor = wx.Colour(242, 178, 56)

        self.pad = self.FromDIP(wx.Size(8, 7))
        self.barWidth = self.FromDIP(3)
        self.lineHeight = self.GetFullTextExtent("Ag", self.normalFont)[1]
        self.smallHeight = self.GetFullTextExtent("Ag", self.smallFont)[1]

        # the note texts wrapped to fit the list, for each item index,
        # valid for wrapWidth
        self.wrapCache = {}
        self.wrapWidth = None

        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setItems(self, items):
        self.items = items
        self.wrapCache = {}

        # also makes the list re-measure all rows
        self.SetItemCount(len(items))
        self.Refresh()

    # the x position and width of the text in a row
    def getTextArea(self):
        x = self.barWidth + self.pad.x

        return x, self.GetClientSize().width - x - self.pad.x

    # return item n's note text wrapped to fit the list's width
    def getTextLines(self, n):
        width = self.getTextArea()[1]

        if width != self.wrapWidth:
            self.wrapCache = {}
            self.wrapWidth = width

        lines = self.wrapCache.get(n)

        if lines is None:
            lines = []

            if width > 0:
                dc = wx.ClientDC(self)
                dc.SetFont(self.normalFont)

                for para in self.items[n].note.text.split("\n"):
                    lines += wordwrap(para, width, dc).split("\n")

            self.wrapCache[n] = lines

        return lines

    # y offset of item n's note text in its row: below the context, and the
    # snippet if it has one
    def getTextY(self, n):
        y = self.pad.y + self.smallHeight

        if self.items[n].snippet is not None:
            y += self.lineHeight

        return y

    def OnMeasureItem(self, n):
        lines = len(self.getTextLines(n))

        if n == self.editRow:
            lines = max(lines + 1, EDIT_LINES)

        return self.getTextY(n) + max(1, lines) * self.lineHeight + self.pad.y

    def isHighlighted(self, n):
        return self.IsSelected(n) and self.HasFocus()

    def getRowColor(self, n):
        bg = self.GetBackgroundColour()

        if self.isHighlighted(n) or (n == self.editRow):
            return blendColors(bg, self.highlight, 0.2)
        elif self.IsSelected(n):
            return blendColors(bg, self.highlight, 0.1)

        return bg

    def OnDrawBackground(self, dc, rect, n):
        bg = self.GetBackgroundColour()
        fill = self.getRowColor(n)

        if fill != bg:
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.Brush(fill))
            dc.DrawRectangle(rect)

        bar = self.barColor

        if self.items[n].note.resolved:
            bar = blendColors(bar, bg, 0.6)

        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(bar))
        dc.DrawRectangle(rect.x, rect.y, self.barWidth, rect.height)

        # separator between rows
        dc.SetPen(wx.Pen(blendColors(bg, self.GetForegroundColour(), 0.12)))
        y = rect.GetBottom()
        dc.DrawLine(rect.GetLeft(), y, rect.GetRight() + 1, y)

    def OnDrawItem(self, dc, rect, n):
        it = self.items[n]
        bg = self.getRowColor(n)
        fg = self.GetForegroundColour()
        dim = blendColors(fg, bg, 0.45)

        x, width = self.getTextArea()
        x += rect.x
        y = rect.y + self.pad.y

        # where the note is: the page and scene, with a check mark at the
        # right on resolved notes
        dc.SetFont(self.smallFont)
        dc.SetTextForeground(dim)

        contextW = width

        if it.note.resolved:
            mark = "✓ " + _("Resolved")
            markW = dc.GetTextExtent(mark).width
            dc.DrawText(mark, x + width - markW, y)
            contextW -= markW + self.pad.x

        if contextW > 0:
            dc.DrawText(
                wx.Control.Ellipsize(it.context, dc, wx.ELLIPSIZE_END, contextW), x, y
            )

        # the start of the paragraph the note is on
        if it.snippet is not None:
            dc.SetFont(self.italicFont)
            snippet = "“%s”" % it.snippet if it.snippet else _("(empty)")
            dc.DrawText(
                wx.Control.Ellipsize(snippet, dc, wx.ELLIPSIZE_END, width),
                x,
                y + self.smallHeight,
            )

        if n == self.editRow:
            return

        y = rect.y + self.getTextY(n)

        dc.SetFont(self.normalFont)
        dc.SetTextForeground(dim if it.note.resolved else fg)

        for s in self.getTextLines(n):
            dc.DrawText(s, x, y)
            y += self.lineHeight

    # the rectangle for the text field editing item n's note, in client
    # coordinates
    def getEditRect(self, n):
        rect = self.GetItemRect(n)
        x, width = self.getTextArea()
        y = rect.y + self.getTextY(n)

        return wx.Rect(rect.x + x, y, width, rect.GetBottom() - self.pad.y - y)

    def OnSize(self, event):
        event.Skip()

        # rows' heights depend on how the notes wrap
        if self.getTextArea()[1] != self.wrapWidth:
            self.SetItemCount(len(self.items))
            self.Refresh()


# the side panel with the notes list
class NotesPanel(wx.Panel):

    # how long to wait after the last change before refreshing, in ms
    REFRESH_DELAY = 300

    def __init__(self, parent, scriptPanel):
        wx.Panel.__init__(self, parent, -1)

        # trelbypanel.MyPanel whose script we show
        self.scriptPanel = scriptPanel

        # NoteItems currently shown
        self.items = []

        # whether resolved notes are listed
        self.showResolved = True

        # True while we change the list's selection ourselves, so that we
        # don't mistake it for the user picking a note
        self.updating = False

        # while a note is edited: (NoteItem, wx.TextCtrl), otherwise None
        self.editing = None

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hdr = wx.BoxSizer(wx.HORIZONTAL)

        self.title = wx.StaticText(self, -1, _("Notes"))
        self.title.SetFont(self.title.GetFont().Bold())
        hdr.Add(self.title, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, self.FromDIP(6))

        def addBtn(iconFilename, toolTip):
            bitmap = icons.svgBitmap(iconFilename, wx.Size(16, 16))
            btn = wx.BitmapButton(self, -1, bitmap, style=wx.BORDER_NONE)
            btn.SetToolTip(toolTip)
            hdr.Add(btn, 0, wx.ALL, self.FromDIP(2))

            return btn

        self.addBtn = addBtn(
            "addnote.svg", _("Add a note to the paragraph at the cursor (Alt+N)")
        )
        hdr.AddSpacer(self.FromDIP(6))
        self.closeBtn = addBtn("closepanel.svg", _("Hide the notes"))

        vsizer.Add(hdr, 0, wx.EXPAND)
        self.separator = widgets.Separator(self)
        vsizer.Add(self.separator, 0, wx.EXPAND)

        # as in the outline, the list's native scrollbar is hidden past the
        # right edge of listHolder, and scrollBar stands in for it
        self.listHolder = wx.Window(self, -1, style=wx.BORDER_NONE)

        # the cards show the script's text, which is left to right in a
        # right-to-left interface too
        gutil.keepLeftToRight(self.listHolder)

        self.list = NotesList(self.listHolder)
        self.scrollBar = ScrollBar(self, self.list)

        lsizer = wx.BoxSizer(wx.HORIZONTAL)
        lsizer.Add(self.listHolder, 1, wx.EXPAND)
        lsizer.Add(self.scrollBar, 0, wx.EXPAND)
        vsizer.Add(lsizer, 1, wx.EXPAND)

        # shown instead of the list when there are no notes
        self.emptyText = wx.StaticText(self, -1, emptyMessage())
        vsizer.Add(self.emptyText, 0, wx.EXPAND | wx.ALL, self.FromDIP(10))

        self.SetSizer(vsizer)

        self.timer = wx.Timer(self)

        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind(wx.EVT_SIZE, self.OnPanelSize)
        self.listHolder.Bind(wx.EVT_SIZE, self.OnListHolderSize)
        self.scrollBar.Bind(wx.EVT_COMMAND_SCROLL, self.OnScroll)
        self.list.Bind(wx.EVT_SIZE, self.OnListSize)
        self.list.Bind(wx.EVT_IDLE, self.OnListIdle)
        self.list.Bind(wx.EVT_LISTBOX, self.OnItemSelected)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnItemActivated)
        self.list.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.list.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.list.Bind(wx.EVT_SET_FOCUS, self.OnListFocus)
        self.list.Bind(wx.EVT_KILL_FOCUS, self.OnListFocus)
        self.list.Bind(wx.EVT_MOUSEWHEEL, self.OnListWheel)
        self.addBtn.Bind(wx.EVT_BUTTON, self.OnAddBtn)
        self.closeBtn.Bind(wx.EVT_BUTTON, self.OnClose)

        self.showEmptyText()

    def getCtrl(self):
        return self.scriptPanel.ctrl

    # use the colors of the theme in the given configgui.ConfigGui, like
    # the outline: the header like the tab bar, and the list like the page
    def applyTheme(self, cfgGui):
        self.SetBackgroundColour(cfgGui.tabBarBgColor)
        self.SetForegroundColour(cfgGui.tabTextColor)

        for w in (self.title, self.addBtn, self.closeBtn, self.emptyText):
            w.SetBackgroundColour(cfgGui.tabBarBgColor)
            w.SetForegroundColour(cfgGui.tabTextColor)

        self.separator.applyTheme(cfgGui)

        self.list.SetBackgroundColour(cfgGui.textBgColor)
        self.list.SetForegroundColour(cfgGui.textColor)
        self.list.highlight = cfgGui.accentColor
        self.list.barColor = cfgGui.noteMarkerColor
        self.listHolder.SetBackgroundColour(cfgGui.textBgColor)
        self.scrollBar.setColors(cfgGui.textBgColor, cfgGui.textColor)

        self.Refresh()

    # show the list, or the text saying there are no notes
    def showEmptyText(self):
        empty = not self.items

        if empty == self.emptyText.IsShown():
            return

        self.emptyText.Show(empty)
        self.listHolder.Show(not empty)
        self.scrollBar.Show(not empty)
        self.Layout()

        if empty:
            self.wrapEmptyText()

    def wrapEmptyText(self):
        width = self.GetClientSize().width - self.FromDIP(20)

        if width > 0:
            self.emptyText.SetLabel(emptyMessage())
            self.emptyText.Wrap(width)
            self.Layout()

    def OnPanelSize(self, event):
        event.Skip()

        if self.emptyText.IsShown():
            wx.CallAfter(self.wrapEmptyText)

    # size the list to fill listHolder plus its native scrollbar's width,
    # as in the outline
    def layoutList(self):
        lc = self.list
        size = self.listHolder.GetClientSize()
        sbWidth = lc.GetSize().width - lc.GetClientSize().width
        rect = wx.Rect(0, 0, size.width + sbWidth, size.height)

        if lc.GetRect() != rect:
            lc.SetSize(rect)

        self.updateScrollBar()

    def updateScrollBar(self):
        lc = self.list
        thumb = lc.GetScrollThumb(wx.VERTICAL)

        self.scrollBar.SetScrollbar(
            lc.GetScrollPos(wx.VERTICAL), thumb, lc.GetScrollRange(wx.VERTICAL), thumb
        )

    def OnListHolderSize(self, event):
        self.layoutList()

    def OnListSize(self, event):
        event.Skip()

        # the text field doesn't move with the rows
        self.finishEdit(True)
        self.layoutList()

    def OnListIdle(self, event):
        event.Skip()
        self.updateScrollBar()

    def OnScroll(self, event):
        self.finishEdit(True)
        self.list.ScrollToRow(self.scrollBar.GetThumbPosition())

    def OnListWheel(self, event):
        self.finishEdit(True)
        event.Skip()

    # refresh the list once things have been quiet for a moment
    def scheduleRefresh(self):
        if self.IsShown():
            self.timer.StartOnce(self.REFRESH_DELAY)

    # refresh the list right away
    def refresh(self):
        self.timer.Stop()

        if not self.IsShown():
            return

        # the text field would end up over the wrong card; finishEdit
        # refreshes
        if self.editing:
            return

        self.setItems(getItems(self.getCtrl().sp, self.showResolved))
        self.selectCurrent()

    # show 'items', keeping the selected note selected
    def setItems(self, items):
        if items == self.items:
            return

        sel = self.getSelected()
        self.items = items

        self.updating = True

        try:
            self.list.setItems(items)
            self.select(sel.key() if sel else None)
        finally:
            self.updating = False

        self.showEmptyText()

    # the selected NoteItem, or None
    def getSelected(self):
        idx = self.list.GetSelection()

        return self.items[idx] if 0 <= idx < len(self.items) else None

    # select the item with the given key (see NoteItem.key), or nothing
    # if there's no such item. returns its index, or -1.
    def select(self, key):
        idx = next((i for i, it in enumerate(self.items) if it.key() == key), -1)

        if idx != self.list.GetSelection():
            self.updating = True

            try:
                # also scrolls the item into view
                self.list.SetSelection(idx)
            finally:
                self.updating = False

        return idx

    # select a note on the paragraph with the cursor, unless one is
    # already selected
    def selectCurrent(self):
        ctrl = self.getCtrl()
        line = ctrl.sp.getParaFirstIndexFromLine(ctrl.ed.line)
        sel = self.getSelected()

        if sel and (sel.line == line):
            return

        for it in self.items:
            if it.line == line:
                self.select(it.key())

                return

    # the first line of the paragraph whose note is selected, while the
    # list has the focus, for the script view to highlight it; otherwise
    # None
    def getHighlightLine(self):
        if not self.IsShownOnScreen():
            return None

        if self.editing:
            return self.editing[0].line

        sel = self.getSelected()

        if sel and self.list.HasFocus():
            return sel.line

        return None

    # show and focus the notes of the paragraph starting at line, for a
    # click on its marker in the script
    def showNotesOf(self, line):
        self.refresh()

        for it in self.items:
            if it.line == line:
                self.select(it.key())
                self.list.SetFocus()

                return

    # start writing a new note on the paragraph at the cursor
    def addNote(self):
        self.finishEdit(True)

        ctrl = self.getCtrl()
        sp = ctrl.sp
        line = sp.getParaFirstIndexFromLine(ctrl.ed.line)

        self.refresh()

        context, snippet = describe(sp, line, sp.getOutlineStarts())
        item = NoteItem(line, None, Note(""), context, snippet)

        # after the paragraph's own notes, which are in script order
        pos = len([it for it in self.items if it.line <= line])

        items = list(self.items)
        items.insert(pos, item)
        self.setItems(items)
        self.select(item.key())

        self.startEdit(pos)

    def startEdit(self, idx):
        if not (0 <= idx < len(self.items)):
            return

        self.finishEdit(True)

        item = self.items[idx]
        lc = self.list

        lc.editRow = idx
        lc.SetItemCount(len(self.items))
        lc.SetSelection(idx)
        lc.Refresh()

        ctrl = wx.TextCtrl(
            lc,
            -1,
            item.note.text,
            style=wx.TE_MULTILINE | wx.BORDER_SIMPLE,
        )
        ctrl.SetBackgroundColour(lc.GetBackgroundColour())
        ctrl.SetForegroundColour(lc.GetForegroundColour())
        ctrl.SetFont(lc.normalFont)
        ctrl.SetToolTip(_("Ctrl+Enter or click elsewhere to finish, Esc to cancel"))
        ctrl.SetRect(lc.getEditRect(idx))

        ctrl.Bind(wx.EVT_CHAR_HOOK, self.OnEditKey)
        ctrl.Bind(wx.EVT_KILL_FOCUS, lambda e: self.OnEditKillFocus(e, ctrl))

        self.editing = (item, ctrl)

        ctrl.SetFocus()
        ctrl.SetInsertionPointEnd()

        self.getCtrl().Refresh(False)

    # stop editing a note, if one is being edited, keeping the new text or
    # not. 'refocus' gives the list the focus back. a note left empty is
    # deleted, and a new one isn't added.
    def finishEdit(self, keep, refocus=False):
        if not self.editing:
            return

        item, ctrl = self.editing
        self.editing = None

        text = ctrl.GetValue().replace("\r\n", "\n").strip()

        # this can be called from the control's own event handlers, so
        # it's destroyed later
        ctrl.Hide()
        wx.CallAfter(ctrl.Destroy)

        self.list.editRow = None

        sc = self.getCtrl()
        key = item.key()

        if keep and (item.index is None):
            if text:
                key = sc.addNote(item.line, text)
        elif keep and (text != item.note.text):
            if text:
                sc.setNote(item.line, item.index, item.note.replace(text=text))
            else:
                sc.deleteNote(item.line, item.index)

        # a cancelled new note, and a refill that changed nothing, need
        # the list redone by hand
        self.items = []
        self.refresh()
        self.select(key)

        if refocus:
            self.list.SetFocus()

        sc.Refresh(False)

    def OnEditKey(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.finishEdit(False, True)
        elif event.ControlDown() and (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
            self.finishEdit(True, True)
        else:
            event.Skip()

    # clicking elsewhere ends the editing. it's done after the focus has
    # moved, and only if that control is still being edited with.
    def OnEditKillFocus(self, event, ctrl):
        event.Skip()

        def finish():
            if self.editing and (self.editing[1] is ctrl):
                self.finishEdit(True)

        wx.CallAfter(finish)

    def toggleResolved(self, item):
        if item.index is not None:
            self.getCtrl().setNote(
                item.line,
                item.index,
                item.note.replace(resolved=not item.note.resolved),
            )
            self.refresh()

    def deleteNote(self, item):
        if item.index is None:
            return

        idx = self.items.index(item)
        self.getCtrl().deleteNote(item.line, item.index)
        self.refresh()

        # select the next note, or the last one
        if self.items:
            self.select(self.items[min(idx, len(self.items) - 1)].key())

    def OnTimer(self, event):
        self.refresh()

    def OnDestroy(self, event):
        if event.GetEventObject() is self:
            self.timer.Stop()

        event.Skip()

    # the highlighted paragraph in the script follows the list's focus
    def OnListFocus(self, event):
        event.Skip()
        self.list.Refresh()
        wx.CallAfter(self.refreshScript)

    def refreshScript(self):
        if self:
            self.getCtrl().Refresh(False)

    def OnItemSelected(self, event):
        if self.updating:
            return

        item = self.getSelected()

        if item:
            self.getCtrl().showLine(item.line)

    def OnItemActivated(self, event):
        self.startEdit(event.GetSelection())

    def OnKeyDown(self, event):
        kc = event.GetKeyCode()
        item = self.getSelected()

        if kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_F2):
            self.startEdit(self.list.GetSelection())
        elif (kc in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE)) and item:
            self.deleteNote(item)
        elif (kc == wx.WXK_SPACE) and item:
            self.toggleResolved(item)
        elif kc == wx.WXK_ESCAPE:
            self.getCtrl().SetFocus()
        else:
            event.Skip()

    def OnContextMenu(self, event):
        lc = self.list
        pos = event.GetPosition()

        # from the keyboard: use the selected item
        if pos == wx.DefaultPosition:
            idx = lc.GetSelection()
            pos = wx.Point(0, 0)

            if idx != -1:
                rect = lc.GetItemRect(idx)
                pos = wx.Point(rect.x + lc.pad.x, rect.GetBottom())
        else:
            pos = lc.ScreenToClient(pos)
            idx = lc.VirtualHitTest(pos.y)

            if idx != wx.NOT_FOUND:
                lc.SetSelection(idx)
                self.OnItemSelected(None)

        item = self.items[idx] if 0 <= idx < len(self.items) else None

        menu = wx.Menu()
        editId = wx.NewIdRef()
        resolveId = wx.NewIdRef()
        deleteId = wx.NewIdRef()
        addId = wx.NewIdRef()
        showId = wx.NewIdRef()

        if item:
            menu.Append(editId, _("Edit"))
            if item.note.resolved:
                menu.Append(resolveId, _("Mark as not resolved"))
            else:
                menu.Append(resolveId, _("Mark as resolved"))

            menu.Append(deleteId, _("Delete"))
            menu.AppendSeparator()

        menu.Append(addId, _("Add note at the cursor"))
        menu.AppendCheckItem(showId, _("Show resolved notes")).Check(self.showResolved)

        try:
            sel = lc.GetPopupMenuSelectionFromUser(menu, pos)
        finally:
            menu.Destroy()

        if sel == int(editId):
            self.startEdit(idx)
        elif sel == int(resolveId):
            self.toggleResolved(item)
        elif sel == int(deleteId):
            self.deleteNote(item)
        elif sel == int(addId):
            self.addNote()
        elif sel == int(showId):
            self.showResolved = not self.showResolved
            self.refresh()

    def OnAddBtn(self, event):
        self.addNote()

    def OnClose(self, event):
        self.finishEdit(True)
        self.scriptPanel.gd.mainFrame.setShowNotes(False)
