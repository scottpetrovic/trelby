import os

import wx

import trelby.config as config
import trelby.misc as misc
import trelby.pdf.fontinfo as fontinfo
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

        # on Windows, graphics contexts (GDI+) only see the fonts added
        # before the first one is created
        loadBundledFonts()


# whether the bundled fonts could be loaded, or None before the first
# loadBundledFonts call
_bundledFontsLoaded = None


# make the bundled fonts (fontinfo.BUNDLED_FONTS) usable in this process,
# once. returns True if they all loaded, so fonts can use BUNDLED_FACE.
def loadBundledFonts():
    global _bundledFontsLoaded

    if _bundledFontsLoaded is None:
        add = registerMacFont if misc.isMac else wx.Font.AddPrivateFont

        _bundledFontsLoaded = all(
            [
                add(fontinfo.bundledFontPath(fileName))
                for name, fileName in fontinfo.BUNDLED_FONTS.values()
            ]
        )

    return _bundledFontsLoaded


# make the font file at path usable in this process on macOS, where
# wx.Font.AddPrivateFont only accepts fonts in the app bundle's
# Resources/Fonts folder (listed in its Info.plist), through CoreText's
# CTFontManagerRegisterFontsForURL. returns True if it worked.
def registerMacFont(path):
    import ctypes
    import ctypes.util

    try:
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        ct = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreText"))
    except OSError:
        return False

    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_bool,
    ]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    ct.CTFontManagerRegisterFontsForURL.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]

    data = os.fsencode(path)
    url = cf.CFURLCreateFromFileSystemRepresentation(None, data, len(data), False)

    if not url:
        return False

    try:
        # 1 = kCTFontManagerScopeProcess
        return bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None))
    finally:
        cf.CFRelease(url)


# the face to draw Courier text (pml.COURIER) in on the screen: the
# bundled font, or the old default if it didn't load
def courierFace():
    if loadBundledFonts():
        return fontinfo.BUNDLED_FACE

    return config.oldDefaultFace()


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


# how much finishWindow widens the borders and grid gaps the windows'
# layouts give, which were picked for a denser look.
SPACING = 1.5

# the gap finishWindow puts between items stacked on top of each other
# that have none, like a label and the control under it.
MIN_GAP = 5


# multiply the borders of the items in sizer and its child sizers, and the
# gaps of grid sizers, by factor, and put MIN_GAP between the items of
# vertical box sizers that have no gap between them. each sizer is only
# done once, so laying a window out again doesn't keep widening it.
def spaceSizer(sizer, factor=SPACING):
    if getattr(sizer, "_trelbySpaced", False):
        return

    sizer._trelbySpaced = True

    if isinstance(sizer, wx.GridSizer):
        sizer.SetVGap(round(sizer.GetVGap() * factor))
        sizer.SetHGap(round(sizer.GetHGap() * factor))

    vertical = (
        isinstance(sizer, wx.BoxSizer) and sizer.GetOrientation() == wx.VERTICAL
    )

    # indexes of the items that need a MIN_GAP spacer before them. a
    # spacer, since giving an item a top border would change its other
    # borders too.
    gaps = []
    prev = None

    for i, item in enumerate(sizer.GetChildren()):
        item.SetBorder(round(item.GetBorder() * factor))

        if (
            vertical
            and prev
            and not prev.IsSpacer()
            and not item.IsSpacer()
            and not (prev.GetFlag() & wx.BOTTOM and prev.GetBorder())
            and not (item.GetFlag() & wx.TOP and item.GetBorder())
        ):
            gaps.append(i)

        prev = item

        if item.IsSizer():
            spaceSizer(item.GetSizer(), factor)
        elif item.IsSpacer():
            # fixed gaps; the (1, 1) stretch spacers are left alone.
            w, h = item.GetSpacer()
            item.AssignSpacer(
                wx.Size(*(round(n * factor) if n > 1 else n for n in (w, h)))
            )

    for i in reversed(gaps):
        sizer.Insert(i, 0, MIN_GAP)


# the direction the interface is laid out in, wx.Layout_RightToLeft for
# right-to-left languages like Hebrew. set by setLanguageDirection at
# startup.
layoutDirection = wx.Layout_LeftToRight


# return the direction the language 'language' (e.g. "he_IL") is written
# in, as wx.Layout_LeftToRight or wx.Layout_RightToLeft. gettext doesn't
# know, so this comes from wx's table of languages.
def languageDirection(language):
    info = wx.Locale.FindLanguageInfo(language)

    if info and (info.LayoutDirection == wx.Layout_RightToLeft):
        return wx.Layout_RightToLeft

    return wx.Layout_LeftToRight


# lay the interface out in the direction of 'language', the one Trelby's
# own strings are shown in. windows take it from their parent when they're
# created, so this is needed before the main window is.
def setLanguageDirection(language):
    global layoutDirection

    layoutDirection = languageDirection(language)

    if isRightToLeft():
        # on Windows, every text a wx.GraphicsContext draws is laid out in
        # the direction of the first one it draws. if that's in a
        # right-to-left window, the pages in the title, header and footer
        # previews and the dialogue chart come out right-to-left too, so
        # draw some left to right first. (in right-to-left windows, the
        # labels theming draws are drawn on a wx.DC.)
        bmp = wx.Bitmap(8, 8)
        dc = wx.MemoryDC(bmp)
        gc = wx.GraphicsContext.Create(dc)
        gc.SetFont(wx.NORMAL_FONT, wx.BLACK)
        gc.DrawText("x", 0, 0)


def isRightToLeft():
    return layoutDirection == wx.Layout_RightToLeft


# keep window 'win' laid out left to right whatever the interface's
# direction, for windows that show the script or a page of it, which stay
# left to right, and whose drawing uses x coordinates from the left, which
# a right-to-left window would mirror. applyLayoutDirection leaves it and
# the windows in it alone.
def keepLeftToRight(win):
    win.keepLeftToRight = True
    win.SetLayoutDirection(wx.Layout_LeftToRight)


# lay window 'win' and the windows in it out in the interface's direction.
# windows created in a right-to-left window are right-to-left already, so
# this is for the top-level windows that have no parent to take it from.
def applyLayoutDirection(win):
    if (layoutDirection == wx.Layout_LeftToRight) or getattr(
        win, "keepLeftToRight", False
    ):
        return

    if win.GetLayoutDirection() != layoutDirection:
        win.SetLayoutDirection(layoutDirection)

    for c in win.GetChildren():
        if not c.IsTopLevel():
            applyLayoutDirection(c)


# create pad sizer for given window whose controls are in topSizer, with
# 'pad' pixels of padding on each side, resize window to correct size, and
# optionally center it. the spacing inside topSizer is widened by SPACING.
def finishWindow(window, topSizer, pad=20, center=False):
    # dialogs and other top-level windows are shown in the theme's colors.
    # before the layout, since it pads the buttons.
    if window.IsTopLevel():
        applyLayoutDirection(window)
        theming.themeWindow(window)

    spaceSizer(topSizer)

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

        # labels with no stock button (e.g. "Insert variable") get a
        # plain one
        if label in ids:
            return wx.Button(parent, ids[label])

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
