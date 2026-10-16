# linebreak types
#
# a script is a flat list of Lines, one per displayed / printed line, and
# each line's lb says what separates it from the next one:
#
#  LB_SPACE: the line was wrapped at a space. the space isn't stored
#  anywhere; it's implied between this line and the next one.
#
#  LB_NONE: the line was wrapped with nothing between it and the next
#  one, in the middle of a word too long for the line, or between
#  double-width characters.
#
#  LB_FORCED: a line break typed by the user inside an element. it ends
#  a paragraph, the unit that is rewrapped (see rewrapPara).
#
#  LB_LAST: the last line of an element. it ends a paragraph too. all
#  lines of an element have the same lt, and the script's last line is
#  always LB_LAST.
#
# only LB_FORCED and LB_LAST carry information from the user; LB_SPACE and
# LB_NONE are recomputed by wrapLine whenever a paragraph is rewrapped.
# config.lb2str gives the text each one stands for.

LB_SPACE = 1

# we don't use this anymore, but we have to keep it in order to be able to
# load old scripts
LB_SPACE2 = 2

LB_NONE = 3
LB_FORCED = 4
LB_LAST = 5

# line types
SCENE = 1
ACTION = 2
CHARACTER = 3
DIALOGUE = 4
PAREN = 5
TRANSITION = 6
SHOT = 7
NOTE = 8
ACTBREAK = 9
