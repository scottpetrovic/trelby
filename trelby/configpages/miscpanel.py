import trelby.gutil as gutil
import trelby.misc as misc
import trelby.util as util
import wx


class MiscPanel(wx.Panel):
    def __init__(self, parent, id, cfg, cfgFrame):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg
        self.cfgFrame = cfgFrame

        vsizer = wx.BoxSizer(wx.VERTICAL)

        bsizer = wx.StaticBoxSizer(
            wx.StaticBox(self, -1, _("Default script directory")), wx.VERTICAL
        )

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.scriptDirEntry = wx.TextCtrl(self, -1)
        hsizer.Add(self.scriptDirEntry, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        btn = wx.Button(self, -1, _("Browse"))
        self.Bind(wx.EVT_BUTTON, self.OnBrowse, id=btn.GetId())
        hsizer.Add(btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        bsizer.Add(hsizer, 1, wx.EXPAND | wx.RIGHT | wx.TOP | wx.BOTTOM, 10)

        vsizer.Add(bsizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        bsizer = wx.StaticBoxSizer(
            wx.StaticBox(self, -1, _("Spell checker")), wx.VERTICAL
        )

        btn = wx.Button(bsizer.GetStaticBox(), -1, _("Global dictionary") + "...")
        btn.Bind(wx.EVT_BUTTON, self.OnScDict)
        bsizer.Add(btn, 0, wx.ALL, 10)

        vsizer.Add(bsizer, 0, wx.EXPAND)

        # wxGTK adds way more space by default than wxMSW between the
        # items, have to adjust for that
        pad = 5
        if misc.isWindows:
            pad = 10

        self.checkListItems = [
            ("capitalize", _("Auto-capitalize sentences")),
            ("capitalizeI", _("Auto-capitalize i -> I")),
            ("honorSavedPos", _("When opening a script, start at last saved position")),
            ("recenterOnScroll", _("Recenter screen on scrolling")),
            ("overwriteSelectionOnInsert", _("Typing replaces selected text")),
            (
                "checkOnExport",
                _("Check script for errors before export or compare"),
            ),
        ]

        self.checkList = gutil.ThemedListBox(self, -1, size=(-1, 120), checkable=True)

        for it in self.checkListItems:
            self.checkList.Append(it[1])

        vsizer.Add(self.checkList, 0, wx.TOP | wx.BOTTOM, pad)

        self.Bind(wx.EVT_LISTBOX, self.OnMisc, id=self.checkList.GetId())
        self.Bind(wx.EVT_CHECKLISTBOX, self.OnMisc, id=self.checkList.GetId())

        self.addSpin(
            "paginate",
            _("Auto-paginate interval in seconds:\n (0 = disable)"),
            self,
            vsizer,
            "paginateInterval",
        )

        self.addSpin(
            "autosave",
            _("Autosave recovery copy interval in minutes:\n (0 = disable)"),
            self,
            vsizer,
            "autosaveInterval",
        )

        self.addSpin(
            "wheelScroll",
            _("Lines to scroll per mouse wheel event:"),
            self,
            vsizer,
            "mouseWheelLines",
        )

        self.cfg2gui()

        util.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.scriptDirEntry.GetId())

    def addSpin(self, name, descr, parent, sizer, cfgName):
        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(parent, -1, descr), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10
        )

        tmp = wx.SpinCtrl(parent, -1)
        tmp.SetRange(*self.cfg.cvars.getMinMax(cfgName))
        self.Bind(wx.EVT_SPINCTRL, self.OnMisc, id=tmp.GetId())
        tmp.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        hsizer.Add(tmp)

        sizer.Add(hsizer, 0, wx.BOTTOM, 10)

        setattr(self, name + "Entry", tmp)

    def OnKillFocus(self, event):
        self.OnMisc()

        # if we don't call this, the spin entry on wxGTK gets stuck in
        # some weird state
        event.Skip()

    def OnMisc(self, event=None):
        self.cfg.scriptDir = self.scriptDirEntry.GetValue().rstrip("/\\")

        for i, it in enumerate(self.checkListItems):
            setattr(self.cfg, it[0], bool(self.checkList.IsChecked(i)))

        self.cfg.paginateInterval = util.getSpinValue(self.paginateEntry)
        self.cfg.autosaveInterval = util.getSpinValue(self.autosaveEntry)
        self.cfg.mouseWheelLines = util.getSpinValue(self.wheelScrollEntry)

    def OnBrowse(self, event):
        dlg = wx.DirDialog(
            self.cfgFrame, defaultPath=self.cfg.scriptDir, style=wx.DD_NEW_DIR_BUTTON
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.scriptDirEntry.SetValue(dlg.GetPath())

        dlg.Destroy()

    def OnScDict(self, event):
        self.cfgFrame.editScDict()

    def cfg2gui(self):
        # stupid wxwindows/wxpython displays empty box if the initial
        # value is zero if we don't do this...
        self.paginateEntry.SetValue(5)
        self.autosaveEntry.SetValue(5)

        self.scriptDirEntry.SetValue(self.cfg.scriptDir)

        for i, it in enumerate(self.checkListItems):
            self.checkList.Check(i, getattr(self.cfg, it[0]))

        self.paginateEntry.SetValue(self.cfg.paginateInterval)
        self.autosaveEntry.SetValue(self.cfg.autosaveInterval)
        self.wheelScrollEntry.SetValue(self.cfg.mouseWheelLines)
