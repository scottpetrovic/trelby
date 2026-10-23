import wx

import trelby.misc as misc
import trelby.screenplay.breakdown as breakdown
import trelby.ui.gutil as gutil


# asks for a breakdown element: its category and name, for adding one to a
# scene or renaming one (see screenplay/breakdown.py). existing is a dict
# of category key -> the names already in the script, offered in the name
# field's list. after OK, self.category is the category's key and
# self.name the name.
class ElementDlg(wx.Dialog):
    def __init__(self, parent, title, heading, category, name, existing):
        wx.Dialog.__init__(self, parent, -1, title)

        self.category = category
        self.name = name
        self.existing = existing

        dip = self.FromDIP

        vsizer = wx.BoxSizer(wx.VERTICAL)

        if heading:
            label = wx.StaticText(
                self, -1, heading, style=wx.ST_ELLIPSIZE_END | wx.ST_NO_AUTORESIZE
            )
            label.SetFont(label.GetFont().Bold())
            gutil.keepLeftToRight(label)
            vsizer.Add(label, 0, wx.EXPAND | wx.BOTTOM, 10)

        grid = wx.FlexGridSizer(2, 2, 5, 10)
        grid.AddGrowableCol(1)

        grid.Add(wx.StaticText(self, -1, _("Category:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.categoryCombo = wx.Choice(
            self, -1, choices=[c.label() for c in breakdown.CATEGORIES]
        )
        self.categoryCombo.SetSelection(self.categoryIndex(category))
        grid.Add(self.categoryCombo, 1, wx.EXPAND)

        grid.Add(wx.StaticText(self, -1, _("Name:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.nameCombo = wx.ComboBox(self, -1, name, size=dip(wx.Size(260, -1)))
        gutil.keepLeftToRight(self.nameCombo)
        grid.Add(self.nameCombo, 1, wx.EXPAND)

        vsizer.Add(grid, 0, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        self.okBtn = gutil.createStockButton(self, "OK")
        self.okBtn.SetDefault()
        hsizer.Add(self.okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 15)

        self.fillNames()

        gutil.finishWindow(self, vsizer, center=True)

        self.Bind(wx.EVT_CHOICE, self.OnCategory, id=self.categoryCombo.GetId())
        self.Bind(wx.EVT_TEXT, self.OnName, id=self.nameCombo.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=self.okBtn.GetId())

        self.OnName()
        self.nameCombo.SetFocus()
        self.nameCombo.SelectAll()

    @staticmethod
    def categoryIndex(key):
        keys = [c.key for c in breakdown.CATEGORIES]

        return keys.index(key) if key in keys else 0

    def selectedCategory(self):
        return breakdown.CATEGORIES[self.categoryCombo.GetSelection()].key

    # offer the names in the selected category, keeping what's typed
    def fillNames(self):
        text = self.nameCombo.GetValue()
        self.nameCombo.Set(self.existing.get(self.selectedCategory(), []))
        self.nameCombo.ChangeValue(text)

    def OnCategory(self, event):
        self.fillNames()

    def OnName(self, event=None):
        self.okBtn.Enable(bool(self.nameCombo.GetValue().strip()))

    def OnOK(self, event=None):
        name = breakdown.cleanName(misc.fromGUI(self.nameCombo.GetValue()))

        if not name:
            return

        self.category = self.selectedCategory()
        self.name = name

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)


# the names in the script, for ElementDlg's existing: category key -> the
# names, sorted. castSpeakers is as for Screenplay.getElementList.
def existingNames(sp, castSpeakers=True):
    ret = {}

    for e in sp.getElementList(castSpeakers):
        ret.setdefault(e.category, []).append(e.name)

    return ret


# ask for an element with an ElementDlg, returning (category key, name),
# or None if cancelled
def askElement(parent, title, heading, sp, category, name=""):
    dlg = ElementDlg(parent, title, heading, category, name, existingNames(sp))

    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None

        return (dlg.category, dlg.name)
    finally:
        dlg.Destroy()
