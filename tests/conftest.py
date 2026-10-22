import pytest

# one wx.App for every test that needs one (the 'app' fixture). an app
# per test module worked on Windows, but on macOS the windows and events
# left over from one were cleaned up after it was gone, which crashed
# Python on exit. wx is imported here only when a test asks for the app,
# so the model tests still run without it.


@pytest.fixture(scope="session")
def app():
    import wx

    import tests.u as u
    import trelby.ui.gutil as gutil

    u.init()
    a = wx.App(False)
    gutil.init()

    yield a

    for w in wx.GetTopLevelWindows():
        w.Destroy()

    # the destroys, and anything else queued with wx.CallAfter
    a.ProcessPendingEvents()
    a.Destroy()
