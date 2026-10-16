import tests.u as u
import trelby.config as config
import trelby.textutil as textutil
import trelby.translations as translations

_ = translations.trelby_translations_load()

# textutil.encodeStr / decodeStr, used for StrBinaryVar config values (screen
# font names, PDF viewer arguments).


def testRoundTrip():
    u.init()

    for s in [
        "",
        "plain text",
        "back\\slash",
        "tab\there\nnewline",
        "\xe5\xe4\xf6 \xa4\xbd\xff",
        "MS \u30b4\u30b7\u30c3\u30af",
        "\u0100 \uffff \U0001f600 \U0010ffff",
        'C:\\Program Files\\x.exe "%s"',
    ]:
        assert textutil.decodeStr(textutil.encodeStr(s)) == s


def testEncodeFormat():
    u.init()

    assert textutil.encodeStr("a\\b") == "a\\5Cb"
    assert textutil.encodeStr("\n\xe5") == "\\0A\\E5"
    assert textutil.encodeStr("\u30b4") == "\\u30B4"
    assert textutil.encodeStr("\U0001f600") == "\\U0001F600"


def testDecodeOldFormat():
    u.init()

    # strings written by old versions, which existing config files contain,
    # must decode the same as they always did.
    assert textutil.decodeStr("a\\5Cb\\E5\\0A") == "a\\b\xe5\n"
    assert textutil.decodeStr("\\e5") == "\xe5"

    # old versions wrote characters above U+00FF as "\" plus all their hex
    # digits, which were read back as two digits plus literal text.
    assert textutil.decodeStr("MS \\30B4") == "MS 0B4"


def testDecodeInvalid():
    u.init()

    # invalid escapes are dropped.
    assert textutil.decodeStr("a\\zzb") == "ab"
    assert textutil.decodeStr("a\\u12") == "a2"
    assert textutil.decodeStr("\\UFFFFFFFF") == ""


def testFontNameSurvivesConfig():
    u.init()

    font = "0;-12;0;0;0;400;0;0;0;128;0;0;0;0;MS \u30b4\u30b7\u30c3\u30af"
    args = '--page "\u30da\u30fc\u30b8"'

    cfg = config.ConfigGlobal()
    cfg.fontNormal = font
    cfg.pdfViewerArgs = args

    cfg2 = config.ConfigGlobal()
    cfg2.load(cfg.save())

    assert cfg2.fontNormal == font
    assert cfg2.pdfViewerArgs == args
