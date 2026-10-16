#!/usr/bin/env python3
# make trelby/thesaurus_en.dat from the WordNet 3.0 database:
#
#   python tools/make_thesaurus.py WordNet-3.0/dict trelby/thesaurus_en.dat
#
# the dict directory comes from WordNet-3.0.tar.gz, at
# https://wordnetcode.princeton.edu/3.0/ (WNdb-3.0.tar.gz lacks the *.exc
# files). see trelby/thesaurus.py for the output's format. it also reads
# trelby/dict_en.dat, the spelling dictionary, to see which forms are used.

import collections
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import trelby.thesaurus as thesaurus  # noqa: E402

SPELLING = os.path.join(ROOT, "trelby", "dict_en.dat")

POS_FILES = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}

# sense key ss_type -> data file. 5 is an adjective satellite.
SS_TYPES = {"1": "n", "2": "v", "3": "a", "4": "r", "5": "a"}

# how many words each kind of relation adds to a sense, at most
MAX_SIMILAR = 20
MAX_BROADER = 6
MAX_NARROWER = 15

# verbs whose past tense is the word itself, which verb.exc leaves out
SAME_PAST = """
    beat bet bid broadcast browbeat burst cast cost cut forecast hit hurt
    let offset outbid overbid put quit read reset rid set shed shut slit
    split spread sublet thrust undercut upset
""".split()

# the endings ("ed" past tense, "en" past participle) of the irregular
# verb forms the rules in verbEndings get wrong. "am" and "are" aren't
# either, and are left out.
VERB_ENDINGS = {
    "am": "",
    "are": "",
    "backslid": "ed en",
    "beat": "ed",
    "beheld": "ed en",
    "browbeat": "ed",
    "dove": "ed",
    "might": "ed",
    "skydove": "ed",
    "slid": "ed en",
}

# irregular forms that are British ("dreamt") or old-fashioned ("wrought"),
# for which the regular form is used if the spelling dictionary has it.
# so is a British "-ll-" ("travelled") or "-mme" ("programmes").
PREFER_REGULAR = set("""
    addrest blest burnt bypast chid chidden clad curst dreamt gelt gilt girt
    gript hove leant leapt learnt misspelt molten overpast overspilt pent
    reft rove smelt spelt spilt spoilt stove thriven throve transfixt unclad
    unlearnt wrought
""".split())

# irregular forms that are used only if there's no other with the same
# ending: "born" (but "has borne"), and rare ones
RARE = set("""
    abye backslidden begat beholden bestrid born cloven forbad shrunken
    slidden smit sunken yclept
""".split())

# nouns that have no plural, or whose plural is the same word, but that
# the spelling dictionary has a plural for
UNCOUNTABLE = set("""
    advice aircraft baggage bison cod deer equipment evidence fish furniture
    hovercraft information knowledge luggage moose music news offspring
    progeny research salmon sheep spacecraft swine trout
""".split()) | {"child's play"}

# WordNet's lexicographer files for nouns that are things you can count:
# noun.animal, artifact, body, location, object, person, plant and
# quantity. a noun with a sense in one of them always has a plural.
LEX_COUNTABLE = {5, 6, 8, 15, 17, 18, 20, 23}

# the headwords we keep: single words the editor can find under the
# cursor (see spellcheck.lineWords)
HEADWORD_RE = re.compile(r"^[a-z0-9']+$")

LICENSE = """\
WordNet Release 3.0

This software and database is being provided to you, the LICENSEE, by
Princeton University under the following license.  By obtaining, using
and/or copying this software and database, you agree that you have
read, understood, and will comply with these terms and conditions.:

Permission to use, copy, modify and distribute this software and
database and its documentation for any purpose and without fee or
royalty is hereby granted, provided that you agree to comply with
the following copyright notice and statements, including the disclaimer,
and that the same appear on ALL copies of the software, database and
documentation, including modifications that you make for internal
use or for distribution.

WordNet 3.0 Copyright 2006 by Princeton University.  All rights reserved.

THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON
UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR
IMPLIED.  BY WAY OF EXAMPLE, BUT NOT LIMITATION, PRINCETON
UNIVERSITY MAKES NO REPRESENTATIONS OR WARRANTIES OF MERCHANT-
ABILITY OR FITNESS FOR ANY PARTICULAR PURPOSE OR THAT THE USE
OF THE LICENSED SOFTWARE, DATABASE OR DOCUMENTATION WILL NOT
INFRINGE ANY THIRD PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR
OTHER RIGHTS.

The name of Princeton University or Princeton may not be used in
advertising or publicity pertaining to distribution of the software
and/or database.  Title to copyright in this software, database and
any associated documentation shall at all times remain with
Princeton University and LICENSEE agrees to preserve same.
"""


class Synset:
    def __init__(self, pos, lexFile, words, ptrs, gloss):
        self.pos = pos
        # its lexicographer file's number (see LEX_COUNTABLE)
        self.lexFile = lexFile
        # the words as WordNet writes them, e.g. "Paris", "give_up"
        self.words = words
        # (symbol, (pos, offset)) for the relations between whole synsets
        self.ptrs = ptrs
        self.gloss = gloss


def lines(path):
    with open(path, encoding="latin-1") as f:
        for line in f:
            # the license at the top of the data and index files
            if not line.startswith("  "):
                yield line.rstrip("\n")


def loadSynsets(dictDir):
    res = {}

    for pos, name in POS_FILES.items():
        for line in lines(f"{dictDir}/data.{name}"):
            data, gloss = line.split(" | ", 1)
            f = data.split()

            offset = int(f[0])
            wcnt = int(f[3], 16)
            words = [re.sub(r"\(.*\)$", "", w) for w in f[4 : 4 + 2 * wcnt : 2]]

            i = 4 + 2 * wcnt
            pcnt = int(f[i])
            ptrs = []

            for j in range(pcnt):
                sym, off, ppos, st = f[i + 1 + 4 * j : i + 5 + 4 * j]

                if st == "0000":
                    ptrs.append((sym, ("a" if ppos == "s" else ppos, int(off))))

            # the definition, without the examples after it
            gloss = re.split(r';\s*"', gloss, maxsplit=1)[0].strip().rstrip(";").strip()

            res[(pos, offset)] = Synset(pos, int(f[1]), words, ptrs, gloss)

    return res


# (lemma, pos, offset) -> how often that sense was seen in WordNet's
# tagged texts
def loadCounts(dictDir):
    res = {}

    for line in lines(f"{dictDir}/index.sense"):
        key, offset, senseNo, count = line.split()
        lemma, rest = key.split("%")
        res[(lemma, SS_TYPES[rest[0]], int(offset))] = int(count)

    return res


# lemma -> [(pos, [offsets in sense order])]
def loadIndex(dictDir):
    res = collections.defaultdict(list)

    for pos, name in POS_FILES.items():
        for line in lines(f"{dictDir}/index.{name}"):
            f = line.split()
            lemma = f[0]
            synsetCnt = int(f[2])
            res[lemma].append((pos, [int(x) for x in f[-synsetCnt:]]))

    return res


# (form, pos, base) for each irregular form in WordNet's exception lists,
# with "_" in phrases replaced by spaces
def loadExceptions(dictDir):
    res = []

    for pos, name in POS_FILES.items():
        for line in lines(f"{dictDir}/{name}.exc"):
            f = line.split()
            form = f[0].replace("_", " ")

            for base in f[1:]:
                res.append((form, pos, base.replace("_", " ")))

    return res


# which inflection an irregular form is, as thesaurus.py's endings: "s",
# "ed", "ing", "er" or "est"
def endingOf(form, pos):
    if pos == "n":
        return "s"

    if pos in "ar":
        # "worst", "most", "least"
        return "est" if form.endswith("st") else "er"

    # a verb phrase's first word is the one inflected ("took pains")
    form = form.split(" ")[0]

    if form.endswith("ing"):
        return "ing"

    # "was" is the one past tense in verb.exc ending in "s"
    if form.endswith("s") and form != "was":
        return "s"

    return "ed"


# which of a verb's past tense ("ed") and past participle ("en") an
# irregular form is. forms are the base's irregular forms of both kinds.
# a form ending in "ed" ("fled", "stopped") or that's the base itself
# ("hit") is both, and so is one with no other ("bought"), except "-en"
# ones ("proven"), and "ran" and "came", whose participle is the base.
# with more than one, "-en" ones ("taken", "gone", "torn") and ones with a
# "u" for another's "a" ("sung") are participles, the others past tenses.
def verbEndings(form, base, forms):
    word = form.split(" ")[0]
    baseWord = base.split(" ")[0]

    if word in VERB_ENDINGS:
        return VERB_ENDINGS[word].split()

    if word == baseWord or word.endswith(("ed", "'d")):
        return ["ed", "en"]

    if word.endswith(("en", "wn")):
        return ["en"]

    others = [f for f in forms if f not in (word, baseWord) and not f.endswith("ed")]

    if others:
        if word.endswith(("ne", "rn", "ain")) or any(isAtoU(f, word) for f in others):
            return ["en"]

        return ["ed"]

    if baseWord.endswith(("run", "come")):
        return ["ed"]

    return ["ed", "en"]


# whether form is other with an "a" changed to "u" ("sang", "sung")
def isAtoU(other, form):
    diffs = [(a, b) for a, b in zip(other, form) if a != b]

    return len(other) == len(form) and diffs == [("a", "u")]


# whether a verb's irregular form could be a British or old-fashioned
# spelling of reg, its regular form (which is used if it's a word)
def isVariant(form, base, reg):
    if form in PREFER_REGULAR:
        return True

    for double in ("ll", "mme"):
        if double in form and double not in base:
            return form.replace(double, double[0]) == reg

    return False


# the X lines' (form, pos, base, ending) for the irregular forms of the
# words in synonyms, in the order inflect prefers them
def irregularForms(exceptions, synonyms, spelling):
    # some exceptions are the base itself ("bed bed"), to stop WordNet
    # from taking it for a form of something else ("b")
    rows = {(f, p, b) for f, p, b in exceptions if f != b and b in synonyms}
    rows |= {(w, "v", w) for w in SAME_PAST if w in synonyms}

    # verb -> its past tenses and participles
    pasts = collections.defaultdict(set)

    for form, pos, base in rows:
        if pos == "v" and endingOf(form, pos) == "ed":
            pasts[base].add(form.split(" ")[0])

    # (pos, base, ending) -> {(rank, form)}. regular forms used instead of
    # an irregular one come first, then the forms that are both a past
    # tense and a participle, then the others, then the rare ones.
    res = collections.defaultdict(set)

    for form, pos, base in rows:
        ending = endingOf(form, pos)

        if pos == "v" and ending == "ed":
            endings = verbEndings(form, base, pasts[base])
        else:
            endings = [ending]

        rank = 3 if form in RARE else 1 if len(endings) == 2 else 2

        for e in endings:
            res[(pos, base, e)].add((rank, form))

            if pos == "v" and " " not in base:
                reg = thesaurus.regularForm(base, pos, e)

                if reg in spelling and isVariant(form, base, reg):
                    res[(pos, base, e)].add((0, reg))

        # "has run"
        if endings == ["ed"] and base.split(" ")[0].endswith(("run", "come")):
            res[(pos, base, "en")].add((1, base))

    for word in UNCOUNTABLE & synonyms:
        res[("n", word, "s")].add((0, word))

    out = []

    for (pos, base, ending), forms in sorted(res.items()):
        out += [(form, pos, base, ending) for rank, form in sorted(forms)]

    return out


# whether an adjective or adverb can have "more" / "most": adverbs ending
# in "-ly", and adjectives that have an "-ly" adverb ("more furious", but
# not "more male" or "more hurrying"). ordinals' adverbs ("firstly") and
# adjectives ("worldly", which kinds says aren't adverbs) don't count.
def isGradable(word, pos, spelling, kinds):
    if pos == "r":
        return word.endswith("ly") or word == "often"

    adverbs = [word + "ly"]

    if word.endswith("ic"):
        adverbs.append(word + "ally")

    if word.endswith("y"):
        adverbs.append(word[:-1] + "ily")

    if word.endswith(("le", "ll")):
        adverbs.append(word[:-1] + "y")

    for a in adverbs:
        if a in spelling and not a.endswith(("stly", "ndly", "rdly", "thly")):
            if "r" in kinds.get(a, "r"):
                return True

    return False


# X lines for the forms inflect would make by the rules that aren't used:
# the plurals of uncountable nouns ("advices", "walkings"), and the
# comparatives and superlatives of adjectives and adverbs that have none
# ("maler", "more presto"), with the word itself as the form. one made
# with "-er" / "-est" that the spelling dictionary doesn't have is made
# with "more" / "most" instead if the word can have that ("boyish", which
# the rules take for one syllable). words is the (word, pos) the senses
# have. kinds is lemma -> the parts of speech it has, and the
# lexicographer files of its senses (see LEX_COUNTABLE).
def unusedForms(th, words, spelling, kinds):
    res = []

    for word, pos in sorted(words):
        if word not in spelling:
            continue

        if pos == "n":
            # the spelling dictionary lacks plurals of rare words ("langurs")
            if LEX_COUNTABLE & kinds.get(word, set()):
                continue

            endings = ["s"]
        elif pos in "ar":
            endings = ["er", "est"]
        else:
            continue

        for ending in endings:
            if th.irregular.get((pos, word, ending)):
                continue

            form = th.inflect(word, pos, ending)

            if form == word or " " in form.replace("more ", "").replace("most ", ""):
                continue

            more = form.startswith(("more ", "most "))

            if not more and form in spelling:
                continue

            if pos != "n" and len(word) > 2 and isGradable(word, pos, spelling, kinds):
                if not more:
                    prefix = "more " if ending == "er" else "most "
                    res.append((prefix + word, pos, word, ending))
            else:
                res.append((word, pos, word, ending))

    return res


def main(dictDir, outFile):
    synsets = loadSynsets(dictDir)
    counts = loadCounts(dictDir)
    index = loadIndex(dictDir)
    exceptions = loadExceptions(dictDir)

    with open(SPELLING, encoding="utf-8") as f:
        spelling = set(f.read().split())

    def count(word, key):
        return counts.get((word.lower(), key[0], key[1]), 0)

    # the words of the given synsets, most used first, at most n
    def wordsOf(keys, n=None):
        ws = [(count(w, k), w) for k in keys for w in synsets[k].words]
        ws.sort(key=lambda x: -x[0])

        return [w for c, w in ws][:n]

    def related(key):
        ss = synsets[key]
        res = wordsOf([key])

        if ss.pos == "a":
            res += wordsOf([k for s, k in ss.ptrs if s == "&"], MAX_SIMILAR)
        else:
            res += wordsOf([k for s, k in ss.ptrs if s == "@"], MAX_BROADER)
            res += wordsOf([k for s, k in ss.ptrs if s == "~"], MAX_NARROWER)

        seen = set()
        out = []

        for w in res:
            w = w.replace("_", " ")

            if w.lower() not in seen:
                seen.add(w.lower())
                out.append(w)

        return out

    # headword -> [synset keys], in the order they're shown
    heads = {}

    for lemma, entries in index.items():
        if not HEADWORD_RE.match(lemma):
            continue

        # the parts of speech the word is used as most come first
        entries = sorted(
            entries,
            key=lambda e: -sum(counts.get((lemma, e[0], o), 0) for o in e[1]),
        )
        keys = [(pos, o) for pos, offs in entries for o in offs]

        # leave out the senses that have nothing but the word itself
        keys = [k for k in keys if any(w.lower() != lemma for w in related(k))]

        if keys:
            heads[lemma] = keys

    used = sorted({k for keys in heads.values() for k in keys})
    ids = {k: i for i, k in enumerate(used)}

    out = ["# Trelby's thesaurus, made from WordNet 3.0 by tools/make_thesaurus.py."]
    out += ["# see trelby/thesaurus.py for the format.", "#"]
    out += [("# " + line).rstrip() for line in LICENSE.splitlines()]

    for k in used:
        out.append("S\t%s\t%s\t%s" % (k[0], synsets[k].gloss, "|".join(related(k))))

    for lemma in sorted(heads):
        out.append("W\t%s\t%s" % (lemma, " ".join(str(ids[k]) for k in heads[lemma])))

    # the irregular forms of the words a sense can have
    synonyms = {w.lower() for k in used for w in related(k)}

    for row in irregularForms(exceptions, synonyms, spelling):
        out.append("X\t%s\t%s\t%s\t%s" % row)

    # the lower case words the senses have as each part of speech, and the
    # last words of nouns like "domestic dog", which inflect makes plural
    words = set()

    for k in used:
        for w in related(k):
            if w == w.lower():
                words.add((w, k[0]))

                if k[0] == "n" and " " in w:
                    words.add((w.split(" ")[-1], "n"))

    # lemma -> its parts of speech and its senses' lexicographer files
    kinds = collections.defaultdict(set)

    for lemma, entries in index.items():
        kind = kinds[lemma.replace("_", " ")]

        for pos, offsets in entries:
            kind.add(pos)
            kind.update(synsets[(pos, o)].lexFile for o in offsets)

    th = thesaurus.Thesaurus("\n".join(out))

    for row in unusedForms(th, words, spelling, kinds):
        out.append("X\t%s\t%s\t%s\t%s" % row)

    with open(outFile, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
