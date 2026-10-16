# ut:ignore
# makes tests/fixtures/import/sample.pdf, a PDF laid out the way other
# screenwriting programs make them (Letter paper, Courier 12, scene numbers
# on both sides, bold scene headings, page numbers, CONTINUED, (MORE) and
# (CONT'D), right-aligned transitions, dual dialogue, a title page, a
# watermark and text outside the page), for the PDF importer's tests. run
# from the repo root:
#
#   .venv/Scripts/python -m tests.pdffixture

from reportlab.pdfgen import canvas

import tests.u as u

W, H = 612, 792

# Courier 12's character width and line height
CW = 7.2
LH = 12

# the first line's baseline
TOP = H - 72


class Writer:
    def __init__(self, path):
        self.c = canvas.Canvas(path, pagesize=(W, H), invariant=1)
        self.row = 0

    def y(self):
        return TOP - self.row * LH

    # a line of text at column col, moving down a line
    def line(self, col, s, bold=False):
        self.c.setFont("Courier-Bold" if bold else "Courier", 12)
        self.c.drawString(col * CW, self.y(), s)
        self.row += 1

    def blank(self):
        self.row += 1

    # a transition ending at the right margin
    def right(self, s):
        self.c.setFont("Courier", 12)
        self.c.drawRightString(W - 72, self.y(), s)
        self.row += 1

    # a scene heading with its number on both sides
    def scene(self, num, s):
        self.c.setFont("Courier-Bold", 12)
        self.c.drawString(72 - 3 * CW, self.y(), num)
        self.c.drawString(W - 72 + 2 * CW, self.y(), num)
        self.line(15, s, bold=True)

    # start page n, with its page number
    def page(self, n):
        self.c.showPage()
        self.row = 0
        self.c.setFont("Courier", 12)
        self.c.drawRightString(W - 72, H - 36, "%d." % n)

    def save(self):
        self.c.showPage()
        self.c.save()


def write(path):
    w = Writer(path)
    c = w.c

    # title page
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(W / 2, H - 300, "THE TEST SCRIPT")
    c.setFont("Courier", 12)
    c.drawCentredString(W / 2, H - 336, "Written by")
    c.drawCentredString(W / 2, H - 360, "Some Writer")
    c.drawString(108, 120, "Some Writer")
    c.drawString(108, 108, "writer@example.com")

    w.page(1)
    w.line(15, "FADE IN:")
    w.blank()
    w.scene("1", "INT. KITCHEN - DAY")
    w.blank()
    w.line(15, "Anna stirs a pot. Steam rises and fills the small")
    w.line(15, "room.")
    w.blank()
    w.line(37, "ANNA")
    w.line(31, "(quietly)")
    w.line(25, "It's almost ready. Just a few")
    w.line(25, "more minutes.")
    w.blank()
    w.line(37, "BEN (V.O.)")
    w.line(25, "Good. I'm starving.")
    w.blank()
    w.line(15, "He sits down.")
    w.blank()
    w.right("CUT TO:")
    w.blank()
    w.scene("2", "EXT. GARDEN - NIGHT")
    w.blank()
    w.line(15, "Crickets.")
    w.blank()
    w.line(37, "ANNA")
    w.line(25, "Did you hear that? Something is out")
    w.line(25, "there in the dark, waiting for us")
    w.line(37, "(MORE)")
    c.setFont("Courier", 12)
    c.drawRightString(W - 72, 36, "(CONTINUED)")

    w.page(2)
    c.setFont("Courier", 12)

    # the previous page's last line again, above the top edge where it
    # isn't shown, as Scrite does
    c.drawString(25 * CW, H + 6, "there in the dark, waiting for us")

    # a big diagonal watermark
    c.saveState()
    c.setFont("Courier-Bold", 100)
    c.translate(W / 2, H / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, "DRAFT")
    c.restoreState()

    c.setFont("Courier", 12)
    c.drawString(72 - 3 * CW, w.y(), "2")
    w.line(15, "CONTINUED:")
    w.blank()
    w.line(37, "ANNA (CONT'D)")
    w.line(25, "to make a mistake.")
    w.blank()

    # dual dialogue: two narrower columns side by side
    for left, right in [
        ((28, "BEN"), (51, "ANNA")),
        ((25, "Nothing's there."), (48, "Something's there.")),
        ((25, "Go to sleep."), None),
    ]:
        c.setFont("Courier", 12)
        c.drawString(left[0] * CW, w.y(), left[1])

        if right:
            c.drawString(right[0] * CW, w.y(), right[1])

        w.blank()

    w.blank()
    w.line(15, "They look at each other.")
    w.blank()
    w.right("DISSOLVE TO:")
    w.blank()
    w.scene("3", "INT. KITCHEN - LATER")
    w.blank()
    w.line(15, "The pot is empty.")
    w.blank()
    w.right("FADE OUT.")

    w.save()


if __name__ == "__main__":
    write(u.fixtureFilePath("import/sample.pdf"))
