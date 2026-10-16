import os.path

import trelby.ui.gutil as gutil
import trelby.misc as misc
import trelby.ui.pdfviewer as pdfviewer
import trelby.util as util
import wx


class PDFViewerPanel(wx.Panel):
    def __init__(self, parent, id, cfg, cfgFrame):
        wx.Panel.__init__(self, parent, id)
        self.cfg = cfg
        self.cfgFrame = cfgFrame

        vsizer = wx.BoxSizer(wx.VERTICAL)

        self.builtinCb = wx.CheckBox(self, -1, _("Use built-in PDF viewer"))
        vsizer.Add(self.builtinCb, 0, wx.BOTTOM, 5)

        if pdfviewer.isAvailable():
            note = _(
                "The application below is used when the built-in viewer is"
                " turned off or can't open a file."
            )
        else:
            self.builtinCb.Disable()
            note = _("The built-in viewer isn't available on this system.")

        vsizer.Add(wx.StaticText(self, -1, note), 0, wx.BOTTOM, 10)

        bsizer = wx.StaticBoxSizer(
            wx.StaticBox(self, -1, _("PDF viewer application")), wx.VERTICAL
        )
        box = bsizer.GetStaticBox()

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(box, -1, _("Path:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.progEntry = wx.TextCtrl(box, -1)
        hsizer.Add(self.progEntry, 1, wx.ALIGN_CENTER_VERTICAL)

        btn = wx.Button(box, -1, _("Browse"))
        self.Bind(wx.EVT_BUTTON, self.OnBrowsePDF, id=btn.GetId())
        hsizer.Add(btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        btn = wx.Button(box, -1, _("Guess"))
        self.Bind(wx.EVT_BUTTON, self.OnGuessPDF, id=btn.GetId())
        hsizer.Add(btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        bsizer.Add(hsizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add(
            wx.StaticText(box, -1, _("Arguments:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        self.argsEntry = wx.TextCtrl(box, -1)
        hsizer.Add(self.argsEntry, 1, wx.ALIGN_CENTER_VERTICAL)

        bsizer.Add(hsizer, 1, wx.EXPAND | wx.ALL, 10)

        vsizer.Add(bsizer, 0, wx.EXPAND)

        self.cfg2gui()

        gutil.finishWindow(self, vsizer, center=False)

        self.Bind(wx.EVT_CHECKBOX, self.OnMisc, id=self.builtinCb.GetId())
        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.progEntry.GetId())
        self.Bind(wx.EVT_TEXT, self.OnMisc, id=self.argsEntry.GetId())

    def OnMisc(self, event=None):
        self.cfg.pdfUseBuiltinViewer = self.builtinCb.GetValue()
        self.cfg.pdfViewerPath = self.progEntry.GetValue()
        self.cfg.pdfViewerArgs = misc.fromGUI(self.argsEntry.GetValue())

    def OnBrowsePDF(self, event):
        dlg = wx.FileDialog(
            self.cfgFrame,
            _("Choose program"),
            os.path.dirname(self.cfg.pdfViewerPath),
            self.cfg.pdfViewerPath,
            style=wx.FD_OPEN,
        )

        if dlg.ShowModal() == wx.ID_OK:
            self.progEntry.SetValue(dlg.GetPath())

        dlg.Destroy()

    def OnGuessPDF(self, event):
        viewer = util.getPDFViewer()[0]

        if viewer:
            self.progEntry.SetValue(viewer)
        else:
            wx.MessageBox(
                _("Unable to guess. Please set the path manually."),
                _("PDF Viewer"),
                wx.OK,
                self.cfgFrame,
            )

    def cfg2gui(self):
        self.builtinCb.SetValue(self.cfg.pdfUseBuiltinViewer)
        self.progEntry.SetValue(self.cfg.pdfViewerPath)
        self.argsEntry.SetValue(self.cfg.pdfViewerArgs)
