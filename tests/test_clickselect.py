import tests.u as u

# tests word and element selection used by double/triple clicks


def selected(sp):
    cd = sp.getSelectedAsCD(False)

    return [ln.text for ln in cd.lines]


def testSelectWordMiddle():
    sp = u.new()
    sp.lines[0].text = "Hello there, world"
    sp.selectWordAt(0, 8)
    assert selected(sp) == ["there"]
    assert (sp.mark.column == 6) and (sp.column == 10)


def testSelectWordEdges():
    sp = u.new()
    sp.lines[0].text = "Hello world"
    sp.selectWordAt(0, 0)
    assert selected(sp) == ["Hello"]
    sp.selectWordAt(0, 10)
    assert selected(sp) == ["world"]

    # past the end of the line picks the last word
    sp.selectWordAt(0, 11)
    assert selected(sp) == ["world"]


def testSelectWordApostrophe():
    sp = u.new()
    sp.lines[0].text = "I don't know"
    sp.selectWordAt(0, 4)
    assert selected(sp) == ["don't"]


def testSelectWordSingleChar():
    sp = u.new()
    sp.lines[0].text = "I am"
    sp.selectWordAt(0, 0)
    assert selected(sp) == ["I"]


def testSelectWhitespaceAndPunctuation():
    sp = u.new()
    sp.lines[0].text = "Wait...   what"
    sp.selectWordAt(0, 5)
    assert selected(sp) == ["..."]
    sp.selectWordAt(0, 8)
    assert selected(sp) == ["   "]


def testSelectWordEmptyLine():
    sp = u.new()
    sp.lines[0].text = ""
    sp.selectWordAt(0, 0)
    assert sp.mark is None


def testSelectElement():
    sp = u.load()

    # line 2 is in the middle of a multi-line action element
    first, last = sp.getElemIndexesFromLine(2)
    assert first < last

    sp.selectElementAt(2)
    assert (sp.mark.line == first) and (sp.mark.column == 0)
    assert sp.line == last
    assert selected(sp) == [sp.lines[i].text for i in range(first, last + 1)]
