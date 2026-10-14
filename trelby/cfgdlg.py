import copy
import os.path

import wx

import trelby.config as config
import trelby.gutil as gutil
import trelby.spellcheckcfgdlg as spellcheckcfgdlg
import trelby.util as util
from trelby.configpages.colorspanel import ColorsPanel
from trelby.configpages.displaypanel import DisplayPanel
from trelby.configpages.elementsglobalpanel import ElementsGlobalPanel
from trelby.configpages.elementspanel import ElementsPanel
from trelby.configpages.formattingpanel import FormattingPanel

# import config pages
from trelby.configpages.globalaboutpanel import GlobalAboutPanel
from trelby.configpages.keyboardpanel import KeyboardPanel
from trelby.configpages.miscpanel import MiscPanel
from trelby.configpages.paperpanel import PaperPanel
from trelby.configpages.pdffontspanel import PDFFontsPanel
from trelby.configpages.pdfpanel import PDFPanel
from trelby.configpages.scriptaboutpanel import ScriptAboutPanel
from trelby.configpages.stringspanel import StringsPanel
from trelby.configpages.themepanel import ThemePanel


# ask for a global settings file to load (save=False) or save, starting at
# 'filename'. returns the chosen path, or None if the user cancelled.
def askSettingsFile(parent, filename, save):
    if save:
        title = _("Filename to save as")
        style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    else:
        title = _("File to open")
        style = wx.FD_OPEN

    dlg = wx.FileDialog(
        parent,
        title,
        defaultDir=os.path.dirname(filename),
        defaultFile=os.path.basename(filename),
        wildcard=_("Setting")
        + " "
        + _("files")
        + " (*.conf)|*.conf|"
        + _("All files")
        + "|*",
        style=style,
    )

    path = None
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPath()

    dlg.Destroy()

    return path


# load global settings from the given file. returns a ConfigGlobal, or None
# on error.
def loadGlobalCfg(filename, parent):
    s = util.loadFile(filename, parent)

    if not s:
        return None

    c = config.ConfigGlobal()
    c.load(s)

    return c


class CfgDlg(wx.Dialog):
    # gd is only needed (and used) for the global settings dialog.
    def __init__(self, parent, cfg, applyFunc, isGlobal, gd=None):
        wx.Dialog.__init__(
            self, parent, -1, "", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.cfg = cfg
        self.applyFunc = applyFunc
        self.isGlobal = isGlobal
        self.gd = gd

        if isGlobal:
            # settings file the global config is written to when applied.
            # Load/Save as change it, but it only takes effect on Apply/OK.
            self.confFilename = gd.confFilename

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.listbook = wx.Treebook(self, -1)

        if isGlobal:
            self.SetTitle(_("Settings dialog"))
        else:
            self.SetTitle(_("Script settings dialog"))

        self.addPages()

        # the page list is a flat tree (a wx.Listbook truncates long page
        # names). drop the indent meant for child pages, and make it wide
        # enough for the longest name plus some padding.
        tree = self.listbook.GetTreeCtrl()
        tree.SetIndent(0)
        w = max(
            tree.GetTextExtent(self.listbook.GetPageText(i))[0]
            for i in range(self.listbook.GetPageCount())
        )
        tree.SetMinSize((w + tree.FromDIP(40), -1))

        vsizer.Add(self.listbook, 1, wx.EXPAND)

        vsizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        if isGlobal:
            loadBtn = wx.Button(self, -1, _("Load") + "...")
            loadBtn.SetToolTip(_("Load settings from a file"))
            hsizer.Add(loadBtn, 0, wx.RIGHT, 10)
            self.Bind(wx.EVT_BUTTON, self.OnLoad, id=loadBtn.GetId())

            saveBtn = wx.Button(self, -1, _("Save as") + "...")
            saveBtn.SetToolTip(_("Save these settings to a file"))
            hsizer.Add(saveBtn, 0, wx.RIGHT, 10)
            self.Bind(wx.EVT_BUTTON, self.OnSaveAs, id=saveBtn.GetId())

        hsizer.Add((1, 1), 1)

        applyBtn = gutil.createStockButton(self, _("Apply"))
        hsizer.Add(applyBtn, 0, wx.LEFT, 10)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        util.finishWindow(self, vsizer)
        # self.Center()

        self.Bind(wx.EVT_BUTTON, self.OnApply, id=applyBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

    def addPages(self):
        if self.isGlobal:
            self.AddPage(ThemePanel, _("Theme"))
            self.AddPage(GlobalAboutPanel, _("About"))
            self.AddPage(ColorsPanel, _("Colors"))
            self.AddPage(DisplayPanel, _("Display"))
            self.AddPage(ElementsGlobalPanel, _("Elements"))
            self.AddPage(KeyboardPanel, _("Keyboard"))
            self.AddPage(MiscPanel, _("Misc"))
        else:
            self.AddPage(ScriptAboutPanel, _("About"))
            self.AddPage(ElementsPanel, _("Elements"))
            self.AddPage(FormattingPanel, _("Formatting"))
            self.AddPage(PaperPanel, _("Paper"))
            self.AddPage(PDFPanel, "PDF")
            self.AddPage(PDFFontsPanel, _("PDF/Fonts"))
            self.AddPage(StringsPanel, _("Strings"))

    def AddPage(self, classObj, name):
        # stupid hack to get correct window modality stacking for dialogs
        needs_frame_ref = [DisplayPanel, KeyboardPanel, MiscPanel, PDFFontsPanel]
        if classObj in needs_frame_ref:
            p = classObj(self.listbook, -1, self.cfg, self)
        else:
            p = classObj(self.listbook, -1, self.cfg)

        self.listbook.AddPage(p, name)

    # check for errors in each panel
    def checkForErrors(self):
        for pageNum in range(self.listbook.GetPageCount()):
            panel = self.listbook.GetPage(pageNum)
            if hasattr(panel, "checkForErrors"):
                panel.checkForErrors()

    # make the settings file chosen in this dialog the active one. must be
    # called before the config is applied, since that writes it out.
    def commitConfFilename(self):
        if self.isGlobal:
            self.gd.confFilename = self.confFilename

    def OnOK(self, event):
        self.checkForErrors()
        self.commitConfFilename()
        self.EndModal(wx.ID_OK)

    def OnApply(self, event):
        self.checkForErrors()
        self.commitConfFilename()
        self.applyFunc(self.cfg)

    # replace the settings being edited with ones loaded from a file. they
    # are applied, like any other change, on Apply/OK.
    def OnLoad(self, event):
        path = askSettingsFile(self, self.confFilename, False)
        if not path:
            return

        c = loadGlobalCfg(path, self)
        if not c:
            return

        self.cfg = c
        self.confFilename = path

        # the pages hold references to the old config, so recreate them
        sel = self.listbook.GetSelection()
        self.listbook.DeleteAllPages()
        self.addPages()
        self.listbook.SetSelection(sel)

    def OnSaveAs(self, event):
        self.checkForErrors()

        path = askSettingsFile(self, self.confFilename, True)
        if not path:
            return

        # save what the dialog currently shows, applied or not
        c = copy.deepcopy(self.cfg)
        c.recalc()

        if util.writeToFile(path, c.save(), self):
            self.confFilename = path

    # edit the global spell checker dictionary. it's stored separately from
    # the settings, so changes are saved immediately.
    def editScDict(self):
        dlg = spellcheckcfgdlg.SCDictDlg(self, copy.deepcopy(self.gd.scDict), True)

        if dlg.ShowModal() == wx.ID_OK:
            self.gd.scDict = dlg.scDict
            self.gd.saveScDict()

        dlg.Destroy()

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
