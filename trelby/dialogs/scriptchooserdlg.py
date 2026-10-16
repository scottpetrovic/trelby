import wx

import trelby.ui.gutil as gutil


# dialog that shows two lists of script names, allowing user to choose one
# from both. stores indexes of selections in members named 'sel1' and
# 'sel2' when OK is pressed. 'items' must have at least two items.
class ScriptChooserDlg(wx.Dialog):
    def __init__(self, parent, items):
        wx.Dialog.__init__(
            self, parent, -1, _("Choose scripts"), style=wx.DEFAULT_DIALOG_STYLE
        )

        vsizer = wx.BoxSizer(wx.VERTICAL)

        gsizer = wx.FlexGridSizer(2, 2, 5, 0)

        self.addCombo("first", _("Compare script"), self, gsizer, items, 0)
        self.addCombo("second", _("to"), self, gsizer, items, 1)

        vsizer.Add(gsizer)

        self.forceCb = wx.CheckBox(self, -1, _("Use same configuration"))
        self.forceCb.SetValue(True)
        vsizer.Add(self.forceCb, 0, wx.TOP, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        okBtn.SetFocus()

    def addCombo(self, name, descr, parent, sizer, items, sel):
        al = wx.ALIGN_CENTER_VERTICAL | wx.RIGHT
        if sel == 1:
            al |= wx.ALIGN_RIGHT

        sizer.Add(wx.StaticText(parent, -1, descr), 0, al, 10)

        combo = wx.ComboBox(parent, -1, style=wx.CB_READONLY)
        gutil.setWH(combo, w=200)

        for s in items:
            combo.Append(s)

        combo.SetSelection(sel)

        sizer.Add(combo)

        setattr(self, name + "Combo", combo)

    def OnOK(self, event):
        self.sel1 = self.firstCombo.GetSelection()
        self.sel2 = self.secondCombo.GetSelection()
        self.forceSameCfg = bool(self.forceCb.GetValue())

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
