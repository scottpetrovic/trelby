# Built-in PDF viewer: shows PDFs in an embedded web view, using the PDF
# support of the platform's browser engine (Edge WebView2 on Windows,
# WebKit on macOS). Elsewhere, or if the engine fails, util.showPDF falls
# back to the external viewer application.

import shutil

import trelby.misc as misc
import trelby.util as util
import wx
import wx.html2

# the single viewer window, reused for every PDF shown
_viewer = None


def _getBackend():
    if misc.isWindows:
        return wx.html2.WebViewBackendEdge
    if misc.isMac:
        return wx.html2.WebViewBackendWebKit

    # WebKitGTK has no built-in PDF support
    return None


# return True if the built-in viewer can be used on this machine.
def isAvailable() -> bool:
    backend = _getBackend()

    return bool(backend) and wx.html2.WebView.IsBackendAvailable(backend)


# show PDF file 'filename' in the built-in viewer window, creating it if
# needed.
def show(filename: str, cfgGl: "config.ConfigGlobal") -> None:
    global _viewer

    if not _viewer:
        _viewer = PDFViewerFrame(wx.GetApp().GetTopWindow(), cfgGl)

    _viewer.load(filename)


class PDFViewerFrame(wx.Frame):
    def __init__(self, parent, cfgGl):
        wx.Frame.__init__(self, parent, -1, _("PDF Preview"))

        self.cfgGl = cfgGl
        self.filename = None

        self.SetIcons(wx.GetApp().GetTopWindow().GetIcons())
        self.setInitialSize()

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        btn = wx.Button(panel, -1, _("Save As..."))
        self.Bind(wx.EVT_BUTTON, self.OnSaveAs, id=btn.GetId())
        hsizer.Add(btn, 0, wx.RIGHT, 10)

        btn = wx.Button(panel, -1, _("Open in External Viewer"))
        self.Bind(wx.EVT_BUTTON, self.OnExternal, id=btn.GetId())
        hsizer.Add(btn)

        vsizer.Add(hsizer, 0, wx.ALL, 5)

        self.webView = wx.html2.WebView.New(panel, backend=_getBackend())
        vsizer.Add(self.webView, 1, wx.EXPAND)

        panel.SetSizer(vsizer)

        self.Bind(wx.html2.EVT_WEBVIEW_ERROR, self.OnWebViewError)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def setInitialSize(self):
        parent = self.GetParent()
        displayIdx = wx.Display.GetFromWindow(parent) if parent else 0
        area = wx.Display(max(displayIdx, 0)).GetClientArea()

        w = min(900, int(area.width * 0.9))
        h = int(area.height * 0.9)

        self.SetSize(
            area.x + (area.width - w) // 2, area.y + (area.height - h) // 2, w, h
        )

    def load(self, filename):
        self.filename = filename
        self.webView.LoadURL(wx.FileSystem.FileNameToURL(filename))

        self.Show()

        if self.IsIconized():
            self.Iconize(False)

        self.Raise()

    def OnSaveAs(self, event):
        dlg = wx.FileDialog(
            self,
            _("Save PDF As"),
            self.cfgGl.scriptDir,
            wildcard=_("PDF files") + " (*.pdf)|*.pdf|" + _("All files") + "|*",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            try:
                shutil.copyfile(self.filename, dlg.GetPath())
            except OSError as e:
                wx.MessageBox(
                    _("Error saving file: {}").format(e), _("Error"), wx.OK, self
                )

        dlg.Destroy()

    def OnExternal(self, event):
        util.showPDFExternal(self.filename, self.cfgGl, self)

    # the browser engine couldn't show the file (e.g. its PDF support is
    # disabled by policy), so hand it to the external viewer instead.
    def OnWebViewError(self, event):
        filename = self.filename
        self.Close()
        util.showPDFExternal(filename, self.cfgGl, wx.GetApp().GetTopWindow())

    def OnClose(self, event):
        global _viewer

        _viewer = None
        self.Destroy()
