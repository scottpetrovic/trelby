import wx

import trelby.misc as misc
import trelby.pdf.pml as pml
import trelby.screenplay.headers as headers
import trelby.textutil as textutil
import trelby.ui.gutil as gutil
import trelby.ui.widgets as widgets
import trelby.util as util
from trelby.dialogs.headerspreview import MARGIN, SAMPLE_LINES
from trelby.dialogs.titlespreview import BASELINE, faceName


class FooterDlg(wx.Dialog):
    def __init__(self, parent, footer, sp, applyFunc):
        wx.Dialog.__init__(
            self,
            parent,
            -1,
            _("Page footer"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.footer = footer
        self.cfg = sp.cfg
        self.applyFunc = applyFunc

        # the variables as they are on page 2, for the preview
        self.pvars = headers.pageVars(sp, 2)

        vsizer = wx.BoxSizer(wx.VERTICAL)

        gsizer = wx.FlexGridSizer(3, 2, 5, 10)
        gsizer.AddGrowableCol(1)

        # text field of each part, in Footer.PARTS order
        self.entries = []
        labels = [_("Left:"), _("Center:"), _("Right:")]

        for (attr, align, key), label in zip(headers.Footer.PARTS, labels):
            gsizer.Add(wx.StaticText(self, -1, label), 0, wx.ALIGN_CENTER_VERTICAL)

            entry = wx.TextCtrl(self, -1, getattr(footer, attr))

            # text on the page, which is left to right in a right-to-left
            # interface too
            gutil.keepLeftToRight(entry)
            entry.SetMinSize(self.FromDIP(wx.Size(260, -1)))
            self.Bind(wx.EVT_TEXT, self.OnMisc, id=entry.GetId())
            entry.Bind(wx.EVT_SET_FOCUS, self.OnEntryFocus)
            gsizer.Add(entry, 1, wx.EXPAND)

            self.entries.append(entry)

        vsizer.Add(gsizer, 0, wx.EXPAND)

        # the field "Insert variable" puts the variable in
        self.lastEntry = self.entries[0]

        self.varBtn = gutil.createStockButton(self, _("Insert variable"))
        self.Bind(wx.EVT_BUTTON, self.OnVarMenu, id=self.varBtn.GetId())
        vsizer.Add(self.varBtn, 0, wx.TOP, 10)

        vsizer.Add(
            widgets.WrappedText(
                self,
                _(
                    "The title, author and draft come from the strings of that "
                    "kind on the title pages."
                ),
            ),
            0,
            wx.EXPAND | wx.TOP,
            10,
        )

        self.firstPageCb = wx.CheckBox(self, -1, _("Print on the first page"))
        self.firstPageCb.SetValue(footer.showOnFirstPage)
        self.Bind(wx.EVT_CHECKBOX, self.OnMisc, id=self.firstPageCb.GetId())
        vsizer.Add(self.firstPageCb, 0, wx.TOP, 20)

        if not headers.Footer.fits(self.cfg):
            vsizer.Add(
                widgets.WrappedText(
                    self,
                    _(
                        "The footer is printed in the bottom margin, which is too "
                        "small for it. Make the margin bigger in Script settings."
                    ),
                ),
                0,
                wx.EXPAND | wx.TOP,
                20,
            )

        # controls on the left, live preview of the bottom of a page on the
        # right
        mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        mainSizer.Add(vsizer, 0, wx.EXPAND)

        self.previewCtrl = FooterPreview(self, self, self.cfg)
        self.previewCtrl.SetMinSize(self.FromDIP(wx.Size(560, 240)))
        mainSizer.Add(self.previewCtrl, 1, wx.EXPAND | wx.LEFT, 20)

        topSizer = wx.BoxSizer(wx.VERTICAL)
        topSizer.Add(mainSizer, 1, wx.EXPAND)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        hsizer.Add((1, 1), 1)

        applyBtn = gutil.createStockButton(self, _("Apply"))
        hsizer.Add(applyBtn)

        cancelBtn = gutil.createStockButton(self, _("Cancel"))
        hsizer.Add(cancelBtn, 0, wx.LEFT, 10)

        okBtn = gutil.createStockButton(self, "OK")
        hsizer.Add(okBtn, 0, wx.LEFT, 10)

        topSizer.Add(hsizer, 0, wx.EXPAND | wx.TOP, 20)

        gutil.finishWindow(self, topSizer)

        self.Bind(wx.EVT_BUTTON, self.OnApply, id=applyBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=cancelBtn.GetId())
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=okBtn.GetId())

        self.entries[0].SetFocus()

    def OnOK(self, event):
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnApply(self, event):
        self.applyFunc(self.footer)

    def OnEntryFocus(self, event):
        self.lastEntry = event.GetEventObject()
        event.Skip()

    def OnVarMenu(self, event):
        showVariablesMenu(self, self.varBtn, lambda: self.lastEntry)

    def OnMisc(self, event=None):
        for (attr, align, key), entry in zip(headers.Footer.PARTS, self.entries):
            text = textutil.toInputStr(misc.fromGUI(entry.GetValue()))
            setattr(self.footer, attr, text)

        self.footer.showOnFirstPage = self.firstPageCb.GetValue()

        self.previewCtrl.Refresh()


# show the menu of the variables (headers.VARIABLES) below button 'btn' of
# dialog 'dlg'. picking one puts it at the cursor in the text field that
# getEntry() returns.
def showVariablesMenu(dlg, btn, getEntry):
    menu = wx.Menu()

    def insert(name):
        entry = getEntry()
        entry.SetFocus()
        entry.WriteText("${%s}" % name)

    for name, desc in headers.VARIABLES:
        item = menu.Append(wx.ID_ANY, "${%s}\t%s" % (name, desc()))
        dlg.Bind(wx.EVT_MENU, lambda ev, name=name: insert(name), item)

    dlg.PopupMenu(menu, btn.GetRect().GetBottomLeft())
    menu.Destroy()


# live preview of the bottom of a script page (page 2) with the footer
class FooterPreview(wx.Window):
    def __init__(self, parent, dlg, cfg):
        wx.Window.__init__(self, parent, -1, style=wx.FULL_REPAINT_ON_RESIZE)

        # a page, which is left to right in a right-to-left interface too
        gutil.keepLeftToRight(self)

        self.cfg = cfg
        self.dlg = dlg

        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.OnPaint)

    def OnPaint(self, event):
        self.draw(wx.AutoBufferedPaintDC(self))

    def draw(self, dc):
        dc.SetBackground(
            wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_APPWORKSPACE))
        )
        dc.Clear()

        cfg = self.cfg
        ww, wh = self.GetClientSize()

        # the page fills the width and runs off the top, since only its
        # bottom part is of interest
        w = max(1, ww - 2 * MARGIN)
        h = w * cfg.paperHeight / cfg.paperWidth
        ox = MARGIN
        oy = wh - MARGIN - h

        # pixels per mm
        scale = w / cfg.paperWidth

        gc = wx.GraphicsContext.Create(dc)

        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 60)))
        gc.DrawRectangle(ox + 3, oy + 3, w, h)

        gc.SetPen(wx.Pen(wx.Colour(160, 160, 160)))
        gc.SetBrush(wx.WHITE_BRUSH)
        gc.DrawRectangle(ox, oy, w, h)

        # margin guides
        gc.SetPen(wx.Pen(wx.Colour(200, 210, 225), 1, wx.PENSTYLE_SHORT_DASH))

        left = ox + cfg.marginLeft * scale
        right = ox + (cfg.paperWidth - cfg.marginRight) * scale
        bottom = oy + (cfg.paperHeight - cfg.marginBottom) * scale

        gc.StrokeLine(left, 0, left, oy + h)
        gc.StrokeLine(right, 0, right, oy + h)
        gc.StrokeLine(ox, bottom, ox + w, bottom)

        fs = cfg.fontSize
        sizeMM = util.getTextHeight(fs)
        fontPx = max(1.0, sizeMM * scale)
        charW = util.getTextWidth(" ", pml.COURIER, fs)

        # sample text filling the page down to its last line
        gc.SetFont(
            gc.CreateFont(
                fontPx,
                faceName(pml.COURIER),
                wx.FONTFLAG_DEFAULT,
                wx.Colour(150, 150, 150),
            )
        )

        y = cfg.marginTop + (cfg.linesOnPage - len(SAMPLE_LINES)) * sizeMM

        for it in SAMPLE_LINES:
            if it:
                lt, text = it
                x = cfg.marginLeft + cfg.getType(lt).indent * charW
                drawLine(gc, text, ox + x * scale, oy + y * scale, fontPx)

            y += sizeMM

        gc.SetFont(
            gc.CreateFont(fontPx, faceName(pml.COURIER), wx.FONTFLAG_DEFAULT, wx.BLACK)
        )

        top = oy + headers.Footer.getY(cfg) * scale

        for text, align in self.dlg.footer.getTexts(self.dlg.pvars):
            xp = ox + headers.alignX(align, cfg) * scale
            tw = gc.GetTextExtent(text)[0]

            if align == util.ALIGN_CENTER:
                xp -= tw / 2
            elif align == util.ALIGN_RIGHT:
                xp -= tw

            drawLine(gc, text, xp, top, fontPx)


# draw 'text' with its top at widget y coordinate 'top', lining up the
# baseline with where the PDF puts it
def drawLine(gc, text, x, top, heightPx):
    tw, th, descent, lead = gc.GetFullTextExtent(text)
    gc.DrawText(text, x, top + BASELINE * heightPx - (th - descent))
