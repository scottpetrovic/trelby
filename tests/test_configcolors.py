import json
import os

import pytest

import tests.u as u
import trelby.config as config
import trelby.configgui as configgui
import trelby.gutil as gutil
import trelby.themes as themes
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests for the color themes


@pytest.fixture
def themesDir(tmp_path):
    yield tmp_path

    # don't leave custom themes around for other tests
    themes.loadCustom(str(tmp_path / "nonexistent"))


# write a theme file in 'dirName', with the given contents (a dict is
# written as JSON)
def writeTheme(dirName, filename, contents):
    if not isinstance(contents, str):
        contents = json.dumps(contents)

    with open(os.path.join(dirName, filename), "w", encoding="utf-8") as f:
        f.write(contents)


# a valid theme file's contents
def themeDict(name="Mine", **kwargs):
    d = json.loads(themes.toJson(themes.NORD, name))
    d.update(kwargs)

    return d


def testOldAppearancesAreThemes():
    assert config._oldAppearances[0] == config.THEME_SYSTEM
    assert config._oldAppearances[1:] == [t.name for t in themes.BUILTIN]


def testThemeColorsAreValid():
    for theme in themes.BUILTIN:
        for rgb in theme.colors.values():
            assert len(rgb) == 3
            assert all(0 <= c <= 255 for c in rgb)


def testEveryElementHasAThemeColor():
    u.init()

    assert set(configgui._lt2themeElem) == {t.lt for t in config.getTIs()}
    assert set(configgui._lt2themeElem.values()) == set(themes.ELEMENTS)


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


def testThemeRejectsBadColorValues():
    with pytest.raises(ValueError):
        themes.Theme("Test", False, dict(themes.LIGHT.colors, text=(0, 0, 256)))


def testSceneHeadingsAreColored():
    for theme in themes.BUILTIN:
        assert theme.elementColor("scene") != theme.colors["text"]


def testThemeIsSavedByName():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load("Theme:Monokai\n")
    assert cfg.theme == "Monokai"

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())
    assert cfg2.theme == "Monokai"


def testOldAppearanceSettingIsLoaded():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load("Appearance:6\n")
    assert cfg.theme == "Monokai"
    assert "Appearance" not in cfg.save()

    # the new setting wins
    cfg.load("Appearance:6\nTheme:Nord\n")
    assert cfg.theme == "Nord"

    for bad in ["99", "-1", "x"]:
        cfg = config.ConfigGlobal()
        cfg.load("Appearance:%s\n" % bad)
        assert cfg.theme == config.THEME_SYSTEM


def testOldColorSettingsAreIgnored():
    u.init()
    cfg = config.ConfigGlobal()
    cfg.load("Color/TextBG:10,20,30\nUseCustomElemColors:True\nAppearance:8\n")
    s = cfg.save()

    assert cfg.theme == "Nord"
    assert "Color/" not in s
    assert "UseCustomElemColors" not in s


def testExportedThemeLoadsBack():
    for theme in themes.BUILTIN:
        t = themes.fromJson(themes.toJson(theme, "Copy"), "x")

        assert t.name == "Copy"
        assert t.dark == theme.dark
        assert t.colors == theme.colors


def testThemeFileColorFormats():
    d = themeDict(colors=dict(themeDict()["colors"], text=[1, 2, 3], scene="#0aFf10"))
    t = themes.fromJson(json.dumps(d), "x")

    assert t.colors["text"] == (1, 2, 3)
    assert t.colors["scene"] == (10, 255, 16)


def testThemeFileNameDefaultsToFileName():
    d = themeDict()
    del d["name"]

    assert themes.fromJson(json.dumps(d), "From File").name == "From File"


@pytest.mark.parametrize(
    "contents, message",
    [
        ("{", "not valid JSON"),
        ("[]", "JSON object"),
        (themeDict(extra=1), "unknown settings: extra"),
        (themeDict(name=""), "'name'"),
        (themeDict(name=5), "'name'"),
        (themeDict(dark="no"), "'dark'"),
        (themeDict(colors=[]), "'colors'"),
        (themeDict(colors={"text": "#000000"}), "missing colors"),
        (
            themeDict(colors=dict(themeDict()["colors"], txet="#000000")),
            "unknown colors: txet",
        ),
    ],
)
def testInvalidThemeFile(contents, message):
    if not isinstance(contents, str):
        contents = json.dumps(contents)

    with pytest.raises(ValueError, match=message):
        themes.fromJson(contents, "x")


@pytest.mark.parametrize(
    "val",
    [
        "#12345",
        "#1234567",
        "#12345g",
        "#+12345",
        "red",
        [1, 2],
        [0, 0, 256],
        [0, 0, 1.5],
        7,
    ],
)
def testInvalidThemeFileColor(val):
    d = themeDict(colors=dict(themeDict()["colors"], text=val))

    with pytest.raises(ValueError, match="color 'text'"):
        themes.fromJson(json.dumps(d), "x")


def testLoadCustomThemes(themesDir):
    writeTheme(themesDir, "b.json", themeDict("Zed"))
    writeTheme(themesDir, "a.json", themeDict("Alpha", dark=False))
    writeTheme(themesDir, "notes.txt", "not a theme")

    assert themes.loadCustom(str(themesDir)) == []

    assert [t.name for t in themes.getCustom()] == ["Alpha", "Zed"]
    assert themes.getAll() == themes.BUILTIN + themes.getCustom()

    t = themes.find("Alpha")
    assert not t.isBuiltin()
    assert not t.dark
    assert t.path == os.path.join(str(themesDir), "a.json")


def testInvalidThemeFilesAreSkipped(themesDir):
    writeTheme(themesDir, "good.json", themeDict("Good"))
    writeTheme(themesDir, "broken.json", "{")
    writeTheme(themesDir, "nord.json", themeDict("nord"))
    writeTheme(themesDir, "good2.json", themeDict("GOOD"))
    with open(os.path.join(themesDir, "latin1.json"), "wb") as f:
        f.write(b'{"name": "\xe9"}')

    errors = themes.loadCustom(str(themesDir))

    assert [t.name for t in themes.getCustom()] == ["Good"]
    assert len(errors) == 4
    assert errors[0].startswith("broken.json: not valid JSON")
    assert errors[1] == "good2.json: there's already a theme named 'GOOD'"
    assert errors[2] == "latin1.json: not UTF-8 text"
    assert errors[3] == "nord.json: there's already a theme named 'nord'"


def testMissingThemesDir(themesDir):
    assert themes.loadCustom(str(themesDir / "nope")) == []
    assert themes.getCustom() == []


def testReloadReplacesCustomThemes(themesDir):
    writeTheme(themesDir, "a.json", themeDict("A"))
    themes.loadCustom(str(themesDir))
    old = themes.find("A")

    os.remove(os.path.join(themesDir, "a.json"))
    writeTheme(themesDir, "b.json", themeDict("B"))
    themes.loadCustom(str(themesDir))

    assert themes.find("A") is None
    assert themes.find("B") is not None
    assert old is not themes.find("B")


def testCustomThemeSettingFallsBack(themesDir, monkeypatch):
    u.init()
    monkeypatch.setattr(gutil, "isDarkAppearance", lambda: True)
    writeTheme(themesDir, "mine.json", themeDict("Mine"))
    themes.loadCustom(str(themesDir))

    cfg = config.ConfigGlobal()
    cfg.load("Theme:Mine\n")

    assert config.findTheme(cfg.theme) is themes.find("Mine")
    assert config.findTheme("Nord") is themes.NORD
    assert config.findTheme(config.THEME_SYSTEM) is None

    # the file is gone: the system default is used, but the setting keeps
    # the name in case the file comes back
    themes.loadCustom(str(themesDir / "nope"))

    assert config.findTheme(cfg.theme) is None
    assert configgui.getTheme(cfg.theme) is themes.DARK

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())
    assert cfg2.theme == "Mine"
