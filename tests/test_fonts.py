import pytest
import wx

import tests.u as u
import trelby.config as config
import trelby.pdf.fontinfo as fontinfo
import trelby.translations as translations
import trelby.ui.configgui as configgui
import trelby.ui.gutil as gutil

_ = translations.trelby_translations_load()

# the bundled Courier Prime as the default screen font, and moving
# configs from the old default (Courier New, Monospace on Unix) to it

FONT_KEYS = ("FontNormal", "FontBold", "FontItalic", "FontBoldItalic")


@pytest.fixture(scope="module")
def app():
    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


def testMigrateFont():
    m = config.migrateFont

    # Windows, both NativeFontInfo versions
    assert (
        m("0;-13;0;0;0;700;0;0;0;0;3;2;1;49;Courier New")
        == "0;-13;0;0;0;700;0;0;0;0;3;2;1;49;Courier Prime"
    )
    assert (
        m("1;9.75;-13;0;0;0;400;0;0;0;0;3;2;1;49;Courier New")
        == "1;9.75;-13;0;0;0;400;0;0;0;0;3;2;1;49;Courier Prime"
    )

    # Pango
    assert m("Courier New Bold 14") == "Courier Prime Bold 14"
    assert m("Monospace Bold Italic 12") == "Courier Prime Bold Italic 12"

    # anything else stays
    for s in [
        "0;-13;0;0;0;400;0;0;0;0;3;2;1;49;Consolas",
        "Monospace 10",
        "DejaVu Sans Mono 12",
        "",
    ]:
        assert m(s) == s


def loadConfig(s):
    u.init()
    cfgGl = config.ConfigGlobal()
    cfgGl.load(s)

    return cfgGl


def testOldConfigMigratedOnce():
    old = "".join(
        "%s:0;-13;0;0;0;400;0;0;0;0;3;2;1;49;Courier New\n" % k for k in FONT_KEYS
    )
    cfgGl = loadConfig(old)

    for name in ["fontNormal", "fontBold", "fontItalic", "fontBoldItalic"]:
        assert getattr(cfgGl, name).endswith(";Courier Prime")

    # saved with FontVersion, so Courier New chosen again stays
    saved = cfgGl.save()
    assert "FontVersion:1" in saved

    cfgGl = loadConfig(saved.replace("Courier Prime", "Courier New"))
    assert cfgGl.fontNormal.endswith(";Courier New")


def testDefaultFontsAreBundled():
    cfgGl = loadConfig("")
    cfgGl.setDefaultFonts()

    for name in ["fontNormal", "fontBold", "fontItalic", "fontBoldItalic"]:
        assert fontinfo.BUNDLED_FACE in getattr(cfgGl, name)


def testScreenUsesBundledFont(app):
    cfgGl = loadConfig("")
    cfgGl.setDefaultFonts()

    assert gutil.loadBundledFonts()

    cfgGui = configgui.ConfigGui(cfgGl, 100)

    for fi in cfgGui.fonts:
        assert fi.font.GetFaceName() == fontinfo.BUNDLED_FACE
        assert gutil.isFixedWidth(fi.font)
