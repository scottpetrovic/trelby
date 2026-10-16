"""Translation related functions"""

import os
import gettext
import re

import trelby

# used when LANG is unset or names a language we have no translation for
DEFAULT_LANGUAGE = "en_US"


def parseLanguage(code):
    """Split a locale name like "zh_CN.UTF-8", "zh-cn" or "it" into a
    (language, region) tuple, e.g. ("zh", "CN") or ("it", ""). Returns None
    if code isn't a locale name (e.g. "C" or "POSIX")."""

    # drop the encoding and modifier: "sr_RS.UTF-8@latin" -> "sr_RS"
    code = re.split("[.@]", code)[0]

    m = re.fullmatch("([a-zA-Z]{2,3})(?:[-_]([a-zA-Z]{2}|[0-9]{3}))?", code)
    if not m or (code.upper() in ("C", "POSIX")):
        return None

    return (m.group(1).lower(), (m.group(2) or "").upper())


def getLanguages(localedir):
    """Return the installed translations' folder names, e.g. ["en_US",
    "it_IT"]."""

    if not os.path.isdir(localedir):
        return []

    return sorted(
        name
        for name in os.listdir(localedir)
        if os.path.isfile(os.path.join(localedir, name, "LC_MESSAGES", "trelby.mo"))
    )


def findLanguage(code, available):
    """Return the name in available that best matches the locale name code,
    or None. An exact match ("zh_CN") wins, then another region of the same
    language, preferring its home region ("it" -> "it_IT", "en_GB" ->
    "en_US")."""

    wanted = parseLanguage(code)
    if not wanted:
        return None

    lang, region = wanted
    sameLang = []

    for name in available:
        have = parseLanguage(name)
        if not have or (have[0] != lang):
            continue

        if have[1] == region:
            return name

        sameLang.append((have[1] != lang.upper(), name))

    if sameLang:
        return min(sameLang)[1]

    return None


def getLocaleDir():
    return os.path.dirname(trelby.__file__) + "/locales"


# each language's name in that language, for the Language menu. a
# translation missing from here is listed by its folder name.
LANGUAGE_NAMES = {
    "en_US": "English",
    "it_IT": "Italiano",
    "zh_CN": "简体中文",
}


def languageName(name):
    return LANGUAGE_NAMES.get(name, name)


def pickLanguage(setting, lang, available):
    """Return the translation to use: the one the Language setting names,
    or failing that (it's "", meaning the system's language, or that
    translation is gone) the best match for the LANG environment variable,
    or DEFAULT_LANGUAGE."""

    return (
        findLanguage(setting, available)
        or findLanguage(lang, available)
        or DEFAULT_LANGUAGE
    )


def getTranslation(setting=""):
    """Return the gettext translation for the global config's language
    setting."""
    localedir = getLocaleDir()
    available = getLanguages(localedir)

    language = pickLanguage(setting, os.environ.get("LANG", ""), available)

    # fallback: if even the default isn't built, show the untranslated
    # (English) strings instead of failing to start
    return gettext.translation(
        "trelby", localedir=localedir, languages=[language], fallback=True
    )


def trelby_translations_load(setting=""):
    """load translations. setting is the global config's language."""
    trans = getTranslation(setting)
    trans.install()

    return trans.gettext
