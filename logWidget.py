#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  auto_upload.py Author "sinhnn <sinhnn.92@gmail.com>" Date 20.10.2019
import sys
import threading
import os
import time
import datetime
from PyQt5.QtWidgets import (
        QMainWindow, QApplication, QWidget, QAction,
        QTableView, QTableWidget,QTableWidgetItem, QHeaderView,
        QVBoxLayout, QGridLayout, QHBoxLayout,
        QPushButton, QLineEdit, QShortcut, QPlainTextEdit, QTextEdit, QComboBox,
        QMenu, QAbstractItemView,QStyle, QStyleOptionTitleBar,
        QLabel,QSpacerItem, QCheckBox
        )
from PyQt5.QtGui import *
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5 import QtWidgets
from PyQt5.QtCore import *

COLOR_NEED_ACTION = QColor(255, 204, 204)
COLOR_BUTTON = QColor("#99ccff")
 
import re
import subprocess
import tailer
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from widgets.highlight import KeywordHighlighter

class LogWidget(QWidget):
    def __init__(self, files,**kwargs):
        super().__init__()
        self.watchFiles = files
        self.numbLogLine  = 200
        self.currentLogFile = files[0]
        self.initUI()
        # self.initRefreshThreads()

    def set_numbLogLine(self, i):
        self.numbLogLine =  i

    def initUI(self):
        self.layout = QVBoxLayout()
        self.initLogFileChooser()
        self.initLogDisplay()
        self.layout.addWidget(self.displayLog)
        self.setLayout(self.layout) 
        self.initShortcut()
        self.show()
    
    def initShortcut(self):
        pass


    def _filter(self, line, date=None):
        o = True
        if self.errors.isChecked():
            o = o and bool(re.search(r"errors?|critical", line, flags=re.I))
        if self.today.isChecked() and date:
            o = o and bool(re.match(r"{}".format(date), line))
        return o

    def initLogFileChooser(self):
        layout = QHBoxLayout()

        self.comboBox = QComboBox(self)
        for f in self.watchFiles:
            self.comboBox.addItem(f)
        self.comboBox.setFixedWidth(200)
        self.comboBox.currentTextChanged.connect(self.refreshLog)
        self.currentLogFile = self.watchFiles[0]

        self.lineNumbWidget = QLineEdit()
        self.lineNumbWidget.setMaximumWidth(100)
        label = QLabel("NumberLine")
        self.fullLog = QCheckBox("FullLog", self) 
        self.fullLog.stateChanged.connect(self.refreshLog)

        self.errors = QCheckBox("Error", self) 
        self.today = QCheckBox("Today", self) 
        self.today.setCheckState(Qt.Checked)
        self.errors.stateChanged.connect(self.refreshLog)
        self.today.stateChanged.connect(self.refreshLog)

        layout.addWidget(self.comboBox)
        layout.addWidget(self.lineNumbWidget, Qt.AlignRight)
        layout.addWidget(label)
        layout.addWidget(self.errors)
        layout.addWidget(self.today)
        layout.addWidget(self.fullLog)
        layout.addSpacerItem(QSpacerItem(10,0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding))
        # layout.addSpacing(100)
        self.layout.addLayout(layout)

    def updateLogFile(self, path):
        self.currentLogFile = path
        
    def initWatcher(self):
        self.watcher = QFileSystemWatcher(self.watchFiles)
        # self.watcher.fileChanged.connect(lambda path: self.refreshLog(path, self.numbLogLine, self.fullLog.isChecked()))
        self.watcher.fileChanged.connect(self.refreshLog)

    def initLogDisplay(self):
        self.logWatchs = []
        self.initWatcher()
        self.font = QFont("Consolas", 10)
        self.displayLog = QTextEdit(self)
        self.displayLog.setReadOnly(True)
        self.displayLog.setFont(self.font)
        self.refreshLog()
        self.highlighter = KeywordHighlighter(self.displayLog.document())
        self.displayLog.verticalScrollBar().setValue(self.displayLog.verticalScrollBar().maximum())
        self.displayLog.moveCursor(QTextCursor.End)

    def _full_log(self, full):
        if full == False:
            self.refreshLog(self.currentLogFile, self.numbLogLine, False)
            return 
        self.displayLog.clear()
        t = '\n'.join(tailer.tail(open(self.currentLogFile), 1000))
        self.displayLog.setText(t)
        # fp = open(self.currentLogFile, 'r', encoding='utf-8-sig', errors='ignore' ).read()
        # self.displayLog.setPlainText(fp)
        # fp = open(self.currentLogFile, 'r', encoding='utf-8-sig', errors='ignore' )
        # line = fp.readline()
        # while (line):
        #     self.displayLog.insertPlainText(line)
        #     line = fp.readline()
        # fp.close()
        # return

    def refreshLog(self):
        path = self.comboBox.currentText()
        # numbLine = int(self.lineNumbWidget.text())
        numbLine = self.numbLogLine
        fullLog = self.fullLog.isChecked()
        today = datetime.date.today().strftime("%Y-%m-%d")
        regex = r'{}'.format(today)
        self.__refreshLog__(self.comboBox.currentText(), numbLine, self.fullLog.isChecked(), lambda l: self._filter(l, today))

    def __refreshLog__(self, path, numbLine, full, afilter=None):
        self.currentLogFile = path
        self.numbLogLine = numbLine
        self.watcher.addPath(self.currentLogFile) # check is exist
        try:
            if self.numbLogLine <= 0 or full == True:
                numbLogLine = 10000
            t = filter(afilter, tailer.tail(open(path), numbLine))
        except Exception as e:
            logging.error('unable to load {} because of {}'.format(path, e))
            t = []
        self.displayLog.setFont(self.font)
        self.displayLog.setText('\n'.join(t))
        self.displayLog.verticalScrollBar().setValue(self.displayLog.verticalScrollBar().maximum())
        self.displayLog.moveCursor(QTextCursor.End)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    files=[r"E:\work-snn\autoupload.log", r"E:\work-dnn\autoupload.log"]
    ex = LogWidget(files)
    sys.exit(app.exec_())
