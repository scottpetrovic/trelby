# the Revisions dialog: the script's revision settings (see
# screenplay/revisions.py). it works on a copy of sp.revisions, which the
# caller takes from dlg.revisions on OK. revision mode itself is switched
# on and off only by its menu item, Production > Revision mode.

import wx

import trelby.misc as misc
import trelby.screenplay.revisions as revisions
import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets


class RevisionsDlg(wx.Dialog):
    def __init__(self, parent, rv, revisedPages):
        wx.Dialog.__init__(self, parent, -1, _("Revisions"))

        self.revisions = rv

        # the dates as edited, by level, and the levels whose date has
        # been filled in with today's without being edited
        self.dates = dict(rv.dates)
        self.autoDated = set()

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _(
                    "While revision mode is on (Production > Revision mode), "
                    "the text you change is marked with the current revision, "
                    "and its lines get a revision mark in the right margin "
                    "when printed."
                ),
            ),
            0,
            wx.EXPAND,
        )

        gsizer = wx.FlexGridSizer(3, 2, 5, 10)
        gsizer.AddGrowableCol(1)

        gsizer.Add(
            wx.StaticText(self, -1, _("Current revision:")), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.levelCombo = wx.Choice(
            self,
            -1,
            choices=[
                revisions.levelName(level)
                for level in range(1, revisions.MAX_LEVEL + 1)
            ],
        )
        self.levelCombo.SetSelection(max(rv.level, 1) - 1)
        self.Bind(wx.EVT_CHOICE, self.OnLevel, id=self.levelCombo.GetId())
        gsizer.Add(self.levelCombo, 1, wx.EXPAND)

        gsizer.Add(wx.StaticText(self, -1, _("Date:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.dateEntry = wx.TextCtrl(self, -1)
        gutil.keepLeftToRight(self.dateEntry)
        self.Bind(wx.EVT_TEXT, self.OnDate, id=self.dateEntry.GetId())
        gsizer.Add(self.dateEntry, 1, wx.EXPAND)

        gsizer.Add(
            wx.StaticText(self, -1, _("Revision mark:")), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.markEntry = wx.TextCtrl(self, -1, rv.markChar)
        self.markEntry.SetMaxLength(1)
        self.markEntry.SetMinSize(self.FromDIP(wx.Size(40, -1)))
        gsizer.Add(self.markEntry)

        vsizer.Add(gsizer, 0, wx.EXPAND | wx.TOP, 20)

        self.headerCb = wx.CheckBox(
            self, -1, _("Show each revised page's revision above its header")
        )
        self.headerCb.SetValue(rv.showInHeader)
        vsizer.Add(self.headerCb, 0, wx.TOP, 20)

        self.currentCb = wx.CheckBox(
            self, -1, _("Mark only the current revision's changes")
        )
        self.currentCb.SetValue(rv.currentOnly)
        vsizer.Add(self.currentCb, 0, wx.TOP, 5)

        if revisedPages:
            s = _("Pages revised in the current revision: {}").format(
                ", ".join(revisedPages)
            )
        else:
            s = _("No pages have been revised in the current revision.")

        self.pagesText = widgets.WrappedText(self, s)
        vsizer.Add(self.pagesText, 0, wx.EXPAND | wx.TOP, 20)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add((1, 1), 1)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.showDate()
        gutil.finishWindow(self, vsizer, center=True)

        okBtn.SetDefault()

    # the level chosen
    def getLevel(self):
        return self.levelCombo.GetSelection() + 1

    # show the chosen revision's date, today's for one without a date
    def showDate(self):
        level = self.getLevel()

        if level not in self.dates:
            self.dates[level] = revisions.today()
            self.autoDated.add(level)

        self.dateEntry.ChangeValue(self.dates[level])

    def OnLevel(self, event):
        self.showDate()

    def OnDate(self, event):
        level = self.getLevel()
        self.dates[level] = misc.fromGUI(self.dateEntry.GetValue()).strip()
        self.autoDated.discard(level)

    def OnOK(self, event):
        rv = self.revisions

        rv.level = self.getLevel()
        rv.showInHeader = self.headerCb.GetValue()
        rv.currentOnly = self.currentCb.GetValue()
        rv.markChar = misc.fromGUI(self.markEntry.GetValue()).strip()[:1] or (
            revisions.DEFAULT_MARK
        )

        # today's date is kept only for the revision chosen, the others
        # having only been looked at
        rv.dates = {
            level: date
            for level, date in self.dates.items()
            if date and ((level not in self.autoDated) or (level == rv.level))
        }

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
