# the color themes for the screen. a theme is plain data, a name and a
# dict of color name -> (r, g, b), so themes could also be read from files.
# the PDF output is always black on white.

# the colors every theme must define
COLORS = [
    # text, and the text of page headers
    "text",
    "textHdr",
    # the page, and the area around it
    "textBg",
    "workspace",
    "pageBorder",
    "pageShadow",
    "selected",
    "cursor",
    "autoCompFg",
    "autoCompBg",
    # the background of script notes
    "note",
    "pagebreak",
    "pagebreakNoAdjust",
    "tabText",
    "tabBorder",
    "tabBarBg",
    "tabNonActiveBg",
]

# colors a theme may define. the per-element text colors default to "text".
# "accent" and "accentText", for the selected item in lists and toolbars
# we draw ourselves, default to the system's highlight colors.
ELEMENTS = [
    "scene",
    "action",
    "character",
    "dialogue",
    "parenthetical",
    "transition",
    "shot",
    "actBreak",
    "noteText",
]
OPTIONAL = ELEMENTS + ["accent", "accentText"]


class Theme:
    # name is in English, translated when shown. dark is whether the rest
    # of the application should use its dark appearance.
    def __init__(self, name, dark, colors):
        missing = set(COLORS) - set(colors)
        unknown = set(colors) - set(COLORS) - set(OPTIONAL)

        if missing or unknown:
            raise ValueError(
                "theme %s: missing colors %s, unknown colors %s"
                % (name, sorted(missing), sorted(unknown))
            )

        if ("accent" in colors) != ("accentText" in colors):
            raise ValueError("theme %s: accent needs accentText" % name)

        self.name = name
        self.dark = dark
        self.colors = colors

    # the (r, g, b) text color of the given element (see ELEMENTS)
    def elementColor(self, elem):
        return self.colors.get(elem, self.colors["text"])


LIGHT = Theme(
    "Light",
    False,
    {
        "text": (0, 0, 0),
        "textHdr": (128, 128, 128),
        "textBg": (255, 255, 255),
        "workspace": (237, 237, 237),
        "pageBorder": (202, 202, 202),
        "pageShadow": (153, 153, 153),
        "selected": (200, 200, 200),
        "cursor": (135, 135, 253),
        "autoCompFg": (0, 0, 0),
        "autoCompBg": (242, 242, 242),
        "note": (255, 237, 223),
        "pagebreak": (221, 221, 221),
        "pagebreakNoAdjust": (221, 221, 221),
        "tabText": (50, 50, 50),
        "tabBorder": (202, 202, 202),
        "tabBarBg": (221, 217, 215),
        "tabNonActiveBg": (180, 180, 180),
        "scene": (30, 75, 140),
        "character": (30, 75, 140),
        "parenthetical": (95, 95, 95),
        "transition": (95, 95, 95),
        "shot": (30, 75, 140),
        "actBreak": (30, 75, 140),
    },
)

DARK = Theme(
    "Dark",
    True,
    {
        "text": (220, 220, 220),
        "textHdr": (150, 150, 150),
        "textBg": (40, 40, 40),
        "workspace": (28, 28, 28),
        "pageBorder": (70, 70, 70),
        "pageShadow": (15, 15, 15),
        "selected": (75, 80, 100),
        "cursor": (110, 110, 230),
        "autoCompFg": (230, 230, 230),
        "autoCompBg": (55, 55, 55),
        "note": (80, 62, 50),
        "pagebreak": (70, 70, 70),
        "pagebreakNoAdjust": (70, 70, 70),
        "tabText": (220, 220, 220),
        "tabBorder": (70, 70, 70),
        "tabBarBg": (43, 43, 43),
        "tabNonActiveBg": (58, 58, 58),
        "scene": (135, 175, 235),
        "character": (135, 175, 235),
        "parenthetical": (155, 155, 155),
        "transition": (155, 155, 155),
        "shot": (135, 175, 235),
        "actBreak": (135, 175, 235),
    },
)

# warm yellow paper, like a legal pad
PARCHMENT = Theme(
    "Parchment",
    False,
    {
        "text": (35, 30, 20),
        "textHdr": (140, 120, 80),
        "textBg": (251, 233, 162),
        "workspace": (222, 202, 150),
        "pageBorder": (200, 176, 118),
        "pageShadow": (165, 140, 90),
        "selected": (238, 204, 120),
        "cursor": (196, 150, 90),
        "autoCompFg": (35, 30, 20),
        "autoCompBg": (246, 226, 160),
        "note": (249, 206, 158),
        "pagebreak": (226, 202, 140),
        "pagebreakNoAdjust": (226, 202, 140),
        "tabText": (60, 45, 25),
        "tabBorder": (200, 176, 118),
        "tabBarBg": (234, 216, 168),
        "tabNonActiveBg": (216, 194, 142),
        "accent": (190, 120, 45),
        "accentText": (255, 255, 255),
        "scene": (135, 65, 20),
        "character": (105, 45, 40),
        "parenthetical": (115, 98, 70),
        "transition": (115, 98, 70),
        "shot": (135, 65, 20),
        "actBreak": (135, 65, 20),
    },
)

# https://ethanschoonover.com/solarized/
SOLARIZED_LIGHT = Theme(
    "Solarized Light",
    False,
    {
        "text": (88, 110, 117),
        "textHdr": (147, 161, 161),
        "textBg": (253, 246, 227),
        "workspace": (238, 232, 213),
        "pageBorder": (220, 213, 190),
        "pageShadow": (200, 192, 168),
        "selected": (228, 220, 194),
        "cursor": (38, 139, 210),
        "autoCompFg": (88, 110, 117),
        "autoCompBg": (238, 232, 213),
        "note": (250, 228, 204),
        "pagebreak": (225, 218, 196),
        "pagebreakNoAdjust": (225, 218, 196),
        "tabText": (88, 110, 117),
        "tabBorder": (220, 213, 190),
        "tabBarBg": (238, 232, 213),
        "tabNonActiveBg": (222, 215, 192),
        "accent": (38, 139, 210),
        "accentText": (253, 246, 227),
        "scene": (203, 75, 22),
        "character": (38, 139, 210),
        "parenthetical": (131, 148, 150),
        "transition": (108, 113, 196),
        "shot": (203, 75, 22),
        "actBreak": (211, 54, 130),
    },
)

SOLARIZED_DARK = Theme(
    "Solarized Dark",
    True,
    {
        "text": (147, 161, 161),
        "textHdr": (88, 110, 117),
        "textBg": (0, 43, 54),
        "workspace": (0, 33, 43),
        "pageBorder": (20, 70, 82),
        "pageShadow": (0, 22, 29),
        "selected": (20, 75, 90),
        "cursor": (38, 139, 210),
        "autoCompFg": (147, 161, 161),
        "autoCompBg": (7, 54, 66),
        "note": (62, 54, 30),
        "pagebreak": (20, 70, 82),
        "pagebreakNoAdjust": (20, 70, 82),
        "tabText": (147, 161, 161),
        "tabBorder": (20, 70, 82),
        "tabBarBg": (0, 38, 48),
        "tabNonActiveBg": (7, 54, 66),
        "accent": (38, 139, 210),
        "accentText": (253, 246, 227),
        "scene": (181, 137, 0),
        "character": (38, 139, 210),
        "parenthetical": (101, 123, 131),
        "transition": (108, 113, 196),
        "shot": (181, 137, 0),
        "actBreak": (211, 54, 130),
    },
)

MONOKAI = Theme(
    "Monokai",
    True,
    {
        "text": (248, 248, 242),
        "textHdr": (117, 113, 94),
        "textBg": (39, 40, 34),
        "workspace": (30, 31, 26),
        "pageBorder": (62, 61, 50),
        "pageShadow": (20, 20, 16),
        "selected": (73, 72, 62),
        "cursor": (253, 151, 31),
        "autoCompFg": (248, 248, 242),
        "autoCompBg": (62, 61, 50),
        "note": (82, 66, 36),
        "pagebreak": (62, 61, 50),
        "pagebreakNoAdjust": (62, 61, 50),
        "tabText": (248, 248, 242),
        "tabBorder": (62, 61, 50),
        "tabBarBg": (30, 31, 26),
        "tabNonActiveBg": (52, 53, 46),
        "accent": (249, 38, 114),
        "accentText": (248, 248, 242),
        "scene": (253, 151, 31),
        "character": (166, 226, 46),
        "parenthetical": (150, 146, 125),
        "transition": (174, 129, 255),
        "shot": (253, 151, 31),
        "actBreak": (249, 38, 114),
    },
)

# https://draculatheme.com/
DRACULA = Theme(
    "Dracula",
    True,
    {
        "text": (248, 248, 242),
        "textHdr": (98, 114, 164),
        "textBg": (40, 42, 54),
        "workspace": (30, 31, 41),
        "pageBorder": (68, 71, 90),
        "pageShadow": (21, 22, 28),
        "selected": (68, 71, 90),
        "cursor": (189, 147, 249),
        "autoCompFg": (248, 248, 242),
        "autoCompBg": (68, 71, 90),
        "note": (84, 58, 78),
        "pagebreak": (68, 71, 90),
        "pagebreakNoAdjust": (68, 71, 90),
        "tabText": (248, 248, 242),
        "tabBorder": (68, 71, 90),
        "tabBarBg": (33, 34, 44),
        "tabNonActiveBg": (52, 55, 70),
        "accent": (189, 147, 249),
        "accentText": (40, 42, 54),
        "scene": (255, 121, 198),
        "character": (139, 233, 253),
        "parenthetical": (130, 142, 185),
        "transition": (189, 147, 249),
        "shot": (255, 121, 198),
        "actBreak": (255, 184, 108),
    },
)

# https://www.nordtheme.com/
NORD = Theme(
    "Nord",
    True,
    {
        "text": (216, 222, 233),
        "textHdr": (97, 110, 136),
        "textBg": (46, 52, 64),
        "workspace": (36, 41, 51),
        "pageBorder": (67, 76, 94),
        "pageShadow": (26, 30, 37),
        "selected": (67, 76, 94),
        "cursor": (136, 192, 208),
        "autoCompFg": (216, 222, 233),
        "autoCompBg": (59, 66, 82),
        "note": (90, 70, 66),
        "pagebreak": (67, 76, 94),
        "pagebreakNoAdjust": (67, 76, 94),
        "tabText": (216, 222, 233),
        "tabBorder": (67, 76, 94),
        "tabBarBg": (40, 45, 56),
        "tabNonActiveBg": (59, 66, 82),
        "accent": (136, 192, 208),
        "accentText": (46, 52, 64),
        "scene": (136, 192, 208),
        "character": (180, 142, 173),
        "parenthetical": (130, 142, 165),
        "transition": (129, 161, 193),
        "shot": (136, 192, 208),
        "actBreak": (235, 203, 139),
    },
)
