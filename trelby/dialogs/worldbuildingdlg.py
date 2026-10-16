import wx

import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets

# shown above the text to suggest what to write about: list of (topic,
# description). a function so that the strings are translated when used.
def guideTopics():
    return [
        (
            _("Physical Environment"),
            _(
                "The land, climate, weather, natural resources, and geography"
                " that shape daily life and travel."
            ),
        ),
        (
            _("Society and Culture"),
            _(
                "The religions, social classes, traditions, values, languages,"
                " and governance systems of the inhabitants."
            ),
        ),
        (
            _("History and Conflict"),
            _(
                "Past wars, power shifts, ancient legends, or systemic"
                " oppressions that still influence the present narrative."
            ),
        ),
        (
            _("Rules and Systems"),
            _(
                "The logical boundaries of magic, technology, or physics that"
                " must remain consistent without contradiction."
            ),
        ),
    ]


class WorldBuildingDlg(wx.Dialog):
    def __init__(self, parent, worldBuilding):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("World building"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.worldBuilding = worldBuilding

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        tmp = wx.StaticText(
            self, -1, _("Notes about the world your story takes place in, such as:")
        )
        vsizer.Add(tmp)

        guideSizer = wx.FlexGridSizer(2, dip(10), dip(10))
        guideSizer.AddGrowableCol(1, 1)

        for topic, desc in guideTopics():
            label = wx.StaticText(self, -1, topic)
            label.SetFont(label.GetFont().Bold())
            guideSizer.Add(label)

            tmp = wx.StaticText(self, -1, desc)
            tmp.Wrap(dip(480))
            guideSizer.Add(tmp, 1, wx.EXPAND)

        vsizer.Add(guideSizer, 0, wx.EXPAND | wx.TOP | wx.LEFT, dip(10))

        textBox = widgets.ThemedTextCtrl(
            self, value=worldBuilding.text, size=dip(wx.Size(640, 360))
        )
        self.textCtrl = textBox.text
        vsizer.Add(textBox, 1, wx.EXPAND | wx.TOP, dip(15))

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.textCtrl.SetFocus()
        self.textCtrl.SetInsertionPointEnd()

    def OnOK(self, event):
        self.worldBuilding.text = self.textCtrl.GetValue()

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
