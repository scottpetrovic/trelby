import tests.u as u
import trelby.pagelock as pagelock
import trelby.screenplay as scr
import trelby.screenplay.render as render
import trelby.translations as translations
from trelby.line import Line

_ = translations.trelby_translations_load()

# tests for page locking: trelby.pagelock and the Screenplay functions
# using it


# return a script with 'scenes' scenes, each with a heading, 'actions'
# action elements and a note, paginated
def makeScript(scenes=8, actions=12):
    lines = ["#Version 3", "#Start-Script "]

    for s in range(scenes):
        lines.append(".\\INT. ROOM %d - DAY" % (s + 1))

        for a in range(actions):
            lines.append("..Scene %d, action %d." % (s + 1, a + 1))

        lines.append(".%%Note for scene %d." % (s + 1))

    sp = u.loadString("\n".join(lines))
    sp.paginate()

    return sp


# return a locked script
def makeLocked(**kwargs):
    sp = makeScript(**kwargs)
    sp.lockPages()

    return sp


# return text of the first line of the page with the given label
def firstText(sp, label):
    p = sp.label2page(label)
    assert p != -1

    return sp.lines[sp.page2lines(p)[0]].text


# return {label: text of first line of that page} for all pages
def pageStarts(sp):
    return {label: firstText(sp, label) for label in sp.getPageNumbers()}


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
    sp = makeScript()
    pageCnt = len(sp.pages) - 1

    assert pageCnt > 3
    assert sp.getPageNumbers() == [str(p) for p in range(1, pageCnt + 1)]
    assert not sp.hasPageLocks()


def testLockKeepsPagination():
    sp = makeScript()
    pages = list(sp.pages)
    labels = list(sp.pageLabels)

    sp.lockPages()

    assert sp.hasPageLocks()
    assert sp.pages == pages
    assert sp.pageLabels == labels
    assert [ln.pageLock for ln in sp.lines if ln.pageLock] == labels[1:]


def testAddTextCreatesAPages():
    sp = makeLocked()
    starts = pageStarts(sp)
    pageCnt = len(sp.pages) - 1

    # add a lot of text in the middle of page 2
    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()
    sp._validate()

    labels = sp.getPageNumbers()
    assert labels[:4] == ["1", "2", "2A", "2B"]
    assert labels[4:] == [str(p) for p in range(3, pageCnt + 1)]

    # all the original pages still start with the same text
    for label, text in starts.items():
        assert firstText(sp, label) == text


def testAddTextAtEnd():
    sp = makeLocked()
    labels = sp.getPageNumbers()

    sp.gotoPos(len(sp.lines) - 1, len(sp.lines[-1].text))
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(80)])
    sp.paginate()

    newLabels = sp.getPageNumbers()
    added = len(newLabels) - len(labels)

    assert added >= 2
    assert newLabels[: len(labels)] == labels
    assert newLabels[len(labels) :] == [labels[-1] + c for c in "ABCDEF"[:added]]


def testDeleteTextLeavesGap():
    sp = makeLocked()
    starts = pageStarts(sp)
    labels = sp.getPageNumbers()
    start, end = sp.page2lines(2)

    # delete the middle of page 2
    sp.setMark(start + 4, 0)
    sp.gotoPos(end - 4, 0)
    sp.getSelectedAsCD(True)
    sp.paginate()
    sp._validate()

    assert sp.getPageNumbers() == labels
    assert pageStarts(sp) == starts

    newStart, newEnd = sp.page2lines(2)
    assert newStart == start
    assert newEnd < end


def testDeleteFirstLineOfPage():
    sp = makeLocked()
    labels = sp.getPageNumbers()
    start, end = sp.page2lines(3)
    second = sp.lines[start + 1].text

    # delete the first element on page 3; page 3 now starts with what was
    # its second line
    assert sp.lines[start].lb == scr.LB_LAST

    sp.setMark(start, 0)
    sp.gotoPos(start, len(sp.lines[start].text) - 1)
    sp.getSelectedAsCD(True)
    sp.paginate()
    sp._validate()

    assert sp.getPageNumbers() == labels
    assert firstText(sp, "3") == second


def testDeleteWholePageCombines():
    sp = makeLocked()
    start, end = sp.page2lines(2)
    page3 = firstText(sp, "3")

    sp.setMark(start, 0)
    sp.gotoPos(end, len(sp.lines[end].text))
    sp.getSelectedAsCD(True)
    sp.paginate()
    sp._validate()

    labels = sp.getPageNumbers()
    assert labels[:3] == ["1", "2-3", "4"]
    assert firstText(sp, "2-3") == page3


def testTypingKeepsLock():
    sp = makeLocked()
    start = sp.page2lines(3)[0]

    sp.gotoPos(start, 0)

    for ch in "Inserted text that is long enough to wrap to more lines. " * 3:
        sp.cmd("addChar", char=ch)

    sp.paginate()
    sp._validate()

    assert sp.lines[start].pageLock == "3"
    assert firstText(sp, "3").startswith("Inserted")


def testRewrapMovesLock():
    sp = makeScript()

    # lock a page to start in the middle of a multi-line element
    sp.gotoPos(1, len(sp.lines[1].text))
    for ch in " more words" * 20:
        sp.cmd("addChar", char=ch)

    assert sp.lines[2].lb != scr.LB_LAST
    text = sp.lines[2].text
    sp.lines[2].pageLock = "2"

    # make the element's first line shorter, which moves text from the
    # line with the lock up
    sp.gotoPos(1, 0)
    for i in range(10):
        sp.cmd("deleteForward")

    lockLines = [i for i, ln in enumerate(sp.lines) if ln.pageLock]
    assert len(lockLines) == 1

    # the lock is on the line now containing the start of the old text
    ln = sp.lines[lockLines[0]]
    nextLn = sp.lines[lockLines[0] + 1]
    assert text.split()[0] in ln.text + " " + nextLn.text


def testJoinWithPrevElement():
    sp = makeLocked()
    start = sp.page2lines(3)[0]
    text = sp.lines[start].text

    # page 3 starts with an action; joining it with the previous element
    # keeps page 3 starting at the line containing its text
    assert sp.lines[start].lt == scr.ACTION
    assert sp.lines[start - 1].lt == scr.ACTION

    sp.gotoPos(start, 0)
    sp.cmd("deleteBackward")
    sp.paginate()
    sp._validate()

    assert text.split()[0] in firstText(sp, "3")
    assert sp.getPageNumbers()[:3] == ["1", "2", "3"]


def testUndoRedo():
    sp = makeLocked()
    pages = list(sp.pages)
    labels = list(sp.pageLabels)

    start, end = sp.page2lines(2)
    sp.setMark(start, 0)
    sp.gotoPos(end, len(sp.lines[end].text))
    sp.getSelectedAsCD(True)
    sp.paginate()
    assert sp.pageLabels != labels

    sp.cmd("undo")
    sp.paginate()
    assert sp.pages == pages
    assert sp.pageLabels == labels

    sp.cmd("redo")
    sp.paginate()
    assert sp.getPageNumbers()[1] == "2-3"


def testUndoLock():
    sp = makeScript()
    sp.lockPages()
    sp.cmd("undo")

    assert not sp.hasPageLocks()

    sp.cmd("redo")

    assert sp.hasPageLocks()


def testUnlock():
    sp = makeLocked()

    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()
    assert "2A" in sp.getPageNumbers()

    sp.unlockPages()

    assert not sp.hasPageLocks()
    pageCnt = len(sp.pages) - 1
    assert sp.getPageNumbers() == [str(p) for p in range(1, pageCnt + 1)]


def testRelockLocksAPages():
    sp = makeLocked()

    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()

    labels = sp.getPageNumbers()
    sp.lockPages()

    assert sp.getPageNumbers() == labels
    assert sum(1 for ln in sp.lines if ln.pageLock) == len(labels)


def testSaveLoad():
    sp = makeLocked()

    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()

    data = sp.save().decode("UTF-8")
    assert "#Page-Lock 2\n" in data

    sp2 = u.loadString(data)

    assert sp2.pages == sp.pages
    assert sp2.getPageNumbers() == sp.getPageNumbers()
    assert [ln.pageLock for ln in sp2.lines] == [ln.pageLock for ln in sp.lines]


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
    sp = makeLocked()
    start, end = sp.page2lines(2)

    sp.setMark(start, 0)
    sp.gotoPos(end, 0)
    cd = sp.getSelectedAsCD(False)

    assert not any(ln.pageLock for ln in cd.lines)


def testDeepcopyKeepsLocks():
    import copy

    sp = makeLocked()
    sp2 = copy.deepcopy(sp)

    assert [ln.pageLock for ln in sp2.lines] == [ln.pageLock for ln in sp.lines]


def testRemoveNotesKeepsLocks():
    sp = makeScript()

    # a page starting with a note starts with the line after it once
    # notes are removed (as is done when printing without notes)
    note = [i for i, ln in enumerate(sp.lines) if ln.lt == scr.NOTE][2]
    nextText = sp.lines[note + 1].text

    sp.lines[0].pageLock = "1"
    sp.lines[note].pageLock = "2"

    sp.removeElementTypes({scr.NOTE: None}, False)
    sp.paginate()

    assert "2" in sp.getPageNumbers()
    assert firstText(sp, "2") == nextText


def testMoveSceneLeavesLocks():
    sp = makeLocked()
    starts = sp.getOutlineStarts()

    # find a scene (not the last one) containing a page start
    for idx in range(1, len(starts) - 1):
        moved = sp.lines[starts[idx] : starts[idx + 1]]
        movedLocks = [ln.pageLock for ln in moved if ln.pageLock]

        if movedLocks:
            break

    following = sp.lines[starts[idx + 1]]
    expected = movedLocks[0]

    for label in movedLocks[1:] + [following.pageLock]:
        if label:
            expected = pagelock.combine(expected, label)

    # move it to the end. its pages stay where they were, now starting
    # with the scene that followed it.
    sp.moveSceneTo(starts[idx], len(starts) - 1)
    sp.paginate()
    sp._validate()

    assert following.pageLock == expected
    assert not any(ln.pageLock for ln in moved)

    allLocks = [(i, ln.pageLock) for i, ln in enumerate(sp.lines) if ln.pageLock]
    assert sp.getPageLocks() == allLocks


def testOutOfOrderLocksIgnored():
    sp = makeLocked(scenes=20)
    labels = sp.getPageNumbers()
    start = sp.page2lines(2)[0]

    assert len(labels) > 6

    # a stray lock for a later page in the middle of page 2
    sp.lines[start + 3].pageLock = "5"
    sp.paginate()

    assert sp.getPageNumbers() == labels


def testLinesBeforeFirstLock():
    sp = makeLocked()

    # put text before page 1
    sp.lines[0].pageLock = None
    sp.lines[2].pageLock = "1"
    sp.paginate()

    assert sp.getPageNumbers()[:3] == ["A1", "1", "2"]
    assert firstText(sp, "1") == sp.lines[2].text


def testHeaderShowsLabel():
    sp = makeScript()
    sp.headers.addDefaults()
    sp.paginate()
    sp.lockPages()

    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()

    doc = render.generatePML(sp)
    texts = [
        " ".join(op.text for op in pg.ops if hasattr(op, "text"))
        for pg in doc.pages
    ]

    p = sp.label2page("2A")
    assert "2A." in texts[p - 1]


def testLabel2Page():
    sp = makeLocked()

    start, end = sp.page2lines(2)
    sp.gotoPos((start + end) // 2, 0)
    sp.paste([Line(scr.LB_LAST, scr.ACTION, "New action %d." % i) for i in range(40)])
    sp.paginate()

    assert sp.label2page("2a") == 3
    assert sp.label2page(" 2A ") == 3
    assert sp.label2page("nope") == -1
    assert sp.line2pageLabel(sp.page2lines(3)[0]) == "2A"
