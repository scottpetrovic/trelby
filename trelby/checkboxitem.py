# an item in a list the user can tick items in (checkboxdlg.CheckBoxDlg),
# e.g. the characters to include in a report. it doesn't need wx, so the
# reports can use it without the GUI.
class CheckBoxItem:
    def __init__(self, text, selected=True, cdata=None):
        self.text = text
        self.selected = selected
        self.cdata = cdata

    # return dict which has keys for all selected items' client data.
    # takes a list of CheckBoxItem's as its parameter. note: this is a
    # static function.
    @staticmethod
    def getClientData(cbil):
        tmp = {}

        for i in range(len(cbil)):
            cbi = cbil[i]

            if cbi.selected:
                tmp[cbi.cdata] = None

        return tmp
