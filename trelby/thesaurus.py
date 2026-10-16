import collections
import re

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
#   X  form  pos  word  ending
#
#     a form of a word as a part of speech, and which of ENDINGS it is,
#     e.g. "ran v run ed". most are irregular forms from WordNet's
#     exception lists. a form that's both a past tense and a participle
#     has a line for each. when a word has more than one form with an
#     ending, the first is the one used: "traveled v travel ed" comes
#     before "travelled v travel ed". a form that's the word itself
#     means the rules' form isn't used: "advice n advice s" (not
#     "advices"), "male a male er" (not "maler").
FILENAME = trelby.__path__[0] + "/thesaurus_en.dat"

# the loaded Thesaurus, or None. trelbyctrl.loadThesaurus loads it.
gThesaurus = None

# word: the headword it's a sense of. pos: "n", "v", "a" or "r".
# definition: what it means. words: the related words.
Sense = collections.namedtuple("Sense", "word pos definition words")

# the forms a word can have: the plural or the "he / she / it" form, the
# past tense ("ran"), the past participle ("run"), the "-ing" form, the
# comparative and the superlative
ENDINGS = ["s", "ed", "en", "ing", "er", "est"]

# WordNet's endings for regular forms (its "morphy" rules): the ending,
# what replaces it in the headword, which of ENDINGS it is, and the parts
# of speech it's for. a candidate is only used if it's a headword.
SUFFIXES = [
    ("s", "", "s", "nv"),
    ("ses", "s", "s", "n"),
    ("xes", "x", "s", "n"),
    ("zes", "z", "s", "n"),
    ("ches", "ch", "s", "n"),
    ("shes", "sh", "s", "n"),
    ("men", "man", "s", "n"),
    ("ies", "y", "s", "nv"),
    ("es", "e", "s", "v"),
    ("es", "", "s", "v"),
    ("ed", "e", "ed", "v"),
    ("ed", "", "ed", "v"),
    ("ed", "e", "en", "v"),
    ("ed", "", "en", "v"),
    ("ing", "e", "ing", "v"),
    ("ing", "", "ing", "v"),
    ("er", "", "er", "ar"),
    ("est", "", "est", "ar"),
    ("er", "e", "er", "ar"),
    ("est", "e", "est", "ar"),
]

# words that make a noun like "man of war" or "mother-in-law" too hard to
# put in the plural
PREPOSITIONS = set("a at by de for from in of on the to with".split())

# words that make the past tense form of a verb after them a past
# participle: "has walked", "was taken", "he's gone"
AUXILIARIES = set("""
    have has had having 've 'd be am is are was were been being 's 're 'm
    get gets got gotten getting
""".split())

# words that can come between those and the participle: "had never
# walked", "had he walked". so can words ending in "-ly".
BETWEEN = set("""
    not never already just also always ever still even all both i you he
    she it we they
""".split())


# return word's form with ending (one of ENDINGS) by the regular spelling
# rules, as a noun, verb, adjective or adverb (pos "n", "v", "a" or "r").
# word is a lower case word with no irregular forms.
def regularForm(word, pos, ending):
    if not word[-1:].isalpha():
        return word

    # a consonant and "y": "carry", "angry"
    consY = word[-1] == "y" and word[-2:-1] not in "aeiou"

    if ending == "s":
        # already a plural, or a noun like "physics"
        if pos == "n" and word[-1] == "s" and not word.endswith(("ss", "us", "is")):
            return word

        # "goes", "echoes". nouns are "photos" (the exception lists have
        # "potatoes")
        oes = pos == "v" and word[-1] == "o" and word[-2:-1] not in "aeiou"

        if word.endswith(("s", "x", "z", "ch", "sh")) or oes:
            return word + "es"

        return word[:-1] + "ies" if consY else word + "s"

    if ending in ("ed", "en"):
        if word[-1] == "e":
            return word + "d"

        return word[:-1] + "ied" if consY else word + "ed"

    if ending == "ing":
        if word.endswith("ie"):
            return word[:-2] + "ying"

        # "being", "seeing", "hoeing", "dyeing" keep it
        if word[-1] == "e" and len(word) > 2 and not word.endswith(("ee", "oe", "ye")):
            return word[:-1] + "ing"

        return word + "ing"

    # "er" / "est" is for one syllable ("fast", "large") or two ending in
    # "y" ("angry", "friendly", but not the adverb "quickly"). the others
    # take "more" / "most".
    n = syllables(word)

    if n > 2 or (n == 2 and not (consY and (pos == "a" or not word.endswith("ly")))):
        return ("more " if ending == "er" else "most ") + word

    if word[-1] == "e":
        return word + ending[1:]

    return word[:-1] + "i" + ending if consY else word + ending


# return roughly how many syllables word has
def syllables(word):
    n = len(re.findall("[aeiouy]+", word))

    # a silent "e": "large", "irate", but not "able" or "free"
    if n > 1 and word[-1] == "e" and not word.endswith(("le", "ee")):
        n -= 1

    return max(n, 1)


# return the auxiliary verb from AUXILIARIES that comes before a word in a
# sentence, if any, given the text before it: "has" for "He has never",
# "'d" for "I'd", "has" for "hasn't", None for "When she" or "He has,".
def auxiliaryBefore(text):
    tokens = re.findall(r"(?:[^\W_]|')+|[^\w\s]", text.replace("\u2019", "'"))

    for token in reversed(tokens[-4:]):
        word = textutil.lower(token)

        if word.endswith("n't"):
            word = word[:-3]

        if word in AUXILIARIES:
            return word

        if "'" in word[1:]:
            suffix = word[word.index("'", 1) :]

            return suffix if suffix in AUXILIARIES else None

        if word not in BETWEEN and not word.endswith("ly"):
            return None

    return None


class Thesaurus:
    # load from s, the contents of FILENAME
    def __init__(self, s):
        # the S lines' fields after the "S", parsed when they're used
        self.senses = []

        # headword -> its W line's senses, as a string
        self.words = {}

        # form -> [(word, pos, ending)], from the X lines
        self.forms = collections.defaultdict(list)

        # (pos, word, ending) -> [form], from the X lines
        self.irregular = collections.defaultdict(list)

        for line in s.splitlines():
            if line.startswith("S\t"):
                self.senses.append(line[2:])
            elif line.startswith("W\t"):
                word, ids = line[2:].split("\t")
                self.words[word] = ids
            elif line.startswith("X\t"):
                form, pos, word, ending = line[2:].split("\t")
                self.forms[form].append((word, pos, ending))
                self.irregular[(pos, word, ending)].append(form)

    # return the headwords word could be a form of: itself, the
    # headwords of an irregular form, then the ones with a regular ending
    # replaced. the possessive "'s" is left out.
    def headwords(self, word):
        return [head for head, ending, poses in self.headForms(word)]

    # return headwords(word) as (headword, ending, poses): word is the
    # headword's form with ending (one of ENDINGS, or None for the
    # headword itself) as the parts of speech in poses. before is the
    # text before word, which tells a past participle from a past tense:
    # "walked" is "ed", but "en" after "has", and so is "run" in "has
    # run". without it, a word that can be a past tense is one.
    def headForms(self, word, before=""):
        word = textutil.lower(word)

        if word.endswith("'s"):
            word = word[:-2]

        cands = [(word, None, "")]
        cands += [(w, ending, pos) for w, pos, ending in self.forms.get(word, [])]

        for end, repl, ending, poses in SUFFIXES:
            if word.endswith(end) and len(word) > len(end):
                cands.append((word[: -len(end)] + repl, ending, poses))

        # headword -> {ending: poses}, in the order found
        res = {}

        for head, ending, poses in cands:
            if head in self.words:
                ends = res.setdefault(head, {})
                old = ends.get(ending, "")
                ends[ending] = old + "".join(p for p in poses if p not in old)

        aux = auxiliaryBefore(before)
        out = []

        for head, ends in res.items():
            # "I'd walked" is "had", but "I'd run" is "would"
            if "en" in ends and aux and (aux != "'d" or "ed" in ends):
                ending = "en"
            else:
                ending = ([e for e in ends if e != "en"] + ["en"])[0]

            out.append((head, ending, ends[ending]))

        return out

    # return word (a word or phrase from a sense whose part of speech is
    # pos) in its form with ending (one of ENDINGS), or word itself if
    # that can't be done safely: proper nouns, phrases other than a
    # verb's ("takes care") or a simple noun's ("facial expressions"),
    # and the forms the X lines say aren't used ("advices").
    def inflect(self, word, pos, ending):
        if word != textutil.lower(word):
            return word

        forms = self.irregular.get((pos, word, ending))

        if forms:
            return forms[0]

        if pos == "n" and PREPOSITIONS.intersection(re.split("[ -]", word)):
            return word

        parts = word.split(" ")

        # "fireman" is "firemen", but "human" is "humans"
        if pos == "n" and len(parts) == 1 and word.endswith("man"):
            prefix = word[:-3]

            if word in ("man", "woman") or (len(prefix) > 3 and prefix in self.words):
                return prefix + "men"

            return word

        # "grandchild", "schoolchild"
        if pos == "n" and len(parts) == 1 and word.endswith("child"):
            return word + "ren"

        if len(parts) > 1:
            if pos == "v":
                return " ".join([self.inflect(parts[0], pos, ending)] + parts[1:])

            if pos == "n":
                return " ".join(parts[:-1] + [self.inflect(parts[-1], pos, ending)])

            return word

        return regularForm(word, pos, ending)

    # return the Senses of word and the headwords it's a form of (see
    # headForms, which before is for). their words have word's form
    # ("looks" gives "stares", see inflect) and case (see
    # spellcheck.matchCase), and don't include word or the headword. a
    # headword's senses that can't have word's ending are left out: the
    # noun "walk" for "walked".
    def lookup(self, word, before=""):
        res = []

        for head, ending, poses in self.headForms(word, before):
            skip = {head, textutil.lower(word)}

            for id in self.words[head].split():
                pos, definition, words = self.senses[int(id)].split("\t")

                if ending and pos not in poses:
                    continue

                ws = []

                for w in words.split("|"):
                    form = self.inflect(w, pos, ending) if ending else w

                    if not {textutil.lower(w), textutil.lower(form)} & skip:
                        ws.append(spellcheck.matchCase(word, form))

                res.append(Sense(head, pos, definition, ws))

        return res
