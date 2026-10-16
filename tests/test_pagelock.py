import tests.u as u
import trelby.screenplay.pagelock as pagelock
import trelby.screenplay as scr
import trelby.screenplay.render as render
import trelby.translations as translations
from trelby.screenplay.line import Line

_ = translations.trelby_translations_load()

# tests for page locking: trelby.screenplay.pagelock and the Screenplay and Editor
# functions using it


# return a script with 'scenes' scenes, each with a heading, 'actions'
# action elements and a note, paginated
def makeScript(scenes=8, actions=12):
    lines = ["#Version 3", "#Start-Script "]

    for s in range(scenes):
        lines.append(".\\INT. ROOM %d - DAY" % (s + 1))

        for a in range(actions):
            lines.append("..Scene %d, action %d." % (s + 1, a + 1))

        lines.append(".%%Note for scene %d." % (s + 1))

    ed = u.loadStringEditor("\n".join(lines))
    ed.sp.paginate()

    return ed


# return a locked script
def makeLocked(**kwargs):
    ed = makeScript(**kwargs)
    ed.lockPages()

    return ed


# return text of the first line of the page with the given label
def firstText(ed, label):
    p = ed.sp.label2page(label)
    assert p != -1

    return ed.sp.lines[ed.sp.page2lines(p)[0]].text


# return {label: text of first line of that page} for all pages
def pageStarts(ed):
    return {label: firstText(ed, label) for label in ed.sp.getPageNumbers()}


def testSegmentLabels():
    assert pagelock.segmentLabels("15", "16", 3) == ["15", "15A", "15B"]
    assert pagelock.segmentLabels("15", None, 1) == ["15"]
    assert pagelock.segmentLabels("15", None, 0) == []

    labels = pagelock.segmentLabels("15", None, 28)
    assert labels[26] == "15Z"
    assert labels[27] == "15ZA"


def testSegmentLabelsBetweenAPages():
    # 15A is followed by locked page 15B, so new pages go between them
    assert pagelock.segmentLabels("15A", "15B", 3) == ["15A", "15AA", "15AB"]
    assert pagelock.segmentLabels("15A", "16", 2) == ["15A", "15B"]


def testSegmentLabelsCombined():
    assert pagelock.segmentLabels("16-17", "18", 2) == ["16-17", "17A"]


def testLabelsBefore():
    assert pagelock.labelsBefore("1", 2) == ["A1", "B1"]


def testLabelOrder():
    order = ["A1", "B1", "1", "1A", "1AA", "1B", "2-3", "4", "10"]

    for i in range(1, len(order)):
        r1 = pagelock.labelRange(order[i - 1])
        r2 = pagelock.labelRange(order[i])
        assert r1[1] < r2[0]


def testLabelValidity():
    for s in ("1", "15A", "A1", "16-17", "15A-16"):
        assert pagelock.isValid(s)

    for s in ("", "A", "15a", "A1A", "17-16", "1-2-3", "x", None):
        assert not pagelock.isValid(s)


def testCombine():
    assert pagelock.combine("16", "17") == "16-17"
    assert pagelock.combine("16-17", "18") == "16-18"
    assert pagelock.combine("15A", "16") == "15A-16"

    # out of order: keep the second one
    assert pagelock.combine("17", "16") == "16"


def testOrderedLocks():
    locks = [(0, "1"), (10, "2"), (20, "3")]
    assert pagelock.orderedLocks(locks) == locks

    # page 9 moved into the middle of the script
    locks = [(0, "1"), (10, "2"), (15, "9"), (20, "3"), (30, "4"), (40, "10")]
    assert pagelock.orderedLocks(locks) == [
        (0, "1"),
        (10, "2"),
        (20, "3"),
        (30, "4"),
        (40, "10"),
    ]


def testUnlockedLabels():
    ed = makeScript()
    pageCnt = len(ed.sp.pages) - 1

    assert pageCnt > 3
    assert ed.sp.getPageNumbers() == [str(p) for p in range(1, pageCnt + 1)]
    assert not ed.sp.hasPageLocks()


def testLockKeepsPagination():
    ed = makeScript()
    pages = list(ed.sp.pages)
    labels = list(ed.sp.pageLabels)

    ed.lockPages()

    assert ed.sp.hasPageLocks()
    assert ed.sp.pages == pages
    assert ed.sp.pageLabels == labels
    assert [ln.pageLock for ln in ed.sp.lines if ln.pageLock] == labels[1:]


def testAddTextCreatesAPages():
    ed = makeLocked()
    starts = pageStarts(ed)
    pageCnt = len(ed.sp.pages) - 1

    # add a lot of text in the middle of page 2
    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()
    ed._validate()

    labels = ed.sp.getPageNumbers()
    assert labels[:4] == ["1", "2", "2A", "2B"]
    assert labels[4:] == [str(p) for p in range(3, pageCnt + 1)]

    # all the original pages still start with the same text
    for label, text in starts.items():
        assert firstText(ed, label) == text


def testAddTextAtEnd():
    ed = makeLocked()
    labels = ed.sp.getPageNumbers()

    ed.gotoPos(len(ed.sp.lines) - 1, len(ed.sp.lines[-1].text))
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(80)])
    ed.sp.paginate()

    newLabels = ed.sp.getPageNumbers()
    added = len(newLabels) - len(labels)

    assert added >= 2
    assert newLabels[: len(labels)] == labels
    assert newLabels[len(labels) :] == [labels[-1] + c for c in "ABCDEF"[:added]]


def testDeleteTextLeavesGap():
    ed = makeLocked()
    starts = pageStarts(ed)
    labels = ed.sp.getPageNumbers()
    start, end = ed.sp.page2lines(2)

    # delete the middle of page 2
    ed.setMark(start + 4, 0)
    ed.gotoPos(end - 4, 0)
    ed.getSelectedAsCD(True)
    ed.sp.paginate()
    ed._validate()

    assert ed.sp.getPageNumbers() == labels
    assert pageStarts(ed) == starts

    newStart, newEnd = ed.sp.page2lines(2)
    assert newStart == start
    assert newEnd < end


def testDeleteFirstLineOfPage():
    ed = makeLocked()
    labels = ed.sp.getPageNumbers()
    start, end = ed.sp.page2lines(3)
    second = ed.sp.lines[start + 1].text

    # delete the first element on page 3; page 3 now starts with what was
    # its second line
    assert ed.sp.lines[start].lb == scr.LB_LAST

    ed.setMark(start, 0)
    ed.gotoPos(start, len(ed.sp.lines[start].text) - 1)
    ed.getSelectedAsCD(True)
    ed.sp.paginate()
    ed._validate()

    assert ed.sp.getPageNumbers() == labels
    assert firstText(ed, "3") == second


def testDeleteWholePageCombines():
    ed = makeLocked()
    start, end = ed.sp.page2lines(2)
    page3 = firstText(ed, "3")

    ed.setMark(start, 0)
    ed.gotoPos(end, len(ed.sp.lines[end].text))
    ed.getSelectedAsCD(True)
    ed.sp.paginate()
    ed._validate()

    labels = ed.sp.getPageNumbers()
    assert labels[:3] == ["1", "2-3", "4"]
    assert firstText(ed, "2-3") == page3


def testTypingKeepsLock():
    ed = makeLocked()
    start = ed.sp.page2lines(3)[0]

    ed.gotoPos(start, 0)

    for ch in "Inserted text that is long enough to wrap to more lines. " * 3:
        ed.cmd("addChar", char=ch)

    ed.sp.paginate()
    ed._validate()

    assert ed.sp.lines[start].pageLock == "3"
    assert firstText(ed, "3").startswith("Inserted")


def testRewrapMovesLock():
    ed = makeScript()

    # lock a page to start in the middle of a multi-line element
    ed.gotoPos(1, len(ed.sp.lines[1].text))
    for ch in " more words" * 20:
        ed.cmd("addChar", char=ch)

    assert ed.sp.lines[2].lb != scr.LB_LAST
    text = ed.sp.lines[2].text
    ed.sp.lines[2].pageLock = "2"

    # make the element's first line shorter, which moves text from the
    # line with the lock up
    ed.gotoPos(1, 0)
    for i in range(10):
        ed.cmd("deleteForward")

    lockLines = [i for i, ln in enumerate(ed.sp.lines) if ln.pageLock]
    assert len(lockLines) == 1

    # the lock is on the line now containing the start of the old text
    ln = ed.sp.lines[lockLines[0]]
    nextLn = ed.sp.lines[lockLines[0] + 1]
    assert text.split()[0] in ln.text + " " + nextLn.text


def testJoinWithPrevElement():
    ed = makeLocked()
    start = ed.sp.page2lines(3)[0]
    text = ed.sp.lines[start].text

    # page 3 starts with an action; joining it with the previous element
    # keeps page 3 starting at the line containing its text
    assert ed.sp.lines[start].lt == scr.ACTION
    assert ed.sp.lines[start - 1].lt == scr.ACTION

    ed.gotoPos(start, 0)
    ed.cmd("deleteBackward")
    ed.sp.paginate()
    ed._validate()

    assert text.split()[0] in firstText(ed, "3")
    assert ed.sp.getPageNumbers()[:3] == ["1", "2", "3"]


def testUndoRedo():
    ed = makeLocked()
    pages = list(ed.sp.pages)
    labels = list(ed.sp.pageLabels)

    start, end = ed.sp.page2lines(2)
    ed.setMark(start, 0)
    ed.gotoPos(end, len(ed.sp.lines[end].text))
    ed.getSelectedAsCD(True)
    ed.sp.paginate()
    assert ed.sp.pageLabels != labels

    ed.cmd("undo")
    ed.sp.paginate()
    assert ed.sp.pages == pages
    assert ed.sp.pageLabels == labels

    ed.cmd("redo")
    ed.sp.paginate()
    assert ed.sp.getPageNumbers()[1] == "2-3"


def testUndoLock():
    ed = makeScript()
    ed.lockPages()
    ed.cmd("undo")

    assert not ed.sp.hasPageLocks()

    ed.cmd("redo")

    assert ed.sp.hasPageLocks()


def testUnlock():
    ed = makeLocked()

    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()
    assert "2A" in ed.sp.getPageNumbers()

    ed.unlockPages()

    assert not ed.sp.hasPageLocks()
    pageCnt = len(ed.sp.pages) - 1
    assert ed.sp.getPageNumbers() == [str(p) for p in range(1, pageCnt + 1)]


def testRelockLocksAPages():
    ed = makeLocked()

    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()

    labels = ed.sp.getPageNumbers()
    ed.lockPages()

    assert ed.sp.getPageNumbers() == labels
    assert sum(1 for ln in ed.sp.lines if ln.pageLock) == len(labels)


def testSaveLoad():
    ed = makeLocked()

    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()

    data = ed.save().decode("UTF-8")
    assert "#Page-Lock 2\n" in data

    ed2 = u.loadStringEditor(data)

    assert ed2.sp.pages == ed.sp.pages
    assert ed2.sp.getPageNumbers() == ed.sp.getPageNumbers()
    assert [ln.pageLock for ln in ed2.sp.lines] == [ln.pageLock for ln in ed.sp.lines]


def testLoadIgnoresInvalidLock():
    sp, msg = scr.Screenplay.load(
        "\n".join(
            [
                "#Version 3",
                "#Start-Script ",
                "#Page-Lock bogus",
                ".\\int. kitchen - day",
            ]
        ),
        u.new().cfgGl,
    )

    assert not sp.hasPageLocks()
    assert msg


def testCopyDoesNotCopyLocks():
    ed = makeLocked()
    start, end = ed.sp.page2lines(2)

    ed.setMark(start, 0)
    ed.gotoPos(end, 0)
    cd = ed.getSelectedAsCD(False)

    assert not any(ln.pageLock for ln in cd.lines)


def testDeepcopyKeepsLocks():
    import copy

    ed = makeLocked()
    ed2 = copy.deepcopy(ed)

    assert [ln.pageLock for ln in ed2.sp.lines] == [ln.pageLock for ln in ed.sp.lines]


def testRemoveNotesKeepsLocks():
    ed = makeScript()

    # a page starting with a note starts with the line after it once
    # notes are removed (as is done when printing without notes)
    note = [i for i, ln in enumerate(ed.sp.lines) if ln.lt == scr.NOTE][2]
    nextText = ed.sp.lines[note + 1].text

    ed.sp.lines[0].pageLock = "1"
    ed.sp.lines[note].pageLock = "2"

    ed.removeElementTypes({scr.NOTE: None}, False)
    ed.sp.paginate()

    assert "2" in ed.sp.getPageNumbers()
    assert firstText(ed, "2") == nextText


def testMoveSceneLeavesLocks():
    ed = makeLocked()
    starts = ed.sp.getOutlineStarts()

    # find a scene (not the last one) containing a page start
    for idx in range(1, len(starts) - 1):
        moved = ed.sp.lines[starts[idx] : starts[idx + 1]]
        movedLocks = [ln.pageLock for ln in moved if ln.pageLock]

        if movedLocks:
            break

    following = ed.sp.lines[starts[idx + 1]]
    expected = movedLocks[0]

    for label in movedLocks[1:] + [following.pageLock]:
        if label:
            expected = pagelock.combine(expected, label)

    # move it to the end. its pages stay where they were, now starting
    # with the scene that followed it.
    ed.moveSceneTo(starts[idx], len(starts) - 1)
    ed.sp.paginate()
    ed._validate()

    assert following.pageLock == expected
    assert not any(ln.pageLock for ln in moved)

    allLocks = [(i, ln.pageLock) for i, ln in enumerate(ed.sp.lines) if ln.pageLock]
    assert ed.sp.getPageLocks() == allLocks


def testOutOfOrderLocksIgnored():
    ed = makeLocked(scenes=20)
    labels = ed.sp.getPageNumbers()
    start = ed.sp.page2lines(2)[0]

    assert len(labels) > 6

    # a stray lock for a later page in the middle of page 2
    ed.sp.lines[start + 3].pageLock = "5"
    ed.sp.paginate()

    assert ed.sp.getPageNumbers() == labels


def testLinesBeforeFirstLock():
    ed = makeLocked()

    # put text before page 1
    ed.sp.lines[0].pageLock = None
    ed.sp.lines[2].pageLock = "1"
    ed.sp.paginate()

    assert ed.sp.getPageNumbers()[:3] == ["A1", "1", "2"]
    assert firstText(ed, "1") == ed.sp.lines[2].text


def testHeaderShowsLabel():
    ed = makeScript()
    ed.sp.headers.addDefaults()
    ed.sp.paginate()
    ed.lockPages()

    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()

    doc = render.generatePML(ed.sp)
    texts = [
        " ".join(op.text for op in pg.ops if hasattr(op, "text"))
        for pg in doc.pages
    ]

    p = ed.sp.label2page("2A")
    assert "2A." in texts[p - 1]


def testLabel2Page():
    ed = makeLocked()

    start, end = ed.sp.page2lines(2)
    ed.gotoPos((start + end) // 2, 0)
    ed.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    ed.sp.paginate()

    assert ed.sp.label2page("2a") == 3
    assert ed.sp.label2page(" 2A ") == 3
    assert ed.sp.label2page("nope") == -1
    assert ed.sp.line2pageLabel(ed.sp.page2lines(3)[0]) == "2A"
