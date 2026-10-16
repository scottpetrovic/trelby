import trelby.gutil as gutil
import wx


class DraftPanel(wx.Panel):
    def __init__(self, parent, id, cfg):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg

        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Row spacing:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.spacingEntry = wx.SpinCtrl(self, -1)
        self.spacingEntry.SetRange(*self.cfg.cvars.getMinMax("fontYdelta"))
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.spacingEntry.GetId())
        self.spacingEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        hsizer.Add(self.spacingEntry, 0)

        hsizer.Add(
            wx.StaticText(self, -1, _("pixels")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            10,
        )

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.pbRb = wx.RadioBox(
            self,
            -1,
            _("Page break lines to show"),
            style=wx.RA_SPECIFY_COLS,
            majorDimension=1,
            choices=[_("None"), _("Normal"), _("Normal + unadjusted   ")],
        )
        vsizer.Add(self.pbRb)

        self.cfg2gui()

        gutil.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_RADIOBOX, self.OnMisc, id=self.pbRb.GetId())

        # changing the screen font on the Display page resets the row
        # spacing, so refresh it whenever this page is shown
        self.Bind(wx.EVT_SHOW, self.OnShow)

    def OnShow(self, event):
        if event.IsShown():
            self.cfg2gui()

        event.Skip()

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wx.GTK gets stuck in
        # some weird state
        event.Skip()

    def OnMisc(self, event=None):
        self.cfg.fontYdelta = gutil.getSpinValue(self.spacingEntry)
        self.cfg.pbi = self.pbRb.GetSelection()

    def cfg2gui(self):
        self.spacingEntry.SetValue(self.cfg.fontYdelta)
        self.pbRb.SetSelection(self.cfg.pbi)
