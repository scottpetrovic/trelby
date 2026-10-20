import wx

import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets


# the Settings dialog's Writing Goals page: the daily and weekly writing
# goals, counted across all scripts (see writinglog.py), and the writing
# sprints (see sprint.py)
class GoalsPanel(wx.Panel):
    def __init__(self, parent, id, cfg):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _(
                    "What you write is counted across all your scripts, and "
                    "shown in the status bar and on the Home screen. Set a "
                    "goal to 0 to have none."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        grid = wx.FlexGridSizer(2, 3, 10, 10)

        self.dailyEntry = self.addSpin(grid, _("Daily goal:"), "dailyGoal")

        self.unitChoice = wx.Choice(self, -1, choices=[_("words"), _("pages")])
        grid.Add(self.unitChoice, 0, wx.ALIGN_CENTER_VERTICAL)

        self.weeklyEntry = self.addSpin(grid, _("Weekly goal:"), "weeklyGoal")
        self.weeklyUnit = wx.StaticText(self, -1, "")
        grid.Add(self.weeklyUnit, 0, wx.ALIGN_CENTER_VERTICAL)

        vsizer.Add(grid, 0, wx.BOTTOM, 10)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _("The week starts on Monday."),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            20,
        )

        vsizer.Add(widgets.Separator(self), 0, wx.EXPAND | wx.BOTTOM, 20)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _(
                    "A writing sprint is writing against the clock (Tools > "
                    "Writing sprint, F7, or a click on the status bar's goal). "
                    "It can end early when you reach a number of words."
                ),
            ),
            0,
            wx.EXPAND | wx.BOTTOM,
            10,
        )

        grid = wx.FlexGridSizer(2, 3, 10, 10)

        self.minutesEntry = self.addSpin(grid, _("Sprint length:"), "sprintMinutes")
        grid.Add(
            wx.StaticText(self, -1, _("minutes")), 0, wx.ALIGN_CENTER_VERTICAL
        )

        self.wordsEntry = self.addSpin(grid, _("End early at:"), "sprintWords")
        grid.Add(wx.StaticText(self, -1, _("words")), 0, wx.ALIGN_CENTER_VERTICAL)

        vsizer.Add(grid, 0, wx.BOTTOM, 10)

        self.soundCb = wx.CheckBox(self, -1, _("Play a sound when a sprint ends"))
        vsizer.Add(self.soundCb, 0, wx.BOTTOM, 10)

        self.Bind(wx.EVT_CHOICE, self.OnMisc, id=self.unitChoice.GetId())
        self.Bind(wx.EVT_CHECKBOX, self.OnMisc, id=self.soundCb.GetId())

        self.cfg2gui()

        gutil.finishWindow(self, vsizer, center=False)

    # add a label and a spin control for the config variable 'name' to
    # grid, returning the spin control
    def addSpin(self, grid, label, name):
        grid.Add(wx.StaticText(self, -1, label), 0, wx.ALIGN_CENTER_VERTICAL)

        entry = wx.SpinCtrl(self, -1, size=(self.FromDIP(100), -1))
        entry.SetRange(*self.cfg.cvars.getMinMax(name))
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=entry.GetId())
        entry.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        grid.Add(entry, 0)

        return entry

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wx.GTK gets stuck in
        # some weird state
        event.Skip()

    def OnMisc(self, event=None):
        cfg = self.cfg
        cfg.dailyGoal = gutil.getSpinValue(self.dailyEntry)
        cfg.dailyGoalPages = self.unitChoice.GetSelection() == 1
        cfg.weeklyGoal = gutil.getSpinValue(self.weeklyEntry)
        cfg.sprintMinutes = gutil.getSpinValue(self.minutesEntry)
        cfg.sprintWords = gutil.getSpinValue(self.wordsEntry)
        cfg.sprintSound = self.soundCb.GetValue()

        self.updateUnit()

    # the weekly goal is in the daily one's unit
    def updateUnit(self):
        self.weeklyUnit.SetLabel(self.unitChoice.GetStringSelection())

    def cfg2gui(self):
        cfg = self.cfg
        self.dailyEntry.SetValue(cfg.dailyGoal)
        self.unitChoice.SetSelection(1 if cfg.dailyGoalPages else 0)
        self.weeklyEntry.SetValue(cfg.weeklyGoal)
        self.minutesEntry.SetValue(cfg.sprintMinutes)
        self.wordsEntry.SetValue(cfg.sprintWords)
        self.soundCb.SetValue(cfg.sprintSound)
        self.updateUnit()
