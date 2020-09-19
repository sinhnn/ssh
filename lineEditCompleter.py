#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  LineCompleter.py Author "sinhnn <sinhnn.92@gmail.com>" Date 23.04.2020


from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from watch_file import WatchFile


class LineEditCompleter(QtWidgets.QLineEdit):
    def __init__(self, completer_file, *args, **kwargs):
        QtWidgets.QLineEdit.__init__(self, *args, **kwargs)

        self._complete_file = WatchFile(completer_file)
        self._completer = QtWidgets.QCompleter()
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.model = QtCore.QStringListModel()
        self._completer.setModel(self.model)
        self._completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.updateCompleter()

        self.setCompleter(self._completer)
        # self.textChanged.connect(self._showOnlyRowContainText)

        self.returnPressed.connect(self.appendToCompleter)

    def updateCompleter(self):
        self._completer.model().setStringList(self._complete_file.to_list())

    def appendToCompleter(self):
        line = self.text().strip()
        m = self._completer.model()
        if line in m.stringList():
            return

        fp = open(self._complete_file.path, 'a')
        fp.write(line.strip() + '\n')
        fp.close()
        m.insertRow(m.rowCount())
        index = m.index(m.rowCount() - 1, 0)
        m.setData(index, line.strip())


def main(): 
    import sys
    app = QtWidgets.QApplication(sys.argv)
    lineedit = LineEditCompleter(completer_file='bash_history')
    lineedit.show()
    sys.exit(app.exec_())


if __name__ == "__main__": 
    main()
