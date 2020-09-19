import os
import subprocess
import logging
import json
from PyQt5 import QtGui, QtWidgets, QtCore
from collections import deque

# My modules
from worker import Worker
from sshDialogForm import ChooseCommandDialog, SCPDialog, SSHInputDialog
from urlDialog import URLForm
import crypt
from ssh import load_ssh_file


XDOTOOL = 'DISPLAY=:1 xdotool'


class SSHActions(object):
    """Docstring for SSHMenu. """
    def __init__(self, tasklist=None, parent=None):
        self._parent = parent

        if tasklist is None:
            self.tasklist = []
        else:
            self.tasklist = tasklist

        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(20)
        self.threadpool.waitForDone(-1)

        self.scp_pool = QtCore.QThreadPool()
        self.scp_pool.setMaxThreadCount(5)
        self.scp_pool.waitForDone(-1)

        self.backup_pool = QtCore.QThreadPool()
        self.backup_pool.setMaxThreadCount(5)
        self.backup_pool.waitForDone(-1)

        self.vncviewer_threads = QtCore.QThreadPool()
        self.vncviewer_threads.setMaxThreadCount(10)

        self.terminal_threads = QtCore.QThreadPool()
        self.terminal_threads.setMaxThreadCount(100)

    def clearJobs(self):
        for f in [self.threadpool, self.scp_pool, self.backup_pool]:
            f.clear()

    def __debot__(self, item):
        item.exec_command('DISPLAY=:1 xdotool mousemove 56 223 click 1')
        item.open_vncviewer()
        item.exec_command('rm -f ~/.ytv/robot.txt')
        item.update_server_info()
        # item.is_robot()
        item.update_vncthumnail()

    def debot(self):
        for item in self.selectedItems():
            worker = Worker(self.__debot__, item)
            self.vncviewer_threads.start(worker)

    def firefox_via_sshtunnel(self):
        for item in self.selectedItems():
            worker = Worker(item.firefox_via_sshtunnel)
            self.vncviewer_threads.start(worker)

    def chrome_via_sshtunnel(self):
        for item in self.selectedItems():
            worker = Worker(item.chrome_via_sshtunnel)
            self.vncviewer_threads.start(worker)

    def selectedItems(self, select_all=False):
        return []

    def create_socks5_tunnel(self, port=None):
        for item in self.selectedItems():
            item.create_socks5()

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
            self.tasklist.append(worker)
            self.vncviewer_threads.start(worker)

    def ping(self):
        for item in self.selectedItems():
            worker = Worker(item.ping)
            self.tasklist.append(worker)
            self.threadpool.start(worker)

    def update_url(self):
        dl = URLForm(self)
        urls = dl.getResult()
        if not urls:
            return
        msg = "Are you sure you want to update new url?\n"
        msg += json.dumps(urls, indent=2)
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
        # d = {'urls': r}
        text = '\n'.join(urls)
        with open(dl[0] + '.txt', 'w') as fp:
            fp.write(text)
        crypt.encryptFile(dl[0] + '.txt', dl[0])

    def update_info(self):
        for item in self.selectedItems():
            worker = Worker(item.update_server_info)
            self.tasklist.append(worker)
            self.scp_pool.start(worker)

    def exec_command(self, cmd=None, items=None, select_all=False):
        if cmd is None:
            dialog = ChooseCommandDialog(parent=self)
            cmd = dialog.getResult()
        if not cmd:
            return

        for item in self.selectedItems(select_all=select_all):
            logging.info("try to send command {} to {}".format(cmd, str(item)))
            worker = Worker(item.exec_command, cmd, store=True)
            # item.exec_command(cmd) #, store=True)
            # logging.info("created new worker {}".format(worker))
            self.tasklist.append(worker)
            # logging.info("added worker to takslist{}".format(worker))
            self.threadpool.start(worker)
            # logging.info("run worker to takslist{}".format(worker))

    def open_terminal(self, command=None):
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell, command)
            # self.tasklist.append(worker)
            self.terminal_threads.start(worker)

    def open_folder(self):
        for item in self.selectedItems():
            worker = Worker(os.startfile, item.path())
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

    def upload_email(self):
        self.upload(path='~/.ytv/email')

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

    def force_reconnect(self):
        for item in self.selectedItems():
            item.force_reconnect()

    def reload_config(self):
        for item in self.selectedItems():
            item.reloadConfig()

    def copy_hostaddress(self):
        items = self.selectedItems()
        t = [i.hostaddress() for i in items]
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard)
        clipboard.setText("\n".join(t), mode=clipboard.Clipboard)

    def copy_tunnel_cmd(self):
        cmds = [item.ssh_tunnel_cmd() for item in self.selectedItems()]
        cb = QtWidgets.QApplication.clipboard()
        cb.clear(mode=cb.Clipboard)
        cb.setText("\n".join(cmds), mode=cb.Clipboard)

    def new_url_at_current_tab(self):
        text, okPressed = QtWidgets.QInputDialog.getText(
                self, "URL", "URL",
                QtWidgets.QLineEdit.Normal, "")
        url = text.strip()
        if not okPressed or not url:
            return
        cmd = '{0} key "ctrl+l" && {0} type --delay 100 "{1}" && {0} key Return'.format(XDOTOOL, url)
        for item in self.selectedItems():
            worker = Worker(item.exec_command, cmd)
            self.threadpool.start(worker)

    def send_key(self):
        items = ("Escape", "F5", "space", "Return", "f", "ctrl+w", "ctrl+q")
        item, okPressed = QtWidgets.QInputDialog.getItem(
                self,
                "Send key", "Key", items, 0, False)
        if okPressed and item:
            cmd = '{} key {}'.format(XDOTOOL, item)
            for item in self.selectedItems():
                worker = Worker(item.exec_command, cmd)
                self.threadpool.start(worker)

    def open_terminal_with_cmd(self, cmd=None):
        if cmd is None:
            cmd, okPressed = QtWidgets.QInputDialog.getText(
                    self, "CMD", "CMD",
                    QtWidgets.QLineEdit.Normal, "")
            if not okPressed:
                return
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell, cmd)
            self.terminal_threads.start(worker)

    def move_to_trash(self):
        items = self.selectedItems()
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
        return items

    def copy_ssh_cmd(self):
        t = []
        for item in self.selectedItems():
            t.append(item.cmdline())
        t = [i.cmdline() for i in self.selectedItems()]
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard)
        clipboard.setText("\n".join(t), mode=clipboard.Clipboard)

    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)

    def new_item(self):
        try:
            # no selected items
            item = self.selectedItems()[0]
            dialog = SSHInputDialog(parent=self, root=os.path.dirname(item.path()))
        except Exception:
            dialog = SSHInputDialog(parent=self)
        r = dialog.getResult()
        if not r:
            return
        for f in r:
            item = load_ssh_file(f)
            item.info['filepath'] = str(r)
            if item.get('hostname') not in self.model().hostnames:
                self.model().appendItem(item)

