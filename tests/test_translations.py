import gettext
import os
import re

import tests.u as u
import trelby
import trelby.config as config
import trelby.translations as translations

# test picking a translation from LANG


def testParseLanguage():
    pl = translations.parseLanguage

    assert pl("zh_CN") == ("zh", "CN")
    assert pl("zh_CN.UTF-8") == ("zh", "CN")
    assert pl("zh-cn") == ("zh", "CN")
    assert pl("sr_RS.UTF-8@latin") == ("sr", "RS")
    assert pl("es_419") == ("es", "419")
    assert pl("it") == ("it", "")
    assert pl("") is None
    assert pl("C") is None
    assert pl("C.UTF-8") is None
    assert pl("POSIX") is None
    assert pl("english") is None


def testFindLanguage():
    fl = translations.findLanguage
    avail = ["en_GB", "en_US", "it_IT", "zh_CN", "zh_TW"]

    # exact matches, however LANG is spelled
    assert fl("zh_CN", avail) == "zh_CN"
    assert fl("zh_TW.UTF-8", avail) == "zh_TW"
    assert fl("zh-tw", avail) == "zh_TW"
    assert fl("en_GB", avail) == "en_GB"

    # same language, other region: the home region first, else the first
    assert fl("it", avail) == "it_IT"
    assert fl("it_CH", avail) == "it_IT"
    assert fl("en", avail) == "en_GB"
    assert fl("en_AU", avail) == "en_GB"
    assert fl("zh_SG", avail) == "zh_CN"
    assert fl("en", ["en_GB", "en_EN"]) == "en_EN"

    # nothing for this language
    assert fl("de_DE", avail) is None
    assert fl("C", avail) is None
    assert fl("", avail) is None
    assert fl("en_US", []) is None


def testInstalledLanguages():
    localedir = os.path.join(trelby.__path__[0], "locales")
    avail = translations.getLanguages(localedir)

    assert translations.DEFAULT_LANGUAGE in avail
    for name in avail:
        assert translations.parseLanguage(name)[1], name

    assert translations.findLanguage("it_IT.UTF-8", avail) == "it_IT"
    assert translations.findLanguage("en_GB", avail) == "en_US"


def testPickLanguage():
    pk = translations.pickLanguage
    avail = ["en_US", "it_IT"]

    # the Language menu's choice wins over LANG
    assert pk("it_IT", "en_US", avail) == "it_IT"
    assert pk("en_US", "it_IT.UTF-8", avail) == "en_US"

    # "" (system default) or a translation that's gone: LANG decides
    assert pk("", "it_IT.UTF-8", avail) == "it_IT"
    assert pk("de_DE", "it", avail) == "it_IT"

    # and failing that, the default
    assert pk("", "", avail) == translations.DEFAULT_LANGUAGE
    assert pk("de_DE", "C", avail) == translations.DEFAULT_LANGUAGE


def testGetTranslation(monkeypatch):
    monkeypatch.setenv("LANG", "en_US")

    assert translations.getTranslation("it_IT").gettext("Language") == "Lingua"
    assert translations.getTranslation("").gettext("Language") == "Language"

    monkeypatch.setenv("LANG", "it_IT")
    assert translations.getTranslation("").gettext("Language") == "Lingua"
    assert translations.getTranslation("en_US").gettext("Language") == "Language"

    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    assert translations.getTranslation("").gettext("Language") == "语言"


def testPlaceholders():
    localedir = translations.getLocaleDir()

    # a translation must keep the msgid's format fields, in the same
    # order, or .format() / % would fail or put values in the wrong place
    def fields(s):
        return re.findall(r"\{[^{}]*\}|%[-0-9.]*[sdf]", s)

    for name in translations.getLanguages(localedir):
        trans = gettext.translation("trelby", localedir, languages=[name])

        for msgid, msgstr in trans._catalog.items():
            if msgid and msgstr:
                assert fields(msgid) == fields(msgstr), (name, msgid, msgstr)


def testLanguageNames():
    localedir = translations.getLocaleDir()

    # every installed translation has a proper name in the menu
    for name in translations.getLanguages(localedir):
        assert translations.languageName(name) != name, name

    assert translations.languageName("xx_XX") == "xx_XX"


def testLanguageSetting():
    u.init()

    cfg = config.ConfigGlobal()
    assert cfg.language == ""

    cfg.language = "it_IT"
    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())
    assert cfg2.language == "it_IT"
