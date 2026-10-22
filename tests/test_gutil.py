import pytest
import wx

import trelby.ui.gutil as gutil

# the spacing finishWindow adds to the windows' layouts (spaceSizer)


@pytest.fixture
def frame(app):
    f = wx.Frame(None)
    yield f
    f.Destroy()


def testWidensBordersGapsAndSpacers(frame):
    vsizer = wx.BoxSizer(wx.VERTICAL)
    vsizer.Add(wx.StaticText(frame, -1, "a"), 0, wx.BOTTOM, 10)

    grid = wx.FlexGridSizer(2, 4, 10)
    grid.Add(wx.StaticText(frame, -1, "b"), 0, wx.LEFT, 5)
    vsizer.Add(grid)

    hsizer = wx.BoxSizer(wx.HORIZONTAL)
    hsizer.Add((20, -1))
    hsizer.Add((1, 1), 1)
    vsizer.Add(hsizer, 0, wx.TOP, 20)

    gutil.spaceSizer(vsizer, 1.5)

    items = vsizer.GetChildren()
    assert items[0].GetBorder() == 15
    assert items[1].GetSizer() is grid
    assert (grid.GetVGap(), grid.GetHGap()) == (6, 15)
    assert grid.GetChildren()[0].GetBorder() == 8
    assert items[2].GetBorder() == 30
    spacers = [it.GetSpacer() for it in hsizer.GetChildren()]
    assert spacers == [wx.Size(30, -1), wx.Size(1, 1)]

    # a second call doesn't widen it again
    gutil.spaceSizer(vsizer, 1.5)
    assert vsizer.GetChildren()[0].GetBorder() == 15


def testGapBetweenStackedItems(frame):
    vsizer = wx.BoxSizer(wx.VERTICAL)
    label = wx.StaticText(frame, -1, "label")
    ctrl = wx.TextCtrl(frame)
    other = wx.TextCtrl(frame)
    last = wx.TextCtrl(frame)

    # label right on top of ctrl gets a gap, ctrl / other already have one,
    # and other / last only have borders on other sides
    vsizer.Add(label)
    vsizer.Add(ctrl, 0, wx.EXPAND | wx.BOTTOM, 10)
    vsizer.Add(other, 0, wx.LEFT, 10)
    vsizer.Add(last)

    gutil.spaceSizer(vsizer)

    kinds = [
        it.GetWindow() if it.IsWindow() else it.GetSpacer()
        for it in vsizer.GetChildren()
    ]
    gap = wx.Size(0, gutil.MIN_GAP)
    assert kinds == [label, gap, ctrl, other, gap, last]

    # borders are kept, not changed to make the gap
    assert vsizer.GetItem(other).GetBorder() == 15
    assert vsizer.GetItem(other).GetFlag() & wx.ALL == wx.LEFT


def testHorizontalSizersGetNoGaps(frame):
    hsizer = wx.BoxSizer(wx.HORIZONTAL)
    hsizer.Add(wx.Button(frame, -1, "a"))
    hsizer.Add(wx.Button(frame, -1, "b"))

    gutil.spaceSizer(hsizer)

    assert hsizer.GetItemCount() == 2
