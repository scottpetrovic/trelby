import tests.u as u
import trelby.config as config
import trelby.keys as keys
import trelby.screenplay as screenplay
import trelby.screenplay.proofing as proofing
import trelby.translations as translations

_ = translations.trelby_translations_load()

# the formatting checker (screenplay/proofing.py) on
# fixtures/formatting-errors.trelby, a short script with one of each kind of
# formatting error a user can make, spread over two pages


def errors():
    sp = u.load("formatting-errors.trelby")

    return sp, proofing.findErrors(sp)


def testFindsEveryError():
    sp, errs = errors()

    assert [(sp.line2pageLabel(e.line), sp.lines[e.line].text, e.msg) for e in errs] == [
        ("1", "", "Empty line."),
        (
            "1",
            "DETECTIVE HALE",
            "Element type 'Action' can not follow type 'Character'.",
        ),
        (
            "1",
            "Coffee. Black.",
            "Element type 'Dialogue' can not follow type 'Action'.",
        ),
        ("1", "()", "Empty parenthetical."),
        (
            "2",
            "(to himself)",
            "Element type 'Parenthetical' can not follow type 'Action'.",
        ),
        ("2", "   ", "Empty line (contains only spaces)."),
        ("2", "Nobody home.", "Element type 'Dialogue' can not follow type 'Scene'."),
    ]


def testEmptyLinesInNotesAreAllowed():
    sp, errs = errors()

    notes = [i for i, ln in enumerate(sp.lines) if ln.lt == screenplay.NOTE]
    assert "" in [sp.lines[i].text for i in notes]
    assert not [e for e in errs if e.line in notes]


def testSampleScriptHasNoErrors():
    u.init()

    with open("trelby/sample.trelby", encoding="utf-8-sig") as f:
        assert proofing.findErrors(u.loadString(f.read())) == []


def testFixingAnErrorRemovesIt():
    sp, errs = errors()

    ed = u.loadEditor("formatting-errors.trelby")
    ed.line = errs[0].line
    ed.column = 0
    ed.cmd("deleteBackward")

    assert len(proofing.findErrors(ed.sp)) == len(errs) - 1


def testOldFindNextErrorKeysCarryOver():
    u.init()
    ctrlG = keys.Key(7, ctrl=True).toInt()

    cfg = config.ConfigGlobal()
    cfg.load("Command/FindNextError/Keys:1\nCommand/FindNextError/Keys/1:%d\n" % ctrlG)

    cmd = [c for c in cfg.commands if c.name == "CheckFormatting"][0]
    assert cmd.keys == [ctrlG]

    # but not over keys saved for the new command
    cfg = config.ConfigGlobal()
    cfg.load(
        "Command/FindNextError/Keys:1\nCommand/FindNextError/Keys/1:%d\n"
        "Command/CheckFormatting/Keys:0\n" % ctrlG
    )

    cmd = [c for c in cfg.commands if c.name == "CheckFormatting"][0]
    assert cmd.keys == [keys.Key(5, ctrl=True).toInt()]
