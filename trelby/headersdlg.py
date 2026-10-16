import wx

import trelby.gutil as gutil
import trelby.headers as headers
import trelby.misc as misc
import trelby.textutil as textutil
from trelby.headerspreview import HeadersPreview


class HeadersDlg(wx.Dialog):
    def __init__(self, parent, headers, cfg, cfgGl, applyFunc):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Page headers"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.headers = headers
        self.cfg = cfg
        self.cfgGl = cfgGl
        self.applyFunc = applyFunc

        # whether some events are blocked
        self.block = False

        self.hdrIndex = -1
        if len(self.headers.hdrs) > 0:
            self.hdrIndex = 0

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Empty lines after headers:")),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )

        self.elinesEntry = wx.SpinCtrl(self, -1)
        self.elinesEntry.SetRange(0, 5)
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.elinesEntry.GetId())
        self.elinesEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        hsizer.Add(self.elinesEntry, 0, wx.LEFT, 10)

        vsizer.Add(hsizer)

        vsizer.Add(gutil.Separator(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)

        tmp = wx.StaticText(self, -1, _("Strings:"))
        vsizer.Add(tmp)

        self.stringsLb = gutil.ThemedListBox(self, -1, size=(200, 100))
        vsizer.Add(self.stringsLb, 0, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.addBtn = gutil.createStockButton(self, _("Add"))
        hsizer.Add(self.addBtn)
        self.Bind(wx.EVT_BUTTON, self.OnAddString, id=self.addBtn.GetId())
        gutil.btnDblClick(self.addBtn, self.OnAddString)

        self.delBtn = gutil.createStockButton(self, _("Delete"))
        hsizer.Add(self.delBtn, 0, wx.LEFT, 10)
        self.Bind(wx.EVT_BUTTON, self.OnDeleteString, id=self.delBtn.GetId())
        gutil.btnDblClick(self.delBtn, self.OnDeleteString)

        vsizer.Add(hsizer, 0, wx.TOP, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(wx.StaticText(self, -1, _("Text:")), 0, wx.ALIGN_CENTER_VERTICAL)

        self.textEntry = wx.TextCtrl(self, -1)
        hsizer.Add(self.textEntry, 1, wx.LEFT, 10)
        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.textEntry.GetId())

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        vsizer.Add(
            wx.StaticText(
                self, -1, _("'${PAGE}' will be replaced by the page number.")
            ),
            0,
            wx.ALIGN_CENTER | wx.TOP,
            5,
        )

        hsizerTop = wx.BoxSizer(wx.HORIZONTAL)

        gsizer = wx.FlexGridSizer(4, 2, 5, 0)

        gsizer.Add(
            wx.StaticText(self, -1, _("Header line:")), 0, wx.ALIGN_CENTER_VERTICAL
        )

        self.lineEntry = wx.SpinCtrl(self, -1)
        self.lineEntry.SetRange(1, 5)
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.lineEntry.GetId())
        self.lineEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        gsizer.Add(self.lineEntry)

        gsizer.Add(
            wx.StaticText(self, -1, _("X offset (characters):")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.xoffEntry = wx.SpinCtrl(self, -1)
        self.xoffEntry.SetRange(-100, 100)
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.xoffEntry.GetId())
        self.xoffEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        gsizer.Add(self.xoffEntry)

        gsizer.Add(
            wx.StaticText(self, -1, _("Alignment:")), 0, wx.ALIGN_CENTER_VERTICAL
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.alignBtns = gutil.addAlignToggles(self, hsizer, self.OnMisc)
        gsizer.Add(hsizer)

        gsizer.Add(wx.StaticText(self, -1, _("Format:")), 0, wx.ALIGN_CENTER_VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.boldBtn, self.italicBtn, self.underlinedBtn = gutil.addStyleToggles(
            self, hsizer, self.OnMisc
        )
        gsizer.Add(hsizer)

        hsizerTop.Add(gsizer)

        vsizer.Add(hsizerTop, 0, wx.TOP, 20)

        # controls on the left, live preview of the top of a page on the
        # right
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        mainSizer.Add(vsizer, 0, wx.EXPAND)

        self.previewCtrl = HeadersPreview(self, self, self.cfg)
        self.previewCtrl.SetMinSize(self.FromDIP(wx.Size(560, 300)))
        mainSizer.Add(self.previewCtrl, 1, wx.EXPAND | wx.LEFT, 20)

        topSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer.Add(mainSizer, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        applyBtn = gutil.createStockButton(self, _("Apply"))
        hsizer.Add(applyBtn)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        topSizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        gutil.finishWindow(self, topSizer)

        self.Bind(wx.EVT_BUTTON, self.OnApply, id=applyBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.Bind(wx.EVT_LISTBOX, self.OnStringsLb, id=self.stringsLb.GetId())

        # list of widgets that are specific to editing the selected string
        self.widList = [
            self.textEntry,
            self.xoffEntry,
            self.lineEntry,
            self.boldBtn,
            self.italicBtn,
            self.underlinedBtn,
        ] + list(self.alignBtns.values())

        self.updateGui()

        self.textEntry.SetFocus()

    def OnOK(self, event):
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnApply(self, event):
        self.applyFunc(self.headers)

    # select header string 'i' (called when it's clicked in the preview)
    def selectHeader(self, i):
        self.hdrIndex = i
        self.stringsLb.SetSelection(i)
        self.updateHeaderGui()
        self.textEntry.SetFocus()

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wxGTK gets stuck in
        # some weird state
        event.Skip()

    def OnStringsLb(self, event=None):
        self.hdrIndex = self.stringsLb.GetSelection()
        self.updateHeaderGui()

    def OnAddString(self, event):
        h = headers.HeaderString()
        h.text = "new string"

        self.headers.hdrs.append(h)
        self.hdrIndex = len(self.headers.hdrs) - 1

        self.updateGui()

    def OnDeleteString(self, event):
        if self.hdrIndex == -1:
            return

        del self.headers.hdrs[self.hdrIndex]
        self.hdrIndex = min(self.hdrIndex, len(self.headers.hdrs) - 1)

        self.updateGui()

    # update listbox
    def updateGui(self):
        self.stringsLb.Clear()

        self.elinesEntry.SetValue(self.headers.emptyLinesAfter)

        self.delBtn.Enable(self.hdrIndex != -1)

        for h in self.headers.hdrs:
            self.stringsLb.Append(h.text)

        if self.hdrIndex != -1:
            self.stringsLb.SetSelection(self.hdrIndex)

        self.updateHeaderGui()

    # update selected header stuff
    def updateHeaderGui(self):
        if self.hdrIndex == -1:
            for w in self.widList:
                w.Disable()

            self.textEntry.SetValue("")
            self.lineEntry.SetValue(1)
            self.xoffEntry.SetValue(0)
            self.boldBtn.SetValue(False)
            self.italicBtn.SetValue(False)
            self.underlinedBtn.SetValue(False)
            gutil.setAlignment(self.alignBtns, None)
            self.previewCtrl.Refresh()

            return

        self.block = True

        h = self.headers.hdrs[self.hdrIndex]

        for w in self.widList:
            w.Enable(True)

        self.textEntry.SetValue(h.text)
        self.xoffEntry.SetValue(h.xoff)

        gutil.setAlignment(self.alignBtns, h.align)
        self.lineEntry.SetValue(h.line)

        self.boldBtn.SetValue(h.isBold)
        self.italicBtn.SetValue(h.isItalic)
        self.underlinedBtn.SetValue(h.isUnderlined)

        self.block = False

        self.previewCtrl.Refresh()

    def OnMisc(self, event=None):
        if self.block:
            return

        self.headers.emptyLinesAfter = gutil.getSpinValue(self.elinesEntry)
        self.previewCtrl.Refresh()

        if self.hdrIndex == -1:
            return

        h = self.headers.hdrs[self.hdrIndex]

        h.text = textutil.toInputStr(misc.fromGUI(self.textEntry.GetValue()))
        self.stringsLb.SetString(self.hdrIndex, h.text)

        h.xoff = gutil.getSpinValue(self.xoffEntry)
        h.line = gutil.getSpinValue(self.lineEntry)
        h.align = gutil.getAlignment(self.alignBtns)

        h.isBold = self.boldBtn.GetValue()
        h.isItalic = self.italicBtn.GetValue()
        h.isUnderlined = self.underlinedBtn.GetValue()
