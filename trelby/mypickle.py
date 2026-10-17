import copy

import trelby.config as config
import trelby.textutil as textutil
import trelby.util as util


# keep track about one object's variables
#
# settings are saved as plain text, one "Name:value" line per variable.
# nested objects prepend a slash-separated prefix to their names, so e.g.
# the per-script config's action element is saved as lines like
# "Element/Action/Indent:0" and "Element/Action/Screen/AllCaps:False".
#
# a class using this keeps one Vars, shared by all its instances, in its
# class attribute 'cvars', built by the first instance's __init__ (see
# config.TextType for the pattern). setDefaults then gives each instance
# its own copy of the defaults as ordinary attributes.
class Vars:
    def __init__(self):
        self.cvars = []

    def __iter__(self):
        for v in self.cvars:
            yield v

    # make various dictionaries pointing to the config variables. must be
    # called after the last add*, as getDefault/getMin/getMax (e.g. the
    # settings pages' spin control ranges) and the recalc methods that
    # clamp numeric values use these; a class that
    # never calls them (e.g. config.TextType) can skip this.
    def makeDicts(self):
        self.all = self.getDict()
        self.numeric = self.getDict(NumericVar)
        self.stringLatin1 = self.getDict(StrLatin1Var)

    # return dictionary containing given type of variable objects, or all
    # if typeObj is None.
    def getDict(self, typeObj=None):
        tmp = {}

        for it in self.cvars:
            if not typeObj or isinstance(it, typeObj):
                tmp[it.name] = it

        return tmp

    # get default value of a setting
    def getDefault(self, name):
        return self.all[name].defVal

    # get minimum value of a numeric setting
    def getMin(self, name):
        return self.numeric[name].minVal

    # get maximum value of a numeric setting
    def getMax(self, name):
        return self.numeric[name].maxVal

    # get minimum and maximum value of a numeric setting as a (min,max)
    # tuple.
    def getMinMax(self, name):
        return (self.getMin(name), self.getMax(name))

    def setDefaults(self, obj):
        for it in self.cvars:
            setattr(obj, it.name, copy.deepcopy(it.defVal))

    # transform string 's' (loaded from file) into a form suitable for
    # load() to take: a dict of full name (prefix included) -> value
    # string. lines are split at the first ":", so values may contain ":"
    # but names can't. lines without one are ignored, and a name that
    # appears twice gets the later value.
    @staticmethod
    def makeVals(s):
        tmp = textutil.fixNL(str(s)).split("\n")

        vals = {}
        for it in tmp:
            if it.find(":") != -1:
                name, v = it.split(":", 1)
                vals[name] = v

        return vals

    def save(self, prefix, obj):
        s = ""

        for it in self.cvars:
            if it.name2:
                s += it.toStr(getattr(obj, it.name), prefix + it.name2)

        return s

    # set obj's variables from vals (see makeVals). a variable missing from
    # vals keeps its current value, normally its default, so files from
    # older versions without newer settings load fine.
    def load(self, vals, prefix, obj):
        for it in self.cvars:
            if it.name2:
                name = prefix + it.name2
                if name in vals:
                    res = it.fromStr(vals, vals[name], name)
                    setattr(obj, it.name, res)
                    del vals[name]

    def addVar(self, var):
        self.cvars.append(var)

    def addBool(self, *params):
        self.addVar(BoolVar(*params))

    def addFloat(self, *params):
        self.addVar(FloatVar(*params))

    def addInt(self, *params):
        self.addVar(IntVar(*params))

    def addStrLatin1(self, *params):
        self.addVar(StrLatin1Var(*params))

    def addStrUnicode(self, *params):
        self.addVar(StrUnicodeVar(*params))

    def addStrBinary(self, *params):
        self.addVar(StrBinaryVar(*params))

    def addElemName(self, *params):
        self.addVar(ElementNameVar(*params))

    def addList(self, *params):
        self.addVar(ListVar(*params))


class ConfVar:
    # name2 is the name to use while saving/loading the variable. if it's
    # empty, the variable is not loaded/saved, i.e. is used only
    # internally.
    def __init__(self, name, defVal, name2):
        self.name = name
        self.defVal = defVal
        self.name2 = name2


class BoolVar(ConfVar):
    def __init__(self, name, defVal, name2):
        ConfVar.__init__(self, name, defVal, name2)

    def toStr(self, val, prefix):
        return "%s:%s\n" % (prefix, str(bool(val)))

    def fromStr(self, vals, val, prefix):
        return val == "True"


class NumericVar(ConfVar):
    def __init__(self, name, defVal, name2, minVal, maxVal):
        ConfVar.__init__(self, name, defVal, name2)
        self.minVal = minVal
        self.maxVal = maxVal


class FloatVar(NumericVar):
    def __init__(self, name, defVal, name2, minVal, maxVal, precision=2):
        NumericVar.__init__(self, name, defVal, name2, minVal, maxVal)
        self.precision = precision

    def toStr(self, val, prefix):
        return "%s:%.*f\n" % (prefix, self.precision, val)

    def fromStr(self, vals, val, prefix):
        return util.str2float(val, self.defVal, self.minVal, self.maxVal)


class IntVar(NumericVar):
    def __init__(self, name, defVal, name2, minVal, maxVal):
        NumericVar.__init__(self, name, defVal, name2, minVal, maxVal)

    def toStr(self, val, prefix):
        return "%s:%d\n" % (prefix, val)

    def fromStr(self, vals, val, prefix):
        return util.str2int(val, self.defVal, self.minVal, self.maxVal)


# originally an ISO-8859-1 (Latin 1) string. textutil.toUTF8/fromUTF8 no longer
# convert anything, so it now holds any Unicode text, like StrUnicodeVar.
# the remaining difference is that Config.recalc passes Config's own
# variables of this type through textutil.toInputStr (see Vars.stringLatin1).
class StrLatin1Var(ConfVar):
    def __init__(self, name, defVal, name2):
        ConfVar.__init__(self, name, defVal, name2)

    def toStr(self, val, prefix):
        return "%s:%s\n" % (prefix, textutil.toUTF8(val))

    def fromStr(self, vals, val, prefix):
        return textutil.fromUTF8(val)


# Unicode string.
class StrUnicodeVar(ConfVar):
    def __init__(self, name, defVal, name2):
        ConfVar.__init__(self, name, defVal, name2)

    def toStr(self, val, prefix):
        return "%s:%s\n" % (prefix, str(val))

    def fromStr(self, vals, val, prefix):
        return val


# binary string, can contain anything. characters outside of printable
# ASCII (and \ itself) are escaped with their hex code: \XX up to U+00FF,
# \uXXXX or \UXXXXXXXX above that (see textutil.encodeStr).
class StrBinaryVar(ConfVar):
    def __init__(self, name, defVal, name2):
        ConfVar.__init__(self, name, defVal, name2)

    def toStr(self, val, prefix):
        return "%s:%s\n" % (prefix, textutil.encodeStr(val))

    def fromStr(self, vals, val, prefix):
        return textutil.decodeStr(val)


# screenplay.ACTION <-> "Action"
class ElementNameVar(ConfVar):
    def __init__(self, name, defVal, name2):
        ConfVar.__init__(self, name, defVal, name2)

    def toStr(self, val, prefix):
        return "%s:%s\n" % (prefix, config.lt2ti(val).name)

    def fromStr(self, vals, val, prefix):
        # e.g. "Note", which isn't an element type anymore
        ti = config.name2ti(val, False)

        if ti:
            return ti.lt
        else:
            return self.defVal


# a list, saved as its length followed by one line per item, numbered
# from 1, e.g. "Command/Undo/Keys:2", "Command/Undo/Keys/1:...",
# "Command/Undo/Keys/2:...". the item type's own name2 is not used.
class ListVar(ConfVar):
    def __init__(self, name, defVal, name2, itemType):
        ConfVar.__init__(self, name, defVal, name2)

        # itemType is an instance of one of the *Var classes, and is the
        # type of item contained in the list.
        self.itemType = itemType

    def toStr(self, val, prefix):
        s = ""

        s += "%s:%d\n" % (prefix, len(val))

        i = 1
        for v in val:
            s += self.itemType.toStr(v, prefix + "/%d" % i)
            i += 1

        return s

    def fromStr(self, vals, val, prefix):
        # 1000 is totally arbitrary, increase if needed
        count = util.str2int(val, -1, -1, 1000)
        if count == -1:
            return copy.deepcopy(self.defVal)

        tmp = []
        for i in range(1, count + 1):
            name = prefix + "/%d" % i

            if name in vals:
                res = self.itemType.fromStr(vals, vals[name], name)
                tmp.append(res)
                del vals[name]

        return tmp
