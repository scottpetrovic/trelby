#!/usr/bin/env python3
# make trelby/thesaurus_en.dat from the WordNet 3.0 database:
#
#   python tools/make_thesaurus.py WordNet-3.0/dict trelby/thesaurus_en.dat
#
# the dict directory comes from WordNet-3.0.tar.gz, at
# https://wordnetcode.princeton.edu/3.0/ (WNdb-3.0.tar.gz lacks the *.exc
# files). see trelby/thesaurus.py for the output's format.

import collections
import re
import sys

POS_FILES = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}

# sense key ss_type -> data file. 5 is an adjective satellite.
SS_TYPES = {"1": "n", "2": "v", "3": "a", "4": "r", "5": "a"}

# how many words each kind of relation adds to a sense, at most
MAX_SIMILAR = 20
MAX_BROADER = 6
MAX_NARROWER = 15

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
    def __init__(self, pos, words, ptrs, gloss):
        self.pos = pos
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

            res[(pos, offset)] = Synset(pos, words, ptrs, gloss)

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


def loadExceptions(dictDir):
    res = collections.defaultdict(list)

    for name in POS_FILES.values():
        for line in lines(f"{dictDir}/{name}.exc"):
            f = line.split()

            for base in f[1:]:
                if base not in res[f[0]]:
                    res[f[0]].append(base)

    return res


def main(dictDir, outFile):
    synsets = loadSynsets(dictDir)
    counts = loadCounts(dictDir)
    index = loadIndex(dictDir)
    exceptions = loadExceptions(dictDir)

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

    for form in sorted(exceptions):
        bases = [b for b in exceptions[form] if b in heads and b != form]

        if bases and HEADWORD_RE.match(form):
            out.append("X\t%s\t%s" % (form, " ".join(bases)))

    with open(outFile, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
