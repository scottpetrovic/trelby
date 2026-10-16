import wx

import trelby.reports.characterreport as characterreport
import trelby.reports.dialoguechart as dialoguechart
import trelby.ui.gutil as gutil
import trelby.reports.locationreport as locationreport
import trelby.pdf.writer as pdf
import trelby.reports.reportwindow as reportwindow
import trelby.reports.scenereport as scenereport
import trelby.reports.scriptreport as scriptreport


class SceneReportFrame(reportwindow.TextReportFrame):
    def getName(self):
        return _("Scene Report")

    def createReport(self):
        return scenereport.SceneReport(self.sp)


class LocationReportFrame(reportwindow.TextReportFrame):
    def getName(self):
        return _("Location Report")

    def createReport(self):
        return locationreport.LocationReport(scenereport.SceneReport(self.sp))


class ScriptReportFrame(reportwindow.TextReportFrame):
    def getName(self):
        return _("Script Report")

    def createReport(self):
        return scriptreport.ScriptReport(self.sp)


# character report, with a list on the side for choosing which characters
# to include.
class CharacterReportFrame(reportwindow.TextReportFrame):
    def getName(self):
        return _("Character Report")

    def createReport(self):
        return characterreport.CharacterReport(self.sp)

    def makeReport(self):
        old = getattr(self, "report", None)
        super().makeReport()

        if old:
            excluded = {ci.name for ci in old.cinfo if not ci.include}

            for ci in self.report.cinfo:
                ci.include = ci.name not in excluded

    def createControls(self, panel):
        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(panel, -1, _("Characters to include:")))

        self.charList = gutil.ThemedListBox(
            panel, -1, size=self.FromDIP(wx.Size(220, -1)), checkable=True
        )
        self.Bind(wx.EVT_CHECKLISTBOX, self.OnCharList, id=self.charList.GetId())
        vsizer.Add(self.charList, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        btn = wx.Button(panel, -1, _("All"))
        self.Bind(wx.EVT_BUTTON, lambda e: self.includeAll(True), id=btn.GetId())
        hsizer.Add(btn, 1)

        btn = wx.Button(panel, -1, _("None"))
        self.Bind(wx.EVT_BUTTON, lambda e: self.includeAll(False), id=btn.GetId())
        hsizer.Add(btn, 1, wx.LEFT, 5)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        self.contentSizer.Add(vsizer, 0, wx.EXPAND | wx.LEFT | wx.BOTTOM, 8)

        super().createControls(panel)

    def updateControls(self):
        cinfo = self.report.cinfo

        self.charList.Set([ci.name for ci in cinfo])
        self.charList.SetCheckedItems([i for i, ci in enumerate(cinfo) if ci.include])

    def OnCharList(self, event):
        for i, ci in enumerate(self.report.cinfo):
            ci.include = self.charList.IsChecked(i)

        self.update()

    def includeAll(self, include):
        for ci in self.report.cinfo:
            ci.include = include

        self.updateControls()
        self.update()

    def getEmptyMessage(self):
        if not self.report.cinfo:
            return _("No characters speaking found.")

        return _("No characters selected.")


# the dialogue chart, with its sort order and whether to show the
# characters with only a few lines
class DialogueChartFrame(reportwindow.ReportFrame):
    def __init__(self, parent, sp, scriptName):
        self.allChars = True
        self.doc = None

        reportwindow.ReportFrame.__init__(self, parent, sp, scriptName, (1100, 800))

    def getName(self):
        return _("Dialogue Chart")

    def makeReport(self):
        self.chart = dialoguechart.DialogueChart(self.sp)

    def createControls(self, panel):
        self.allCharsCb = wx.CheckBox(panel, -1, _("Characters with < 10 lines"))
        self.allCharsCb.SetValue(self.allChars)
        self.Bind(wx.EVT_CHECKBOX, self.OnAllChars, id=self.allCharsCb.GetId())
        self.optionsSizer.Add(
            self.allCharsCb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15
        )

        self.sortChoice = wx.Choice(
            panel, -1, choices=[label() for name, label, key in dialoguechart.SORTS]
        )
        self.sortChoice.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, lambda e: self.update(), id=self.sortChoice.GetId())
        self.optionsSizer.Add(self.sortChoice, 0, wx.ALIGN_CENTER_VERTICAL)

        self.view = reportwindow.PageView(panel)
        self.contentSizer.Add(self.view, 1, wx.EXPAND)

    def OnAllChars(self, event):
        self.allChars = self.allCharsCb.GetValue()
        self.update()

    def updateView(self):
        sort = dialoguechart.SORTS[self.sortChoice.GetSelection()][0]
        minLines = 1 if self.allChars else 10

        self.doc = dialoguechart.generateDoc(self.chart, self.sp.cfg, [sort], minLines)

        if self.doc:
            self.view.setDoc(self.doc)
        elif self.allChars:
            self.view.setDoc(None, _("No characters speaking found."))
        else:
            self.view.setDoc(None, _("No characters with 10 or more lines found."))

        self.hasContents = self.doc is not None

    def getPDF(self):
        return pdf.generate(self.doc)


def genSceneReport(mainFrame, sp, scriptName):
    reportwindow.show(SceneReportFrame, mainFrame, sp, scriptName)


def genLocationReport(mainFrame, sp, scriptName):
    reportwindow.show(LocationReportFrame, mainFrame, sp, scriptName)


def genCharacterReport(mainFrame, sp, scriptName):
    reportwindow.show(CharacterReportFrame, mainFrame, sp, scriptName)


def genScriptReport(mainFrame, sp, scriptName):
    reportwindow.show(ScriptReportFrame, mainFrame, sp, scriptName)


def genDialogueChart(mainFrame, sp, scriptName):
    reportwindow.show(DialogueChartFrame, mainFrame, sp, scriptName)
