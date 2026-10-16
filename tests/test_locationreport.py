import tests.u as u
import trelby.reports.locationreport as locationreport
import trelby.reports.scenereport as scenereport
import trelby.textutil as textutil
import trelby.translations as translations

_ = translations.trelby_translations_load()

# tests location report (just that it runs without exceptions, for now)


def testBasic():
    sp = u.load()
    report = locationreport.LocationReport(scenereport.SceneReport(sp))
    data = report.generate()

    # try to catch cases where generate returns something other than a PDF
    # document
    assert len(data) > 200
    assert data[:8] == textutil.toLatin1("%PDF-1.5")


def testHtml():
    sp = u.load()
    report = locationreport.LocationReport(scenereport.SceneReport(sp))
    html = report.generateHtml()

    assert html.startswith("<tt>")
    assert "Lines: " in html


def testOptions():
    sp = u.load()
    report = locationreport.LocationReport(scenereport.SceneReport(sp))

    assert [label() for name, label in report.options] == ["Speakers"]
    assert "FISHERMAN" in report.generateHtml()

    report.opts["speakers"] = False
    assert "FISHERMAN" not in report.generateHtml()
