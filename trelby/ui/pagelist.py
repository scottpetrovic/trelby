# -*- coding: utf-8 -*-


# keeps a collection of page numbers from a given screenplay, and allows
# formatting of the list intelligently, e.g. "4-7, 9, 11-16".
class PageList:
    def __init__(self, allPages):
        # list of all pages in the screenplay, in the format returned by
        # Screenplay.getPageNumbers().
        self.allPages = allPages

        # the page numbers (str) in the list
        self.pages = set()

    # add page to page list if it's not already there
    def addPage(self, page):
        self.pages.add(str(page))

    def __len__(self):
        return len(self.pages)

    # merge two PageLists
    def __iadd__(self, other):
        self.pages |= other.pages

        return self

    # return textual representation of pages where consecutive pages are
    # formatted as "x-y". example: "3, 5-8, 11".
    def __str__(self):
        # one entry for each page from above, containing True if that page
        # is contained in this PageList object
        hasPage = [p in self.pages for p in self.allPages]

        # finished string
        s = ""

        # start index of current range, or -1 if no range in progress
        rangeStart = -1

        for i in range(len(self.allPages)):
            if rangeStart != -1:
                if not hasPage[i]:

                    # range ends

                    if i != (rangeStart + 1):
                        s += "-%s" % self.allPages[i - 1]

                    rangeStart = -1
            else:
                if hasPage[i]:
                    if s:
                        s += ", "

                    s += self.allPages[i]
                    rangeStart = i

        last = len(self.allPages) - 1

        # finish last range if needed
        if (rangeStart != -1) and (rangeStart != last):
            s += "-%s" % self.allPages[last]

        return s
