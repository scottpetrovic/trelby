import pytest
import wx

import trelby.ui.gutil as gutil
import trelby.ui.tabctrl as tabctrl

# laying the interface out right to left for right-to-left languages
# (gutil.setLanguageDirection), while the windows showing the script or a
# page stay left to right (gutil.keepLeftToRight)


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    yield a
    a.Destroy()


# the interface laid out in the direction of 'language' during the test
@pytest.fixture
def direction(app):
    def set(language):
        gutil.setLanguageDirection(language)

    yield set

    gutil.setLanguageDirection("en_US")


@pytest.mark.parametrize("language", ["he_IL", "he", "ar", "fa_IR"])
def testRightToLeftLanguages(app, language):
    assert gutil.languageDirection(language) == wx.Layout_RightToLeft


@pytest.mark.parametrize("language", ["en_US", "it_IT", "zh_CN", "xx_YY", ""])
def testLeftToRightLanguages(app, language):
    assert gutil.languageDirection(language) == wx.Layout_LeftToRight


def testSetLanguageDirection(direction):
    direction("he_IL")
    assert gutil.isRightToLeft()
    assert gutil.layoutDirection == wx.Layout_RightToLeft

    direction("en_US")
    assert not gutil.isRightToLeft()


# a dialog with no parent, holding a panel with a field, and a page that
# stays left to right, with something in it
def makeDialog():
    dlg = wx.Dialog(None)
    panel = wx.Panel(dlg)
    field = wx.TextCtrl(panel)
    page = wx.Window(dlg)
    gutil.keepLeftToRight(page)
    inPage = wx.Window(page)

    return dlg, [dlg, panel, field], [page, inPage]


def testApplyLayoutDirection(direction):
    direction("he_IL")
    dlg, mirrored, kept = makeDialog()

    gutil.applyLayoutDirection(dlg)

    try:
        for w in mirrored:
            assert w.GetLayoutDirection() == wx.Layout_RightToLeft

        for w in kept:
            assert w.GetLayoutDirection() == wx.Layout_LeftToRight
    finally:
        dlg.Destroy()


def testLeftToRightLanguageChangesNothing(direction):
    direction("en_US")
    dlg, mirrored, kept = makeDialog()

    gutil.applyLayoutDirection(dlg)

    try:
        for w in mirrored + kept:
            assert w.GetLayoutDirection() == wx.Layout_LeftToRight
    finally:
        dlg.Destroy()


def testWindowsTakeTheDirectionFromTheirParent(direction):
    direction("he_IL")
    frame = wx.Frame(None)
    frame.SetLayoutDirection(gutil.layoutDirection)

    try:
        assert wx.Panel(frame).GetLayoutDirection() == wx.Layout_RightToLeft
        assert wx.Dialog(frame).GetLayoutDirection() == wx.Layout_RightToLeft

        page = wx.Panel(frame)
        gutil.keepLeftToRight(page)
        assert wx.Window(page).GetLayoutDirection() == wx.Layout_LeftToRight
    finally:
        frame.Destroy()


# a script's tab fills the area below the tab bar after the window is
# resized, in a right-to-left window too, where setting only the size used
# to leave it where it was measured from the left
@pytest.mark.parametrize("language", ["en_US", "he_IL"])
def testTabPageFillsTheWindow(direction, language):
    direction(language)
    frame = wx.Frame(None, size=(400, 300))
    frame.SetLayoutDirection(gutil.layoutDirection)

    try:
        tabs = tabctrl.MyTabCtrl(frame, -1, lambda: None)
        tabs.setPageChangedFunc(lambda i: None)
        holder = tabctrl.MyTabCtrl2(frame, -1, tabs)
        holder.SetSize(0, 0, 400, 300)

        page = wx.Panel(holder)
        tabs.addPage(page, "script")

        holder.SetSize(0, 0, 700, 300)
        tabs.setPageSizes()

        assert page.GetPosition() == wx.Point(0, 0)
        assert page.GetSize() == holder.GetClientSize()
    finally:
        frame.Destroy()
