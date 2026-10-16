import re

import trelby
import trelby.mypickle as mypickle
import trelby.textutil as textutil

# words loaded from dict_en.dat.
gdict = set()

# key = textutil.getWordPrefix(word), value = set of words beginning with
# that prefix (only words in gdict)
#
# only used by suggest, to narrow down the words to suggest. words of two
# letters or less aren't in it, so the main dictionary never suggests
# them, and getWordPrefix maps non-letters to "z", so a set can hold words
# that don't start with its key; suggest checks startswith itself.
prefixDict = {}


# the word dictionary file. packaged versions have only the gzipped copy,
# which fileio.loadMaybeCompressedFile falls back to.
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

    # return True if word is a known word. apostrophes around it are
    # quotes, not part of it, and the possessive of a known word, e.g. a
    # character's name, is known too.
    def isKnown(self, word):
        word = textutil.lower(word).strip("'")

        if not word or self._isKnown(word):
            return True

        return word.endswith("'s") and self._isKnown(word[:-2])

    def _isKnown(self, word):
        return (
            word in gdict
            or word in self.cnames
            or self.sp.scDict.isKnown(word)
            or self.gScDict.isKnown(word)
            or word.isdigit()
        )

    # return the misspelled words on the given line as (col, length)
    # pairs, for underlining them. apostrophes around a word aren't part
    # of it. if cursorCol is given, the word ending there isn't included,
    # as it's probably still being typed.
    def lineErrors(self, line, cursorCol=None):
        res = []

        for start, word in lineWords(self.sp.lines[line].text):
            if (start + len(word) != cursorCol) and not self.isKnown(word):
                res.append((start, len(word)))

        return res


# the words in text (as SpellChecker / Screenplay.getWord split them,
# with apostrophes around them left out), as (col, word) pairs
def lineWords(text):
    res = []

    for m in _wordRe.finditer(text):
        s = m.group()
        word = s.strip("'")

        if word:
            res.append((m.start() + len(s) - len(s.lstrip("'")), word))

    return res


# return the (col, word) of lineWords(text) that col is in or right
# after, or None
def wordAt(text, col):
    for start, word in lineWords(text):
        if start <= col <= start + len(word):
            return (start, word)

    return None


# letters, digits and apostrophes, like textutil.isWordBoundary
_wordRe = re.compile(r"(?:[^\W_]|')+")


# return up to n replacements for a misspelled word, closest first (by
# Levenshtein distance, then alphabetically), cased like word: all caps
# or capitalized. they come from the main dictionary and the Dicts in
# 'dicts' (the user's and the script's), and start with the same two
# letters as word, and differ in length by 3 or less.
def suggest(word, dicts, n=5):
    lower = textutil.lower(word)
    start = lower[:2]

    words = set(prefixDict.get(textutil.getWordPrefix(lower), ()))
    for d in dicts:
        words.update(d.words)

    scored = sorted(
        (lev(lower, w), w)
        for w in words
        if w.startswith(start) and (abs(len(w) - len(lower)) <= 3)
    )

    return [matchCase(word, w) for d, w in scored[:n]]


# return word cased like 'model': all caps, capitalized, or as it is
def matchCase(model, word):
    if model == textutil.upper(model):
        return textutil.upper(word)

    if model[:1] == textutil.upper(model[:1]):
        return textutil.capitalize(word)

    return word


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
