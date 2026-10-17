# beat sheets: templates the outline's add scene button can insert, a
# scene per beat. a beat's scene heading is its name, its description is a
# note on the heading (so the outline shows it as the scene's summary), and
# its color says which act it's in.
#
# the texts are made when asked for (BeatSheet.name / beats), as the
# sheets are defined before the translations are loaded.

from collections import namedtuple

import trelby.textutil as textutil
from trelby.screenplay.constants import LB_LAST, SCENE
from trelby.screenplay.line import Line
from trelby.screenplay.notes import Note

# a beat: its name, what happens in it, and its outline color ("rrggbb")
Beat = namedtuple("Beat", "name description color")

# the colors beats get, from the outline's scene colors
# (outline.getSceneColors)
ACT_ONE = "b8d4ff"  # blue
ACT_TWO = "fff2a8"  # yellow
ACT_THREE = "ffb3b3"  # red
ORDINARY_WORLD = "b8d4ff"  # blue
UNFAMILIAR_WORLD = "dcc4ff"  # purple


class BeatSheet:
    def __init__(self, key, name, beats):
        # id, e.g. "savethecat"
        self.key = key

        # functions returning the name shown in the menu and the list of
        # Beats
        self._name = name
        self._beats = beats

    def name(self):
        return self._name()

    def beats(self):
        return self._beats()

    # return the sheet as Lines: a scene heading per beat
    def lines(self):
        return [
            Line(
                LB_LAST,
                SCENE,
                textutil.upper(b.name),
                color=b.color,
                notes=(Note(b.description),),
            )
            for b in self.beats()
        ]


def saveTheCat():
    return [
        Beat(
            _("Opening Image"),
            _(
                "Page 1. A snapshot of the hero's world before the story "
                "changes it, setting the tone of the film."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Theme Stated"),
            _(
                "Page 5. Someone, usually not the hero, says what the story "
                "is really about: the lesson the hero will have to learn."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Set-Up"),
            _(
                "Pages 1-10. The hero's ordinary life, their flaws and what's "
                "missing from it, and the people who will matter later."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Catalyst"),
            _(
                "Page 12. The event that knocks the hero's world off "
                "balance: a telegram, a death, a chance meeting."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Debate"),
            _(
                "Pages 12-25. The hero doubts, resists or prepares: should "
                "they go? Can they?"
            ),
            ACT_ONE,
        ),
        Beat(
            _("Break into Two"),
            _(
                "Page 25. The hero chooses to act, leaving the old world for "
                "the upside-down world of Act Two."
            ),
            ACT_TWO,
        ),
        Beat(
            _("B Story"),
            _(
                "Page 30. A new relationship, often a love story or mentor, "
                "that carries the theme and helps the hero learn it."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Fun and Games"),
            _(
                "Pages 30-55. The promise of the premise: the scenes the "
                "audience came to see, the hero exploring the new world."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Midpoint"),
            _(
                "Page 55. A false victory or a false defeat. The stakes are "
                "raised and the fun and games are over."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Bad Guys Close In"),
            _(
                "Pages 55-75. The enemies regroup, doubt and jealousy split "
                "the hero's team, and things get steadily worse."
            ),
            ACT_TWO,
        ),
        Beat(
            _("All Is Lost"),
            _(
                "Page 75. The lowest point, the opposite of the midpoint. "
                "Something or someone dies, if only an old way of thinking."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Dark Night of the Soul"),
            _(
                "Pages 75-85. The hero mourns what's lost and hits bottom, "
                "until they find the last idea that will save them."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Break into Three"),
            _(
                "Page 85. The answer, found by bringing the A and B stories "
                "together. The hero chooses to fight."
            ),
            ACT_THREE,
        ),
        Beat(
            _("Finale"),
            _(
                "Pages 85-110. The hero puts the lesson into practice, beats "
                "the bad guys and changes the world for the better."
            ),
            ACT_THREE,
        ),
        Beat(
            _("Final Image"),
            _(
                "Page 110. The opposite of the opening image: proof that "
                "change has happened."
            ),
            ACT_THREE,
        ),
    ]


def threeAct():
    return [
        Beat(
            _("Setup"),
            _(
                "The protagonist, their world and what they want, before "
                "anything goes wrong."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Inciting Incident"),
            _(
                "The event that upsets the protagonist's life and sets the "
                "story in motion."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Plot Point One"),
            _(
                "About a quarter in. The protagonist commits to the goal and "
                "there's no going back. End of Act One."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Rising Action"),
            _(
                "The protagonist pursues the goal against growing "
                "obstacles, allies and enemies take shape."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Midpoint"),
            _(
                "Halfway. A reversal or revelation that raises the stakes "
                "and changes how the protagonist goes after the goal."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Complications"),
            _(
                "Pressure builds from outside and within, and the cost of "
                "failure keeps rising."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Plot Point Two"),
            _(
                "About three quarters in. A crisis or the lowest point that "
                "forces a final decision. End of Act Two."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Climax"),
            _(
                "The protagonist confronts the central conflict head on, "
                "and wins or loses."
            ),
            ACT_THREE,
        ),
        Beat(
            _("Resolution"),
            _(
                "The aftermath: loose ends tied up and a new normal for the "
                "protagonist."
            ),
            ACT_THREE,
        ),
    ]


def storyCircle():
    return [
        Beat(
            _("You"),
            _("1. A character is in a zone of comfort."),
            ORDINARY_WORLD,
        ),
        Beat(
            _("Need"),
            _("2. But they want something."),
            ORDINARY_WORLD,
        ),
        Beat(
            _("Go"),
            _("3. They enter an unfamiliar situation."),
            UNFAMILIAR_WORLD,
        ),
        Beat(
            _("Search"),
            _("4. They adapt to it."),
            UNFAMILIAR_WORLD,
        ),
        Beat(
            _("Find"),
            _("5. They get what they wanted."),
            UNFAMILIAR_WORLD,
        ),
        Beat(
            _("Take"),
            _("6. They pay a heavy price for it."),
            UNFAMILIAR_WORLD,
        ),
        Beat(
            _("Return"),
            _("7. Then they return to their familiar situation."),
            ORDINARY_WORLD,
        ),
        Beat(
            _("Change"),
            _("8. Having changed."),
            ORDINARY_WORLD,
        ),
    ]


def sequences():
    return [
        Beat(
            _("Sequence A: Status Quo and Inciting Incident"),
            _(
                "Pages 1-15. The protagonist's world and what they want, "
                "ending with the inciting incident."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Sequence B: Predicament and Lock-In"),
            _(
                "Pages 15-30. The protagonist wrestles with the new "
                "situation, ending when they're locked into the story's main "
                "tension. End of Act One."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Sequence C: First Obstacle"),
            _(
                "Pages 30-45. The first attempt to solve the problem, the "
                "easy way, which fails and raises the stakes."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Sequence D: First Culmination"),
            _(
                "Pages 45-60. A bigger attempt, ending at the midpoint with "
                "a glimpse of how things could end."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Sequence E: Subplot and Rising Action"),
            _(
                "Pages 60-75. The consequences of the midpoint, subplots "
                "come to the fore, things get harder."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Sequence F: Main Culmination"),
            _(
                "Pages 75-90. The main tension is resolved, often at the "
                "protagonist's lowest point. End of Act Two."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Sequence G: New Tension and Twist"),
            _(
                "Pages 90-105. A new tension carries the story to the end, "
                "with a twist that upends expectations."
            ),
            ACT_THREE,
        ),
        Beat(
            _("Sequence H: Resolution"),
            _(
                "Pages 105-120. The climax and its aftermath: the story's "
                "questions answered and loose ends tied up."
            ),
            ACT_THREE,
        ),
    ]


def miniMovies():
    return [
        Beat(
            _("Mini-Movie 1: The Setup"),
            _(
                "Pages 1-12. Hook the audience, show the hero's world, and "
                "end on the inciting incident. Each mini-movie has its own "
                "beginning, middle and end, and closes on a question that "
                "pulls into the next."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Mini-Movie 2: The Lock-In"),
            _(
                "Pages 12-25. The hero is drawn in until there's no way "
                "out, ending on the decision that starts Act Two."
            ),
            ACT_ONE,
        ),
        Beat(
            _("Mini-Movie 3: The First Trial"),
            _(
                "Pages 25-37. A new world and the first try at the goal, "
                "ending in a setback."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Mini-Movie 4: The Midpoint"),
            _(
                "Pages 37-55. Things build to a big reversal at the "
                "midpoint that changes the hero's course."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Mini-Movie 5: The Complications"),
            _(
                "Pages 55-67. Fallout from the midpoint, subplots tighten "
                "and the opposition hits back."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Mini-Movie 6: The Lowest Point"),
            _(
                "Pages 67-80. Everything falls apart, ending with all hope "
                "lost. End of Act Two."
            ),
            ACT_TWO,
        ),
        Beat(
            _("Mini-Movie 7: The Twist"),
            _(
                "Pages 80-95. The hero regroups with a new plan, and a "
                "twist raises the stakes one last time."
            ),
            ACT_THREE,
        ),
        Beat(
            _("Mini-Movie 8: The Climax"),
            _(
                "Pages 95-110. The final confrontation and the new world "
                "it leaves behind."
            ),
            ACT_THREE,
        ),
    ]


SHEETS = [
    BeatSheet("savethecat", lambda: _("Save the Cat"), saveTheCat),
    BeatSheet("threeact", lambda: _("Three-Act Structure"), threeAct),
    BeatSheet("storycircle", lambda: _("Dan Harmon's Story Circle"), storyCircle),
    BeatSheet("sequence", lambda: _("The Sequence Method"), sequences),
    BeatSheet("minimovie", lambda: _("The Mini-Movie Method"), miniMovies),
]


def get(key):
    return next(s for s in SHEETS if s.key == key)
