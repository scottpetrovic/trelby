import collections

import trelby
import trelby.spellcheck as spellcheck
import trelby.textutil as textutil

# the thesaurus file, made from WordNet 3.0 by tools/make_thesaurus.py.
# packaged versions have only the gzipped copy, which
# fileio.loadMaybeCompressedFile falls back to.
#
# lines starting with "#" are comments (WordNet's license). the others
# are tab-separated fields:
#
#   S  pos  definition  word|word|...
#
#     a sense (a WordNet synset): its part of speech (n, v, a or r), and
#     its words, then for adjectives similar ones, for the others broader
#     and narrower ones. the S lines are numbered from 0.
#
#   W  headword  sense sense ...
#
#     a word's senses, most used first. headwords are lower case.
#
#   X  form  headword headword ...
#
#     an irregular form of the headwords, e.g. "ran" for "run".
FILENAME = trelby.__path__[0] + "/thesaurus_en.dat"

# the loaded Thesaurus, or None. trelbyctrl.loadThesaurus loads it.
gThesaurus = None

# word: the headword it's a sense of. pos: "n", "v", "a" or "r".
# definition: what it means. words: the related words.
Sense = collections.namedtuple("Sense", "word pos definition words")

# WordNet's endings for regular forms, and what replaces them in the
# headword. a candidate is only used if it's a headword.
SUFFIXES = [
    ("s", ""),
    ("ses", "s"),
    ("xes", "x"),
    ("zes", "z"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("men", "man"),
    ("ies", "y"),
    ("es", "e"),
    ("es", ""),
    ("ed", "e"),
    ("ed", ""),
    ("ing", "e"),
    ("ing", ""),
    ("er", ""),
    ("est", ""),
    ("er", "e"),
    ("est", "e"),
]


class Thesaurus:
    # load from s, the contents of FILENAME
    def __init__(self, s):
        # the S lines' fields after the "S", parsed when they're used
        self.senses = []

        # headword -> its W line's senses, as a string
        self.words = {}

        # form -> its X line's headwords, as a string
        self.forms = {}

        for line in s.splitlines():
            if line.startswith("S\t"):
                self.senses.append(line[2:])
            elif line.startswith("W\t"):
                word, ids = line[2:].split("\t")
                self.words[word] = ids
            elif line.startswith("X\t"):
                form, words = line[2:].split("\t")
                self.forms[form] = words

    # return the headwords word could be a form of: itself, the
    # headwords of an irregular form, then the ones with a regular ending
    # replaced. the possessive "'s" is left out.
    def headwords(self, word):
        word = textutil.lower(word)

        if word.endswith("'s"):
            word = word[:-2]

        res = [word]
        res += self.forms.get(word, "").split()

        for end, repl in SUFFIXES:
            if word.endswith(end) and len(word) > len(end):
                res.append(word[: -len(end)] + repl)

        return [w for i, w in enumerate(res) if w in self.words and w not in res[:i]]

    # return the Senses of word and the headwords it's a form of. their
    # words are cased like word (see spellcheck.matchCase), and don't
    # include word or the headword.
    def lookup(self, word):
        res = []

        for head in self.headwords(word):
            skip = {head, textutil.lower(word)}

            for id in self.words[head].split():
                pos, definition, words = self.senses[int(id)].split("\t")
                ws = [
                    spellcheck.matchCase(word, w)
                    for w in words.split("|")
                    if textutil.lower(w) not in skip
                ]

                res.append(Sense(head, pos, definition, ws))

        return res
