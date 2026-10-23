# lays the script out as pml pages: what's printed on each page (script
# lines, headers, the footer, CONTINUED / (MORE) / (cont'd), scene
# numbers, revision marks), and where. used for PDF export and by the editor's
# page view modes. the page breaks themselves are decided by pagination.

import trelby.pdf.mypager as mypager
import trelby.pdf.pml as pml
import trelby.screenplay.headers as headers
import trelby.screenplay.revisions as revisions
import trelby.textutil as textutil
import trelby.util as util
from trelby.screenplay.constants import (
    ACTBREAK,
    SCENE,
)


# Same as generatePDF, but returns a PML document. if revisedOnly is
# True, it has only the pages with text marked with the current revision
# (see Screenplay.isPageRevised), and no title pages.
def generatePML(sp, revisedOnly=False) -> pml.Document:
    pager = mypager.Pager(sp.cfg)

    if not revisedOnly:
        sp.titles.generatePages(pager.doc)

    pager.doc.showTOC = sp.cfg.pdfShowTOC

    # every page is generated, since each one carries things over to the
    # next (see mypager)
    for i in range(1, len(sp.pages)):
        pg = generatePMLPage(sp, pager, i, True, True)

        if not pg:
            break

        if not revisedOnly or sp.isPageRevised(i):
            pager.doc.add(pg)

    for pfi in sp.cfg.getPDFFontIds():
        pf = sp.cfg.getPDFFont(pfi)

        if pf.pdfName and pf.filename != "":
            pager.doc.addFont(pf.style, pml.PDFFontInfo(pf.pdfName, pf.filename))

    return pager.doc


# generate one page of PML data and return it.
#
# if forPDF is True, output is meant for PDF generation.
#
# if doExtra is False, omits headers and other stuff that is
# automatically added, i.e. outputs only actual screenplay lines. also
# text style/capitalization is not done 100% correctly. this should
# only be True for callers that do not show the results in any way,
# just calculate things based on text positions.
#
# can also return None, which means pagination is not up-to-date and
# the given page number doesn't point to a valid page anymore, and the
# caller should stop calling this since all pages have been generated
# (assuming 1-to-n calling sequence).
def generatePMLPage(sp, pager, pageNr, forPDF, doExtra):
    # lsdjflksj = util.TimerDev("generatePMLPage")

    cfg = sp.cfg
    ls = sp.lines

    fs = cfg.fontSize
    chX = util.getTextWidth(" ", pml.COURIER, fs)
    chY = util.getTextHeight(fs)
    cw = cfg.getCharWidth()
    length = len(ls)

    start = sp.pages[pageNr - 1] + 1

    if start >= length:
        # text has been deleted at end of script and pagination has
        # not been updated.
        return None

    # pagination may not be up-to-date, so any overflow text gets
    # dumped onto the last page which may thus be arbitrarily long.
    if pageNr == (len(sp.pages) - 1):
        end = length - 1
    else:
        # another side-effect is that if text is deleted at the end,
        # sp.pages can point to lines that no longer exist, so we
        # need to clamp it.
        end = util.clamp(sp.pages[pageNr], maxVal=length - 1)

    pg = pml.Page(pager.doc)

    # what line we're on, counted from first line after top
    # margin, units = line / 10
    y = 0

    # the footer is in the bottom margin, so it doesn't move anything.
    # it goes before the script lines, since the page views take the last
    # text on a page as the bottom of the script's lines.
    if doExtra:
        pvars = headers.pageVars(sp, pageNr)

        if sp.footer.isOnPage(pageNr):
            sp.footer.generatePML(pg, pvars, cfg)

        # the page's revision, above where the header starts, unless the
        # headers show it themselves
        if pvars["REVISION"] and sp.revisions.showInHeader and not any(
            "${REVISION}" in h.text for h in sp.headers.hdrs
        ):
            pg.add(
                pml.TextOp(
                    pvars["REVISION"],
                    cfg.paperWidth - cfg.marginRight,
                    max(cfg.marginTop - chY, 0),
                    fs,
                    align=util.ALIGN_RIGHT,
                )
            )

    # the y positions (in tenths of a line) of the revision marks added,
    # so that the two columns of a dual dialogue don't get one each
    marksAt = set()

    # the first page has no header and never continues anything. on
    # the others, the header, a "CONTINUED:" plus a blank line when the
    # page starts mid-scene, and "NAME (cont'd)" when it starts
    # mid-speech take the room paginateRange reserved for them. pager
    # carries the scene number and CONTINUED count over from the
    # previous pages, so pages must be generated in order, 1 to n.
    if pageNr != 1:
        if doExtra:
            sp.headers.generatePML(pg, pvars, cfg)
        y += sp.headers.getNrOfLines() * 10

    # a two-column script's column headings, on every page
    if sp.getColumnHeadingsHeight():
        if doExtra:
            for text, indent in sp.getColumnHeadings():
                pg.add(
                    pml.TextOp(
                        text,
                        cfg.marginLeft + indent * chX,
                        cfg.marginTop + (y / 10.0) * chY,
                        fs,
                        pml.BOLD | pml.UNDERLINED,
                        charWidth=cw,
                    )
                )

        y += sp.getColumnHeadingsHeight()

    if pageNr != 1:
        if cfg.sceneContinueds and not sp.isFirstLineOfScene(start):
            if doExtra:
                s = cfg.strContinuedPageStart
                if pager.sceneContNr != 0:
                    s += " (%d)" % (pager.sceneContNr + 1)

                pg.add(
                    pml.TextOp(
                        s,
                        cfg.marginLeft + pager.sceneIndent * chX,
                        cfg.marginTop + (y / 10.0) * chY,
                        fs,
                        charWidth=cw,
                    )
                )

                pager.sceneContNr += 1

                if cfg.pdfShowSceneNumbers:
                    addSceneNumbers(sp, pg,
                        pager.scene,
                        cfg.getType(SCENE).width,
                        y,
                        chX,
                        chY,
                    )

            y += 20

        if sp.needsMore(start - 1):
            if doExtra:
                pg.add(
                    pml.TextOp(
                        sp.getPrevSpeaker(start) + cfg.strDialogueContinued,
                        cfg.marginLeft + pager.charIndent * chX,
                        cfg.marginTop + (y / 10.0) * chY,
                        fs,
                        charWidth=cw,
                    )
                )

            y += 10

    # dual dialogues: the right-hand speech goes back up to where the
    # left one started, and what follows goes below the longer one
    dualLines = sp.getDualLines(start, end)
    dualTop = dualLeftBottom = 0

    # a two-column script's rows are placed by a twocolumn.RowLayout
    layout = sp.makeRowLayout(y)
    cols = sp.getColumns()

    for i in range(start, end + 1):
        line = ls[i]
        tcfg = cfg.getType(line.lt)
        dual = dualLines.get(i)

        if layout:
            y = layout.place(cols[line.lt], sp.getSpacingBefore(i))
        elif dual and (i == dual[2]):
            dualLeftBottom = y
            y = dualTop
        elif i != start:
            y += sp.getSpacingBefore(i)

        if dual and (i == dual[1]):
            dualTop = y

        if dual:
            indent = cfg.getDualIndentWidth(line.lt, dual[0])[0]
        else:
            indent = tcfg.indent

        typ = pml.NORMAL

        if doExtra:
            if forPDF:
                tt = tcfg.export
            else:
                tt = tcfg.screen

            if tt.isCaps:
                text = textutil.upper(line.text)
            else:
                text = line.text

            if tt.isBold:
                typ |= pml.BOLD
            if tt.isItalic:
                typ |= pml.ITALIC
            if tt.isUnderlined:
                typ |= pml.UNDERLINED
        else:
            text = line.text

        extraIndent = 1 if sp.needsExtraParenIndent(i) else 0
        extraIndent += sp.getCenterOffset(i)

        to = pml.TextOp(
            text,
            cfg.marginLeft + (indent + extraIndent) * chX,
            cfg.marginTop + (y / 10.0) * chY,
            fs,
            typ,
            line=i,
            fmt=line.fmt,
            charWidth=cw,
        )

        pg.add(to)

        if doExtra and forPDF and (y not in marksAt) and sp.revisions.isMarked(line):
            marksAt.add(y)
            pg.add(
                pml.TextOp(
                    sp.revisions.markChar,
                    revisions.markX(cfg, chX),
                    cfg.marginTop + (y / 10.0) * chY,
                    fs,
                )
            )

        if doExtra and (tcfg.lt == ACTBREAK) and sp.isFirstLineOfElem(i):
            pager.sceneContNr = 0

        if doExtra and (tcfg.lt == SCENE) and sp.isFirstLineOfElem(i):
            pager.sceneContNr = 0

            if cfg.pdfShowSceneNumbers:
                if pager.sceneNrs is None:
                    pager.sceneNrs = dict(sp.getSceneLabels())

                pager.scene = pager.sceneNrs.get(i, "")
                addSceneNumbers(sp, pg, pager.scene, tcfg.width, y, chX, chY)

            if cfg.pdfIncludeTOC:
                if cfg.pdfShowSceneNumbers:
                    s = "%s %s" % (pager.scene, text)
                else:
                    s = text

                to.toc = pml.TOCItem(s, to)

        # the left column's line numbers are where the right one's
        # would go
        besideLeft = (dual and (dual[0] == 2)) or (layout and layout.inRightRun())

        if doExtra and cfg.pdfShowLineNumbers and not besideLeft:
            pg.add(
                pml.TextOp(
                    "%02d" % (i - start + 1),
                    cfg.marginLeft - 3 * chX,
                    cfg.marginTop + (y / 10.0) * chY,
                    fs,
                )
            )

        y += 10

        if dual and (i == dual[3]):
            y = max(y, dualLeftBottom)

    if sp.needsMore(end):
        if doExtra:
            pg.add(
                pml.TextOp(
                    cfg.strMore,
                    cfg.marginLeft + pager.charIndent * chX,
                    cfg.marginTop + (y / 10.0) * chY,
                    fs,
                    charWidth=cw,
                )
            )

        y += 10

    # (MORE) goes right below the speech, in its column, and the rest
    # below both columns
    if layout:
        y = max(y, layout.bottom())

    if cfg.sceneContinueds and not sp.isLastLineOfScene(end):
        if doExtra:
            pg.add(
                pml.TextOp(
                    cfg.strContinuedPageEnd,
                    cfg.marginLeft + cfg.sceneContinuedIndent * chX,
                    cfg.marginTop + (y / 10.0 + 1.0) * chY,
                    fs,
                    charWidth=cw,
                )
            )

        y += 10

    if forPDF and cfg.pdfShowMargins:
        lx = cfg.marginLeft
        rx = cfg.paperWidth - cfg.marginRight
        uy = cfg.marginTop
        dy = cfg.paperHeight - cfg.marginBottom

        pg.add(pml.LineOp([(lx, uy), (rx, uy), (rx, dy), (lx, dy)], 0, True))

    return pg


# print scene number s on both sides of the scene heading line at y
# (in tenths of a line), as in shooting scripts: in the left margin,
# and one character past the heading's width (in characters).
def addSceneNumbers(sp, pg, s, width, y, chX, chY):
    cfg = sp.cfg

    pg.add(
        pml.TextOp(
            s,
            cfg.marginLeft - 6 * chX,
            cfg.marginTop + (y / 10.0) * chY,
            cfg.fontSize,
        )
    )
    pg.add(
        pml.TextOp(
            s,
            cfg.marginLeft + (width + 1) * chX,
            cfg.marginTop + (y / 10.0) * chY,
            cfg.fontSize,
        )
    )
