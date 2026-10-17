import copy

import pytest
import wx

import tests.u as u
import trelby.pdf.mypager as mypager
import trelby.pdf.pml as pml
import trelby.screenplay.headers as headers
import trelby.screenplay.render as render
import trelby.screenplay.titles as titles
import trelby.translations as translations
import trelby.util as util

# the page footer (headers.Footer) and the variables headers and footers
# can contain

translations.trelby_translations_load()
u.init()


def makeTitles(*strings):
    tp = titles.Titles()
    tp.pages.append(
        [
            titles.TitleString(items, y=i * 10.0, kind=kind)
            for i, (kind, items) in enumerate(strings)
        ]
    )

    return tp


# return the footer's texts on page 'pageNr' of 'sp', left to right
def footerTexts(sp, pageNr):
    doc = render.generatePML(sp)
    pg = doc.pages[len(sp.titles.pages) + pageNr - 1]
    y = headers.Footer.getY(sp.cfg)
    ops = [op for op in pg.ops if (op.line == -1) and (op.y == y)]

    return [op.text for op in sorted(ops, key=lambda op: op.x)]


def loadWithFooter(**kw):
    sp = u.load()
    sp.paginate()

    for k, v in kw.items():
        setattr(sp.footer, k, v)

    return sp


def testJoinItems():
    assert headers.joinItems(["Jane Doe", "", "John Smith"]) == "Jane Doe, John Smith"
    assert headers.joinItems(["Jane Doe", "&", "John Smith"]) == "Jane Doe & John Smith"
    assert headers.joinItems(["Jane", "and", "John"]) == "Jane and John"
    assert headers.joinItems(["THE LONG", "TITLE"], " ") == "THE LONG TITLE"
    assert headers.joinItems([" ", ""]) == ""


def testTitleVars():
    tp = makeTitles(
        (titles.TITLE, ["THE BIG", "ONE"]),
        (titles.BYLINE, ["Written by", "", "Jane Doe", "&", "John Smith"]),
        (titles.DRAFT, ["Second Draft", "May 3, 2026"]),
    )

    assert headers.titleVars(tp) == {
        "TITLE": "THE BIG ONE",
        "AUTHOR": "Jane Doe & John Smith",
        "DRAFT": "Second Draft, May 3, 2026",
        "DRAFTDATE": "May 3, 2026",
    }


def testAuthorStringBeatsByline():
    tp = makeTitles(
        (titles.BYLINE, ["by"]),
        (titles.AUTHOR, ["Jane Doe"]),
    )

    assert headers.titleVars(tp)["AUTHOR"] == "Jane Doe"


def testDraftDate():
    def date(items):
        return headers.titleVars(makeTitles((titles.DRAFT, items)))["DRAFTDATE"]

    assert date(["Blue Revision 5/3/26"]) == "Blue Revision 5/3/26"
    assert date(["5/3/26", "Blue Revision"]) == "5/3/26"
    assert date(["First Draft", "Month Day, Year"]) == "Month Day, Year"
    assert date(["First Draft"]) == ""


def testTitleVarsMissing():
    assert headers.titleVars(titles.Titles()) == {
        "TITLE": "",
        "AUTHOR": "",
        "DRAFT": "",
        "DRAFTDATE": "",
    }


def testTitleVarsOldStrings():
    # saved before title strings had kinds: they're guessed
    sp = u.load()
    vs = headers.titleVars(sp.titles)

    assert vs["TITLE"] == "THE KOALA INCIDENT"
    assert vs["AUTHOR"] == "Anonymous Person"

    # without changing the strings
    assert all(ts.kind is None for pg in sp.titles.pages for ts in pg)


def testExpand():
    pv = {"PAGE": "2", "TITLE": "X"}

    assert headers.expand("${TITLE} p. ${PAGE}", pv) == "X p. 2"
    assert headers.expand("${NOPE} $PAGE {PAGE}", pv) == "${NOPE} $PAGE {PAGE}"


def testPageVarsUseLabels():
    sp = u.load()
    sp.paginate()
    sp.lines[sp.page2lines(2)[0]].pageLock = "7"
    sp.paginate()

    pv = headers.pageVars(sp, 2)

    assert pv["PAGE"] == "7"
    assert pv["PAGES"] == sp.getPageLabel(len(sp.pages) - 1) != "7"


def testFooterOnPages():
    sp = loadWithFooter(
        left="${TITLE}", center="${AUTHOR}", right="Page ${PAGE} of ${PAGES}"
    )
    pages = str(len(sp.pages) - 1)

    for pageNr in (1, 2):
        assert footerTexts(sp, pageNr) == [
            "THE KOALA INCIDENT",
            "Anonymous Person",
            "Page %d of %s" % (pageNr, pages),
        ]


def testFooterNotOnFirstPage():
    sp = loadWithFooter(center="${PAGE}", showOnFirstPage=False)

    assert footerTexts(sp, 1) == []
    assert footerTexts(sp, 2) == ["2"]


def testEmptyPartsLeftOut():
    sp = loadWithFooter(right="x")

    assert footerTexts(sp, 2) == ["x"]


def testFooterPosition():
    sp = loadWithFooter(left="L", center="C", right="R")
    cfg = sp.cfg

    doc = render.generatePML(sp)
    pg = doc.pages[len(sp.titles.pages) + 1]
    ops = {op.text: op for op in pg.ops if op.text in ("L", "C", "R")}

    # TextOp works out the left edge from the alignment
    w = util.getTextWidth("C", pml.COURIER, cfg.fontSize)
    assert ops["L"].x == cfg.marginLeft
    assert ops["R"].x + w == pytest.approx(cfg.paperWidth - cfg.marginRight)
    assert ops["C"].x + w / 2 == pytest.approx(
        (cfg.marginLeft + cfg.paperWidth - cfg.marginRight) / 2.0
    )

    # centered in the bottom margin, below the script's lines
    chY = util.getTextHeight(cfg.fontSize)
    y = ops["L"].y
    assert y + chY / 2.0 == pytest.approx(cfg.paperHeight - cfg.marginBottom / 2.0)

    bottom = max(op.y for op in pg.ops if op.line != -1) + chY
    assert y >= bottom


def testFooterWithSmallMargin():
    cfg = u.load().cfg
    chY = util.getTextHeight(cfg.fontSize)

    assert headers.Footer.fits(cfg)

    # at the bottom of the page, below the script's lines
    cfg.marginBottom = 1.0
    cfg.recalc()

    assert not headers.Footer.fits(cfg)
    assert headers.Footer.getY(cfg) == pytest.approx(cfg.paperHeight - chY)
    assert headers.Footer.getY(cfg) >= cfg.marginTop + cfg.linesOnPage * chY

    # with no room left on the page, below the script's lines anyway
    cfg.marginBottom = 0.0
    cfg.recalc()
    assert headers.Footer.getY(cfg) == pytest.approx(
        cfg.marginTop + cfg.linesOnPage * chY
    )


def testFooterDoesNotChangePagination():
    sp = u.load()
    sp.paginate()
    pages = list(sp.pages)

    sp.footer.center = "${PAGE}"
    sp.paginate()

    assert sp.pages == pages


def testFooterNotInPageLayout():
    # doExtra=False is used for working out positions
    sp = loadWithFooter(center="FOOTER")

    pg = render.generatePMLPage(sp, mypager.Pager(sp.cfg), 2, False, False)
    assert not [op for op in pg.ops if op.text == "FOOTER"]


def testHeaderVariables():
    sp = u.load()
    sp.paginate()
    h = headers.HeaderString()
    h.text = "${TITLE} - ${PAGE}/${PAGES}"
    sp.headers.hdrs = [h]

    doc = render.generatePML(sp)
    pg = doc.pages[len(sp.titles.pages) + 1]
    pages = str(len(sp.pages) - 1)

    assert "THE KOALA INCIDENT - 2/" + pages in [op.text for op in pg.ops]


def testSaveLoad():
    sp = loadWithFooter(left="${TITLE}, ", center=" ", right="© ${AUTHOR}")
    sp.footer.showOnFirstPage = False

    s = sp.save().decode("UTF-8")
    assert "#Footer-Left ${TITLE}, \n" in s

    sp2 = u.loadString(s)
    assert sp2.footer == sp.footer
    assert sp2.footer.center == " "


def testEmptyFooterNotSaved():
    sp = u.load()
    s = sp.save().decode("UTF-8")

    assert "Footer" not in s
    assert u.loadString(s).footer == headers.Footer()


def testDeepCopy():
    sp = loadWithFooter(center="x")
    sp2 = copy.deepcopy(sp)

    assert sp2.footer == sp.footer
    assert sp2.footer is not sp.footer


@pytest.fixture(scope="module")
def app():
    import trelby.ui.gutil as gutil

    a = wx.App(False)
    gutil.init()
    yield a
    a.Destroy()


def testDialog(app):
    import trelby.dialogs.footerdlg as footerdlg

    sp = u.load()
    sp.paginate()
    applied = []

    dlg = footerdlg.FooterDlg(None, copy.deepcopy(sp.footer), sp, applied.append)

    try:
        dlg.entries[1].SetValue("${PAGE}")
        dlg.entries[2].SetValue("${TITLE}")
        dlg.firstPageCb.SetValue(False)
        dlg.OnMisc()

        assert dlg.footer.left == ""
        assert dlg.footer.center == "${PAGE}"
        assert dlg.footer.right == "${TITLE}"
        assert not dlg.footer.showOnFirstPage

        dlg.OnApply(None)
        assert applied == [dlg.footer]

        # the preview paints
        bmp = wx.Bitmap(600, 300)
        dc = wx.MemoryDC(bmp)
        dlg.previewCtrl.SetSize(600, 300)
        dlg.previewCtrl.draw(dc)
        dc.SelectObject(wx.NullBitmap)
    finally:
        dlg.Destroy()
