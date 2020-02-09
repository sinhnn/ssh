#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  ObjectList2TableModel.py Author "sinhnn <sinhnn.92@gmail.com>" Date 16.12.2019

import sys
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QAction, QTableView,QVBoxLayout, QAbstractItemView, QMenu
from PyQt5.QtGui import QIcon
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSlot
from ObjectsTableModel import (
        ObjectsTableModel as MyTableModel,
        )

import random
import ssh

INFO = [1, 2, 4, 5]
class Test(QTableView):
    def __init__(self, **kwargs):
        QTableView.__init__(self, **kwargs)

        self.tabledata = []
        for i in range(10):
            self.tabledata.append(ssh.SSHClient(config={'username': i,
                'hostname':'192.168.1.{}'.format(i),
                'key_filename':'/where/to/identify_file_{}'.format(i),
                }))

        self.createTable()

    def contextMenuEvent(self, event): 
        self.menu = QMenu(self)
        self.actions = {
                'open' : lambda : self.open(event),
                'close' : lambda : self.close(event),
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.exec_(QtGui.QCursor.pos())
        # self.menu.exec_(event.pos())

		
    def createTable(self):
        self.horizontalHeader().setStretchLastSection(True);
        tm = MyTableModel(data=self.tabledata, parent=self) 
        self.setModel(tm)
        self.setSortingEnabled(True)

    def open(self, event):
        row = self.rowAt(event.pos().y())
        col = self.columnAt(event.pos().x())
        print('open at {} {}'.format(row, col))

    def close(self, event):
        row = self.rowAt(event.pos().y())
        col = self.columnAt(event.pos().x())
        print('close at {} {}'.format(row, col))



def main(): 
    import logging
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger()
    logging.basicConfig(level=logging.DEBUG,
            format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s %(message)s', datefmt='%m-%d %H:%M')

    app = QApplication(sys.argv) 
    w = Test() 
    w.show() 
    sys.exit(app.exec_()) 
	
if __name__ == "__main__": 
    main()

