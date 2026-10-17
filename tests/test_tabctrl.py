import builtins

import pytest
import wx

import trelby.ui.tabctrl as tabctrl

# the "+" button after the last tab, which makes a new script


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    yield a
    a.Destroy()


# a tab bar 'width' pixels wide with 'count' tabs, and the list that each
# click on the "+" button adds to
@pytest.fixture
def tabs(app):
    frame = wx.Frame(None, size=(800, 300))

    def make(count, width=800):
        tabs = tabctrl.MyTabCtrl(frame, -1, lambda: None)
        tabs.setPageChangedFunc(lambda i: None)
        holder = tabctrl.MyTabCtrl2(frame, -1, tabs)
        holder.SetSize(0, 0, width, 300)
        tabs.SetSize(0, 0, width, tabctrl.TAB_BAR_HEIGHT)

        for i in range(count):
            tabs.addPage(wx.Panel(holder), "script %d" % i)

        clicks = []
        tabs.setNewTabFunc(lambda: clicks.append(len(tabs.pages)))

        return tabs, clicks

    yield make

    frame.Destroy()


def click(tabs, x):
    event = wx.MouseEvent(wx.wxEVT_LEFT_DOWN)
    event.SetPosition(wx.Point(x, 10))
    tabs.OnLeftDown(event)


def testNewTabButtonFollowsTheLastTab(tabs):
    t, clicks = tabs(2)

    x = t.paddingX + 2 * t.tabWidth
    assert t.getNewTabX() == x

    click(t, x + t.newTabWidth // 2)
    assert clicks == [2]
    assert t.getSelectedPageIndex() == 1

    # the last tab is still that tab
    t.selectPage(0)
    click(t, x - t.tabWidth + 20)
    assert clicks == [2]
    assert t.getSelectedPageIndex() == 1


# with more tabs than fit, the "+" button stays after the last visible one,
# and doesn't push it under the scroll arrows
def testNewTabButtonFitsWithManyTabs(tabs):
    t, clicks = tabs(10, width=500)

    w = t.GetClientSize()[0]
    arrowsX = w - t.paddingX - t.arrowWidth * 2 - t.arrowSpacing

    assert t.firstTab > 0
    assert t.getNewTabX() + t.newTabWidth <= arrowsX

    click(t, t.getNewTabX() + 1)
    assert clicks == [10]


def testHoverHighlightsTheButton(tabs, monkeypatch):
    monkeypatch.setattr(builtins, "_", lambda s: s, raising=False)
    t, clicks = tabs(1)

    t.setNewTabHover(True)
    assert t.newTabHover
    assert t.GetToolTipText() == "New script"

    t.setNewTabHover(False)
    assert not t.newTabHover
    assert not t.GetToolTip()
