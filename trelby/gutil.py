import os
import re
import tempfile

import trelby.config as config
import trelby.misc as misc
import trelby.util as util
from trelby.error import MiscError, TrelbyError

if "TRELBY_TESTING" in os.environ:
    import unittest.mock as mock

    wx = mock.Mock()
else:
    import wx

# this contains misc GUI-related functions


# load one of the black SVG icons in trelby/resources as a bitmap bundle of
# the given size (in DIPs), recolored to show up on a dark appearance. a
# non-zero padding (in DIPs) adds that much empty space on every side of the
# icon, by growing the SVG's viewBox, so the bundle is size + 2 * padding.
def svgBitmap(iconFilename, size, padding=0):
    filepath = misc.getFullPath("trelby/resources/%s" % iconFilename)

    with open(filepath, "r") as svg_file:
        svg_content = svg_file.read()

    if config.isDarkAppearance():
        svg_content = svg_content.replace("fill:#000000", "fill:#CCCCCC")

    if padding:
        svg_content = re.sub(
            r'viewBox="([^"]*)"',
            lambda m: 'viewBox="%s"' % padViewBox(m.group(1), size, padding),
            svg_content,
            count=1,
        )
        size = wx.Size(size.width + padding * 2, size.height + padding * 2)

    return wx.BitmapBundle.FromSVG(svg_content.encode(), size)


# return the SVG viewBox 'box' grown on every side by 'padding' DIPs, for an
# icon drawn at 'size' DIPs
def padViewBox(box, size, padding):
    x, y, w, h = [float(v) for v in box.replace(",", " ").split()]
    padX = w * padding / size.width
    padY = h * padding / size.height

    return "%g %g %g %g" % (x - padX, y - padY, w + padX * 2, h + padY * 2)


# return color c1 mixed with c2, with a being the fraction of c2
def blendColors(c1, c2, a):
    return wx.Colour(
        *[
            int(v1 * (1.0 - a) + v2 * a)
            for v1, v2 in zip(c1.Get(False), c2.Get(False))
        ]
    )


# since at least GTK 1.2's single-selection listbox is buggy in that if we
# don't deselect the old item manually, it does multiple selections, we
# have this function that does the following:
#
#  1) deselects current selection, if any
#  2) select the item with the given index
def listBoxSelect(lb, index):
    old = lb.GetSelection()

    if old != -1:
        lb.SetSelection(old, False)

    lb.SetSelection(index, True)


# add (name, cdata) to the listbox at the correct place, determined by
# cmp(cdata1, cdata2).
def listBoxAdd(lb, name, cdata):
    for i in range(lb.GetCount()):
        if util.cmpfunc(cdata, lb.GetClientData(i)) < 0:
            lb.InsertItems([name], i)
            lb.SetClientData(i, cdata)

            return

    lb.Append(name, cdata)


# create stock button.
def createStockButton(parent, label):
    # wxMSW does not really have them: it does not have any icons and it
    # inconsistently adds the shortcut key to some buttons, but not to
    # all, so it's better not to use them at all on Windows.
    if misc.isUnix:
        ids = {
            "OK": wx.ID_OK,
            _("Cancel"): wx.ID_CANCEL,
            _("Apply"): wx.ID_APPLY,
            _("Add"): wx.ID_ADD,
            _("Delete"): wx.ID_DELETE,
            _("Preview"): wx.ID_PREVIEW,
        }

        return wx.Button(parent, ids[label])
    else:
        return wx.Button(parent, -1, label)


# add a small toggle button showing 'label' in the given font style to
# 'sizer', calling handler(event) when it's toggled, and return it
def addToggle(
    parent,
    sizer,
    label,
    tip,
    handler,
    weight=wx.FONTWEIGHT_NORMAL,
    style=wx.FONTSTYLE_NORMAL,
    underlined=False,
):
    size = parent.FromDIP(wx.Size(30, 28))
    btn = wx.ToggleButton(parent, -1, label, size=size)
    btn.SetToolTip(tip)

    font = btn.GetFont()
    font.SetWeight(weight)
    font.SetStyle(style)
    font.SetUnderlined(underlined)
    btn.SetFont(font)

    btn.Bind(wx.EVT_TOGGLEBUTTON, handler)
    sizer.Add(btn, 0, wx.RIGHT, 2)

    return btn


# add bold / italic / underlined toggles to 'sizer', calling
# handler(event) when one is toggled, and return them as a (bold,
# italic, underlined) tuple
def addStyleToggles(parent, sizer, handler):
    return (
        addToggle(parent, sizer, "B", _("Bold"), handler, wx.FONTWEIGHT_BOLD),
        addToggle(
            parent, sizer, "I", _("Italic"), handler, style=wx.FONTSTYLE_ITALIC
        ),
        addToggle(parent, sizer, "U", _("Underlined"), handler, underlined=True),
    )


# add left / center / right alignment toggles to 'sizer', which work like
# radio buttons, and return them as a {util.ALIGN_*: button} dict.
# handler(event) is called after one is clicked.
def addAlignToggles(parent, sizer, handler):
    btns = {}

    def onAlign(event):
        for btn in btns.values():
            btn.SetValue(btn is event.GetEventObject())

        handler(event)

    for align, tip in [
        (util.ALIGN_LEFT, _("Align left")),
        (util.ALIGN_CENTER, _("Center")),
        (util.ALIGN_RIGHT, _("Align right")),
    ]:
        btn = addToggle(parent, sizer, "", tip, onAlign)
        btn.SetBitmap(makeAlignBitmap(btn, align))
        btns[align] = btn

    return btns


# return the alignment selected in alignment toggles made by
# addAlignToggles
def getAlignment(btns):
    for align, btn in btns.items():
        if btn.GetValue():
            return align

    return util.ALIGN_LEFT


# select 'align' in alignment toggles made by addAlignToggles, or none of
# them if it's None
def setAlignment(btns, align):
    for a, btn in btns.items():
        btn.SetValue(a == align)


# return an icon for alignment button 'btn': four lines of text, aligned
# as 'align'
def makeAlignBitmap(btn, align):
    size = btn.FromDIP(16)
    bmp = wx.Bitmap.FromRGBA(size, size, 0, 0, 0, 0)

    dc = wx.MemoryDC(bmp)
    gc = wx.GraphicsContext.Create(dc)

    gc.SetPen(wx.TRANSPARENT_PEN)
    gc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)))

    thick = max(1, size // 8)
    gap = (size - 4 * thick) / 5

    for i, frac in enumerate([1.0, 0.6, 0.85, 0.5]):
        w = round(size * frac)

        if align == util.ALIGN_CENTER:
            x = (size - w) / 2
        elif align == util.ALIGN_RIGHT:
            x = size - w
        else:
            x = 0

        gc.DrawRectangle(x, gap + i * (thick + gap), w, thick)

    del gc
    dc.SelectObject(wx.NullBitmap)

    return bmp


# wxWidgets has a bug in 2.6 on wxGTK2 where double clicking on a button
# does not send two wx.EVT_BUTTON events, only one. since the wxWidgets
# maintainers do not seem interested in fixing this
# (http://sourceforge.net/tracker/index.php?func=detail&aid=1449838&group_id=9863&atid=109863),
# we work around it ourselves by binding the left mouse button double
# click event to the same callback function on the buggy platforms.
def btnDblClick(btn, func):
    if misc.isUnix:
        btn.Bind(wx.EVT_LEFT_DCLICK, func)


# show PDF document 'pdfData' in an external viewer program. writes out a
# temporary file, first deleting all old temporary files, then opens PDF
# viewer application. 'mainFrame' is used as a parent for message boxes in
# case there are any errors.
def showTempPDF(
    pdfData: bytes, cfgGl: "config.ConfigGlobal", mainFrame: wx.TopLevelWindow
) -> None:
    try:
        try:
            util.removeTempFiles(misc.tmpPrefix)

            fd, filename = tempfile.mkstemp(prefix=misc.tmpPrefix, suffix=".pdf")

            try:
                if isinstance(pdfData, str):
                    os.write(fd, pdfData)
                else:
                    os.write(fd, pdfData)
            finally:
                os.close(fd)

            util.showPDF(filename, cfgGl, mainFrame)

        except IOError as xxx_todo_changeme:
            (errno, strerror) = xxx_todo_changeme.args
            raise MiscError("IOError: %s" % strerror)

    except TrelbyError as e:
        wx.MessageBox(
            _("Error writing temporary PDF file: {}".format(e)),
            _("Error"),
            wx.OK,
            mainFrame,
        )
