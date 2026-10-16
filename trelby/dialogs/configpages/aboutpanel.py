import trelby.ui.gutil as gutil
import wx


class AboutPanel(wx.Panel):
    def __init__(self, parent, id, cfg, text):
        wx.Panel.__init__(self, parent, id)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(self, -1, text))

        gutil.finishWindow(self, vsizer, center=False)
