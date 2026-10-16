import trelby.pml as pml
import trelby.screenplay as screenplay


# used to iteratively add PML pages to a document
#
# besides the document, this holds the state that page generation
# (Screenplay.generatePMLPage) carries over from one page to the next, for
# the "CONTINUED:" lines and scene numbers. ViewModeLayout uses one too
# when generating the pages it shows on screen.
class Pager:
    def __init__(self, cfg):
        self.doc = pml.Document(cfg.paperWidth, cfg.paperHeight)

        # used in several places, so keep around
        self.charIndent = cfg.getType(screenplay.CHARACTER).indent
        self.sceneIndent = cfg.getType(screenplay.SCENE).indent

        # number of the current scene, e.g. "12" or "12A", or "" before
        # the first scene
        self.scene = ""

        # {line: number} for all scene headings, filled in when first
        # needed. see Screenplay.getSceneLabels.
        self.sceneNrs = None

        # number of CONTINUED:'s lines added for current scene
        self.sceneContNr = 0
