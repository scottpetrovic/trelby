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


# tests for the color themes


def testThemesSetEveryColor():
    u.init()
    names = set(config.ConfigGlobal().cvars.color.keys())

    for appearance, (dark, colors) in config._themes.items():
        if appearance == config.APPEARANCE_LIGHT:
            continue

        # every screen color, apart from the per-element text colors that
        # follow textColor
        themed = set(colors) - {"accentColor", "accentTextColor"}
        assert themed <= names
        assert themed == set(config._darkColors)

        assert ("accentColor" in colors) == ("accentTextColor" in colors)


def testEveryAppearanceIsATheme():
    themes = set(config._themes) | {config.APPEARANCE_SYSTEM}

    assert themes == set(
        range(config.APPEARANCE_FIRST, config.APPEARANCE_LAST + 1)
    )


def testThemeAppearanceIsSaved():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load("Appearance:%d\n" % config.APPEARANCE_MONOKAI)
    assert cfg.appearance == config.APPEARANCE_MONOKAI

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())
    assert cfg2.appearance == config.APPEARANCE_MONOKAI
