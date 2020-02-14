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

__PATH__ = os.path.dirname(os.path.abspath(__file__))
class ChooseCommandDialog(QtWidgets.QDialog):
    __PRESET_CMD_DIR__ = os.path.join(__PATH__, 'preset')
    def __init__(self, parent, **kwargs):
        QtWidgets.QDialog.__init__(self, **kwargs)
        self.setWindowTitle("Choose command")
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)
        self.initUI()

    def initUI(self):
        layout = QtWidgets.QGridLayout()
        self.buttonBox = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.command = QtWidgets.QLineEdit(self)

        self.presetBox = QtWidgets.QComboBox(self)
        presetBoxModel = ComboBoxModel(self.__load_preset__())
        self.presetBox.setModel(presetBoxModel)
        self.presetBox.currentIndexChanged.connect(self.__show_preset_value__)

        self.browser = QtWidgets.QPushButton("Browser",self)
        self.browser.clicked.connect(self.__browser__)

        layout.addWidget(self.command, 0, 0, 2, 2)
        layout.addWidget(self.presetBox, 2, 0)
        layout.addWidget(self.browser, 2, 1)
        layout.addWidget(self.buttonBox, 3,0)
        layout.setColumnStretch(0,1)
        layout.setRowStretch(0,1)

        self.setMinimumWidth(600)
        self.setLayout(layout)

    def getResult(self):
        self.exec_()
        return self.command.text()

    def __browser__(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        files, _ = dialog.getOpenFileNames(self, 'Shell script file')
        if not files: return
        self.command.setText(files[0])

    def __show_preset_value__(self, index):
        item = self.presetBox.model().itemAtRow(index)
        self.command.setText(item['value'])

    def __load_preset__ (self):
        results=  []
        for entry in os.scandir(ChooseCommandDialog.__PRESET_CMD_DIR__):
            if entry.is_dir() :
                continue
            if not re.search(r'.preset.json$', entry.name):
                continue

            command = self.__load_preset_file__(entry.path)
            if command: results.append(command)
        return results

    def __load_preset_file__(self, path):
        fp = open(path, 'r')
        command = json.load(fp)
        fp.close()

        for k in ['name', 'value']:
            if k not in command.keys():
                logging.error('unable to parse preset file {}'.format(path))
                return {}
        return command
    

__SSH_DIR__ =  os.path.join(__PATH__, 'ssh')

def load_ssh_dir (dir):
    results=  []
    for entry in os.scandir(dir):
        if entry.is_dir() :
            continue
        if not re.search(r'.json$', entry.name):
            continue

        server = __load_ssh_file__(entry.path)
        if server:
            results.append(server)
    return results


def __load_ssh_file__(path):
    fp = open(path, 'r')
    info = json.load(fp)
    fp.close()

    client = ssh.SSHClient(info=info)
    if client.is_valid(): return client
    return {}
    # return None

class SSHTable(QTableView):
    def __init__(self, data=[], dir=__SSH_DIR__, **kwargs):
        QTableView.__init__(self, **kwargs)
        # self.dir = dir
        self.data = data
        if not self.data:
            self.data = load_ssh_dir(dir)
            self.dir = dir
        self.createTable()

    def createTable(self):
        self.horizontalHeader().setStretchLastSection(True);
        tm = MyTableModel(data=self.data, parent=self) 
        self.setModel(tm)
        self.setSortingEnabled(True)


    def contextMenuEvent(self, event): 
        self.menu = QMenu(self)
        self.actions = {
            'open' : self.open,
            'vncviewer' : self.open_vncviewer,
            'close' : self.close,
            'upload' : self.upload,
            'command' : self.exec_command, # from file or command
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.exec_(QtGui.QCursor.pos())


    def __event2item__(self, event):
        print(event.pos())
        row = self.rowAt(event.pos().y())
        return self.model().itemAtRow(row)

    def selectedItems(self):
        return [self.model().itemAtRow(i.row()) for i in self.selectedIndexes()]

    def exec_command(self):
        dialog = ChooseCommandDialog(parent=self)
        r = dialog.getResult()
        if not r: return
        for item in self.selectedItems():
            print('{} executing {}'.format(item.config['hostname'], r))
            (din, out, err) = item.exec_command(r)
            print(din, out, err)

    def open_vncviewer(self):
        for item in self.selectedItems():
            item.open_vncviewer()

    def upload(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True);
        dialog.setFileMode(QtWidgets.QFileDialog.Directory |
                QtWidgets.QFileDialog.ExistingFiles)
        files, _ = dialog.getOpenFileNames(self, 'Upload files')
        if not files: return

        for item in self.selectedItems():
            print(item)
            # item.upload(files)

    def download(self, path):
        for item in self.selectedItems():
            print(item)

    def open(self):
        for item in self.selectedItems():
            print("open")
            
    def close(self):
        for item in self.selectedItems():
            item.close()


def main(): 
    import logging
    logging.basicConfig(level=logging.INFO,
            format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s', datefmt='%m-%d %H:%M')

    app = QApplication(sys.argv) 
    w = SSHTable() 
    w.show() 
    sys.exit(app.exec_()) 
	
if __name__ == "__main__": 
    main()

