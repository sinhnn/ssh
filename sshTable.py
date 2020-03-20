#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author "sinhnn <sinhnn.92@gmail.com>" Date 16.12.2019

import sys
import re
import os
import time
import threading
import subprocess
import json
import logging

from PyQt5.QtWidgets import (
        QApplication,
        QTableView,
        QMenu,
)

# from PyQt5.QtGui import QIcon
from PyQt5 import QtGui, QtCore, QtWidgets
# from PyQt5.QtCore import pyqtSlot
from ObjectsTableModel import (
        ObjectsTableModel as MyTableModel,
        ComboBoxModel,
        )

# import random

# =============================================================================
import ssh
import crypt
from sshDialogForm import SCPDialog, SSHInputDialog
from urlDialog import URLForm
from simplelistmodel import QObjectListModel
from worker import Worker
# =============================================================================
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
        self.buttonBox = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.command = QtWidgets.QLineEdit(self)

        self.presetBox = QtWidgets.QComboBox(self)
        presetBoxModel = ComboBoxModel(self.__load_preset__())
        self.presetBox.setModel(presetBoxModel)
        self.presetBox.currentIndexChanged.connect(self.__show_preset_value__)

        self.browser = QtWidgets.QPushButton("Browser", self)
        self.browser.clicked.connect(self.__browser__)

        layout.addWidget(self.command, 0, 0, 2, 2)
        layout.addWidget(self.presetBox, 2, 0)
        layout.addWidget(self.browser, 2, 1)
        layout.addWidget(self.buttonBox, 3, 0)
        layout.setColumnStretch(0, 1)
        layout.setRowStretch(0, 1)

        self.setMinimumWidth(600)
        self.setLayout(layout)

    def getResult(self):
        r = self.exec_()
        if r:
            return self.command.text()
        else:
            return False

    def __browser__(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        files, _ = dialog.getOpenFileNames(self, 'Shell script file')
        if not files:
            return
        self.command.setText(files[0])

    def __show_preset_value__(self, index):
        item = self.presetBox.model().itemAtRow(index)
        self.command.setText(item['value'])

    def __load_preset__(self):
        results = []
        for entry in os.scandir(ChooseCommandDialog.__PRESET_CMD_DIR__):
            if entry.is_dir():
                continue
            if not re.search(r'.preset.json$', entry.name):
                continue

            command = self.__load_preset_file__(entry.path)
            if command:
                results.append(command)
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


__SSH_DIR__ = os.path.join(__PATH__, 'ssh')


def load_ssh_dir(dir):
    results = []
    for entry in os.scandir(dir):
        if entry.is_dir():
            continue
        if not re.search(r'.json$', entry.name):
            continue

        try:
            server = load_ssh_file(entry.path)
            if server:
                server.info['filepath'] = os.path.abspath(entry.path)
                results.append(server)
        except Exception:
            pass
    return results


def load_ssh_file(path):
    try:
        fp = open(path, 'r')
        info = json.load(fp)
        fp.close()
        client = ssh.SSHClient(info=info, fileConfig=path)
        if client.is_valid():
            return client
        return {}
    except Exception:
        logging.error('unable to load file {}\n{}'.format(path), exc_info=True)
        return {}
    # return None


class SSHTable(QTableView):
    # def __init__(self, data=[], dir=__SSH_DIR__, **kwargs):
    def __init__(self, tasklist, parent=None, **kwargs):
        QTableView.__init__(self, parent, **kwargs)
        self.configTable()
        self.setStyleSheet('font-family: Consolas; font-size: 8;')
        self.setFont(QtGui.QFont("Consolas", 8))

        self.tasklist = tasklist
        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(50)
        self.threadpool.waitForDone(-1)

        self.scp_pool = QtCore.QThreadPool()
        self.scp_pool.setMaxThreadCount(5)

        self.backup_pool = QtCore.QThreadPool()
        self.backup_pool.setMaxThreadCount(5)

        self.vncviewer_threads = QtCore.QThreadPool()
        self.vncviewer_threads.setMaxThreadCount(10)

        self.terminal_threads = QtCore.QThreadPool()
        self.terminal_threads.setMaxThreadCount(100)
        # self.geometriesChanged.connect(self.updateGeometry)

    def clearJobs(self):
        for f in [self.threadpool, self.scp_pool, self.backup_pool]:
            f.clear()

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
            'new': self.new_item,
            'open_folder': self.open_folder,
            'update_url': self.update_url,
            'update_server_info': self.update_info,
            'command': self.exec_command,
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

    def selectedItems(self):
        allrows = list(set([i.row() for i in self.selectedIndexes()]))
        return [self.model().itemAtRow(i) for i in allrows]

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
            self.tasklist.append(worker)
            self.vncviewer_threads.start(worker)

    def update_url(self):
        dl = URLForm(self)
        r = dl.getResult()
        if not r:
            return
        msg = "Are you sure you want to update new url?\n"
        msg += json.dumps(r, indent=2)
        reply = QtWidgets.QMessageBox.question(
                self,
                'Message',
                msg,
                QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)

        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Encode to file
        dl = QtWidgets.QFileDialog.getSaveFileName(self, 'Save File')
        if not dl:
            return
        d = {'urls': r}
        with open(dl[0] + '.txt', 'w') as fp:
            json.dump(d, fp)
        crypt.encryptFile(dl[0] + '.txt', dl[0])

    def update_info(self):
        for item in self.selectedItems():
            worker = Worker(item.update_server_info)
            self.tasklist.append(worker)
            self.scp_pool.start(worker)

    def exec_command(self):
        dialog = ChooseCommandDialog(parent=self)
        r = dialog.getResult()
        if not r:
            return
        for item in self.selectedItems():
            logging.info("try to send command {} to {}".format(r, str(item)))
            worker = Worker(item.exec_command, r, store=True)
            self.tasklist.append(worker)
            self.threadpool.start(worker)

    def open_terminal(self, command=None):
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell, command)
            # self.tasklist.append(worker)
            self.terminal_threads.start(worker)

    def open_folder(self):
        for item in self.selectedItems():
            worker = Worker(os.startfile, item.storeDir)
            self.tasklist.append(worker)
            self.threadpool.start(worker)

    def open_log(self):
        for item in self.selectedItems():
            worker = Worker(os.startfile, item.logFile)
            # self.tasklist.append(worker)
            self.terminal_threads.start(worker)

    def upload(self, path='~/.ytv'):
        dialog = SCPDialog(download=False)
        dialog.widgets['dst_path']['widget'].setText(path)
        info = dialog.getResult()
        if not info:
            return
        for item in self.selectedItems():
            worker = Worker(
                        item.upload_by_subprocess,
                        recursive=False,
                        src_path=info['src_path'],
                        dst_path=info['dst_path'],
                        store=True
                        )

            self.tasklist.append(worker)
            self.scp_pool.start(worker)

    def backup(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Files")
        if not d:
            return

        for item in self.selectedItems():
            worker = Worker(item.backup, dst_path=d)
            self.tasklist.append(worker)
            self.backup_pool.start(worker)

    def download(self, path='.'):
        dialog = SCPDialog(download=True)
        dialog.widgets['dst_path']['widget'].setText(path)
        info = dialog.getResult()
        if not info:
            return None
        for item in self.selectedItems():
            worker = Worker(
                        item.download_by_subprocess,
                        recursive=False,
                        src_path=info['src_path'],
                        dst_path=info['dst_path'],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        store=True)
            self.tasklist.append(worker)
            self.scp_pool.start(worker)

    def install_sshkey(self):
        f = QtWidgets.QFileDialog.getOpenFileName(self, "Open Files")
        if not f[0]:
            return False

        if f[0]:
            for item in self.selectedItems():
                worker = Worker(item.install_sshkey, f[0])
                self.threadpool.start(worker)

    def open_file(self):
        for item in self.selectedItems():
            p = str(item.get('filepath'))
            if not p:
                return
            try:
                os.startfile(p)
            except Exception:
                logging.error('unable to open {}'.format(p))

    def copy_tunnel_cmd(self):
        cmds = [item.ssh_tunnel_cmd() for item in self.selectedItems()]
        cb = QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText("\n".join(cmds), mode=cb.Clipboard)

    def move_to_trash(self):
        for item in self.selectedItems():
            f = item.get('filepath')
            dirname = os.path.join(os.path.dirname(f), 'Trash')
            os.makedirs(dirname, exist_ok=True)
            newfile = os.path.join(dirname, os.path.basename(f))
            try:
                os.rename(f, newfile)
            except Exception as e:
                logging.error(e, exc_info=True)
            try:
                self.model().removeItem(item)
            except Exception as e:
                logging.error(e, exc_info=True)

    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)

    def new_item(self):
        dialog = SSHInputDialog(parent=self)
        r = dialog.getResult()
        if not r:
            return
        for f in r:
            item = load_ssh_file(f)
            item.info['filepath'] = str(r)
            self.model().appendItem(item)


class SSHWidget(QtWidgets.QWidget):
    def __init__(self, data=[], dir=__SSH_DIR__, parent=None, **kwargs):
        QtWidgets.QWidget.__init__(self, parent, **kwargs)
        self.data = data
        if not self.data:
            self.data = load_ssh_dir(dir)
            self.dir = dir

        self.refresh_pool = QtCore.QThreadPool()
        self.refresh_pool.setMaxThreadCount(5)
        self.initUI()
        self.daemon()

    def initUI(self):
        layout = QtWidgets.QVBoxLayout()

        self.tasklist = QObjectListModel(self)
        self.tasklistview = QtWidgets.QListView(self)
        self.tasklistview.setModel(self.tasklist)

        self.tableview = SSHTable(parent=self, tasklist=self.tasklist)
        tm = MyTableModel(data=self.data, parent=self)
        self.tableview.setModel(tm)
        self.tableview.model().fupate.connect(self.tableview.force_update)

        optW = self.initOpts()

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        splitter.addWidget(self.tableview)
        splitter.addWidget(self.tasklistview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        layout.addWidget(optW)
        layout.addWidget(splitter)
        self.setLayout(layout)

    def initOpts(self):
        widget = QtWidgets.QWidget(self)
        widget.setFixedHeight(50)
        layout = QtWidgets.QHBoxLayout()
        search = QtWidgets.QLineEdit(self)
        search.textChanged.connect(self.on_search)
        self.search = search
        self.info = QtWidgets.QLineEdit(self)
        self.info.setReadOnly(True)

        layout.addWidget(QtWidgets.QLabel("Search"))
        layout.addWidget(search)
        layout.addWidget(self.info)
        widget.setLayout(layout)
        layout.addWidget(QtWidgets.QLabel("THREADS"))
        clearJobButton = QtWidgets.QPushButton(parent=self, text="CLEAR JOBS")
        clearJobButton.clicked.connect(self.tableview.clearJobs)
        layout.addWidget(QtWidgets.QLabel("THREADS"))
        layout.addWidget(clearJobButton)
        return widget

    def refreshTaskList(self):
        while (True):
            # self.tasklistview.update()
            # time.sleep(1)
            for t in self.tasklist.getdata():
                try:
                    if t.done is True:
                        self.tasklist.remove(t)
                        # break
                except Exception:
                    pass
                self.info.setText('ThreadPool={}/scp={}/backup={}'.format(
                    self.tableview.threadpool.activeThreadCount(),
                    self.tableview.scp_pool.activeThreadCount(),
                    self.tableview.backup_pool.activeThreadCount()
                    ))
            time.sleep(1)

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
            time.sleep(5)

    def daemon(self):
        # threads = []
        # for t in [self.refreshTaskList, self.refreshLog]:
        for t in [self.refreshTaskList]:
            t = threading.Thread(target=t)
            t.daemon = True
            t.start()

    def resizeEvent(self, event):
        # QtWidgets.QWidget.updateGeometry()
        self.tableview.updateGeometry()

    def on_search(self, pattern):
        model = self.tableview.model()
        for i in range(0, model.rowCount()):
            item = model.itemAtRow(i)
            hide = pattern not in str(item)
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
        w = SSHWidget(dir=argv[1])
    else:
        w = SSHWidget()

    w.setGeometry(0, 0, 1000, 1000)
    w.tableview.updateGeometry()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
