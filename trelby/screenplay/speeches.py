# who speaks where: the speeches in a script, for the reports.
#
# a speech is a run of consecutive dialogue and parenthetical lines. its
# speaker is the character element right before it, if there is one; a
# run with anything else (or nothing) before it has no speaker.

from dataclasses import dataclass, field
from typing import Iterator, List, Optional

import trelby.textutil as textutil
from trelby.screenplay.constants import CHARACTER, DIALOGUE, PAREN, SCENE


@dataclass
class Speech:
    # the speaker, upper cased: the last line of the character element,
    # or None if the speech has no character element before it. it can be
    # empty or blank, if the character element is.
    name: Optional[str]

    # the first line of the character element, or None
    charLine: Optional[int]

    # the first and last line of the dialogue and parentheticals
    start: int
    end: int

    # the dialogue lines and the parenthetical lines, in order
    dialogue: List[int] = field(default_factory=list)
    parens: List[int] = field(default_factory=list)

    # the first line of the last scene heading before the speech, or None
    # if there is none. act breaks don't end a scene here.
    scene: Optional[int] = None


# yield a Speech for each speech in sp, in order
def iterSpeeches(sp) -> Iterator[Speech]:
    ls = sp.lines
    scene = None
    i = 0

    while i < len(ls):
        lt = ls[i].lt

        if lt not in (DIALOGUE, PAREN):
            if (lt == SCENE) and sp.isFirstLineOfElem(i):
                scene = i

            i += 1

            continue

        speech = Speech(None, None, i, i, scene=scene)

        if (i > 0) and (ls[i - 1].lt == CHARACTER):
            speech.name = textutil.upper(ls[i - 1].text)
            speech.charLine = sp.getElemFirstIndexFromLine(i - 1)

        while (i < len(ls)) and (ls[i].lt in (DIALOGUE, PAREN)):
            if ls[i].lt == DIALOGUE:
                speech.dialogue.append(i)
            else:
                speech.parens.append(i)

            i += 1

        speech.end = i - 1

        yield speech


# return the text of the scene heading starting at line 'scene' (a
# Speech's scene), upper cased. like the reports, this is the heading's
# last line.
def sceneName(sp, scene: int) -> str:
    return textutil.upper(sp.lines[sp.getElemLastIndexFromLine(scene)].text)
