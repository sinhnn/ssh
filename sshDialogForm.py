#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  ObjectList2TableModel.py Author "sinhnn <sinhnn.92@gmail.com>" Date 16.12.2019

import sys, re, os
import json
from PyQt5.QtWidgets import (
        QMainWindow, QApplication, QWidget,
        QAction, QTableView,QVBoxLayout, QAbstractItemView, QMenu,
)

from PyQt5.QtGui import QIcon
from PyQt5 import QtGui, QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot
from ObjectsTableModel import (
        ObjectsTableModel as MyTableModel,
        ComboBoxModel,
        )

import random
import ssh


class SSHInputDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, **kwargs):
        QtWidgets.QDialog.__init__(self, **kwargs)
        self.parent = parent
        self.setWindowTitle("Choose command")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QGridLayout()
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        layout.addWidget(QtWidgets.QLabel("Host Name/IP"), 0, 0)
        self.hostnameWidget = QtWidgets.QLineEdit(self)
        layout.addWidget(self.hostnameWidget, 0, 1)

        layout.addWidget(QtWidgets.QLabel("User Name"), 1, 0)
        self.usernameWidget = QtWidgets.QLineEdit(self)
        layout.addWidget(self.usernameWidget, 1, 1)

        layout.addWidget(QtWidgets.QLabel("Password"), 2, 0)
        self.passwordWidget = QtWidgets.QLineEdit(self)
        layout.addWidget(self.passwordWidget, 2, 1)

        self.browser = QtWidgets.QPushButton("Browser Key File")
        self.browser.clicked.connect(self.__browser__)
        layout.addWidget(self.browser, 3, 0)
        self.private_key_file = QtWidgets.QLineEdit(self)
        layout.addWidget(self.private_key_file, 3, 1)

        layout.addWidget(QtWidgets.QLabel("Tags"), 4, 0)
        self.tags = QtWidgets.QLineEdit(self)
        layout.addWidget(self.tags, 4, 1)

        layout.addWidget(self.buttonBox, 5, 1)

        layout.setColumnStretch(1,1)
        self.setMinimumWidth(400)
        self.setLayout(layout)

    def getResult(self):
        self.exec_()
        if self.result() == QtWidgets.QDialog.Rejected: return None

        info = { "config" : {
                'hostname' : self.hostnameWidget.text(),
                'username' : self.usernameWidget.text(),
                'password' : self.passwordWidget.text(),
                'key_filename' : self.private_key_file.text()
            },
            "tags" : [self.tags.text()]
        }
        config = info['config']
        if not config['hostname'] or not config['username'] or not (config['password'] or config['key_filename']):
            QtWidgets.QMessageBox.critical(self, "SSH Error", "Invalid SSH config")
            return None

        dialog = QtWidgets.QFileDialog()
        files, _ = dialog.getSaveFileName(None, "Create New File", self.hostnameWidget.text() + '.json',"*.json");
        if not files:
            return None
        with open(files, 'w') as fp:
            json.dump(info, fp, indent=4)
        return files

    def __browser__(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        files, _ = dialog.getOpenFileNames(self, 'Shell script file')
        if not files: return
        self.private_key_file.setText(str(files[0]))


# class ChooseCommandDialog(QtWidgets.QDialog):
    # __PRESET_CMD_DIR__ = os.path.join(__PATH__, 'preset')
    # def __init__(self, parent, **kwargs):
        # QtWidgets.QDialog.__init__(self, **kwargs)
        # self.setWindowTitle("Choose command")
        # self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        # self.initUI()

    # def initUI(self):
        # layout = QtWidgets.QGridLayout()
        # self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        # self.buttonBox.accepted.connect(self.accept)
        # self.buttonBox.rejected.connect(self.reject)

        # self.command = QtWidgets.QLineEdit(self)

        # self.presetBox = QtWidgets.QComboBox(self)
        # presetBoxModel = ComboBoxModel(self.__load_preset__())
        # self.presetBox.setModel(presetBoxModel)
        # self.presetBox.currentIndexChanged.connect(self.__show_preset_value__)

        # self.browser = QtWidgets.QPushButton("Browser",self)
        # self.browser.clicked.connect(self.__browser__)

        # layout.addWidget(self.command, 0, 0, 2, 2)
        # layout.addWidget(self.presetBox, 2, 0)
        # layout.addWidget(self.browser, 2, 1)
        # layout.addWidget(self.buttonBox, 3,0)
        # layout.setColumnStretch(0,1)
        # layout.setRowStretch(0,1)

        # self.setMinimumWidth(600)
        # self.setLayout(layout)

    # def getResult(self):
        # self.exec_()
        # return self.command.text()

    # def __browser__(self):
        # dialog = QtWidgets.QFileDialog(self)
        # dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        # files, _ = dialog.getOpenFileNames(self, 'Shell script file')
        # if not files: return
        # self.command.setText(files[0])

    # def __show_preset_value__(self, index):
        # item = self.presetBox.model().itemAtRow(index)
        # self.command.setText(item['value'])

    # def __load_preset__ (self):
        # results=  []
        # for entry in os.scandir(ChooseCommandDialog.__PRESET_CMD_DIR__):
            # if entry.is_dir() :
                # continue
            # if not re.search(r'.preset.json$', entry.name):
                # continue

            # command = self.__load_preset_file__(entry.path)
            # if command: results.append(command)
        # return results

    # def __load_preset_file__(self, path):
        # fp = open(path, 'r')
        # command = json.load(fp)
        # fp.close()

        # for k in ['name', 'value']:
            # if k not in command.keys():
                # logging.error('unable to parse preset file {}'.format(path))
                # return {}
        # return command
    


