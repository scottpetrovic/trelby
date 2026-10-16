import os

import trelby
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
