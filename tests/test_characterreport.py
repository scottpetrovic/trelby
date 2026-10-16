import tests.u as u
import trelby.reports.characterreport as characterreport
import trelby.textutil as textutil
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests character report (just that it runs without exceptions, for now)


def testBasic():
    sp = u.load()
    report = characterreport.CharacterReport(sp)
    data = report.generate()

    # try to catch cases where generate returns something other than a PDF
    # document
    assert len(data) > 200
    assert data[:8] == textutil.toLatin1("%PDF-1.5")


def testHtml():
    sp = u.load()
    report = characterreport.CharacterReport(sp)
    html = report.generateHtml()

    assert report.cinfo[0].name in html

    # nothing to show when no characters are included
    for ci in report.cinfo:
        ci.include = False

    assert report.generateHtml() == ""


def testOptions():
    sp = u.load()
    report = characterreport.CharacterReport(sp)

    assert report.opts == {"basic": True, "pages": True, "locations": True}
    assert "Pages: " in report.generateHtml()

    report.opts["pages"] = False
    assert "Pages: " not in report.generateHtml()
