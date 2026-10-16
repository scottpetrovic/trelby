import wx

import trelby.characterreport as characterreport
import trelby.gutil as gutil
import trelby.locationreport as locationreport
import trelby.reportwindow as reportwindow
import trelby.scenereport as scenereport
import trelby.scriptreport as scriptreport


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


def genSceneReport(mainFrame, sp, scriptName):
    reportwindow.show(SceneReportFrame, mainFrame, sp, scriptName)


def genLocationReport(mainFrame, sp, scriptName):
    reportwindow.show(LocationReportFrame, mainFrame, sp, scriptName)


def genCharacterReport(mainFrame, sp, scriptName):
    reportwindow.show(CharacterReportFrame, mainFrame, sp, scriptName)


def genScriptReport(mainFrame, sp, scriptName):
    reportwindow.show(ScriptReportFrame, mainFrame, sp, scriptName)
