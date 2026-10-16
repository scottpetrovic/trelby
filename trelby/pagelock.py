# -*- coding: utf-8 -*-

import re

# helpers for page locking. once pages are locked, each page keeps its
# label no matter how the script is edited. a label is one of:
#
#   "16"      a page that existed when the pages were locked
#   "15A"     pages added after page 15 (15A, 15B, ..., 15Z, 15ZA, ...)
#   "A1"      pages added before page 1 (A1, B1, ...)
#   "16-17"   pages 16 and 17 combined, after all of page 16's text was
#             deleted
#   "15.1"    pages added after page 15 when there's no letter left for
#             them, i.e. when page 15A is already locked (15.1, 15.2, ...)
#
# labels are compared by sort keys of the form (number, kind, letters,
# sub), where kind is 0 for "A1"-style labels and 1 for the others, and
# sub is the number after the ".", or 0. so A1 < B1 < 1 < 1.1 < 1A < 1AA
# < 1B < 2.

_labelRe = re.compile(r"^([A-Z]*)(\d+)([A-Z]*)(?:\.(\d+))?$")


# return sort key for a single (non-combined) label, or None if it's not
# valid.
def _key(s):
    m = _labelRe.match(s)

    if not m:
        return None

    prefix, num, suffix, sub = m.groups()
    sub = int(sub or 0)

    if (prefix and suffix) or (sub == 0 and m.group(4) is not None):
        return None

    if prefix:
        return (int(num), 0, prefix, sub)

    return (int(num), 1, suffix, sub)


# opposite of _key
def _label(key):
    num, kind, letters, sub = key

    if kind == 0:
        s = "%s%d" % (letters, num)
    else:
        s = "%d%s" % (num, letters)

    if sub:
        s += ".%d" % sub

    return s


# return (firstKey, lastKey) for the given label, or None if it's not
# valid. for non-combined labels both are the same.
def labelRange(label):
    if not isinstance(label, str):
        return None

    parts = label.split("-")

    if len(parts) > 2:
        return None

    keys = [_key(p) for p in parts]

    if None in keys:
        return None

    if (len(keys) == 2) and (keys[1] <= keys[0]):
        return None

    return (keys[0], keys[-1])


def isValid(label):
    return labelRange(label) is not None


# normalize user input (e.g. " 15a ") to label form ("15A")
def normalize(s):
    return s.strip().upper()


# return the label for the combination of the given labels, i.e. what a
# page is called when all the text of page 'first' has been deleted and
# it has been combined with the following page 'second'. if they can't be
# combined (they're out of order), returns 'second'.
def combine(first, second):
    r1 = labelRange(first)
    r2 = labelRange(second)

    if not r1:
        return second

    if not r2:
        return first

    if r1[1] >= r2[0]:
        return second

    return _label(r1[0]) + "-" + _label(r2[1])


# next letter sequence after the given one: "" -> "A", "A" -> "B", "Z" ->
# "ZA".
def _nextLetters(s):
    if not s:
        return "A"

    if s[-1] < "Z":
        return s[:-1] + chr(ord(s[-1]) + 1)

    return s + "A"


# return the sort key of the page following the one with the given key,
# which must sort before 'bound' (the key of the next locked page, or None
# if there is none). in the very unlikely case that there is no room left
# before 'bound', the result may sort after it.
def _keyAfter(key, bound):
    num, kind, letters, sub = key

    if sub == 0:
        cand = (num, kind, _nextLetters(letters), 0)

        if bound and (cand >= bound):
            cand = (num, kind, letters + "A", 0)

        if not bound or (cand < bound):
            return cand

    return (num, kind, letters, sub + 1)


# return a list of labels for 'count' pages that follow a page with the
# given sort key. see _keyAfter.
def _labelsAfter(key, bound, count):
    ret = []

    while len(ret) < count:
        key = _keyAfter(key, bound)
        ret.append(_label(key))

    return ret


# return labels for 'count' pages starting at a page locked with the
# given label (the first page gets that label, the rest are A-pages
# after it). nextLabel is the label of the next locked page, or None.
def segmentLabels(label, nextLabel, count):
    if count < 1:
        return []

    bound = labelRange(nextLabel)[0] if nextLabel else None

    return [label] + _labelsAfter(labelRange(label)[1], bound, count - 1)


# return labels for 'count' pages that come before the first locked page,
# whose label is firstLabel (A1, B1, ... when that is page 1).
def labelsBefore(firstLabel, count):
    num = labelRange(firstLabel)[0][0]

    return _labelsAfter((num, 0, "", 0), labelRange(firstLabel)[0], count)


# given a list of (line, label) tuples sorted by line, return the longest
# subsequence whose labels are in increasing order. page locks normally
# are in order, but moving text around can leave some out of place, and
# those are ignored.
def orderedLocks(locks):
    ranges = [labelRange(label) for line, label in locks]

    # fast path for the usual case
    if all(ranges[i - 1][1] < ranges[i][0] for i in range(1, len(ranges))):
        return locks

    n = len(locks)

    # best[i] = length of the longest valid chain ending at i, prev[i] =
    # previous index in that chain or -1
    best = [1] * n
    prev = [-1] * n

    for i in range(n):
        for j in range(i):
            if (ranges[j][1] < ranges[i][0]) and (best[j] + 1 > best[i]):
                best[i] = best[j] + 1
                prev[i] = j

    i = best.index(max(best))
    ret = []

    while i != -1:
        ret.append(locks[i])
        i = prev[i]

    ret.reverse()

    return ret


# scene locking uses the same labels, except for combined ones: once
# scenes are locked, each scene heading keeps its number, scenes added
# after scene 15 become 15A, 15B, ..., and scenes added before scene 1
# become A1, B1, .... deleting a scene leaves a gap in the numbering.


def isValidScene(label):
    return isValid(label) and ("-" not in label)


# given the number of scenes and a {index: label} dict of the locked ones
# (index being 0 for the first scene, labels valid and distinct), return
# the labels of all the scenes. locked scenes keep their labels. the
# others get labels after the previous scene's, before the next locked
# scene's, skipping labels any locked scene has. locked scenes that are
# out of order (they were moved) keep their labels too, but don't affect
# the others'.
def sceneLabels(count, locks):
    if not locks:
        return [str(i + 1) for i in range(count)]

    anchors = orderedLocks(sorted(locks.items()))
    used = {labelRange(label)[0] for label in locks.values()}

    # sort key of the previous scene, starting at the "before" form of
    # the first anchor so that scenes before it become A1, B1, ... (or
    # 0A, 0B, ... before A1, which nothing else sorts before)
    first = labelRange(anchors[0][1])[0]

    if first[1:3] == (0, "A"):
        prev = (first[0] - 1, 1, "", 0)
    else:
        prev = (first[0], 0, "", 0)

    # index into anchors of the next anchor
    a = 0

    ret = []

    for i in range(count):
        if (a < len(anchors)) and (anchors[a][0] == i):
            prev = labelRange(anchors[a][1])[0]
            a += 1
            ret.append(locks[i])

        elif i in locks:
            ret.append(locks[i])

        else:
            bound = labelRange(anchors[a][1])[0] if a < len(anchors) else None

            key = _keyAfter(prev, bound)
            while key in used:
                key = _keyAfter(key, bound)

            prev = key
            ret.append(_label(key))

    return ret
