# PDF export.

import trelby.pdf.writer as pdf
import trelby.screenplay.render as render


# generate PDF and return it as a string. assumes paginate/reformat is
# 100% correct for the screenplay.
def generatePDF(sp) -> bytes:
    return pdf.generate(render.generatePML(sp))
