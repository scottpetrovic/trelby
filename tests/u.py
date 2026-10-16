# ut:ignore
import os

import trelby.config as config
import trelby.misc as misc
import trelby.screenplay as screenplay
import trelby.util as util

initDone = False


def init():
    global initDone

    if not initDone:
        misc.init(False)
        util.init(False)

        initDone = True


# return new, empty Screenplay
def new():
    init()

    return screenplay.Screenplay(config.ConfigGlobal())


def fixtureFilePath(filePathRelativeToFixturesDir: str) -> str:
    location = os.path.dirname(__file__) + "/fixtures/"

    return os.path.join(location, filePathRelativeToFixturesDir)


# load script from the given file, relative to the current script directory
def load(filename="test.trelby"):
    init()
    filename = fixtureFilePath(filename)

    with open(filename, "r", encoding="utf-8") as f:
        return screenplay.Screenplay.load(f.read(), config.ConfigGlobal())[0]


# load script from given string
def loadString(s: str):
    init()

    return screenplay.Screenplay.load(s, config.ConfigGlobal())[0]
