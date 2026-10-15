import pytest

import tests.u as u
import trelby.config as config
import trelby.themes as themes

# tests for the color themes


def testEveryAppearanceIsATheme():
    appearances = set(config._themes) | {config.APPEARANCE_SYSTEM}

    assert appearances == set(
        range(config.APPEARANCE_FIRST, config.APPEARANCE_LAST + 1)
    )


def testThemeColorsAreValid():
    for theme in config._themes.values():
        for rgb in theme.colors.values():
            assert len(rgb) == 3
            assert all(0 <= c <= 255 for c in rgb)


def testEveryElementHasAThemeColor():
    u.init()

    assert set(config._lt2themeElem) == {t.lt for t in config.getTIs()}
    assert set(config._lt2themeElem.values()) == set(themes.ELEMENTS)


def testElementColorDefaultsToText():
    colors = dict(themes.LIGHT.colors, scene=(1, 2, 3))
    colors.pop("action", None)
    t = themes.Theme("Test", False, colors)

    assert t.elementColor("scene") == (1, 2, 3)
    assert t.elementColor("action") == colors["text"]


def testThemeNeedsEveryColor():
    colors = dict(themes.LIGHT.colors)
    del colors["textBg"]

    with pytest.raises(ValueError):
        themes.Theme("Test", False, colors)


def testThemeRejectsUnknownColors():
    with pytest.raises(ValueError):
        themes.Theme("Test", False, dict(themes.LIGHT.colors, bogus=(0, 0, 0)))


def testThemeAccentNeedsAccentText():
    with pytest.raises(ValueError):
        themes.Theme("Test", False, dict(themes.LIGHT.colors, accent=(0, 0, 0)))


def testSceneHeadingsAreColored():
    for theme in config._themes.values():
        assert theme.elementColor("scene") != theme.colors["text"]


def testThemeAppearanceIsSaved():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load("Appearance:%d\n" % config.APPEARANCE_MONOKAI)
    assert cfg.appearance == config.APPEARANCE_MONOKAI

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())
    assert cfg2.appearance == config.APPEARANCE_MONOKAI


def testOldColorSettingsAreIgnored():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load(
        "Color/TextBG:10,20,30\nUseCustomElemColors:True\nAppearance:%d\n"
        % config.APPEARANCE_NORD
    )
    s = cfg.save()

    assert cfg.appearance == config.APPEARANCE_NORD
    assert "Color/" not in s
    assert "UseCustomElemColors" not in s
