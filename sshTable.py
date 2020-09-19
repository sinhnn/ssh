#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author "sinhnn <sinhnn.92@gmail.com>" Date 16.12.2019

import sys
import re
import os
import time
import threading
import io
# import subprocess
import json
import logging
from collections import OrderedDict
from functools import partial
import sys, csv, io


from PyQt5.QtWidgets import (
        QApplication,
        QTableView,
        QMenu,
)

# from PyQt5.QtGui import QIcon
from common import close_all
from PyQt5 import QtGui, QtCore, QtWidgets
# from PyQt5.QtCore import pyqtSlot
from lineEditCompleter import LineEditCompleter
from ObjectsTableModel import (
        ObjectsTableModel as MyTableModel,
        ComboBoxModel,
        )

# import random

# =============================================================================
import ssh
from ssh import load_ssh_file, load_ssh_dir
# import crypt
# from sshDialogForm import SCPDialog, SSHInputDialog
# from urlDialog import URLForm
from simplelistmodel import QObjectListModel
from sshContextMenu import SSHActions
from worker import Worker
# =============================================================================
__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ = os.path.join(__PATH__, 'ssh')


def path(*args):
    return os.path.join(__PATH__, *args)


__BASH_HISTORY__ = path("bash_history")


class SSHTable(SSHActions, QTableView):
    # def __init__(self, data=[], dir=__SSH_DIR__, **kwargs):
    def __init__(self, tasklist, parent=None, **kwargs):
        SSHActions.__init__(self, tasklist=tasklist, parent=parent)
        QTableView.__init__(self, parent=parent, **kwargs)

        self.configTable()
        self.setAlternatingRowColors(True)
        self.setStyleSheet('font-family: Consolas; font-size: 8;')
        self.installEventFilter(self)
        self.setFont(QtGui.QFont("Consolas", 8))
        self.doubleClicked.connect(self.on_click)

    def configTable(self):
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Interactive)
        self.verticalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Interactive)
        self.setSortingEnabled(True)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def updateGeometry(self):
        w = self.parent().width()
        n = float(0.9 / self.model().columnCount())
        self.setColumnWidth(0, min(100, int(w*0.1)))
        for i in range(1, self.model().columnCount() - 1):
            self.setColumnWidth(1, min(300, int(w*n)))
        self.horizontalHeader().setSectionResizeMode(
                QtWidgets.QHeaderView.Interactive)

    def contextMenuEvent(self, event):
        self.menu = QMenu(self)
        self.actions = {
            'open': self.open_vncviewer,
            'open_terminal': self.open_terminal,
            'open_terminal_with_cmd': self.open_terminal_with_cmd,
            'firefox_via_sshtunnel': self.firefox_via_sshtunnel,
            'chrome_via_sshtunnel': self.chrome_via_sshtunnel,
            'create_socks5_tunnel': self.create_socks5_tunnel,
            'ping': self.ping,
            'new': self.new_item,
            'open_folder': self.open_folder,
            # 'update_url': self.update_url,
            'update_server_info': self.update_info,
            'upload_email': self.upload_email,
            'reload_config': self.reload_config,
            'command': self.exec_command,
            'debot': self.debot,
            'edit': self.open_file,
            'upload': self.upload,
            'download': self.download,
            'backup': self.backup,
            'install_sshkey': self.install_sshkey,
            'copy_tunnel_cmd': self.copy_tunnel_cmd,
            'open_log': self.open_log,
            'move_to_trash': self.move_to_trash,
        }

        for k, v in self.actions.items():
            self.menu.addAction(k, v)
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.exec_(QtGui.QCursor.pos())

    def __event2item__(self, event):
        row = self.rowAt(event.pos().y())
        return self.model().itemAtRow(row)

    def selectedItems(self, select_all=False):
        model = self.model()
        if select_all is True:
            return [model.itemAtRow(i) for i in range(0, model.rowCount())]

        allrows = list(set([i.row() for i in self.selectedIndexes()]))
        return [model.itemAtRow(i) for i in allrows]

    def eventFilter(self, source, event):
        if (event.type() == QtCore.QEvent.KeyPress and event.matches(QtGui.QKeySequence.Copy)):
            self.copySelection()
            return True
        return super(SSHTable, self).eventFilter(source, event)

    def copySelection(self):
        selection = self.selectedIndexes()
        if selection:
            rows = sorted(index.row() for index in selection)
            columns = sorted(index.column() for index in selection)
            rowcount = rows[-1] - rows[0] + 1
            colcount = columns[-1] - columns[0] + 1
            table = [[''] * colcount for _ in range(rowcount)]
            for index in selection:
                row = index.row() - rows[0]
                column = index.column() - columns[0]
                table[row][column] = index.data()
            stream = io.StringIO()
            csv.writer(stream).writerows(table)
            QtWidgets.qApp.clipboard().setText(stream.getvalue())


    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)

    def setColumnVisible(self, i, hide):
        self.setColumnHidden(i, not hide)


    def on_click(self, index):
        try:
            m = self.model()
            item = m.itemAtRow(index.row())
            if not item: return None
            header = m.headername(index)
            f = header + '.txt'
            if f in ssh.WATCH_FILES:
                if not os.path.isfile(item.path(f)):
                    open(item.path(f), 'w').write('')
                return os.startfile(item.path(f))
            return os.startfile(item.path())
        except Exception:
            return None


class SSHWidget(QtWidgets.QWidget):
    def __init__(self, data=[], parent=None, intype="list", **kwargs):
        QtWidgets.QWidget.__init__(self, parent, **kwargs)

        if intype == "list":
            self.data = data
        else:
            self.dir = data
            self.data = []
            for d in data:
                self.data.extend(load_ssh_dir(d))

        self.refresh_pool = QtCore.QThreadPool()
        self.refresh_pool.setMaxThreadCount(5)
        self.initUI()
        self.daemon(self.refreshTaskList)

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tasklist = QObjectListModel(self)
        self.tasklistview = QtWidgets.QListView(self)
        self.tasklistview.setModel(self.tasklist)

        self.tableview = SSHTable(tasklist=self.tasklist, parent=self)
        tm = MyTableModel(data=self.data, parent=self)
        self.tableview.setModel(tm)
        self.tableview.model().fupate.connect(self.tableview.force_update)

        optW = self.initOpts()
        viewOpts = self.initViewOpts()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self.tableview)
        splitter.addWidget(self.tasklistview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(optW)
        layout.addWidget(viewOpts)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def initOpts(self):
        widget = QtWidgets.QWidget(self)
        widget.setFixedHeight(40)
        layout = QtWidgets.QHBoxLayout()

        search = QtWidgets.QLineEdit(self)
        search.textChanged.connect(self.on_search)
        self.search = search
        self.search.setFixedWidth(150)

        command = LineEditCompleter(
                completer_file=__BASH_HISTORY__,
                parent=self
        )
        command.returnPressed.connect(self.send_to_all)
        # search.textChanged.connect(self.on_command)
        self.command = command

        self.info = QtWidgets.QLineEdit(self)
        self.info.setReadOnly(True)
        self.info.setFixedWidth(120)

        layout.addWidget(search)
        layout.addWidget(QtWidgets.QLabel("Search"))

        layout.addWidget(command)
        pushCommand = QtWidgets.QPushButton("Send to All")
        pushCommand.clicked.connect(self.send_to_all)
        layout.addWidget(pushCommand)

        layout.addWidget(self.info)
        widget.setLayout(layout)
        layout.addWidget(QtWidgets.QLabel("THREADS"))

        clearJobButton = QtWidgets.QPushButton(parent=self, text="CLEAR JOBS")
        clearJobButton.clicked.connect(self.tableview.clearJobs)
        layout.addWidget(QtWidgets.QLabel("THREADS"))
        layout.addWidget(clearJobButton)

        return widget

    def initViewOpts(self):
        widget = QtWidgets.QWidget(self)
        widget.setFixedHeight(35)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(0)
        # layout.setContentsMargins(0,0,0,0)
        model = self.tableview.model()
        headers = [model.headerData(i) for i in range(0, model.columnCount())]
        viewables = OrderedDict()

        for i, h in enumerate(headers):
            viewables[h] = QtWidgets.QCheckBox(h, self)
            viewables[h].setChecked(True)
            f = partial(self.tableview.setColumnVisible, i)
            viewables[h].stateChanged.connect(f)
            layout.addWidget(viewables[h])
        spacer = QtWidgets.QSpacerItem(
                0, 0,
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding
        )
        layout.addItem(spacer)
        widget.setLayout(layout)
        return widget

    def send_to_all(self):
        cmd = self.command.text()
        print("Send to all: {}".format(cmd))
        self.tableview.exec_command(cmd=cmd, select_all=True)

    def refreshTaskList(self):
        while (True):
            # changed = False
            for t in self.tasklist.getdata().copy():
                try:
                    if t.done is True:
                        self.tasklist.remove(t)
                        # reload tasklist avoid segmentation fault
                        # changed = True
                except Exception:
                    pass

                # self.info.setText('ThreadPool={}'.format(
                    # self.tableview.threadpool.activeThreadCount(),
                    # ))
                # self.info.setText('ThreadPool={}/scp={}/backup={}'.format(
                #     self.tableview.threadpool.activeThreadCount(),
                #     self.tableview.scp_pool.activeThreadCount(),
                #     self.tableview.backup_pool.activeThreadCount()
                #     ))
                # if changed is True:
                    # break

            if close_all is True:
                break
            time.sleep(1)
            # if changed is False:
                # time.sleep(1)

    def refreshLog(self):
        while(True):
            model = self.tableview.model()
            for i in range(0, model.rowCount()):
                try:
                    item = model.itemAtRow(i)
                    worker = Worker(item.getLog)
                    self.refresh_pool.start(worker)
                    # model.itemAtRow(i).getLog()
                except Exception as e:
                    logging.error('unable to get log at item {}'.format(i))
                    logging.error(e, exc_info=True)
            if close_all is True:
                break
            time.sleep(5)

    def daemon(self, *args):
        for t in args:
            t = threading.Thread(target=t)
            t.daemon = True
            t.start()

    def resizeEvent(self, event):
        self.tableview.updateGeometry()

    def on_search(self, pattern):
        model = self.tableview.model()
        for i in range(0, model.rowCount()):
            item = model.itemAtRow(i)
            hide = pattern not in item.full()
            self.tableview.setRowHidden(i, hide)


def main():
    import logging
    logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s',
            datefmt='%m-%d %H:%M')
    argv = sys.argv
    app = QApplication(argv)
    if len(argv) == 2:
        print("Loading ssh clients in directory {}".format(argv[1]))
        w = SSHWidget(data=[argv[1]], intype="directory")
    elif len(argv) > 2:
        w = SSHWidget(data=argv[1:], intype="directory")
    else:
        w = SSHWidget()

    w.setGeometry(0, 0, 1000, 1000)
    w.tableview.updateGeometry()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
