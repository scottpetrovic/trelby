import trelby.gutil as gutil
import trelby.misc as misc
import wx


# the global spell checker dictionary. it isn't part of the settings, so
# this edits the settings dialog's copy, which is saved on Apply/OK.
class SpellCheckPanel(wx.Panel):
    def __init__(self, parent, id, cfg, cfgFrame):
        wx.Panel.__init__(self, parent, id)
        self.cfgFrame = cfgFrame

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(
            gutil.WrappedText(
                self,
                _(
                    "Mark these words as correct spelling so the spell checker "
                    "won't flag them."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        vsizer.Add(wx.StaticText(self, -1, _("Global words (one per line):")))

        self.itemsEntry = wx.TextCtrl(
            self, -1, style=wx.TE_MULTILINE | wx.TE_DONTWRAP, size=(-1, 250)
        )
        vsizer.Add(self.itemsEntry, 1, wx.EXPAND | wx.TOP, 5)

        self.itemsEntry.SetValue("\n".join(self.cfgFrame.scDict.get()))

        gutil.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.itemsEntry.GetId())

    def OnMisc(self, event):
        self.cfgFrame.scDict.set(misc.fromGUI(self.itemsEntry.GetValue()).split("\n"))
