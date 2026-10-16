# the screenplay model. a script is a Screenplay (model.py), the
# document, and it's edited through an Editor (editor.py), which holds the
# cursor, selection, auto-completion list, typing style and undo history,
# and does every undoable edit. both get their methods from mixins, split
# by area (* = the module also has an Editor-side mixin, *EditMixin):
#
# Screenplay:
#   structure     paragraphs, elements, speeches and scenes; statistics
#   wrapping      word wrapping and rewrapping after edits
#   centering*    centered action
#   dualdialogue* side-by-side speeches
#   pagination    page breaks and page labels
#   locks*        locked pages and scene numbers
#   sceneoutline* the outline, scene colors, moving scenes
#
# Editor:
#   editing       type changes, joining / splitting, whole-script edits
#   formatting    bold / italic / underline
#   autocomp      the auto-completion list
#   selection     the selection and the internal clipboard
#   commands      the editor's commands: movement, type changes, undo
#   textinput     the editor's typing and deleting commands
#
# and code that works on a Screenplay from the outside:
#
#   undohistory   the undo history (ed.undoHistory)
#   fileformat    reading and writing .trelby files (sp.save, load)
#   render        laying pages out as pml, for PDFs and the page views
#   export/       the export formats (text, HTML, FDX, Fountain, RTF, PDF)
#   compare       comparing two scripts
#   proofing      the script checker
#
# constants.py has the line break and element type constants, and
# datatypes.py the small classes used along with Screenplay.

# the constants must be defined before anything else is imported: config
# and line import this package and use them while they're being loaded,
# which in this circular import happens before the imports below finish.
from trelby.screenplay.constants import (  # noqa: F401
    ACTBREAK,
    ACTION,
    CHARACTER,
    DIALOGUE,
    LB_FORCED,
    LB_LAST,
    LB_NONE,
    LB_SPACE,
    LB_SPACE2,
    NOTE,
    PAREN,
    SCENE,
    SHOT,
    TRANSITION,
)
from trelby.screenplay.datatypes import (  # noqa: F401
    ClipData,
    CommandState,
    Mark,
    OutlineItem,
    isValidColor,
)
from trelby.screenplay.model import Screenplay  # noqa: F401
from trelby.screenplay.editor import Editor  # noqa: F401
