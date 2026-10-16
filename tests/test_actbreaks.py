import tests.u as u
import trelby.mypager as mypager
import trelby.pml as pml
import trelby.screenplay.render as render
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests for how act breaks are paginated and formatted, the way TV
# scripts use them: an act heading starts a new page, and an act break
# ends a scene for scene CONTINUEDs.


# return a script made of the given (type char, text) elements, e.g. ("@",
# "ACT ONE"), with scene CONTINUEDs enabled.
def makeScript(elems, actNewPage=True):
    lines = ["#Version 3", "#Start-Script "]
    lines += [".%s%s" % (c, text) for c, text in elems]

    sp = u.loadString("\n".join(lines))
    sp.cfg.sceneContinueds = True
    sp.cfg.pbActNewPage = actNewPage
    sp.reformatAll()
    sp.paginate()

    return sp


def actions(n, name="Action"):
    return [(".", "%s %d." % (name, i + 1)) for i in range(n)]


# return the text of the first line of each page
def pageStarts(sp):
    return [sp.lines[sp.page2lines(p)[0]].text for p in range(1, len(sp.pages))]


# return the text of the last line of each page
def pageEnds(sp):
    return [sp.lines[sp.page2lines(p)[1]].text for p in range(1, len(sp.pages))]


# return the texts of each page as exported to PDF
def pdfTexts(sp):
    pager = mypager.Pager(sp.cfg)
    ret = []

    for p in range(1, len(sp.pages)):
        pg = render.generatePMLPage(sp, pager, p, True, True)
        ret.append([op.text for op in pg.ops if isinstance(op, pml.TextOp)])

    return ret


def testActBreakFitsOnOneLine():
    sp = makeScript([("@", "END OF ACT THREE")])

    assert [ln.text for ln in sp.lines] == ["END OF ACT THREE"]


def testIsActStart():
    sp = makeScript(
        [("@", "TEASER")]
        + actions(2)
        + [("@", "END OF TEASER"), ("@", "ACT ONE"), ("\\", "INT. HOUSE - DAY")]
        + actions(2)
        + [("@", "END OF SHOW")]
    )

    starts = [ln.text for i, ln in enumerate(sp.lines) if sp.isActStart(i)]

    assert starts == ["TEASER", "ACT ONE"]


def testEachActStartsOnNewPage():
    sp = makeScript(
        [("@", "TEASER"), ("\\", "INT. HOUSE - DAY")]
        + actions(3)
        + [("@", "END OF TEASER"), ("@", "ACT ONE"), ("\\", "EXT. STREET - NIGHT")]
        + actions(3)
        + [("@", "END OF ACT ONE"), ("@", "ACT TWO")]
        + actions(3, "More")
    )

    assert pageStarts(sp) == ["TEASER", "ACT ONE", "ACT TWO"]
    assert pageEnds(sp) == ["END OF TEASER", "END OF ACT ONE", "More 3."]


def testActNewPageCanBeTurnedOff():
    sp = makeScript(
        actions(3)
        + [("@", "END OF ACT ONE"), ("@", "ACT TWO")]
        + actions(3, "More"),
        actNewPage=False,
    )

    assert len(sp.pages) == 2


# an act heading near the bottom of a page goes to the next page, with
# the act, even without starting each act on a new page
def testActHeadingNotLeftAtBottomOfPage():
    movedCnt = 0

    # move the act heading down the first page one line at a time, until
    # it's well past the end of it
    for n in range(1, 40):
        sp = makeScript(
            actions(n)
            + [("@", "ACT TWO"), ("\\", "INT. HOUSE - DAY")]
            + actions(5, "More"),
            actNewPage=False,
        )

        texts = [ln.text for ln in sp.lines]
        heading = texts.index("ACT TWO")
        page = sp.line2page(heading)

        assert sp.line2page(heading + 1) == page
        assert sp.line2page(heading + 2) == page

        if (page == 2) and (sp.line2page(heading - 1) == 1):
            movedCnt += 1

    assert movedCnt > 0


def testNoContinuedAcrossActBreaks():
    sp = makeScript(
        [("\\", "INT. HOUSE - DAY")]
        + actions(45)
        + [("@", "END OF ACT ONE"), ("@", "ACT TWO")]
        + actions(3, "More")
    )

    pages = pdfTexts(sp)

    assert len(pages) == 3

    # the scene continues from the first page to the second one, but
    # stops at the end of the act
    assert "(CONTINUED)" in pages[0]
    assert "CONTINUED:" in pages[1]
    assert "(CONTINUED)" not in pages[1]
    assert not any(t.startswith("CONTINUED") for t in pages[2])


def testActBreakEndsScene():
    sp = makeScript(
        [("\\", "INT. HOUSE - DAY")]
        + actions(2)
        + [("@", "END OF ACT ONE"), ("@", "ACT TWO")]
        + actions(2)
    )

    texts = [ln.text for ln in sp.lines]
    endOfAct = texts.index("END OF ACT ONE")
    actTwo = texts.index("ACT TWO")

    assert sp.isLastLineOfScene(endOfAct - 1)
    assert sp.isFirstLineOfScene(endOfAct)
    assert sp.isFirstLineOfScene(actTwo)
    assert not sp.isFirstLineOfScene(actTwo + 1)


def testContinuedCountRestartsAfterActBreak():
    sp = makeScript(
        [("\\", "INT. HOUSE - DAY")]
        + actions(120)
        + [("@", "END OF ACT ONE"), ("@", "ACT TWO")]
        + actions(120, "More")
    )

    continueds = [
        t for page in pdfTexts(sp) for t in page if t.startswith("CONTINUED:")
    ]

    # the second act has no scene heading, so its pages are still marked
    # as continued, but they're counted from the start of the act
    restart = continueds.index("CONTINUED:", 1)

    assert continueds[0] == "CONTINUED:"
    assert continueds[restart - 1] != "CONTINUED:"
    assert continueds[restart + 1] == "CONTINUED: (2)"
