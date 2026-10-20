import wx

import trelby.screenplay.scriptformats as scriptformats
import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets


# Script > Change format: picks one of scriptformats.FORMATS for the
# script, showing what each one is for. after OK, self.format is the
# chosen ScriptFormat.
class ScriptFormatDlg(wx.Dialog):
    def __init__(self, parent, current):
        wx.Dialog.__init__(self, parent, -1, _("Change format"))

        self.formats = scriptformats.FORMATS
        self.format = None

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.list = widgets.ThemedListBox(
            self, -1, choices=[f.name() for f in self.formats]
        )
        vsizer.Add(self.list, 0, wx.EXPAND)

        self.description = widgets.WrappedText(self, "", 320)
        vsizer.Add(self.description, 0, wx.EXPAND | wx.TOP, 10)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _(
                    "This replaces the script's element styles and page break"
                    " settings with the format's, and clears the undo history."
                ),
                320,
            ),
            0,
            wx.EXPAND | wx.TOP,
            10,
        )

        vsizer.Add(widgets.Separator(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.AddStretchSpacer()

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        keys = [f.key for f in self.formats]
        self.list.SetSelection(keys.index(current.key))
        self.showDescription()

        gutil.finishWindow(self, vsizer, center=True)

        self.list.Bind(wx.EVT_LISTBOX, self.OnSelect)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnOK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        okBtn.SetDefault()
        self.list.SetFocus()

    def selected(self):
        return self.formats[max(0, self.list.GetSelection())]

    # show the selected format's description, in room for the longest
    # one, so that the dialog doesn't change size
    def showDescription(self):
        desc = self.description
        height = 0

        for f in self.formats:
            desc.text = f.description()
            desc.rewrap(desc.wrapWidth)
            height = max(height, desc.GetMinSize().height)

        desc.text = self.selected().description()
        desc.rewrap(desc.wrapWidth)
        desc.SetMinSize(wx.Size(desc.GetMinSize().width, height))
        self.Layout()

    def OnSelect(self, event):
        self.showDescription()

    def OnOK(self, event=None):
        self.format = self.selected()
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)
