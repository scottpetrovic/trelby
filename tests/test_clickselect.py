import tests.u as u

# tests word and element selection used by double/triple clicks


def selected(ed):
    cd = ed.getSelectedAsCD(False)

    return [ln.text for ln in cd.lines]


def testSelectWordMiddle():
    ed = u.newEditor()
    ed.sp.lines[0].text = "Hello there, world"
    ed.selectWordAt(0, 8)
    assert selected(ed) == ["there"]
    assert (ed.mark.column == 6) and (ed.column == 10)


def testSelectWordEdges():
    ed = u.newEditor()
    ed.sp.lines[0].text = "Hello world"
    ed.selectWordAt(0, 0)
    assert selected(ed) == ["Hello"]
    ed.selectWordAt(0, 10)
    assert selected(ed) == ["world"]

    # past the end of the line picks the last word
    ed.selectWordAt(0, 11)
    assert selected(ed) == ["world"]


def testSelectWordApostrophe():
    ed = u.newEditor()
    ed.sp.lines[0].text = "I don't know"
    ed.selectWordAt(0, 4)
    assert selected(ed) == ["don't"]


def testSelectWordSingleChar():
    ed = u.newEditor()
    ed.sp.lines[0].text = "I am"
    ed.selectWordAt(0, 0)
    assert selected(ed) == ["I"]


def testSelectWhitespaceAndPunctuation():
    ed = u.newEditor()
    ed.sp.lines[0].text = "Wait...   what"
    ed.selectWordAt(0, 5)
    assert selected(ed) == ["..."]
    ed.selectWordAt(0, 8)
    assert selected(ed) == ["   "]


def testSelectWordEmptyLine():
    ed = u.newEditor()
    ed.sp.lines[0].text = ""
    ed.selectWordAt(0, 0)
    assert ed.mark is None


def testSelectElement():
    ed = u.loadEditor()

    # line 2 is in the middle of a multi-line action element
    first, last = ed.sp.getElemIndexesFromLine(2)
    assert first < last

    ed.selectElementAt(2)
    assert (ed.mark.line == first) and (ed.mark.column == 0)
    assert ed.line == last
    assert selected(ed) == [ed.sp.lines[i].text for i in range(first, last + 1)]
