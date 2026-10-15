import trelby.util as util
import wx


class ThemePanel(wx.Panel):
    def __init__(self, parent, id, cfg):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg

        vsizer = wx.BoxSizer(wx.VERTICAL)

        # in config.APPEARANCE_* order
        self.themeRb = wx.RadioBox(
            self,
            -1,
            _("Theme"),
            style=wx.RA_SPECIFY_COLS,
            majorDimension=1,
            choices=[
                _("System default"),
                _("Light"),
                _("Dark"),
                _("Parchment"),
                _("Solarized Light"),
                _("Solarized Dark"),
                "Monokai",
                "Dracula",
                "Nord",
            ],
        )
        vsizer.Add(self.themeRb, 0, wx.EXPAND | wx.BOTTOM, 10)

        vsizer.Add(
            wx.StaticText(
                self,
                -1,
                _(
                    "System default follows the light or dark mode setting\nof your operating system."
                ),
            )
        )

        self.cfg2gui()

        util.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_RADIOBOX, self.OnMisc, id=self.themeRb.GetId())

    def OnMisc(self, event=None):
        self.cfg.appearance = self.themeRb.GetSelection()

    def cfg2gui(self):
        self.themeRb.SetSelection(self.cfg.appearance)
