import wx

import trelby.gutil as gutil
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.titles as titles
import trelby.util as util
from trelby.titlespreview import TitlesPreview


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

        self.setPage(0)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.pageLabel = wx.StaticText(self, -1, "")
        vsizer.Add(self.pageLabel, 0, wx.ADJUST_MINSIZE)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        tmp = wx.Button(self, -1, _("Add"))
        hsizer.Add(tmp)
        self.Bind(wx.EVT_BUTTON, self.OnAddPage, id=tmp.GetId())
        gutil.btnDblClick(tmp, self.OnAddPage)

        self.delPageBtn = wx.Button(self, -1, _("Delete"))
        hsizer.Add(self.delPageBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnDeletePage, id=self.delPageBtn.GetId())
        gutil.btnDblClick(self.delPageBtn, self.OnDeletePage)

        self.moveBtn = wx.Button(self, -1, _("Move"))
        hsizer.Add(self.moveBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnMovePage, id=self.moveBtn.GetId())
        gutil.btnDblClick(self.moveBtn, self.OnMovePage)

        self.nextBtn = wx.Button(self, -1, _("Next"))
        hsizer.Add(self.nextBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnNextPage, id=self.nextBtn.GetId())
        gutil.btnDblClick(self.nextBtn, self.OnNextPage)

        vsizer.Add(hsizer, 0, wx.TOP, 5)

        vsizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        vsizer2 = wx.BoxSizer(wx.VERTICAL)

        tmp = wx.StaticText(self, -1, _("Items on this page:"))
        vsizer2.Add(tmp)

        self.stringsLc = wx.ListCtrl(
            self, -1, size=(200, 150), style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.stringsLc.AppendColumn(_("Type"), width=self.FromDIP(100))
        self.stringsLc.AppendColumn(_("Text"), width=self.FromDIP(240))
        self.stringsLc.Bind(wx.EVT_SIZE, self.OnListSize)
        vsizer2.Add(self.stringsLc, 1, wx.EXPAND)

        hsizer2 = wx.BoxSizer(wx.HORIZONTAL)

        # pops up a menu of the kinds of strings to add
        self.addBtn = wx.Button(self, -1, _("Add") + " ▾")
        hsizer2.Add(self.addBtn)
        self.Bind(wx.EVT_BUTTON, self.OnAddMenu, id=self.addBtn.GetId())

        self.delBtn = gutil.createStockButton(self, _("Delete"))
        hsizer2.Add(self.delBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnDeleteString, id=self.delBtn.GetId())
        gutil.btnDblClick(self.delBtn, self.OnDeleteString)

        vsizer2.Add(hsizer2, 0, wx.TOP, 5)

        vsizer.Add(vsizer2, 1, wx.EXPAND)

        tmp = wx.StaticText(
            self, -1, _("Click an item in the preview to edit its text.")
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

        self.boldBtn = self.addToggle(hsizer, "B", _("Bold"), wx.FONTWEIGHT_BOLD)
        self.italicBtn = self.addToggle(
            hsizer, "I", _("Italic"), style=wx.FONTSTYLE_ITALIC
        )
        self.underlinedBtn = self.addToggle(
            hsizer, "U", _("Underlined"), underlined=True
        )

        hsizer.AddSpacer(12)

        # alignment buttons, which work like radio buttons
        self.alignBtns = {}

        for align, tip in [
            (util.ALIGN_LEFT, _("Align left")),
            (util.ALIGN_CENTER, _("Center")),
            (util.ALIGN_RIGHT, _("Align right")),
        ]:
            btn = self.addToggle(hsizer, "", tip, handler=self.OnAlign)
            btn.SetBitmap(makeAlignBitmap(btn, align))
            self.alignBtns[align] = btn

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

        self.previewCtrl = TitlesPreview(self, self, self.cfg)
        self.previewCtrl.SetMinSize(wx.Size(380, 480))
        mainSizer.Add(self.previewCtrl, 1, wx.EXPAND | wx.LEFT, 20)

        topSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer.Add(mainSizer, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        self.previewBtn = gutil.createStockButton(self, _("Preview"))
        hsizer.Add(self.previewBtn)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        topSizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        util.finishWindow(self, topSizer)

        self.Bind(wx.EVT_BUTTON, self.OnPreview, id=self.previewBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.Bind(
            wx.EVT_LIST_ITEM_SELECTED, self.OnStringsLc, id=self.stringsLc.GetId()
        )

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

    # add a small toggle button showing 'label' in the given font style
    # to 'sizer', and return it. 'handler' defaults to OnMisc.
    def addToggle(
        self,
        sizer,
        label,
        tip,
        weight=wx.FONTWEIGHT_NORMAL,
        style=wx.FONTSTYLE_NORMAL,
        underlined=False,
        handler=None,
    ):
        size = self.FromDIP(wx.Size(30, 28))
        btn = wx.ToggleButton(self, -1, label, size=size)
        btn.SetToolTip(tip)

        font = btn.GetFont()
        font.SetWeight(weight)
        font.SetStyle(style)
        font.SetUnderlined(underlined)
        btn.SetFont(font)

        btn.Bind(wx.EVT_TOGGLEBUTTON, handler or self.OnMisc)
        sizer.Add(btn, 0, wx.RIGHT, 2)

        return btn

    # an alignment button was clicked: make it the only one pressed
    def OnAlign(self, event):
        for btn in self.alignBtns.values():
            btn.SetValue(btn is event.GetEventObject())

        self.OnMisc()

    def getAlignment(self):
        for align, btn in self.alignBtns.items():
            if btn.GetValue():
                return align

        return util.ALIGN_LEFT

    def setAlignment(self, align):
        for a, btn in self.alignBtns.items():
            btn.SetValue(a == align)

    def OnOK(self, event):
        self.titles.sort()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnPreview(self, event):
        doc = pml.Document(self.cfg.paperWidth, self.cfg.paperHeight)

        self.titles.generatePages(doc)
        tmp = pdf.generate(doc)
        gutil.showTempPDF(tmp, self.cfgGl, self)

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

        ts = self.titles.pages[self.pageIndex][self.tsIndex]
        ts.kind = titles.KINDS[self.kindChoice.GetSelection()]
        self.stringsLc.SetItem(self.tsIndex, 0, self.kindLabel(ts.kind))

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
        self.nextBtn.Enable(pgCnt > 1)
        self.previewBtn.Enable(pgCnt > 0)

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
            self.setAlignment(None)
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

        self.setAlignment(ts.getAlignment())
        self.kindChoice.SetSelection(titles.KINDS.index(ts.kind or titles.TEXT))

        util.reverseComboSelect(self.fontCombo, ts.font)
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

        ts.setAlignment(self.getAlignment())
        self.xEntry.Enable(not ts.isCentered)

        ts.size = util.getSpinValue(self.sizeEntry)
        ts.font = self.fontCombo.GetClientData(self.fontCombo.GetSelection())

        ts.isBold = self.boldBtn.GetValue()
        ts.isItalic = self.italicBtn.GetValue()
        ts.isUnderlined = self.underlinedBtn.GetValue()

        self.previewCtrl.Refresh()


# return an icon for alignment button 'btn': four lines of text, aligned
# as 'align'
def makeAlignBitmap(btn, align):
    size = btn.FromDIP(16)
    bmp = wx.Bitmap.FromRGBA(size, size, 0, 0, 0, 0)

    dc = wx.MemoryDC(bmp)
    gc = wx.GraphicsContext.Create(dc)

    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)))

    thick = max(1, size // 8)
    gap = (size - 4 * thick) / 5

    for i, frac in enumerate([1.0, 0.6, 0.85, 0.5]):
        w = round(size * frac)

        if align == util.ALIGN_CENTER:
            x = (size - w) / 2
        elif align == util.ALIGN_RIGHT:
            x = size - w
        else:
            x = 0

        gc.DrawRectangle(x, gap + i * (thick + gap), w, thick)

    del gc
    dc.SelectObject(wx.NullBitmap)

    return bmp
