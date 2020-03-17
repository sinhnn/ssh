import sys, re, os
import json
from PyQt5 import QtGui, QtCore, QtWidgets


class URLWidget(QtWidgets.QWidget):
    """Docstring for URLForm. """
    def __init__(self, parent=None, **kwargs):
        """TODO: to be defined.

        :parent: TODO
        :**kwargs: TODO

        """
        QtWidgets.QWidget.__init__(self, parent, **kwargs)
        self._parent = parent
        self.UI()

    def UI(self):
        layout = QtWidgets.QHBoxLayout()
        # layout.setContentsMargins(0,0,0,0)
        self.urlW = QtWidgets.QLineEdit(self)
        self.urlW.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.urlW.setMinimumWidth(400)
        self.viewCountW = QtWidgets.QLineEdit(str(2), self)
        self.viewCountW.setFixedWidth(30)
        self.durationW = QtWidgets.QLineEdit(str(1800), self)
        self.durationW.setFixedWidth(30)

    
        layout.addWidget(QtWidgets.QLabel("URL"))
        layout.addWidget(self.urlW)
        layout.addWidget(QtWidgets.QLabel("Count"))
        layout.addWidget(self.viewCountW)
        layout.addWidget(QtWidgets.QLabel("Duration"))
        layout.addWidget(self.durationW)

        self.setLayout(layout)

    def __str__(self):
        return str(self.toDict())

    def toDict(self):
        return {
            'url': self.urlW.text().strip(),
            'viewcount': int(self.viewCountW.text().strip()),
            'duration': int(self.durationW.text().strip())
        }



class URLForm(QtWidgets.QDialog):
    """docstring for URLForm"""
    def __init__(self, parent=None, **kwargs):
        QtWidgets.QDialog.__init__(self, parent, **kwargs)
        self.urls = []
        self.UI()

    def UI(self):
        self._layout = QtWidgets.QVBoxLayout()
        self._layout.setSpacing(0)
        for i in range(0, 2):
            w = URLWidget(self)
            self.urls.append(w)
            self._layout.addWidget(w)

        self.addW = QtWidgets.QPushButton("Add", self)
        self.addW.setFixedWidth(100)
        self.button = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)

        self.button.accepted.connect(self.accept)
        self.button.rejected.connect(self.reject)
        self.addW.clicked.connect(self.add)

        self._layout.addWidget(self.addW, QtCore.Qt.AlignCenter)
        self._layout.addWidget(self.button)
        self.setLayout(self._layout)


    def add(self):
        w = URLWidget(self)
        self.urls.append(w)
        self._layout.removeWidget(self.addW)
        self._layout.removeWidget(self.button)
        self._layout.addWidget(w)
        self._layout.addWidget(self.addW, QtCore.Qt.AlignCenter)
        self._layout.addWidget(self.button)

    def __dict__(self):
        return [i.toDict() for i in self.urls]

    def __list__(self):
        return [i.toDict() for i in self.urls]

    def getResult(self):
        self.exec_()
        if self.result() == QtWidgets.QDialog.Rejected:
            return None
        return self.__list__()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv) 
    w = URLForm() 
    # w.show( 
    print(w.getResult())
    sys.exit(0) 
