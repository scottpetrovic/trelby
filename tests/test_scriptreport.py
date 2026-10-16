import tests.u as u
import trelby.scriptreport as scriptreport
import trelby.textutil as textutil
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests script report (just that it runs without exceptions, for now)


def testBasic():
    sp = u.load()
    report = scriptreport.ScriptReport(sp)
    data = report.generate()

    # try to catch cases where generate returns something other than a PDF
    # document
    assert len(data) > 200
    assert data[:8] == textutil.toLatin1("%PDF-1.5")


def testHtml():
    sp = u.load()
    report = scriptreport.ScriptReport(sp)
    html = report.generateHtml()

    # spaces are kept so the columns line up
    assert "&nbsp;&nbsp;" in html
