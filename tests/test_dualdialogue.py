import tests.u as u
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay as scr
import trelby.screenplay.export as export
import trelby.screenplay.render as render
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
    ed = u.loadStringEditor(
        "\n".join(["#Version 3", "#Start-Script ", ".\\INT. GARAGE - DAY"] + lines)
    )
    ed.sp.paginate()

    return ed


# return a script with an action, then speechLines(dual), then 'extra'
def makeScript(dual=True, extra=[]):
    return loadLines(["..They get out of the car."] + speechLines(dual) + extra)


# return index of the first line of the element whose text starts with s
def find(ed, s):
    for i, ln in enumerate(ed.sp.lines):
        if ln.text.startswith(s) and ed.sp.isFirstLineOfElem(i):
            return i

    assert False, s


# return the text of the element starting at line i
def elemText(ed, i):
    return " ".join(
        ln.text for ln in ed.sp.lines[i : ed.sp.getElemLastIndexFromLine(i) + 1]
    )


# assert the lines of the speech starting at line i fit in the given
# dual dialogue column, or in the normal widths if col is 0
def assertWidths(ed, i, col):
    first, last = ed.sp.getSpeechIndexes(i)

    for ln in ed.sp.lines[first : last + 1]:
        if col:
            width = ed.sp.cfg.getDualIndentWidth(ln.lt, col)[1]
        else:
            width = ed.sp.cfg.getType(ln.lt).width

        assert len(ln.text.rstrip()) <= width


def testDualIndentWidth():
    ed = u.newEditor()
    cfg = ed.sp.cfg

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
    ed = makeScript()

    brick = find(ed, "BRICK")
    steel = find(ed, "STEEL")

    assert ed.sp.lines[steel].dual
    assert ed.sp.getDualBlock(brick) == ed.sp.getDualBlock(steel)

    first, right, last = ed.sp.getDualBlock(steel)
    assert (first, right) == (brick, steel)
    assert ed.sp.lines[last].lt == scr.DIALOGUE
    assert ed.sp.lines[last + 1].lt == scr.ACTION

    assert ed.sp.getDualColumn(brick + 1) == 1
    assert ed.sp.getDualColumn(steel + 1) == 2
    assert ed.sp.getDualColumn(0) == 0
    assert ed.sp.getDualColumn(last + 1) == 0

    # speeches are wrapped to their columns
    assertWidths(ed, brick, 1)
    assertWidths(ed, steel, 2)
    assert elemText(ed, find(ed, "It's")) == STEEL

    # and that makes them longer than normal speeches
    normal = makeScript(dual=False)
    assert len(ed.sp.lines) > len(normal.sp.lines)

    ed._validate()


def testSaveLoad():
    ed = makeScript()
    s = ed.save().decode("UTF-8")

    assert s.count("#Dual-Dialogue \n") == 1
    assert "#Dual-Dialogue \n._STEEL\n" in s

    ed2 = u.loadStringEditor(s)
    assert ed2.sp.lines == ed.sp.lines


def testIgnoredFlags():
    # flag on a character with no speech before it
    ed = u.loadStringEditor(
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

    assert ed.sp.getDualBlock(find(ed, "BRICK")) is None
    assertWidths(ed, find(ed, "BRICK"), 0)

    # flag on something that isn't a character is dropped on save
    ed = u.loadStringEditor(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "#Dual-Dialogue ",
                "..Action.",
            ]
        )
    )

    assert "#Dual-Dialogue" not in ed.save().decode("UTF-8")


def testNoChains():
    # a third speech can't be a dual dialogue with the second one when
    # that's already the right-hand column of one
    ed = makeScript(extra=["#Dual-Dialogue ", "._ROCK", ".:Boys!"])

    rock = find(ed, "ROCK")
    assert ed.sp.getDualBlock(rock) is None
    assert ed.sp.getDualBlock(find(ed, "STEEL"))[0] == find(ed, "BRICK")

    ed.line = rock
    assert not ed.toggleDualDialogue()


def testToggleOff():
    ed = makeScript()
    before = [ln.copy() for ln in ed.sp.lines]

    ed.line = find(ed, "BRICK") + 1
    assert ed.toggleDualDialogue()

    steel = find(ed, "STEEL")
    assert not ed.sp.lines[steel].dual
    assert ed.sp.getDualBlock(steel) is None
    assert ed.sp.lines == makeScript(dual=False).sp.lines

    ed._validate()

    ed.cmd("undo")
    assert ed.sp.lines == before

    ed.cmd("redo")
    assert ed.sp.lines == makeScript(dual=False).sp.lines


def testToggleOn():
    dual = makeScript()

    # from either speech
    for name in ("STEEL", "BRICK"):
        ed = makeScript(dual=False)
        ed.line = find(ed, name)

        assert ed.toggleDualDialogue()
        assert ed.sp.lines == dual.sp.lines

        ed._validate()

    # not from outside a speech
    ed = makeScript(dual=False)
    ed.line = 1

    assert not ed.toggleDualDialogue()
    assert ed.sp.lines == makeScript(dual=False).sp.lines


def testGetDualToggle():
    # in a dual dialogue: would turn it off
    ed = makeScript()
    block = ed.sp.getDualBlock(find(ed, "STEEL"))

    for name in ("BRICK", "STEEL"):
        ed.line = find(ed, name)
        assert ed.getDualToggle() == (block, False)

    # not in one: would turn it on, without changing anything
    ed = makeScript(dual=False)
    ed.line = find(ed, "BRICK")
    block = (find(ed, "BRICK"), find(ed, "STEEL"), find(ed, "They glare") - 1)
    assert ed.getDualToggle() == (block, True)
    assert ed.sp.lines == makeScript(dual=False).sp.lines

    # outside a speech, or with no speech to pair with
    ed.line = 1
    assert ed.getDualToggle() is None

    ed = makeScript(extra=["#Dual-Dialogue ", "._ROCK", ".:Boys!"])
    ed.line = find(ed, "ROCK")
    assert ed.getDualToggle() is None


def testToggleKeepsCursor():
    ed = makeScript(dual=False)

    ed.line = find(ed, "It's")
    ed.column = 5

    assert ed.toggleDualDialogue()
    assert (ed.line, ed.column) == (find(ed, "It's"), 5)


def testUndoStorage():
    ed = makeScript()
    steel = find(ed, "STEEL")

    lines = undo.storage2lines(undo.lines2storage(ed.sp.lines))

    assert lines == ed.sp.lines
    assert lines[steel].dual


def testConvertType():
    # changing BRICK's dialogue into action ends the dual dialogue, so
    # STEEL's speech gets its normal widths again
    ed = makeScript()

    ed.line = find(ed, "I said")
    ed.convertTypeTo(scr.ACTION, True)

    steel = find(ed, "STEEL")
    assert ed.sp.getDualBlock(steel) is None
    assertWidths(ed, steel, 0)
    assert len(ed.sp.lines[find(ed, "It's")].text) > ed.sp.cfg.getDualIndentWidth(
        scr.DIALOGUE, 2
    )[1]

    ed._validate()

    ed.cmd("undo")
    assert ed.sp.lines == makeScript().sp.lines


def testCopyPaste():
    ed = makeScript()

    # copy both speeches and paste them at the end of the script
    ed.setMark(find(ed, "BRICK"), 0)
    ed.line = find(ed, "They glare") - 1
    ed.column = len(ed.sp.lines[ed.line].text)
    cd = ed.getSelectedAsCD(False)

    ed.clearMark()
    ed.line = len(ed.sp.lines) - 1
    ed.column = len(ed.sp.lines[ed.line].text)
    ed.cmd("splitElement")
    ed.paste(cd.lines)

    steels = [i for i, ln in enumerate(ed.sp.lines) if ln.text == "STEEL"]
    assert len(steels) == 2

    for steel in steels:
        assert ed.sp.getDualBlock(steel)
        assertWidths(ed, steel, 2)

    ed._validate()


def testCutLeftSpeech():
    # cutting BRICK's speech leaves STEEL's on its own, with normal widths
    ed = makeScript()

    ed.setMark(find(ed, "BRICK"), 0)
    ed.line = find(ed, "STEEL") - 1
    ed.column = len(ed.sp.lines[ed.line].text)
    ed.getSelectedAsCD(True)

    steel = find(ed, "STEEL")
    assert ed.sp.getDualBlock(steel) is None
    assertWidths(ed, steel, 0)

    ed._validate()


# assert that every element in ed is wrapped the way loading the script
# would wrap it, i.e. speeches fit their dual dialogue columns if they're
# in one, and have normal widths otherwise
def assertWrapped(ed):
    assert ed.sp.lines == u.loadString(ed.save().decode("UTF-8")).lines


# run 'undo' and 'redo' on ed, checking that they restore the lines from
# before and after the last command
def assertUndoRedo(ed, before):
    after = [ln.copy() for ln in ed.sp.lines]

    ed.cmd("undo")
    assert ed.sp.lines == before
    ed._validate()

    ed.cmd("redo")
    assert ed.sp.lines == after
    ed._validate()


def testBackspaceLeftCharacter():
    # backspace at the start of BRICK's character joins it to the action
    # before it, which ends the dual dialogue
    ed = makeScript()
    before = [ln.copy() for ln in ed.sp.lines]

    ed.line = find(ed, "BRICK")
    ed.column = 0
    ed.cmd("deleteBackward")

    assert ed.sp.lines[ed.line].text == "They get out of the car.BRICK"
    assert ed.column == len("They get out of the car.")

    steel = find(ed, "STEEL")
    assert ed.sp.getDualBlock(steel) is None
    assertWidths(ed, steel, 0)
    assertWrapped(ed)
    ed._validate()

    assertUndoRedo(ed, before)


def testEnterLeftDialogue():
    # Enter in the middle of BRICK's dialogue puts a new element between
    # the speeches, which ends the dual dialogue
    ed = makeScript()
    before = [ln.copy() for ln in ed.sp.lines]

    ed.line = find(ed, "I said")
    ed.column = len("I said ")
    ed.cmd("splitElement")

    assert ed.sp.lines[ed.line].text.startswith("we'd")

    assert ed.sp.getDualBlock(find(ed, "BRICK")) is None
    assert ed.sp.getDualBlock(find(ed, "STEEL")) is None
    assertWidths(ed, find(ed, "BRICK"), 0)
    assertWidths(ed, find(ed, "STEEL"), 0)
    assertWrapped(ed)
    ed._validate()

    assertUndoRedo(ed, before)


def testDeleteForwardMakesPair():
    # deleting an empty action between the speeches makes them the dual
    # dialogue STEEL's flag asks for
    lines = speechLines()
    ed = loadLines(lines[:2] + [".."] + lines[2:])
    before = [ln.copy() for ln in ed.sp.lines]

    steel = find(ed, "STEEL")
    assert ed.sp.getDualBlock(steel) is None

    ed.line = find(ed, "I said")
    ed.line = ed.sp.getElemLastIndexFromLine(ed.line)
    ed.column = len(ed.sp.lines[ed.line].text)
    ed.cmd("deleteForward")

    assert ed.sp.getDualBlock(find(ed, "STEEL"))
    assertWidths(ed, find(ed, "BRICK"), 1)
    assertWidths(ed, find(ed, "STEEL"), 2)
    assertWrapped(ed)
    assert ed.sp.lines == loadLines(lines).sp.lines
    ed._validate()

    assertUndoRedo(ed, before)


def getTextOps(ed, pageNr=1):
    pg = render.generatePMLPage(ed.sp, mypager.Pager(ed.sp.cfg), pageNr, True, True)

    return {op.line: op for op in pg.ops if isinstance(op, pml.TextOp) and (op.line != -1)}


def testRender():
    ed = makeScript()
    ops = getTextOps(ed)

    brick = find(ed, "BRICK")
    steel = find(ed, "STEEL")
    first, right, last = ed.sp.getDualBlock(steel)

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
    ed = makeScript(dual=False)
    ops = getTextOps(ed)
    assert ops[find(ed, "STEEL")].y > ops[find(ed, "BRICK")].y


def testRenderTooLong():
    # if the speeches haven't been wrapped for a dual dialogue, they're
    # printed one after another
    ed = makeScript(dual=False)
    ed.sp.lines[find(ed, "STEEL")].dual = True

    assert ed.sp.getDualBlock(find(ed, "STEEL"))
    assert ed.sp.getDualLines(0, len(ed.sp.lines) - 1) == {}

    ops = getTextOps(ed)
    assert ops[find(ed, "STEEL")].y > ops[find(ed, "BRICK")].y


def testPagination():
    # push the dual dialogue to straddle the first page break, with and
    # without the dual flag
    for n in range(30, 60):
        ed = loadLines(["..Action %d." % i for i in range(n)] + speechLines())

        brick = find(ed, "BRICK")
        first, right, last = ed.sp.getDualBlock(find(ed, "STEEL"))

        # never split
        assert ed.sp.line2page(first) == ed.sp.line2page(last)

        # rendered as dual on whatever page it's on
        page = ed.sp.line2page(first)
        ops = getTextOps(ed, page)
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

    assert len(dual.sp.pages) < len(normal.sp.pages)

    # and doesn't overflow: the last text on each page is above the
    # bottom margin
    cfg = dual.sp.cfg
    for p in range(1, len(dual.sp.pages) - 1):
        ops = getTextOps(dual, p)
        assert max(op.y for op in ops.values()) < cfg.paperHeight - cfg.marginBottom


def testExportFountain():
    ed = makeScript()
    s = export.generateFountain(ed.sp)

    assert "\nSTEEL ^\n" in s
    assert "BRICK ^" not in s


def testExportFDX():
    from lxml import etree

    ed = makeScript()
    root = etree.XML(export.generateFDX(ed.sp))

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
    ed = makeScript()
    rows = export.generateText(ed.sp, False).split("\n")

    row = [r for r in rows if "BRICK" in r]
    assert len(row) == 1
    assert "STEEL" in row[0]
    assert row[0].index("BRICK") < row[0].index("STEEL")

    html = export.generateHtml(ed.sp)
    assert "BRICK" in html and "STEEL" in html
