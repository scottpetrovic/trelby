import wx

import trelby.keys as keys


# keys has its own copies of the wx.WXK_* key codes, so the config can be
# loaded without wx. they're saved in the config file, so they must stay
# the same as wx's.
def testKeyCodesMatchWx():
    names = [n for n in dir(keys) if n.startswith("WXK_")]

    assert len(names) == 40

    for name in names:
        assert getattr(keys, name) == getattr(wx, name), name
