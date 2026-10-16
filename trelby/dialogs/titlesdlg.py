import wx

import trelby.ui.gutil as gutil
import trelby.pdf.pml as pml
import trelby.titles as titles
import trelby.ui.widgets as widgets
import trelby.util as util
from trelby.ui.textedit import TextEdit
from trelby.dialogs.titlespreview import TitlesPreview


class TitlesDlg(wx.Dialog):
    def __init__(self, parent, titlePages, cfg, cfgGl):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Title pages"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.titles = titlePages
        self.cfg = cfg
        self.cfgGl = cfgGl

        self.titles.guessKinds()

        # whether some events are blocked
        self.block = False

        # (TitleString, its original lines, wx.TextCtrl) while its text is
        # being edited in the items list, or None
        self.cellEdit = None

        self.setPage(0)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Items on this page:")),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        hsizer.AddStretchSpacer()

        # pops up a menu of the kinds of strings to add
        self.addBtn = wx.Button(self, -1, _("Add") + " ▾")
        hsizer.Add(self.addBtn)
        self.Bind(wx.EVT_BUTTON, self.OnAddMenu, id=self.addBtn.GetId())

        self.delBtn = gutil.createStockButton(self, _("Delete"))
        hsizer.Add(self.delBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnDeleteString, id=self.delBtn.GetId())
        gutil.btnDblClick(self.delBtn, self.OnDeleteString)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        self.stringsLc = wx.ListCtrl(
            self, -1, size=(200, 150), style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.stringsLc.AppendColumn(_("Type"), width=self.FromDIP(100))
        self.stringsLc.AppendColumn(_("Text"), width=self.FromDIP(240))
        self.stringsLc.Bind(wx.EVT_SIZE, self.OnListSize)
        vsizer.Add(self.stringsLc, 1, wx.EXPAND | wx.TOP, 5)

        tmp = wx.StaticText(
            self,
            -1,
            _("Double-click an item's text, or click it in the preview, to edit it."),
        )
        vsizer.Add(tmp, 0, wx.TOP, 20)

        gsizer = wx.FlexGridSizer(4, 2, 10, 10)

        gsizer.Add(wx.StaticText(self, -1, _("Type:")), 0, wx.ALIGN_CENTER_VERTICAL)

        self.kindChoice = wx.Choice(
            self, -1, choices=[self.kindLabel(k) for k in titles.KINDS]
        )
        self.Bind(wx.EVT_CHOICE, self.OnKind, id=self.kindChoice.GetId())
        gsizer.Add(self.kindChoice)

        gsizer.Add(wx.StaticText(self, -1, _("Format:")), 0, wx.ALIGN_CENTER_VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.boldBtn, self.italicBtn, self.underlinedBtn = (
            widgets.addStyleToggles(self, hsizer, self.OnMisc)
        )

        hsizer.AddSpacer(12)

        self.alignBtns = widgets.addAlignToggles(self, hsizer, self.OnMisc)

        gsizer.Add(hsizer)

        gsizer.Add(
            wx.StaticText(self, -1, _("Font / Size:")), 0, wx.ALIGN_CENTER_VERTICAL
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.fontCombo = wx.ComboBox(self, -1, style=wx.CB_READONLY)

        for it in [
            ("Courier", pml.COURIER),
            ("Helvetica", pml.HELVETICA),
            ("Times-Roman", pml.TIMES_ROMAN),
        ]:
            self.fontCombo.Append(it[0], it[1])

        hsizer.Add(self.fontCombo)
        self.Bind(wx.EVT_COMBOBOX, self.OnMisc, id=self.fontCombo.GetId())

        self.sizeEntry = wx.SpinCtrl(self, -1, size=(60, -1))
        self.sizeEntry.SetRange(4, 288)
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.sizeEntry.GetId())
        self.sizeEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        hsizer.Add(self.sizeEntry, 0, wx.LEFT, 10)

        gsizer.Add(hsizer)

        gsizer.Add(
            wx.StaticText(self, -1, _("X / Y Pos (mm):")), 0, wx.ALIGN_CENTER_VERTICAL
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.xEntry = wx.TextCtrl(self, -1)
        hsizer.Add(self.xEntry)
        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.xEntry.GetId())
        self.yEntry = wx.TextCtrl(self, -1)
        hsizer.Add(self.yEntry, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.yEntry.GetId())

        gsizer.Add(hsizer)

        vsizer.Add(gsizer, 0, wx.TOP, 15)

        # controls on the left, live preview of the page on the right
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        mainSizer.Add(vsizer, 0, wx.EXPAND)

        # page controls above the preview
        pvSizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.addPageBtn = self.addPageButton(hsizer, _("Add page"), self.OnAddPage, 0)
        self.delPageBtn = self.addPageButton(
            hsizer, _("Delete page"), self.OnDeletePage
        )
        self.moveBtn = self.addPageButton(hsizer, _("Move page"), self.OnMovePage)
        self.moveBtn.SetToolTip(_("Move this page one place later"))

        hsizer.AddStretchSpacer()

        self.prevBtn = self.addPageButton(
            hsizer, "◂ " + _("Previous"), self.OnPrevPage, 20
        )

        self.pageLabel = wx.StaticText(self, -1, "", style=wx.ALIGN_CENTER_HORIZONTAL)
        self.pageLabel.SetMinSize(wx.Size(self.FromDIP(90), -1))
        hsizer.Add(self.pageLabel, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        self.nextBtn = self.addPageButton(hsizer, _("Next") + " ▸", self.OnNextPage)

        pvSizer.Add(hsizer, 0, wx.EXPAND)

        self.previewCtrl = TitlesPreview(self, self, self.cfg)
        self.previewCtrl.SetMinSize(wx.Size(380, 480))
        pvSizer.Add(self.previewCtrl, 1, wx.EXPAND | wx.TOP, 5)

        mainSizer.Add(pvSizer, 1, wx.EXPAND | wx.LEFT, 20)

        topSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer.Add(mainSizer, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        topSizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        gutil.finishWindow(self, topSizer)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.Bind(
            wx.EVT_LIST_ITEM_SELECTED, self.OnStringsLc, id=self.stringsLc.GetId()
        )
        self.Bind(
            wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivateItem, id=self.stringsLc.GetId()
        )
        self.stringsLc.Bind(wx.EVT_KEY_DOWN, self.OnListKey)

        # list of widgets that are specific to editing the selected string
        self.widList = [
            self.kindChoice,
            self.xEntry,
            self.yEntry,
            self.fontCombo,
            self.sizeEntry,
            self.boldBtn,
            self.italicBtn,
            self.underlinedBtn,
        ] + list(self.alignBtns.values())

        self.updateGui()

        self.previewCtrl.SetFocus()

    # add a page control button to 'sizer', 'gap' pixels from the
    # previous one, and return it
    def addPageButton(self, sizer, label, handler, gap=10):
        btn = wx.Button(self, -1, label)
        sizer.Add(btn, 0, wx.LEFT, gap)
        self.Bind(wx.EVT_BUTTON, handler, id=btn.GetId())
        gutil.btnDblClick(btn, handler)

        return btn

    def OnOK(self, event):
        self.endCellEdit()
        self.titles.sort()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    # set given page. 'page' can be an invalid value.
    def setPage(self, page):
        # selected page index or -1
        self.pageIndex = -1

        if self.titles.pages:
            self.pageIndex = 0

            if (page >= 0) and (len(self.titles.pages) > page):
                self.pageIndex = page

        # selected string index or -1
        self.tsIndex = -1

        if self.pageIndex == -1:
            return

        if len(self.titles.pages[self.pageIndex]) > 0:
            self.tsIndex = 0

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wxGTK gets stuck in
        # some weird state
        event.Skip()

    # make the text column fill the rest of the list's width
    def OnListSize(self, event):
        lc = self.stringsLc
        lc.SetColumnWidth(1, max(50, lc.GetClientSize().width - lc.GetColumnWidth(0)))
        event.Skip()

    def OnStringsLc(self, event):
        if self.block:
            return

        self.tsIndex = event.GetIndex()
        self.updateStringGui()

    # select row 'i' in the strings list, without handling it as a click
    def selectRow(self, i):
        self.block = True
        self.stringsLc.Select(i)
        self.stringsLc.Focus(i)
        self.block = False

    # select string 'i' on the current page (called when it's clicked in
    # the preview)
    def selectString(self, i):
        self.tsIndex = i
        self.selectRow(i)
        self.updateStringGui()

    # the selected string's text was edited in the preview
    def onTextEdited(self):
        ts = self.titles.pages[self.pageIndex][self.tsIndex]
        self.stringsLc.SetItem(self.tsIndex, 1, "--".join(ts.items))

    # return the name shown for title string kind 'kind'
    def kindLabel(self, kind):
        return {
            titles.TITLE: _("Title"),
            titles.BYLINE: _("Written by"),
            titles.AUTHOR: _("Author"),
            titles.BASED_ON: _("Based on"),
            titles.DRAFT: _("Draft / date"),
            titles.CONTACT: _("Contact"),
            titles.COPYRIGHT: _("Copyright"),
        }.get(kind, _("Text"))

    def OnKind(self, event):
        if (self.tsIndex == -1) or self.block:
            return

        self.setKind(titles.KINDS[self.kindChoice.GetSelection()])

    # set the kind of the selected string
    def setKind(self, kind):
        ts = self.titles.pages[self.pageIndex][self.tsIndex]
        ts.kind = kind
        self.stringsLc.SetItem(self.tsIndex, 0, self.kindLabel(kind))
        self.kindChoice.SetSelection(titles.KINDS.index(kind))

    # an item in the list was double-clicked (or Enter was pressed on it):
    # edit its type or its text, depending on the column
    def OnActivateItem(self, event):
        row = event.GetIndex()
        lc = self.stringsLc

        pos = lc.ScreenToClient(wx.GetMousePosition())
        item, flags, col = lc.HitTestSubItem(pos)

        if (item == row) and (col == 0):
            self.showKindMenu(row)
        else:
            self.editCell(row)

    def OnListKey(self, event):
        if (event.GetKeyCode() == wx.WXK_F2) and (self.tsIndex != -1):
            self.editCell(self.tsIndex)
        else:
            event.Skip()

    # return the rectangle of cell ('row', 'col') in the items list
    def getCellRect(self, row, col):
        rect = wx.Rect()
        self.stringsLc.GetSubItemRect(row, col, rect)

        return rect

    # pop up a menu of kinds over the type cell of 'row'
    def showKindMenu(self, row):
        menu = wx.Menu()

        for kind in titles.KINDS:
            item = menu.AppendRadioItem(wx.ID_ANY, self.kindLabel(kind))
            item.Check(kind == self.titles.pages[self.pageIndex][row].kind)
            self.Bind(wx.EVT_MENU, lambda ev, kind=kind: self.setKind(kind), item)

        rect = self.getCellRect(row, 0)
        self.stringsLc.PopupMenu(menu, rect.GetBottomLeft())
        menu.Destroy()

    # start editing the text of 'row' in place, in a text box over its
    # text cell. Enter or clicking elsewhere keeps the changes, Escape
    # undoes them, and Shift+Enter starts a new line.
    def editCell(self, row):
        self.endCellEdit()

        lc = self.stringsLc
        ts = self.titles.pages[self.pageIndex][row]

        lc.EnsureVisible(row)
        rect = self.getCellRect(row, 1)

        ctrl = wx.TextCtrl(
            lc, -1, style=wx.TE_MULTILINE | wx.TE_NO_VSCROLL | wx.BORDER_SIMPLE
        )
        ctrl.SetFont(lc.GetFont())
        ctrl.SetValue("\n".join(ts.items))
        ctrl.SetPosition(rect.GetTopLeft())

        self.cellEdit = (ts, list(ts.items), ctrl)
        self.sizeCellEditor()

        ctrl.Bind(wx.EVT_TEXT, self.OnCellText)
        ctrl.Bind(wx.EVT_CHAR_HOOK, self.OnCellKey)
        ctrl.Bind(wx.EVT_KILL_FOCUS, self.OnCellKillFocus)

        ctrl.SetFocus()
        ctrl.SelectAll()

    # make the cell editor tall enough for its lines (plus one, for long
    # lines that wrap), but keep it within the list
    def sizeCellEditor(self):
        ts, orig, ctrl = self.cellEdit
        lc = self.stringsLc

        pos = ctrl.GetPosition()
        lines = ctrl.GetValue().count("\n") + 2
        h = ctrl.GetCharHeight() * lines + self.FromDIP(6)

        # cover whole rows, not part of one
        rowH = self.getCellRect(0, 1).height
        h = -(-h // rowH) * rowH

        h = min(h, lc.GetClientSize().height - pos.y)

        ctrl.SetSize(lc.GetClientSize().width - pos.x, h)

    # stop editing a list cell, keeping the changes unless 'cancel' is
    # True. if 'ctrl' is given, only stop if that's the current editor.
    # 'refocus' puts the focus back on the list.
    def endCellEdit(self, cancel=False, ctrl=None, refocus=False):
        if not self.cellEdit or (ctrl and (ctrl is not self.cellEdit[2])):
            return

        ts, orig, ctrl = self.cellEdit
        self.cellEdit = None

        if cancel:
            ts.items = orig

        self.cellTextChanged(ts)

        # can't destroy it while it's handling an event
        ctrl.Hide()
        wx.CallAfter(lambda: ctrl and ctrl.Destroy())

        if refocus:
            self.stringsLc.SetFocus()

    def OnCellText(self, event):
        if not self.cellEdit:
            return

        ts, orig, ctrl = self.cellEdit

        # filter the text the same way as editing in the preview does
        ed = TextEdit([""])
        ed.insert(ctrl.GetValue())
        ts.items = ed.lines

        self.cellTextChanged(ts)
        self.sizeCellEditor()

    # the text of 'ts' was changed in the list: update the preview, and the
    # list row once the editor covering it is gone
    def cellTextChanged(self, ts):
        page = self.titles.pages[self.pageIndex]

        if (ts in page) and not self.cellEdit:
            self.stringsLc.SetItem(page.index(ts), 1, "--".join(ts.items))

        self.previewCtrl.resetEdit()

    def OnCellKey(self, event):
        kc = event.GetKeyCode()

        if kc == wx.WXK_ESCAPE:
            self.endCellEdit(cancel=True, refocus=True)
        elif (kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)) and not event.ShiftDown():
            self.endCellEdit(refocus=True)
        else:
            event.Skip()

    def OnCellKillFocus(self, event):
        ctrl = event.GetEventObject()
        wx.CallAfter(lambda: self and self.endCellEdit(ctrl=ctrl))
        event.Skip()

    def OnAddPage(self, event):
        self.titles.pages.append([])
        self.setPage(len(self.titles.pages) - 1)

        self.updateGui()

    def OnDeletePage(self, event):
        del self.titles.pages[self.pageIndex]
        self.setPage(0)

        self.updateGui()

    def OnMovePage(self, event):
        newIndex = (self.pageIndex + 1) % len(self.titles.pages)

        self.titles.pages[self.pageIndex], self.titles.pages[newIndex] = (
            self.titles.pages[newIndex],
            self.titles.pages[self.pageIndex],
        )

        self.setPage(newIndex)

        self.updateGui()

    def OnPrevPage(self, event):
        self.setPage((self.pageIndex - 1) % len(self.titles.pages))

        self.updateGui()

    def OnNextPage(self, event):
        self.setPage((self.pageIndex + 1) % len(self.titles.pages))

        self.updateGui()

    def OnAddMenu(self, event):
        menu = wx.Menu()

        for kind in titles.KINDS:
            item = menu.Append(wx.ID_ANY, self.kindLabel(kind))
            self.Bind(wx.EVT_MENU, lambda ev, kind=kind: self.addString(kind), item)

        rect = self.addBtn.GetRect()
        self.PopupMenu(menu, rect.GetBottomLeft())
        menu.Destroy()

    # add a new string of the given kind to the current page
    def addString(self, kind):
        if self.pageIndex == -1:
            return

        page = self.titles.pages[self.pageIndex]
        ts = titles.makeString(kind, self.cfg.paperWidth, self.cfg.paperHeight)

        # don't put it right on top of an existing string
        while any(abs(o.y - ts.y) < 1.0 for o in page):
            ts.y += util.getTextHeight(ts.size)

        page.append(ts)
        self.tsIndex = len(page) - 1

        self.updateGui()

        # so that typing replaces the placeholder text
        self.previewCtrl.SetFocus()
        self.previewCtrl.selectAllText()

    def OnDeleteString(self, event):
        if (self.pageIndex == -1) or (self.tsIndex == -1):
            return

        del self.titles.pages[self.pageIndex][self.tsIndex]
        self.tsIndex = min(self.tsIndex, len(self.titles.pages[self.pageIndex]) - 1)

        self.updateGui()

    # update page/string listboxes and selection
    def updateGui(self):
        self.block = True
        self.stringsLc.DeleteAllItems()
        self.block = False

        pgCnt = len(self.titles.pages)

        self.delPageBtn.Enable(pgCnt > 0)
        self.moveBtn.Enable(pgCnt > 1)
        self.prevBtn.Enable(pgCnt > 1)
        self.nextBtn.Enable(pgCnt > 1)

        if self.pageIndex != -1:
            page = self.titles.pages[self.pageIndex]

            self.pageLabel.SetLabel("Page: %d / %d" % (self.pageIndex + 1, pgCnt))
            self.addBtn.Enable(True)
            self.delBtn.Enable(len(page) > 0)

            for s in page:
                row = self.stringsLc.GetItemCount()
                self.stringsLc.InsertItem(row, self.kindLabel(s.kind))
                self.stringsLc.SetItem(row, 1, "--".join(s.items))

            if self.tsIndex != -1:
                self.selectRow(self.tsIndex)
        else:
            self.pageLabel.SetLabel(_("No pages."))
            self.addBtn.Disable()
            self.delBtn.Disable()

        self.updateStringGui()

        self.previewCtrl.Refresh()

    # update selected string stuff
    def updateStringGui(self):
        self.previewCtrl.resetEdit()

        if self.tsIndex == -1:
            for w in self.widList:
                w.Disable()

            self.xEntry.SetValue("")
            self.yEntry.SetValue("")
            self.sizeEntry.SetValue(12)
            self.boldBtn.SetValue(False)
            self.italicBtn.SetValue(False)
            self.underlinedBtn.SetValue(False)
            widgets.setAlignment(self.alignBtns, None)
            self.kindChoice.SetSelection(wx.NOT_FOUND)

            return

        self.block = True

        ts = self.titles.pages[self.pageIndex][self.tsIndex]

        for w in self.widList:
            w.Enable(True)

        if ts.isCentered:
            self.xEntry.Disable()

        self.xEntry.SetValue("%.2f" % ts.x)
        self.yEntry.SetValue("%.2f" % ts.y)

        widgets.setAlignment(self.alignBtns, ts.getAlignment())
        self.kindChoice.SetSelection(titles.KINDS.index(ts.kind or titles.TEXT))

        gutil.reverseComboSelect(self.fontCombo, ts.font)
        self.sizeEntry.SetValue(ts.size)

        self.boldBtn.SetValue(ts.isBold)
        self.italicBtn.SetValue(ts.isItalic)
        self.underlinedBtn.SetValue(ts.isUnderlined)

        self.block = False

        self.previewCtrl.Refresh()

    def OnMisc(self, event=None):
        if (self.tsIndex == -1) or self.block:
            return

        ts = self.titles.pages[self.pageIndex][self.tsIndex]

        ts.x = util.str2float(self.xEntry.GetValue(), 0.0)
        ts.y = util.str2float(self.yEntry.GetValue(), 0.0)

        ts.setAlignment(widgets.getAlignment(self.alignBtns))
        self.xEntry.Enable(not ts.isCentered)

        ts.size = gutil.getSpinValue(self.sizeEntry)
        ts.font = self.fontCombo.GetClientData(self.fontCombo.GetSelection())

        ts.isBold = self.boldBtn.GetValue()
        ts.isItalic = self.italicBtn.GetValue()
        ts.isUnderlined = self.underlinedBtn.GetValue()

        self.previewCtrl.Refresh()
