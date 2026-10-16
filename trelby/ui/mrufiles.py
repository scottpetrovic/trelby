import os

import wx


# handles the "Most recently used" list of files, shown in its own menu
# (File/Open Recent).
class MRUFiles:
    def __init__(self, maxCount):
        # max number of items
        self.maxCount = maxCount

        # items (Unicode strings)
        self.items = []

        # menu showing the items, set by useMenu
        self.menu = None

        # contiguous menu ids, since the frame binds them as one
        # EVT_MENU_RANGE and gets the item's index as id - firstId. keep the
        # refs alive so wx doesn't reuse them; store plain ints since the
        # code below does arithmetic on them.
        self.idRefs = wx.NewIdRef(count=self.maxCount)
        if self.maxCount == 1:
            self.idRefs = [self.idRefs]

        self.firstId = int(self.idRefs[0])
        self.lastId = int(self.idRefs[-1])

        # "Clear Recent Files" menu item
        self.clearId = wx.NewIdRef()

    # use given (dedicated) menu. its contents are owned by this object.
    def useMenu(self, menu):
        self.menu = menu
        self.updateMenu()

    # return (firstMenuId, lastMenuId).
    def getIds(self):
        return (self.firstId, self.lastId)

    # add item to top of list.
    def add(self, s):
        s = str(s)

        # if item already exists, remove it
        if s in self.items:
            self.items.remove(s)

        self.items.insert(0, s)

        # prune overlong list
        del self.items[self.maxCount :]

        self.updateMenu()

    # remove item number 'i'.
    def remove(self, i):
        del self.items[i]
        self.updateMenu()

    # remove all items.
    def clear(self):
        self.items = []
        self.updateMenu()

    # rebuild the menu from the current items.
    def updateMenu(self):
        if not self.menu:
            return

        for it in list(self.menu.GetMenuItems()):
            self.menu.Delete(it)

        if not self.items:
            self.menu.Append(wx.ID_ANY, _("No recent files")).Enable(False)

        for i in range(self.getCount()):
            self.menu.Append(
                self.firstId + i,
                "&%d %s" % (i + 1, os.path.basename(self.get(i))),
            )

        self.menu.AppendSeparator()
        self.menu.Append(self.clearId, _("Clear Recent Files")).Enable(
            bool(self.items)
        )

    # return number of items.
    def getCount(self):
        return len(self.items)

    # get item number 'i'.
    def get(self, i):
        return str(self.items[i])
