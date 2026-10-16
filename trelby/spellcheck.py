import trelby
import trelby.mypickle as mypickle
import trelby.textutil as textutil

# words loaded from dict_en.dat.
gdict = set()

# key = textutil.getWordPrefix(word), value = set of words beginning with
# that prefix (only words in gdict)
#
# only used by spellcheckdlg to narrow down the words to suggest. words of
# two letters or less aren't in it, so the main dictionary never suggests
# them, and
# getWordPrefix maps non-letters to "z", so a set can hold words that
# don't start with its key; the caller checks startswith itself.
prefixDict = {}


# the word dictionary file. packaged versions have only the gzipped copy,
# which gutil.loadMaybeCompressedFile falls back to.
DICT_FILENAME = trelby.__path__[0] + "/dict_en.dat"


# load the word dictionary from s, the contents of DICT_FILENAME.
# spellcheckdlg.loadDict reads the file and calls this.
def loadDict(s):
    lines = s.splitlines()

    chars = "abcdefghijklmnopqrstuvwxyz"

    for ch1 in chars:
        for ch2 in chars:
            prefixDict[ch1 + ch2] = set()

    gwp = textutil.getWordPrefix

    for word in lines:
        # theoretically, we should do textutil.lower(textutil.toInputStr(it)), but:
        #
        #  -user's aren't supposed to modify the file
        #
        #  -it takes 1.35 secs, compared to 0.56 secs if we don't, on an
        #   1.33GHz Athlon
        gdict.add(word)

        if len(word) > 2:
            prefixDict[gwp(word)].add(word)


# dictionary, a list of known words that the user has specified.
class Dict:
    cvars = None

    def __init__(self):
        if not self.__class__.cvars:
            v = self.__class__.cvars = mypickle.Vars()

            v.addList("wordsList", [], "Words", mypickle.StrLatin1Var("", "", ""))

            v.makeDicts()

        self.__class__.cvars.setDefaults(self)

        # we have wordsList that we use for saving/loading, and words,
        # which we use during normal operation. it's possible we should
        # introduce a mypickle.SetVar...

        # key = word, lowercased, value = None
        self.words = {}

    # load from string 's'. does not throw any exceptions and silently
    # ignores any errors.
    def load(self, s):
        self.cvars.load(self.cvars.makeVals(s), "", self)

        self.words = {}

        for w in self.wordsList:
            self.words[w] = None

        self.refresh()

    # save to a string and return that.
    def save(self):
        self.wordsList = self.get()

        return self.cvars.save("", self)

    # fix up invalid values.
    def refresh(self):
        ww = {}

        for w in list(self.words.keys()):
            w = self.cleanWord(w)

            if w:
                ww[w] = None

        self.words = ww

    # returns True if word is known
    def isKnown(self, word):
        return word in self.words

    # add word
    def add(self, word):
        word = self.cleanWord(word)

        if word:
            self.words[word] = None

    # set words from a list
    def set(self, words):
        self.words = {}

        for w in words:
            self.add(w)

    # get a sorted list of all the words.
    def get(self):
        keys = list(self.words.keys())
        keys.sort()

        return keys

    # clean up word in all possible ways and return it, or an empty string
    # if nothing remains.
    def cleanWord(self, word):
        word = textutil.splitToWords(textutil.lower(textutil.toInputStr(word)))

        if len(word) == 0:
            return ""

        return word[0]


# spell check a script, starting from the given line
class SpellChecker:
    def __init__(self, sp, gScDict, line=0):
        self.sp = sp

        # user's global dictionary (Dict)
        self.gScDict = gScDict

        # key = word found in character names, value = None. the names
        # come lower-cased from getCharacterNames, matching isKnown.
        self.cnames = {}

        for it in sp.getCharacterNames():
            for w in textutil.splitToWords(it):
                self.cnames[w] = None

        self.word = None
        self.line = line

        # we can't use the current column, because if the cursor is in the
        # middle of a word, we flag the partial word as misspelled.
        self.col = 0

    # find next possibly misspelled word and store its location. returns
    # True if such a word found.
    def findNext(self):
        line = self.line
        col = self.col

        # clear these so there's no chance of them left pointing to
        # something, we return False, and someone tries to access them
        # anyhow.
        self.word = None
        self.line = 0
        self.col = 0

        while 1:
            word, line, col = self.sp.getWord(line, col)

            if not word:
                return False

            if not self.isKnown(word):
                self.word = word
                self.line = line
                self.col = col

                return True

            col += len(word)

    # return True if word is a known word.
    def isKnown(self, word):
        word = textutil.lower(word)

        return (
            word in gdict
            or word in self.cnames
            or self.sp.scDict.isKnown(word)
            or self.gScDict.isKnown(word)
            or word.isdigit()
        )


# Calculates the Levenshtein distance between a and b.
def lev(a, b):
    n, m = len(a), len(b)

    if n > m:
        # Make sure n <= m, to use O(min(n, m)) space
        a, b = b, a
        n, m = m, n

    current = list(range(n + 1))

    for i in range(1, m + 1):
        previous, current = current, [i] + [0] * m

        for j in range(1, n + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1

            change = previous[j - 1]

            if a[j - 1] != b[i - 1]:
                change += 1

            current[j] = min(add, delete, change)

    return current[n]
