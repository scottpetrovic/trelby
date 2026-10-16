# Final Draft XML (.fdx) export.

from lxml import etree

import trelby.textfmt as textfmt
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    NOTE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.export.common import getElementsAsList


# Generate a Final Draft XML file and return as string.
def generateFDX(sp):
    eleList = getElementsAsList(sp)
    fd = etree.Element("FinalDraft")
    fd.set("DocumentType", "Script")
    fd.set("Template", "No")
    fd.set("Version", "1")
    content = etree.SubElement(fd, "Content")

    xmlMap = {
        ACTION: "Action",
        CHARACTER: "Character",
        DIALOGUE: "Dialogue",
        PAREN: "Parenthetical",
        SCENE: "Scene Heading",
        SHOT: "Shot",
        TRANSITION: "Transition",
        NOTE: "Action",
        ACTBREAK: "New Act",
    }

    # where to add paragraphs: 'content', or the DualDialogue element
    # of the dual dialogue we're in, which ends at line dualEnd
    parent = content
    dualEnd = -1

    for typ, txt, first, fmt in eleList:
        if typ == CHARACTER:
            block = sp.getDualBlock(first)

            if block and (block[0] == first):
                general = etree.SubElement(content, "Paragraph")
                general.set("Type", "General")
                parent = etree.SubElement(general, "DualDialogue")
                dualEnd = block[2]

        if typ == NOTE:
            dummyPara = etree.SubElement(content, "Paragraph")
            dummyPara.set("Type", xmlMap[typ])
            scriptnote = etree.SubElement(dummyPara, "ScriptNote")
            scriptnote.set("ID", "1")
            para = etree.SubElement(scriptnote, "Paragraph")
        else:
            para = etree.SubElement(parent, "Paragraph")
            para.set("Type", xmlMap[typ])

            if (typ == ACTION) and sp.hasCenteredFlag(first):
                para.set("Alignment", "Center")

        # a Text element for each run of differently formatted text
        for a, b, style in textfmt.runs(fmt, len(txt)) or [(0, 0, 0)]:
            paratxt = etree.SubElement(para, "Text")
            paratxt.text = str(txt[a:b])

            flags = [
                name
                for bit, name in (
                    (textfmt.BOLD, "Bold"),
                    (textfmt.ITALIC, "Italic"),
                    (textfmt.UNDERLINED, "Underline"),
                )
                if style & bit
            ]

            if flags:
                paratxt.set("Style", "+".join(flags))

        if sp.getElemLastIndexFromLine(first) >= dualEnd:
            parent = content

    # FD does not recognize "New Act" by default. It needs an
    # ElementSettings element added.
    eleSet = etree.SubElement(fd, "ElementSettings")
    eleSet.set("Type", xmlMap[ACTBREAK])
    eleSetFont = etree.SubElement(eleSet, "FontSpec")
    eleSetFont.set("Style", "Underline+AllCaps")
    eleSetPara = etree.SubElement(eleSet, "ParagraphSpec")
    eleSetPara.set("Alignment", "Center")

    return etree.tostring(
        fd, xml_declaration=True, encoding="UTF-8", pretty_print=True
    )
