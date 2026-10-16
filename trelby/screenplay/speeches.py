# who speaks where: the speeches in a script. the reports, the dialogue
# chart and the MCP tools all count characters and speeches from here, so
# that they agree:
#
#  - a speech is a character element followed by dialogue and
#    parenthetical lines, at least one of them dialogue.
#  - the speaker is the character element's whole text, normalized like
#    the character profiles' names: upper cased, without an extension
#    like "(V.O.)", so "Bob (V.O.)" and "BOB" are the same character.
#  - dialogue with no character element before it, or one whose name is
#    empty, has no speaker, and isn't counted anywhere. (the script
#    checker reports both.)
#  - only dialogue lines are counted as spoken lines; parentheticals
#    aren't.
#  - a speech's scene is the part of the script it's in, as in the scene
#    outline: parts start at scene headings and act breaks.

from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import trelby.screenplay.characterprofiles as characterprofiles
import trelby.config as config
import trelby.textutil as textutil
from trelby.screenplay.constants import (
    ACTBREAK,
    CHARACTER,
    DIALOGUE,
    LB_LAST,
    PAREN,
    SCENE,
)


@dataclass
class Speech:
    # the speaker's name, never empty
    name: str

    # the first line of the character element
    charLine: int

    # the first and last line of the dialogue and parentheticals
    start: int
    end: int

    # the dialogue lines and the parenthetical lines, in order
    dialogue: List[int] = field(default_factory=list)
    parens: List[int] = field(default_factory=list)

    # the first line of the scene heading or act break the speech's scene
    # starts with, or None if it's before the first of them
    scene: Optional[int] = None


# yield a Speech for each speech in sp, in order
def iterSpeeches(sp) -> Iterator[Speech]:
    ls = sp.lines
    scene = None
    i = 0

    while i < len(ls):
        lt = ls[i].lt

        if lt not in (DIALOGUE, PAREN):
            if (lt in (SCENE, ACTBREAK)) and sp.isFirstLineOfElem(i):
                scene = i

            i += 1

            continue

        start = i
        dialogue = []
        parens = []

        while (i < len(ls)) and (ls[i].lt in (DIALOGUE, PAREN)):
            if ls[i].lt == DIALOGUE:
                dialogue.append(i)
            else:
                parens.append(i)

            i += 1

        if not dialogue or (start == 0) or (ls[start - 1].lt != CHARACTER):
            continue

        charLine = sp.getElemFirstIndexFromLine(start - 1)
        name = speakerName(sp, charLine)

        if name:
            yield Speech(name, charLine, start, i - 1, dialogue, parens, scene)


# return the normalized name (see above) in the character element starting
# at line 'line', or "" if there's none
def speakerName(sp, line: int) -> str:
    ls = sp.lines
    s = ""

    while 1:
        s += ls[line].text

        if (ls[line].lb == LB_LAST) or (line + 1 >= len(ls)):
            break

        s += config.lb2str(ls[line].lb)
        line += 1

    return characterprofiles.normalizeName(s)


# return the name of the scene starting at line 'scene' (a Speech's
# scene): its heading's last line upper cased, like sp.getSceneNames()
# and the locations, "(EMPTY SCENE NAME)" if that's blank, or "(NO SCENE
# NAME)" for the part before the first heading or one starting at an act
# break.
def sceneName(sp, scene: Optional[int]) -> str:
    if (scene is None) or (sp.lines[scene].lt != SCENE):
        return "(NO SCENE NAME)"

    s = textutil.upper(sp.lines[sp.getElemLastIndexFromLine(scene)].text)

    if not s.strip():
        return "(EMPTY SCENE NAME)"

    return s
