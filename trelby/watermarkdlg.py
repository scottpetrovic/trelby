import random

import wx

import trelby.gutil as gutil
import trelby.pdf as pdf
import trelby.pml as pml
import trelby.screenplay.render as render
import trelby.textutil as textutil


# The watermark tool dialog.
class WatermarkDlg(wx.Dialog):
    # sp - screenplay object, from which to generate PDF
    # prefix - prefix name for the PDF files (unicode)
    def __init__(self, parent, sp, prefix):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Watermarked PDFs generator"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.frame = parent
        self.sp = sp

        vsizer = wx.BoxSizer(wx.VERTICAL)

        vsizer.Add(wx.StaticText(self, -1, _("Directory to save in:")), 0)
        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dirEntry = wx.TextCtrl(self, -1)
        hsizer.Add(self.dirEntry, 1, wx.EXPAND)

        btn = wx.Button(self, -1, _("Browse"))
        self.Bind(wx.EVT_BUTTON, self.OnBrowse, id=btn.GetId())
        hsizer.Add(btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        vsizer.Add(wx.StaticText(self, -1, _("Filename prefix:")), 0)
        self.filenamePrefix = wx.TextCtrl(self, -1, prefix)
        vsizer.Add(self.filenamePrefix, 0, wx.EXPAND | wx.BOTTOM, 5)

        vsizer.Add(wx.StaticText(self, -1, _("Watermark font size:")), 0)
        self.markSize = wx.SpinCtrl(self, -1, size=(60, -1))
        self.markSize.SetRange(20, 80)
        self.markSize.SetValue(40)
        vsizer.Add(self.markSize, 0, wx.BOTTOM, 5)

        vsizer.Add(gutil.Separator(self), 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        vsizer.Add(wx.StaticText(self, -1, _("Common mark:")), 0)
        self.commonMark = wx.TextCtrl(self, -1, _("Confidential"))
        vsizer.Add(self.commonMark, 0, wx.EXPAND | wx.BOTTOM, 5)

        vsizer.Add(wx.StaticText(self, -1, _("Watermarks (one per line):")))
        self.itemsEntry = wx.TextCtrl(
            self, -1, style=wx.TE_MULTILINE | wx.TE_DONTWRAP, size=(300, 200)
        )
        vsizer.Add(self.itemsEntry, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        closeBtn = wx.Button(self, -1, _("Close"))
        hsizer.Add(closeBtn, 0)
        hsizer.Add((1, 1), 1)
        generateBtn = wx.Button(self, -1, _("Generate PDFs"))
        hsizer.Add(generateBtn, 0)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 10)

        gutil.finishWindow(self, vsizer)

        self.Bind(wx.EVT_BUTTON, self.OnClose, id=closeBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnGenerate, id=generateBtn.GetId())

        self.dirEntry.SetFocus()

    @staticmethod
    def getUniqueId(usedIds):
        while True:
            uid = ""

            for i in range(8):
                uid += "%02x" % random.randint(0, 255)

            if uid in usedIds:
                continue

            usedIds.add(uid)

            return uid

    def OnGenerate(self, event):
        watermarks = self.itemsEntry.GetValue().split("\n")
        common = self.commonMark.GetValue()
        directory = self.dirEntry.GetValue()
        fontsize = self.markSize.GetValue()
        fnprefix = self.filenamePrefix.GetValue()

        watermarks = set(watermarks)

        # keep track of ids allocated so far, just on the off-chance we
        # randomly allocated the same id twice
        usedIds = set()

        if not directory:
            wx.MessageBox(_("Please set directory."), _("Error"), wx.OK, self)
            self.dirEntry.SetFocus()
            return

        count = 0

        for item in watermarks:
            s = item.strip()

            if not s:
                continue

            basename = s.replace(" ", "-")
            fn = directory + "/" + fnprefix + "-" + basename + ".pdf"
            pmldoc = render.generatePML(self.sp)

            ops = []

            # almost-not-there gray
            ops.append(pml.PDFOp("0.85 g"))

            if common:
                wm = pml.TextOp(
                    textutil.cleanInput(common),
                    self.sp.cfg.marginLeft + 20,
                    self.sp.cfg.paperHeight * 0.45,
                    fontsize,
                    pml.BOLD,
                    angle=45,
                )
                ops.append(wm)

            wm = pml.TextOp(
                textutil.cleanInput(s),
                self.sp.cfg.marginLeft + 20,
                self.sp.cfg.paperHeight * 0.6,
                fontsize,
                pml.BOLD,
                angle=45,
            )
            ops.append(wm)

            # ...and back to black
            ops.append(pml.PDFOp("0.0 g"))

            # drawn first, so that the script's text is drawn over the
            # watermark rather than hidden by it
            for page in pmldoc.pages:
                page.addOpsToFront(ops)

            # a random id written into the PDF's keywords, different for
            # each recipient's copy, so that a copy can be traced back to
            # whom it was given
            pmldoc.uniqueId = self.getUniqueId(usedIds)

            pdfdata = pdf.generate(pmldoc)

            if not gutil.writeToFile(fn, pdfdata, self):
                wx.MessageBox(_("PDF generation aborted."), _("Error"), wx.OK, self)
                return
            else:
                count += 1

        if count > 0:
            wx.MessageBox(
                _("Generated {} files in directory {}.").format(count, directory),
                _("PDFs generated"),
                wx.OK,
                self,
            )
        else:
            wx.MessageBox(_("No watermarks specified."), _("Error"), wx.OK, self)

    def OnClose(self, event):
        self.EndModal(wx.OK)

    def OnBrowse(self, event):
        dlg = wx.DirDialog(self.frame, style=wx.DD_NEW_DIR_BUTTON)

        if dlg.ShowModal() == wx.ID_OK:
            self.dirEntry.SetValue(dlg.GetPath())

        dlg.Destroy()
