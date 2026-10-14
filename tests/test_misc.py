import trelby.misc as misc


def testMnemonic():
    m = misc.mnemonic

    assert m("N", "New\tCTRL-N") == "&New\tCTRL-N"
    assert m("O", "Open...") == "&Open..."
    assert m("x", "Exit\tCTRL-Q") == "E&xit\tCTRL-Q"

    # exact case match is preferred over an earlier case-insensitive one
    assert m("t", "Settings") == "Se&ttings"
    assert m("S", "Select scene") == "&Select scene"

    # falls back to a case-insensitive match
    assert m("s", "Save") == "&Save"

    # existing escaped ampersands are left alone
    assert m("R", "Find && Replace") == "Find && &Replace"

    # key not in text (e.g. a translation): appended at the end
    assert m("N", "Nuevo") == "&Nuevo"
    assert m("F", "Datei") == "Datei (&F)"
    assert m("o", "Kopieren\tCTRL-C") == "K&opieren\tCTRL-C"
    assert m("q", "Kopieren\tCTRL-C") == "Kopieren (&Q)\tCTRL-C"
