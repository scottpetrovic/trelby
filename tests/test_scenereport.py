import tests.u as u
import trelby.scenereport as scenereport
import trelby.textutil as textutil

# tests scene report (just that it runs without exceptions, for now)


def testBasic():
    sp = u.load()
    report = scenereport.SceneReport(sp)
    data = report.generate()

    # try to catch cases where generate returns something other than a PDF
    # document
    assert len(data) > 200
    assert data[:8] == textutil.toLatin1("%PDF-1.5")


def testHtml():
    sp = u.load()
    report = scenereport.SceneReport(sp)
    html = report.generateHtml()

    assert html.startswith("<tt>")
    assert "<b>" in html
