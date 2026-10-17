# Final Draft XML (.fdx) export.

from lxml import etree

import trelby.textfmt as textfmt
from trelby.screenplay.constants import (
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.export.common import getElemNotes, getElementsAsList


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
        ACTBREAK: "New Act",
    }

    # where to add paragraphs: 'content', or the DualDialogue element
    # of the dual dialogue we're in, which ends at line dualEnd
    parent = content
    dualEnd = -1

    # the last ScriptNote's ID
    noteId = 0

    for typ, txt, first, fmt in eleList:
        if typ == CHARACTER:
            block = sp.getDualBlock(first)

            if block and (block[0] == first):
                general = etree.SubElement(content, "Paragraph")
                general.set("Type", "General")
                parent = etree.SubElement(general, "DualDialogue")
                dualEnd = block[2]

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

        # the element's notes, as script notes in its paragraph
        for note in getElemNotes(sp, first):
            noteId += 1
            scriptnote = etree.SubElement(para, "ScriptNote")
            scriptnote.set("ID", str(noteId))
            notePara = etree.SubElement(scriptnote, "Paragraph")
            etree.SubElement(notePara, "Text").text = note.text

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
