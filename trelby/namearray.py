import array
import collections
import random


# the name database, as parallel arrays indexed by name number: name[i],
# type[i] (a type id, see typeNamesById) and sex[i]. the types and sexes
# are byte arrays (so there can be at most 256 types), and the arrays are
# allocated up front, which keeps the memory use and load time of the
# ~200,000 names down.
class NameArray:
    def __init__(self):
        # room for the names in names.txt, without growing the arrays
        self.maxCount = 205000
        self.count = 0

        self.name = [None] * self.maxCount
        self.type = array.array("B")
        self.type.frombytes(str.encode(chr(0) * self.maxCount))

        # 0 = female, 1 = male
        self.sex = array.array("B")
        self.sex.frombytes(str.encode(chr(0) * self.maxCount))

        # key = type name, value = count of names for that type
        self.typeNamesCnt = collections.defaultdict(int)

        # key = type name, value = integer id for that type
        self.typeId = {}

        # type names indexed by their integer id
        self.typeNamesById = []

    def append(self, name, type, sex):
        if self.count >= self.maxCount:
            for i in range(1000):
                self.name.append(None)
                self.type.append(0)
                self.sex.append(0)

            self.maxCount += 1000

        typeId = self.addType(type)

        self.name[self.count] = name
        self.type[self.count] = typeId
        self.sex[self.count] = 0 if sex == "F" else 1

        self.count += 1

    def addType(self, type):
        self.typeNamesCnt[type] += 1

        typeId = self.typeId.get(type)

        if typeId is None:
            typeId = len(self.typeNamesById)
            self.typeId[type] = typeId
            self.typeNamesById.append(type)

        return typeId

    # return up to 'count' different names picked at random. 'typeIds' is
    # a collection of type ids to pick from, or None for all types. 'sex'
    # is 0 for female names, 1 for male names, or None for both. 'rng' is
    # a random.Random-like object.
    def randomNames(self, count, typeIds=None, sex=None, rng=random):
        candidates = [
            i
            for i in range(self.count)
            if ((typeIds is None) or (self.type[i] in typeIds))
            and ((sex is None) or (self.sex[i] == sex))
        ]

        # the same name can be listed under several types, so pick extra
        # ones to have enough left after removing duplicates
        picked = rng.sample(candidates, min(count * 3, len(candidates)))

        names = []

        for i in picked:
            if self.name[i] not in names:
                names.append(self.name[i])

                if len(names) == count:
                    break

        return names
