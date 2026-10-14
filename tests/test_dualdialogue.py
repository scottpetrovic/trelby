import tests.u as u
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay as scr
import trelby.translations as translations
import trelby.undo as undo

_ = translations.trelby_translations_load()

# tests for dual dialogue

BRICK = (
    "I said we'd be here by noon and we are here by noon, so stop "
    "complaining about the traffic."
)
STEEL = (
    "It's half past twelve and you know it, and the traffic had nothing "
    "to do with it."
)


# return script lines for BRICK's and STEEL's speeches, the latter as the
# right-hand column of a dual dialogue if 'dual' is True, followed by an
# action
def speechLines(dual=True):
    return (
        ["._BRICK", ".:" + BRICK]
        + (["#Dual-Dialogue "] if dual else [])
        + ["._STEEL", ".((shouting)", ".:" + STEEL, "..They glare at each other."]
    )


# return a paginated script from the given script lines, with a header
# and a scene heading added
def loadLines(lines):
    sp = u.loadString(
        "\n".join(["#Version 3", "#Start-Script ", ".\\INT. GARAGE - DAY"] + lines)
    )
    sp.paginate()

    return sp


# return a script with an action, then speechLines(dual), then 'extra'
def makeScript(dual=True, extra=[]):
    return loadLines(["..They get out of the car."] + speechLines(dual) + extra)


# return index of the first line of the element whose text starts with s
def find(sp, s):
    for i, ln in enumerate(sp.lines):
        if ln.text.startswith(s) and sp.isFirstLineOfElem(i):
            return i

    assert False, s


# return the text of the element starting at line i
def elemText(sp, i):
    return " ".join(
        ln.text for ln in sp.lines[i : sp.getElemLastIndexFromLine(i) + 1]
    )


# assert the lines of the speech starting at line i fit in the given
# dual dialogue column, or in the normal widths if col is 0
def assertWidths(sp, i, col):
    first, last = sp.getSpeechIndexes(i)

    for ln in sp.lines[first : last + 1]:
        if col:
            width = sp.cfg.getDualIndentWidth(ln.lt, col)[1]
        else:
            width = sp.cfg.getType(ln.lt).width

        assert len(ln.text.rstrip()) <= width


def testDualIndentWidth():
    sp = u.new()
    cfg = sp.cfg

    # columns don't overlap and stay within the action width
    for lt in (scr.CHARACTER, scr.PAREN, scr.DIALOGUE):
        x1, w1 = cfg.getDualIndentWidth(lt, 1)
        x2, w2 = cfg.getDualIndentWidth(lt, 2)

        assert x1 + w1 < cfg.getDualIndentWidth(scr.DIALOGUE, 2)[0]
        assert x2 + w2 <= cfg.getType(scr.ACTION).width
        assert w1 < cfg.getType(lt).width

    # character names and parentheticals are indented like in a normal
    # speech
    dlgX = cfg.getDualIndentWidth(scr.DIALOGUE, 1)[0]
    parenX = cfg.getDualIndentWidth(scr.PAREN, 1)[0]
    charX = cfg.getDualIndentWidth(scr.CHARACTER, 1)[0]

    assert dlgX < parenX < charX


def testLoad():
    sp = makeScript()

    brick = find(sp, "BRICK")
    steel = find(sp, "STEEL")

    assert sp.lines[steel].dual
    assert sp.getDualBlock(brick) == sp.getDualBlock(steel)

    first, right, last = sp.getDualBlock(steel)
    assert (first, right) == (brick, steel)
    assert sp.lines[last].lt == scr.DIALOGUE
    assert sp.lines[last + 1].lt == scr.ACTION

    assert sp.getDualColumn(brick + 1) == 1
    assert sp.getDualColumn(steel + 1) == 2
    assert sp.getDualColumn(0) == 0
    assert sp.getDualColumn(last + 1) == 0

    # speeches are wrapped to their columns
    assertWidths(sp, brick, 1)
    assertWidths(sp, steel, 2)
    assert elemText(sp, find(sp, "It's")) == STEEL

    # and that makes them longer than normal speeches
    normal = makeScript(dual=False)
    assert len(sp.lines) > len(normal.lines)

    sp._validate()


def testSaveLoad():
    sp = makeScript()
    s = sp.save().decode("UTF-8")

    assert s.count("#Dual-Dialogue \n") == 1
    assert "#Dual-Dialogue \n._STEEL\n" in s

    sp2 = u.loadString(s)
    assert sp2.lines == sp.lines


def testIgnoredFlags():
    # flag on a character with no speech before it
    sp = u.loadString(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "..Action.",
                "#Dual-Dialogue ",
                "._BRICK",
                ".:Hello.",
            ]
        )
    )

    assert sp.getDualBlock(find(sp, "BRICK")) is None
    assertWidths(sp, find(sp, "BRICK"), 0)

    # flag on something that isn't a character is dropped on save
    sp = u.loadString(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "#Dual-Dialogue ",
                "..Action.",
            ]
        )
    )

    assert "#Dual-Dialogue" not in sp.save().decode("UTF-8")


def testNoChains():
    # a third speech can't be a dual dialogue with the second one when
    # that's already the right-hand column of one
    sp = makeScript(extra=["#Dual-Dialogue ", "._ROCK", ".:Boys!"])

    rock = find(sp, "ROCK")
    assert sp.getDualBlock(rock) is None
    assert sp.getDualBlock(find(sp, "STEEL"))[0] == find(sp, "BRICK")

    sp.line = rock
    assert not sp.toggleDualDialogue()


def testToggleOff():
    sp = makeScript()
    before = [ln.copy() for ln in sp.lines]

    sp.line = find(sp, "BRICK") + 1
    assert sp.toggleDualDialogue()

    steel = find(sp, "STEEL")
    assert not sp.lines[steel].dual
    assert sp.getDualBlock(steel) is None
    assert sp.lines == makeScript(dual=False).lines

    sp._validate()

    sp.cmd("undo")
    assert sp.lines == before

    sp.cmd("redo")
    assert sp.lines == makeScript(dual=False).lines


def testToggleOn():
    dual = makeScript()

    # from either speech
    for name in ("STEEL", "BRICK"):
        sp = makeScript(dual=False)
        sp.line = find(sp, name)

        assert sp.toggleDualDialogue()
        assert sp.lines == dual.lines

        sp._validate()

    # not from outside a speech
    sp = makeScript(dual=False)
    sp.line = 1

    assert not sp.toggleDualDialogue()
    assert sp.lines == makeScript(dual=False).lines


def testGetDualToggle():
    # in a dual dialogue: would turn it off
    sp = makeScript()
    block = sp.getDualBlock(find(sp, "STEEL"))

    for name in ("BRICK", "STEEL"):
        sp.line = find(sp, name)
        assert sp.getDualToggle() == (block, False)

    # not in one: would turn it on, without changing anything
    sp = makeScript(dual=False)
    sp.line = find(sp, "BRICK")
    block = (find(sp, "BRICK"), find(sp, "STEEL"), find(sp, "They glare") - 1)
    assert sp.getDualToggle() == (block, True)
    assert sp.lines == makeScript(dual=False).lines

    # outside a speech, or with no speech to pair with
    sp.line = 1
    assert sp.getDualToggle() is None

    sp = makeScript(extra=["#Dual-Dialogue ", "._ROCK", ".:Boys!"])
    sp.line = find(sp, "ROCK")
    assert sp.getDualToggle() is None


def testToggleKeepsCursor():
    sp = makeScript(dual=False)

    sp.line = find(sp, "It's")
    sp.column = 5

    assert sp.toggleDualDialogue()
    assert (sp.line, sp.column) == (find(sp, "It's"), 5)


def testUndoStorage():
    sp = makeScript()
    steel = find(sp, "STEEL")

    lines = undo.storage2lines(undo.lines2storage(sp.lines))

    assert lines == sp.lines
    assert lines[steel].dual


def testConvertType():
    # changing BRICK's dialogue into action ends the dual dialogue, so
    # STEEL's speech gets its normal widths again
    sp = makeScript()

    sp.line = find(sp, "I said")
    sp.convertTypeTo(scr.ACTION, True)

    steel = find(sp, "STEEL")
    assert sp.getDualBlock(steel) is None
    assertWidths(sp, steel, 0)
    assert len(sp.lines[find(sp, "It's")].text) > sp.cfg.getDualIndentWidth(
        scr.DIALOGUE, 2
    )[1]

    sp._validate()

    sp.cmd("undo")
    assert sp.lines == makeScript().lines


def testCopyPaste():
    sp = makeScript()

    # copy both speeches and paste them at the end of the script
    sp.setMark(find(sp, "BRICK"), 0)
    sp.line = find(sp, "They glare") - 1
    sp.column = len(sp.lines[sp.line].text)
    cd = sp.getSelectedAsCD(False)

    sp.clearMark()
    sp.line = len(sp.lines) - 1
    sp.column = len(sp.lines[sp.line].text)
    sp.cmd("splitElement")
    sp.paste(cd.lines)

    steels = [i for i, ln in enumerate(sp.lines) if ln.text == "STEEL"]
    assert len(steels) == 2

    for steel in steels:
        assert sp.getDualBlock(steel)
        assertWidths(sp, steel, 2)

    sp._validate()


def testCutLeftSpeech():
    # cutting BRICK's speech leaves STEEL's on its own, with normal widths
    sp = makeScript()

    sp.setMark(find(sp, "BRICK"), 0)
    sp.line = find(sp, "STEEL") - 1
    sp.column = len(sp.lines[sp.line].text)
    sp.getSelectedAsCD(True)

    steel = find(sp, "STEEL")
    assert sp.getDualBlock(steel) is None
    assertWidths(sp, steel, 0)

    sp._validate()


# assert that every element in sp is wrapped the way loading the script
# would wrap it, i.e. speeches fit their dual dialogue columns if they're
# in one, and have normal widths otherwise
def assertWrapped(sp):
    assert sp.lines == u.loadString(sp.save().decode("UTF-8")).lines


# run 'undo' and 'redo' on sp, checking that they restore the lines from
# before and after the last command
def assertUndoRedo(sp, before):
    after = [ln.copy() for ln in sp.lines]

    sp.cmd("undo")
    assert sp.lines == before
    sp._validate()

    sp.cmd("redo")
    assert sp.lines == after
    sp._validate()


def testBackspaceLeftCharacter():
    # backspace at the start of BRICK's character joins it to the action
    # before it, which ends the dual dialogue
    sp = makeScript()
    before = [ln.copy() for ln in sp.lines]

    sp.line = find(sp, "BRICK")
    sp.column = 0
    sp.cmd("deleteBackward")

    assert sp.lines[sp.line].text == "They get out of the car.BRICK"
    assert sp.column == len("They get out of the car.")

    steel = find(sp, "STEEL")
    assert sp.getDualBlock(steel) is None
    assertWidths(sp, steel, 0)
    assertWrapped(sp)
    sp._validate()

    assertUndoRedo(sp, before)


def testEnterLeftDialogue():
    # Enter in the middle of BRICK's dialogue puts a new element between
    # the speeches, which ends the dual dialogue
    sp = makeScript()
    before = [ln.copy() for ln in sp.lines]

    sp.line = find(sp, "I said")
    sp.column = len("I said ")
    sp.cmd("splitElement")

    assert sp.lines[sp.line].text.startswith("we'd")

    assert sp.getDualBlock(find(sp, "BRICK")) is None
    assert sp.getDualBlock(find(sp, "STEEL")) is None
    assertWidths(sp, find(sp, "BRICK"), 0)
    assertWidths(sp, find(sp, "STEEL"), 0)
    assertWrapped(sp)
    sp._validate()

    assertUndoRedo(sp, before)


def testDeleteForwardMakesPair():
    # deleting an empty action between the speeches makes them the dual
    # dialogue STEEL's flag asks for
    lines = speechLines()
    sp = loadLines(lines[:2] + [".."] + lines[2:])
    before = [ln.copy() for ln in sp.lines]

    steel = find(sp, "STEEL")
    assert sp.getDualBlock(steel) is None

    sp.line = find(sp, "I said")
    sp.line = sp.getElemLastIndexFromLine(sp.line)
    sp.column = len(sp.lines[sp.line].text)
    sp.cmd("deleteForward")

    assert sp.getDualBlock(find(sp, "STEEL"))
    assertWidths(sp, find(sp, "BRICK"), 1)
    assertWidths(sp, find(sp, "STEEL"), 2)
    assertWrapped(sp)
    assert sp.lines == loadLines(lines).lines
    sp._validate()

    assertUndoRedo(sp, before)


def getTextOps(sp, pageNr=1):
    pg = sp.generatePMLPage(mypager.Pager(sp.cfg), pageNr, True, True)

    return {op.line: op for op in pg.ops if isinstance(op, pml.TextOp) and (op.line != -1)}


def testRender():
    sp = makeScript()
    ops = getTextOps(sp)

    brick = find(sp, "BRICK")
    steel = find(sp, "STEEL")
    first, right, last = sp.getDualBlock(steel)

    # the columns start on the same row, side by side
    assert ops[steel].y == ops[brick].y
    assert min(ops[i].x for i in range(right, last + 1)) > max(
        ops[i].x for i in range(first, right)
    )

    # the action after goes below the longer column
    after = last + 1
    bottom = max(ops[i].y for i in range(first, last + 1))
    assert ops[after].y > bottom

    # and nothing overlaps
    rows = [(round(ops[i].y, 3), ops[i].x) for i in ops]
    assert len(rows) == len(set(rows))

    # without the flag, everything is in one column
    sp = makeScript(dual=False)
    ops = getTextOps(sp)
    assert ops[find(sp, "STEEL")].y > ops[find(sp, "BRICK")].y


def testRenderTooLong():
    # if the speeches haven't been wrapped for a dual dialogue, they're
    # printed one after another
    sp = makeScript(dual=False)
    sp.lines[find(sp, "STEEL")].dual = True

    assert sp.getDualBlock(find(sp, "STEEL"))
    assert sp.getDualLines(0, len(sp.lines) - 1) == {}

    ops = getTextOps(sp)
    assert ops[find(sp, "STEEL")].y > ops[find(sp, "BRICK")].y


def testPagination():
    # push the dual dialogue to straddle the first page break, with and
    # without the dual flag
    for n in range(30, 60):
        sp = loadLines(["..Action %d." % i for i in range(n)] + speechLines())

        brick = find(sp, "BRICK")
        first, right, last = sp.getDualBlock(find(sp, "STEEL"))

        # never split
        assert sp.line2page(first) == sp.line2page(last)

        # rendered as dual on whatever page it's on
        page = sp.line2page(first)
        ops = getTextOps(sp, page)
        assert ops[right].y == ops[brick].y


def testPaginationUsesTallerColumn():
    # a page of dual dialogues holds more lines than the same speeches one
    # after another
    lines = []
    for i in range(20):
        lines += ["._A%d" % i, ".:" + BRICK, "#Dual-Dialogue ", "._B%d" % i]
        lines += [".:" + STEEL, "..Pause."]

    dual = loadLines(lines)
    normal = loadLines([s for s in lines if s != "#Dual-Dialogue "])

    assert len(dual.pages) < len(normal.pages)

    # and doesn't overflow: the last text on each page is above the
    # bottom margin
    cfg = dual.cfg
    for p in range(1, len(dual.pages) - 1):
        ops = getTextOps(dual, p)
        assert max(op.y for op in ops.values()) < cfg.paperHeight - cfg.marginBottom


def testExportFountain():
    sp = makeScript()
    s = sp.generateFountain()

    assert "\nSTEEL ^\n" in s
    assert "BRICK ^" not in s


def testExportFDX():
    from lxml import etree

    sp = makeScript()
    root = etree.XML(sp.generateFDX())

    dd = root.xpath("Content/Paragraph[@Type='General']/DualDialogue")
    assert len(dd) == 1

    types = [p.get("Type") for p in dd[0].xpath("Paragraph")]
    assert types == ["Character", "Dialogue", "Character", "Parenthetical", "Dialogue"]

    texts = [p.xpath("Text")[0].text for p in dd[0].xpath("Paragraph")]
    assert texts[0] == "BRICK"
    assert texts[4] == STEEL

    # the rest stays outside
    assert root.xpath("Content/Paragraph[@Type='Action']/Text")[-1].text == (
        "They glare at each other."
    )


def testExportText():
    sp = makeScript()
    rows = sp.generateText(False).split("\n")

    row = [r for r in rows if "BRICK" in r]
    assert len(row) == 1
    assert "STEEL" in row[0]
    assert row[0].index("BRICK") < row[0].index("STEEL")

    html = sp.generateHtml()
    assert "BRICK" in html and "STEEL" in html
