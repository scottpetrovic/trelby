# Windows that show the reports from the Reports menu inside the
# application, with their options shown alongside so that changing one
# updates the report right away. A report can be saved as a PDF from its
# window.

import html
import math
import re

import wx
import wx.html

import trelby.misc as misc
import trelby.pml as pml
import trelby.util as util

# open report windows. key = (window class, id of the Screenplay), value =
# the window.
_frames = {}


# show a report window of class 'frameClass' for screenplay 'sp',
# refreshing and raising it if it's already open.
def show(frameClass, parent, sp, scriptName):
    frame = _frames.get((frameClass, id(sp)))

    if frame:
        frame.refresh()
    else:
        frame = frameClass(parent, sp, scriptName)

    frame.Show()

    if frame.IsIconized():
        frame.Iconize(False)

    frame.Raise()


# base class for report windows. subclasses implement:
#
#  getName(): the report's name, e.g. "Scene report"
#  makeReport(): (re)create the report from self.sp, keeping the options
#    of the previous one, if any
#  createControls(panel): create the option controls, adding them to
#    self.optionsSizer, and the view, adding it to self.contentSizer
#  updateView(): show the report with the current options, and set
#    self.hasContents
#  getPDF(): the report as PDF data
#
# and possibly updateControls(), called after the report is (re)created.
class ReportFrame(wx.Frame):
    def __init__(self, parent, sp, scriptName, size=(800, 700)):
        wx.Frame.__init__(self, parent, -1, "%s - %s" % (self.getName(), scriptName))

        self.sp = sp
        self.scriptName = scriptName
        self.hasContents = False

        _frames[(type(self), id(sp))] = self

        self.SetIcons(parent.GetIcons())
        size = self.FromDIP(wx.Size(*size))
        self.setInitialSize(size.width, size.height)

        panel = wx.Panel(self)
        vsizer = wx.BoxSizer(wx.VERTICAL)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        self.optionsSizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.optionsSizer, 1, wx.ALIGN_CENTER_VERTICAL)

        btn = wx.Button(panel, -1, _("Refresh"))
        btn.SetToolTip(_("Update the report with the script's current contents."))
        self.Bind(wx.EVT_BUTTON, self.OnRefresh, id=btn.GetId())
        hsizer.Add(btn, 0, wx.LEFT, 10)

        self.saveBtn = wx.Button(panel, -1, _("Save as PDF..."))
        self.Bind(wx.EVT_BUTTON, self.OnSavePDF, id=self.saveBtn.GetId())
        hsizer.Add(self.saveBtn, 0, wx.LEFT, 10)

        vsizer.Add(hsizer, 0, wx.EXPAND | wx.ALL, 8)

        self.contentSizer = wx.BoxSizer(wx.HORIZONTAL)
        vsizer.Add(self.contentSizer, 1, wx.EXPAND)

        self.makeReport()
        self.createControls(panel)
        self.updateControls()
        self.update()

        panel.SetSizer(vsizer)

        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)
        self.Bind(wx.EVT_CLOSE, self.OnClose)

    def setInitialSize(self, w, h):
        displayIdx = wx.Display.GetFromWindow(self.GetParent())
        area = wx.Display(max(displayIdx, 0)).GetClientArea()

        w = min(w, int(area.width * 0.9))
        h = min(h, int(area.height * 0.9))

        self.SetSize(
            area.x + (area.width - w) // 2, area.y + (area.height - h) // 2, w, h
        )

    def updateControls(self):
        pass

    def update(self):
        self.updateView()
        self.saveBtn.Enable(self.hasContents)

    # re-create the report from the script's current contents.
    def refresh(self):
        self.sp.paginate()
        self.makeReport()
        self.updateControls()
        self.update()

    def OnRefresh(self, event):
        self.refresh()

    def OnSavePDF(self, event):
        name = self.scriptName

        if name.endswith(".trelby"):
            name = name[: -len(".trelby")]

        dlg = wx.FileDialog(
            self,
            _("Save as PDF"),
            misc.scriptDir,
            "%s - %s.pdf" % (name, self.getName()),
            _("PDF files") + " (*.pdf)|*.pdf|" + _("All files") + "|*",
            wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        )

        if dlg.ShowModal() == wx.ID_OK:
            util.writeToFile(dlg.GetPath(), self.getPDF(), self)

        dlg.Destroy()

    def OnCharHook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def OnClose(self, event):
        _frames.pop((type(self), id(self.sp)), None)
        self.Destroy()


# window for a textreport.TextReport. subclasses implement getName() and
# createReport(), which returns a new report object for self.sp. the
# report's 'inf' items, if it has any, are shown as checkboxes.
class TextReportFrame(ReportFrame):
    def makeReport(self):
        old = getattr(self, "report", None)
        self.report = self.createReport()

        if old:
            for it, oldIt in zip(self.getInf(), old.inf):
                it.selected = oldIt.selected

    def getInf(self):
        return getattr(self.report, "inf", [])

    def createControls(self, panel):
        self.infBoxes = []

        for it in self.getInf():
            cb = wx.CheckBox(panel, -1, it.text)
            cb.SetValue(it.selected)
            self.Bind(wx.EVT_CHECKBOX, self.OnOption, id=cb.GetId())
            self.optionsSizer.Add(cb, 0, wx.RIGHT, 15)
            self.infBoxes.append(cb)

        self.htmlWin = wx.html.HtmlWindow(panel, -1, style=wx.BORDER_NONE)
        self.htmlWin.SetBorders(self.FromDIP(15))
        self.contentSizer.Add(self.htmlWin, 1, wx.EXPAND)

    def OnOption(self, event):
        for it, cb in zip(self.getInf(), self.infBoxes):
            it.selected = cb.GetValue()

        self.update()

    # message shown when the report has no contents
    def getEmptyMessage(self):
        return _("Nothing to show.")

    def updateView(self):
        body = self.report.generateHtml()
        self.hasContents = bool(body)

        if not body:
            body = "<i>%s</i>" % html.escape(self.getEmptyMessage())

        bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
        fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)

        # keep the scroll position when the options change
        pos = self.htmlWin.GetViewStart()

        self.htmlWin.SetPage(
            '<html><body bgcolor="%s" text="%s">%s</body></html>'
            % (
                bg.GetAsString(wx.C2S_HTML_SYNTAX),
                fg.GetAsString(wx.C2S_HTML_SYNTAX),
                body,
            )
        )

        self.htmlWin.Scroll(*pos)

    def getPDF(self):
        return self.report.generate()


# shows the first page of a pml.Document, scaled to fit the window, or
# a message if there's no document. draws the operations the reports use;
# others are ignored.
class PageView(wx.Window):
    def __init__(self, parent):
        wx.Window.__init__(self, parent, -1)

        self.doc = None
        self.message = ""

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def setDoc(self, doc, message=""):
        self.doc = doc
        self.message = message
        self.Refresh()

    def OnSize(self, event):
        self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        dc = wx.AutoBufferedPaintDC(self)

        parent = self.GetParent()
        dc.SetBackground(wx.Brush(parent.GetBackgroundColour()))
        dc.Clear()

        ww, wh = self.GetClientSize()

        if not self.doc:
            dc.SetFont(parent.GetFont())
            dc.SetTextForeground(parent.GetForegroundColour())
            tw, th = dc.GetTextExtent(self.message)
            dc.DrawText(self.message, (ww - tw) // 2, (wh - th) // 2)

            return

        doc = self.doc
        pad = self.FromDIP(10)

        # pixels per mm
        scale = min((ww - pad * 2) / doc.w, (wh - pad * 2) / doc.h)

        if scale <= 0:
            return

        ox = (ww - doc.w * scale) / 2.0
        oy = (wh - doc.h * scale) / 2.0

        gc = wx.GraphicsContext.Create(dc)

        gc.SetPen(wx.Pen(wx.Colour(128, 128, 128)))
        gc.SetBrush(wx.WHITE_BRUSH)
        gc.DrawRectangle(ox, oy, doc.w * scale, doc.h * scale)

        _PageRenderer(gc, ox, oy, scale).draw(doc.pages[0])


def _gray(v):
    c = round(v * 255)

    return wx.Colour(c, c, c)


# key = wx.FONTFAMILY_*, value = face name
_faceNames = {}


def _getFaceName(family):
    if family not in _faceNames:
        _faceNames[family] = wx.Font(wx.FontInfo(10).Family(family)).GetFaceName()

    return _faceNames[family]


# draws pml operations on a wx.GraphicsContext, with the page's upper left
# corner at (ox, oy) and 'scale' pixels per mm.
class _PageRenderer:
    # the PDF commands the reports use in pml.PDFOps: setting the fill (g)
    # or stroke (G) gray level, and the line dash pattern (d)
    grayRe = re.compile(r"([\d.]+) ([gG])$")
    dashRe = re.compile(r"\[(.*)\] [\d.]+ d$")

    def __init__(self, gc, ox, oy, scale):
        self.gc = gc
        self.ox = ox
        self.oy = oy
        self.scale = scale

        self.fill = 0.0
        self.stroke = 0.0
        self.dashed = False

    def x(self, mm):
        return self.ox + mm * self.scale

    def y(self, mm):
        return self.oy + mm * self.scale

    def draw(self, page):
        for op in page.ops:
            if isinstance(op, pml.TextOp):
                self.drawText(op)
            elif isinstance(op, pml.LineOp):
                self.drawLine(op)
            elif isinstance(op, pml.RectOp):
                self.drawRect(op)
            elif isinstance(op, pml.PDFOp):
                self.applyPDFOp(op)

    def pen(self, lw):
        info = wx.GraphicsPenInfo(_gray(self.stroke)).Width(max(1.0, lw * self.scale))

        if self.dashed:
            info.Style(wx.PENSTYLE_SHORT_DASH)

        return self.gc.CreatePen(info)

    def drawText(self, op):
        if op.flags & pml.TIMES_ROMAN:
            family = wx.FONTFAMILY_ROMAN
        elif op.flags & pml.HELVETICA:
            family = wx.FONTFAMILY_SWISS
        else:
            family = wx.FONTFAMILY_TELETYPE

        flags = wx.FONTFLAG_DEFAULT

        if op.flags & pml.BOLD:
            flags |= wx.FONTFLAG_BOLD

        if op.flags & pml.ITALIC:
            flags |= wx.FONTFLAG_ITALIC

        if op.flags & pml.UNDERLINED:
            flags |= wx.FONTFLAG_UNDERLINED

        font = self.gc.CreateFont(
            util.getTextHeight(op.size) * self.scale,
            _getFaceName(family),
            flags,
            _gray(self.fill),
        )
        self.gc.SetFont(font)

        angle = math.radians(op.angle) if op.angle else 0.0
        self.gc.DrawText(op.text, self.x(op.x), self.y(op.y), angle)

    def drawLine(self, op):
        path = self.gc.CreatePath()
        path.MoveToPoint(self.x(op.points[0][0]), self.y(op.points[0][1]))

        for px, py in op.points[1:]:
            path.AddLineToPoint(self.x(px), self.y(py))

        if op.isClosed:
            path.CloseSubpath()

        self.gc.SetPen(self.pen(op.width))
        self.gc.StrokePath(path)

    def drawRect(self, op):
        if op.fillType in (pml.FILL, pml.STROKE_FILL):
            self.gc.SetBrush(wx.Brush(_gray(self.fill)))
        else:
            self.gc.SetBrush(wx.TRANSPARENT_BRUSH)

        if op.fillType in (pml.NO_FILL, pml.STROKE_FILL):
            self.gc.SetPen(self.pen(op.lw))
        else:
            self.gc.SetPen(wx.TRANSPARENT_PEN)

        self.gc.DrawRectangle(
            self.x(op.x), self.y(op.y), op.width * self.scale, op.height * self.scale
        )

    def applyPDFOp(self, op):
        m = self.grayRe.match(op.cmds)

        if m:
            if m.group(2) == "g":
                self.fill = float(m.group(1))
            else:
                self.stroke = float(m.group(1))

            return

        m = self.dashRe.match(op.cmds)

        if m:
            self.dashed = bool(m.group(1).strip())
