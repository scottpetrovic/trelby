from unittest import mock

import tests.u as u
import trelby.myimport as myimport
import trelby.titles as titles
import trelby.translations as translations

_ = translations.trelby_translations_load()


# import 'text' as a Fountain file with the default options (title page
# lines go to the title page) and return (lines, title pages)
def importFountain(tmp_path, text):
    u.init()
    path = tmp_path / "script.fountain"
    path.write_bytes(text.encode("UTF-8"))

    t = titles.Titles()
    t.addDefaults()

    dlg = mock.Mock()
    dlg.ShowModal.return_value = myimport.wx.ID_OK

    with mock.patch.object(myimport.checkboxdlg, "CheckBoxDlg", return_value=dlg):
        return myimport.importFountain(str(path), mock.Mock(), t.pages)


def titleTexts(titlePages):
    return [ts.items for ts in titlePages[0]]


# a title page that runs to the end of the file used to raise IndexError
def testTitlePageAtEndOfFile(tmp_path):
    lines, titlePages = importFountain(tmp_path, "Title: My Script\nAuthor: Me")

    assert titleTexts(titlePages)[0] == ["My Script"]
    assert titleTexts(titlePages)[1] == ["by", "", "Me"]


def testIndentedTitleValueAtEndOfFile(tmp_path):
    lines, titlePages = importFountain(
        tmp_path, "Title: My Script\nContact:\n    Jane Doe\n    555-1234"
    )

    assert titleTexts(titlePages)[2] == ["Jane Doe", "555-1234"]


def testTitlePageThenScript(tmp_path):
    lines, titlePages = importFountain(
        tmp_path, "Title:\n    My Script\n\nINT. HOUSE - DAY\n\nHello.\n"
    )

    assert titleTexts(titlePages)[0] == ["My Script"]
    assert "INT. HOUSE - DAY" in [ln.text for ln in lines]


# keys must start with a letter; "[A-za-z]" used to accept "_" and others
def testTitleKeyMustStartWithLetter(tmp_path):
    lines, titlePages = importFountain(
        tmp_path, "Title: My Script\n_Note: hi\nDraft: 2\n\nHello.\n"
    )

    items = [it for ts in titlePages[0] for it in ts.items]
    assert "Draft: 2" in items
    assert not any("_Note" in it for it in items)
    assert any("_Note: hi" in ln.text for ln in lines)


# decomposed accents are composed, as in the other importers
def testCombiningAccentsAreComposed(tmp_path):
    lines, titlePages = importFountain(tmp_path, "Café au lait.\n")

    assert "Caf\xe9 au lait." in [ln.text for ln in lines]
