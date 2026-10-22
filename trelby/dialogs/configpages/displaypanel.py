import trelby.ui.gutil as gutil
import trelby.misc as misc
import trelby.ui.widgets as widgets
import wx


class DisplayPanel(wx.Panel):
    def __init__(self, parent, id, cfg, cfgFrame=None):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg
        self.cfgFrame = cfgFrame

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(self, -1, _("Screen fonts:")))

        self.fontsLb = widgets.ThemedListBox(self, -1, size=(300, 100))

        for it in ["fontNormal", "fontBold", "fontItalic", "fontBoldItalic"]:
            self.fontsLb.Append("", it)

        vsizer.Add(self.fontsLb, 0, wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(self, -1, _("Change"))
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.OnChangeFont, id=self.fontsLb.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnChangeFont, id=btn.GetId())

        self.errText = wx.StaticText(self, -1, "")

        hsizer.Add(btn)
        hsizer.Add((20, -1))
        hsizer.Add(self.errText, 0, wx.ALIGN_CENTER_VERTICAL)
        vsizer.Add(hsizer, 0, wx.BOTTOM, 20)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(self, -1, _("Toolbar icon size:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.iconSizeEntry = wx.SpinCtrl(self, -1)
        self.iconSizeEntry.SetRange(*self.cfg.cvars.getMinMax("toolbarIconSize"))
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=self.iconSizeEntry.GetId())
        self.iconSizeEntry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        hsizer.Add(self.iconSizeEntry, 0)

        hsizer.Add(
            wx.StaticText(self, -1, _("pixels")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            10,
        )

        vsizer.Add(hsizer, 0, wx.BOTTOM, 20)

        self.fontsLb.SetSelection(0)
        self.updateFontLb()

        self.cfg2gui()

        gutil.finishWindow(self, vsizer, center=False)

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wx.GTK gets stuck in
        # some weird state
        event.Skip()

    def OnChangeFont(self, event):
        fname = self.fontsLb.GetClientData(self.fontsLb.GetSelection())
        nfont = getattr(self.cfg, fname)

        fd = wx.FontData()
        font = wx.Font(gutil.fontInfo(nfont))
        fd.SetInitialFont(font)

        dlg = wx.FontDialog(self, fd)
        if dlg.ShowModal() == wx.ID_OK:
            font = dlg.GetFontData().GetChosenFont()
            if gutil.isFixedWidth(font):
                setattr(self.cfg, fname, font.GetNativeFontInfo().ToString())

                self.cfg.fontYdelta = gutil.getFontHeight(font)

                self.cfg2gui()
                self.updateFontLb()
            else:
                wx.MessageBox(
                    _("The selected font is not fixed width and can not be used."),
                    _("Error"),
                    wx.OK,
                    self.cfgFrame,
                )

        dlg.Destroy()

    def OnMisc(self, event=None):
        self.cfg.toolbarIconSize = gutil.getSpinValue(self.iconSizeEntry)

    def updateFontLb(self):
        names = ["Normal", "Bold", "Italic", "Bold-Italic"]

        # keep track if all fonts have the same width
        widths = set()

        for i in range(len(names)):
            nfi = gutil.fontInfo(getattr(self.cfg, self.fontsLb.GetClientData(i)))

            ps = nfi.GetPointSize()
            s = nfi.GetFaceName()

            row = "%s: %s, %d" % (names[i], s, ps)
            if misc.isMac:
                # Work around odd issue where wxOSX doesn't notice change in width
                self.fontsLb.Insert(row, i, self.fontsLb.GetClientData(i))
                self.fontsLb.Delete(i + 1)
            else:
                self.fontsLb.SetString(i, row)

            f = wx.Font(nfi)
            widths.add(gutil.getTextExtent(f, "iw")[0])

        if len(widths) > 1:
            self.errText.SetLabel(_("Fonts have different widths"))
            self.errText.SetForegroundColour((255, 0, 0))
        else:
            self.errText.SetLabel(_("Fonts have matching widths"))
            self.errText.SetForegroundColour(self.GetForegroundColour())

    def cfg2gui(self):
        self.iconSizeEntry.SetValue(self.cfg.toolbarIconSize)
