import wx

import trelby.misc as misc
import trelby.ui.theming as theming
import trelby.util as util

# this contains misc GUI-related functions: text extents and fonts, drawing,
# laying out windows, small helpers for wx controls, and message boxes


# permanent memory DC to get text extents etc
permDc = None


def init(doWX=True):
    global permDc

    if doWX:
        # dunno if the bitmap needs to be big enough to contain the text
        # we're measuring...
        permDc = wx.MemoryDC()
        permDc.SelectObject(wx.Bitmap(512, 32))


# return True if given font is a fixed-width one.
def isFixedWidth(font):
    return getTextExtent(font, "iiiii")[0] == getTextExtent(font, "OOOOO")[0]


# get extent of 's' as (w, h)
def getTextExtent(font, s):
    permDc.SetFont(font)

    # if we simply return permDc.GetTextExtent(s) from here, on some
    # versions of Windows we will incorrectly reject as non-fixed width
    # fonts (through isFixedWidth) some fonts that actually are fixed
    # width. it's especially bad because one of them is our default font,
    # "Courier New".
    #
    # these are the widths we get for the strings below for Courier New, italic:
    #
    # iiiii 40
    # iiiiiiiiii 80
    # OOOOO 41
    # OOOOOOOOOO 81
    #
    # we can see i and O are both 8 pixels wide, so the font is
    # fixed-width, but for whatever reason, on the O variants there is one
    # additional pixel returned in the width, no matter what the length of
    # the string is.
    #
    # to get around this, we actually call GetTextExtent twice, once with
    # the actual string we want to measure, and once with the string
    # duplicated, and take the difference between those two as the actual
    # width. this handily negates the one-extra-pixel returned and gives
    # us an accurate way of checking if a font is fixed width or not.
    #
    # it's a bit slower but this is not called from anywhere that's
    # performance critical.

    w1, h = permDc.GetTextExtent(s)
    w2 = permDc.GetTextExtent(s + s)[0]

    return (w2 - w1, h)


# get height of font in pixels
def getFontHeight(font):
    permDc.SetFont(font)
    return permDc.GetTextExtent("_\xC5")[1]


# create a font that's height is at most 'height' pixels. other parameters
# are the same as in wx.Font's constructor.
def createPixelFont(height, family, style, weight):
    fs = 6

    selected = fs
    closest = 1000
    over = 0

    # FIXME: what's this "keep trying even once we go over the max height"
    # stuff? get rid of it.
    while 1:
        fn = wx.Font(fs, family, style, weight, encoding=wx.FONTENCODING_ISO8859_1)
        h = getFontHeight(fn)
        diff = height - h

        if diff >= 0:
            if diff < closest:
                closest = diff
                selected = fs
        else:
            over += 1

        if (over >= 3) or (fs > 144):
            break

        fs += 2

    return wx.Font(selected, family, style, weight, encoding=wx.FONTENCODING_ISO8859_1)


def reverseComboSelect(combo, clientData):
    for i in range(combo.GetCount()):
        if combo.GetClientData(i) == clientData:
            if combo.GetSelection() != i:
                combo.SetSelection(i)

            return True

    return False


# set widget's client size. if w or h is -1, that dimension is not changed.
def setWH(ctrl, w=-1, h=-1):
    size = ctrl.GetClientSize()

    if w != -1:
        size.width = w

    if h != -1:
        size.height = h

    ctrl.SetMinSize(wx.Size(size.width, size.height))
    ctrl.SetClientSize(size.width, size.height)


# wxMSW doesn't respect the control's min/max values at all, so we have to
# implement this ourselves
def getSpinValue(spinCtrl):
    tmp = util.clamp(spinCtrl.GetValue(), spinCtrl.GetMin(), spinCtrl.GetMax())
    spinCtrl.SetValue(tmp)

    return tmp


# DrawLine-wrapper that makes it easier when the end-point is just
# offsetted from the starting point
def drawLine(dc, x, y, xd, yd):
    dc.DrawLine(x, y, x + xd, y + yd)


# draws text aligned somehow. returns a (w, h) tuple of the text extent.
def drawText(dc, text, x, y, align=util.ALIGN_LEFT, valign=util.VALIGN_TOP):
    w, h = dc.GetTextExtent(text)

    if align == util.ALIGN_CENTER:
        x -= w // 2
    elif align == util.ALIGN_RIGHT:
        x -= w

    if valign == util.VALIGN_CENTER:
        y -= h // 2
    elif valign == util.VALIGN_BOTTOM:
        y -= h

    dc.DrawText(text, x, y)

    return (w, h)


# create pad sizer for given window whose controls are in topSizer, with
# 'pad' pixels of padding on each side, resize window to correct size, and
# optionally center it.
def finishWindow(window, topSizer, pad=20, center=False):
    # dialogs and other top-level windows are shown in the theme's colors.
    # before the layout, since it pads the buttons.
    if window.IsTopLevel():
        theming.themeWindow(window)

    padSizer = wx.BoxSizer(wx.VERTICAL)
    padSizer.Add(topSizer, 1, wx.EXPAND | wx.ALL, pad)
    window.SetSizerAndFit(padSizer)
    window.Layout()

    if center:
        window.Center()


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


# add (name, cdata) to the listbox at the correct place, in ascending
# order of cdata.
def listBoxAdd(lb, name, cdata):
    for i in range(lb.GetCount()):
        if cdata < lb.GetClientData(i):
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
        if label == "OK":
            label = wx.GetStockLabel(wx.ID_OK, wx.STOCK_NOFLAGS)

        return wx.Button(parent, -1, label)


# wxWidgets' own translations, which have the labels of its stock buttons
# (OK, Cancel, Yes, Save...) and of its generic dialogs. set by
# loadWxTranslations.
wxTranslations = None


# load wxWidgets' translations for 'language' (e.g. "zh_CN"), the one
# Trelby's own strings are shown in. if they exist, message boxes are
# changed to show the stock labels too, since the system's own buttons
# would be in the language of the operating system instead.
def loadWxTranslations(language):
    global wxTranslations

    # wx's strings are in English already
    if language.startswith("en"):
        return

    wxTranslations = wx.Translations()
    wx.Translations.Set(wxTranslations)
    wxTranslations.SetLanguage(language)

    if wxTranslations.AddStdCatalog():
        # every module calls wx.MessageBox through the wx module, so this
        # reroutes all of them
        wx.MessageBox = messageBox


# wx.MessageBox, but with wx's stock labels on the buttons (see
# loadWxTranslations)
def messageBox(message, caption="Message", style=None, parent=None, x=-1, y=-1):
    if style is None:
        style = wx.OK | wx.CENTRE

    # the icon wx.MessageBox adds when none is given
    if not (style & (wx.ICON_MASK | wx.ICON_NONE)):
        style |= wx.ICON_QUESTION if style & wx.YES else wx.ICON_INFORMATION

    dlg = wx.MessageDialog(parent, message, caption, style)

    if style & wx.YES_NO:
        if style & wx.CANCEL:
            dlg.SetYesNoCancelLabels(wx.ID_YES, wx.ID_NO, wx.ID_CANCEL)
        else:
            dlg.SetYesNoLabels(wx.ID_YES, wx.ID_NO)
    elif style & wx.CANCEL:
        dlg.SetOKCancelLabels(wx.ID_OK, wx.ID_CANCEL)
    else:
        dlg.SetOKLabel(wx.ID_OK)

    ret = dlg.ShowModal()
    dlg.Destroy()

    # wx.MessageBox returns wx.YES etc., not the dialog's wx.ID_YES
    return {
        wx.ID_YES: wx.YES,
        wx.ID_NO: wx.NO,
        wx.ID_OK: wx.OK,
    }.get(ret, wx.CANCEL)


# wxWidgets has a bug in 2.6 on wxGTK2 where double clicking on a button
# does not send two wx.EVT_BUTTON events, only one. since the wxWidgets
# maintainers do not seem interested in fixing this
# (http://sourceforge.net/tracker/index.php?func=detail&aid=1449838&group_id=9863&atid=109863),
# we work around it ourselves by binding the left mouse button double
# click event to the same callback function on the buggy platforms.
def btnDblClick(btn, func):
    if misc.isUnix:
        btn.Bind(wx.EVT_LEFT_DCLICK, func)
