import wx

import trelby.ui.gutil as gutil


# lists the formatting errors found in a script (proofing.findErrors), one
# row per error. selecting a row shows its line in the script behind the
# dialog. Go To (or double-click / Enter on a row) closes the dialog with the
# cursor on the selected error; Close (or Escape) puts the cursor back where
# it was.
class FormattingErrorsDlg(wx.Dialog):
    # longest text shown in the Text column
    MAX_TEXT = 60

    def __init__(self, parent, ctrl, errors):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Formatting Errors"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.ctrl = ctrl
        self.errors = errors

        # where the cursor was, for Close
        self.origPos = (ctrl.ed.line, ctrl.ed.column)

        sp = ctrl.sp

        vsizer = wx.BoxSizer(wx.VERTICAL)

        if len(errors) == 1:
            s = _("Found 1 formatting error in \"{1}\".")
        else:
            s = _("Found {0} formatting errors in \"{1}\".")

        vsizer.Add(
            wx.StaticText(self, -1, s.format(len(errors), ctrl.fileNameDisplay))
        )

        self.list = wx.ListCtrl(
            self, -1, style=wx.LC_REPORT | wx.LC_SINGLE_SEL
        )
        self.list.AppendColumn(_("Page"), wx.LIST_FORMAT_RIGHT, self.FromDIP(50))
        self.list.AppendColumn(_("Element"), width=self.FromDIP(100))
        self.list.AppendColumn(_("Problem"), width=self.FromDIP(330))
        self.list.AppendColumn(_("Text"), width=self.FromDIP(260))

        for i, err in enumerate(errors):
            ln = sp.lines[err.line]

            self.list.InsertItem(i, sp.line2pageLabel(err.line))
            self.list.SetItem(i, 1, _(sp.cfg.getType(ln.lt).ti.name))
            self.list.SetItem(i, 2, err.msg)
            self.list.SetItem(i, 3, self.shownText(ln.text))

        width = sum(self.list.GetColumnWidth(c) for c in range(4))
        self.list.SetMinSize(
            wx.Size(width + self.FromDIP(24), self.FromDIP(260))
        )
        vsizer.Add(self.list, 1, wx.EXPAND | wx.TOP, 5)

        vsizer.Add(
            wx.StaticText(
                self, -1, _("Select an error to show it in the script.")
            ),
            0,
            wx.TOP,
            5,
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        closeBtn = wx.Button(self, wx.ID_CANCEL, _("Close"))
        hsizer.Add(closeBtn)

        self.gotoBtn = wx.Button(self, -1, _("Go To"))
        hsizer.Add(self.gotoBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelect, id=self.list.GetId())
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnGoTo, id=self.list.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnGoTo, id=self.gotoBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

        self.gotoBtn.SetDefault()

        if errors:
            self.list.Select(0)
            self.list.Focus(0)

        self.list.SetFocus()

    # the line's text as shown in the Text column: spaces made visible, and
    # long lines cut short
    def shownText(self, text):
        if not text.strip():
            return _("(%d spaces)") % len(text) if text else _("(empty)")

        if len(text) > self.MAX_TEXT:
            return text[: self.MAX_TEXT - 3] + "..."

        return text

    def selected(self):
        return self.list.GetFirstSelected()

    # move the script's cursor to the start of the given line
    def showLine(self, line, column=0):
        ed = self.ctrl.ed
        ed.clearMark()
        ed.line = line
        ed.column = column

        self.ctrl.makeLineVisible(line)
        self.ctrl.updateScreen()

    def OnSelect(self, event):
        self.showLine(self.errors[event.GetIndex()].line)

    def OnGoTo(self, event):
        i = self.selected()

        if i == -1:
            return

        self.showLine(self.errors[i].line)
        self.EndModal(wx.ID_OK)

    def OnClose(self, event):
        self.showLine(*self.origPos)
        self.EndModal(wx.ID_CANCEL)
