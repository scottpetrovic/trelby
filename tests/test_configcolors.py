import tests.u as u
import trelby.config as config

# tests for colors whose default has changed


def bg(s):
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load(s)
    c = cfg.autoCompBgColor

    return (c.r, c.g, c.b)


def testOldDefaultMovesToNew():
    assert bg("Color/AutoCompletionBG:255,240,168\n") == (242, 242, 242)


def testChosenColorIsKept():
    assert bg("Color/AutoCompletionBG:10,20,30\n") == (10, 20, 30)
