# reading scripts in other programs' formats. one module per format, each
# with
#
#   parse(data, options=None) -> ImportResult
#
# data is the file's contents: bytes if the module's BINARY is True,
# otherwise str. options is the module's Options, for formats that have
# any (fountain, text). a failed import raises ImportFailed, whose message
# is for the user.
#
# this package doesn't use wx: reading the file, the options dialogs and
# the error message boxes are in trelby/myimport.py. formats.IMPORT_FORMATS
# lists the formats.

import trelby.importers.astx as astx
import trelby.importers.celtx as celtx
import trelby.importers.fadein as fadein
import trelby.importers.fdx as fdx
import trelby.importers.fountain as fountain
import trelby.importers.text as text
from trelby.importers.common import ImportFailed, ImportResult
