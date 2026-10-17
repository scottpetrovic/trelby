# PDF export.

import trelby.pdf.writer as pdf
import trelby.screenplay.render as render


# generate PDF and return it as a string. assumes paginate/reformat is
# 100% correct for the screenplay. if revisedOnly is True, only the pages
# revised in the current revision are included (see render.generatePML).
def generatePDF(sp, revisedOnly=False) -> bytes:
    return pdf.generate(render.generatePML(sp, revisedOnly))
