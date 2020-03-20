import os
import sys
import threading
import time
import logging
from PyQt5 import (
    QtWidgets,
    QtCore,
    QtGui
)

# My modules ==================================================================
import common
from worker import Worker
from sshDialogForm import (
    SSHInputDialog,
    SCPDialog
)

from sshTable import (
    ChooseCommandDialog,
    # load_ssh_dir,
    load_ssh_file
)

__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ = os.path.join(__PATH__, 'ssh')
__XDOTOOL__ = 'DISPLAY=:1 xdotool'


class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    fupate = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, data=[], auto_update=True, parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.parent = parent
        self.__data__ = data
        self.__auto_update__ = auto_update

        self.delay = 5
        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(50)
        self.threadpool.waitForDone(-1)
        self.threadpool.start(Worker(self.update_thumbnail))
        self.threads = []
        # self.__daemon__()

        self.__updating_item__ = []
        self.__role__ = [QtCore.Qt.DecorationRole | QtCore.Qt.DisplayRole]

    def __daemon__(self):
        for t in [self.update_thumbnail]:
            thread = threading.Thread(target=t)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

    def setAutoUpdate(self, enable):
        self.__auto_update__ = enable

    def force_update_item(self, row):
        try:
            topLeft = self.createIndex(row, 0)
            item = self.__data__[row]
            if item not in self.__updating_item__:
                self.__updating_item__.append(item)
                r = item.update_vncthumnail()
                if r:
                    self.dataChanged.emit(topLeft, topLeft, self.__role__)
                    self.fupate.emit(topLeft)
                self.__updating_item__.remove(item)
        except Exception as e:
            logging.error(e, exc_info=True)

    def update_thumbnail(self):
        while True:
            if common.close_all:
                logging.info("Recieved close signal")
                time.sleep(1)
                break
            if self.__auto_update__:
                for row in range(self.rowCount()):
                    worker = Worker(self.force_update_item, row)
                    self.threadpool.start(worker)

            time.sleep(self.delay)

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()
        return self.createIndex(row, column, parent)

    def getData(self):
        return self.__data__

    def count(self):
        return len(self.__data__)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.__data__)

    def itemAtRow(self, i):
        return self.__data__[i]

    def removeItem(self, item):
        row = self.__data__.index(item)
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.__data__.remove(item)
        self.endRemoveRows()

    def appendItem(self, item):
        lr = self.rowCount() - 1
        self.beginInsertRows(QtCore.QModelIndex(), lr, lr)
        self.__data__.append(item)
        self.endInsertRows()
        return True

    def data(self, index, role=QtCore.Qt.DecorationRole):
        if not index.isValid():
            print("invalid index")
            return None
        if index.row() > self.rowCount():
            return None

        item = self.__data__[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return str(item)
        elif role == QtCore.Qt.DecorationRole:
            img = QtGui.QIcon(item.get('screen', 'icon/computer.png'))
            return img
        return None

    def flags(self, idx):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

    def sort(self, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self.__data__.sort(
                    key=lambda item: item.get('hostname'),
                    reverse=not order)
            self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)

    def sort_by(self, key, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self.__data__.sort(
                    key=lambda item: item.get(key, 'Z'),
                    reverse=not order)
            self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)

    def find(self, key, value):
        try:
            pass
        except Exception as e:
            logging.error(e, exc_info=True)


class ThumbnailListViewer(QtWidgets.QListView):
    """Docstring for ThumbnailListViewer. """
    __DEFAULT_ICON_SIZE__ = QtCore.QSize(160, 65)
    __DEFAULT_GRID_SIZE__ = QtCore.QSize(160, 130)
    __LARGE_ICON_SIZE__ = QtCore.QSize(320, 180)
    __LARGE_GRID_SIZE__ = QtCore.QSize(320, 260)

    def __init__(self, parent=None, **kwargs):
        """TODO: to be defined. """
        QtWidgets.QListView.__init__(self, parent, **kwargs)

        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setIconView()
        self.doubleClicked.connect(self.open)
        self.setDragEnabled(False)
        self.initUI()
        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(100)

        self.scp_pool = QtCore.QThreadPool()
        self.scp_pool.setMaxThreadCount(5)

        self.backup_pool = QtCore.QThreadPool()
        self.backup_pool.setMaxThreadCount(10)

        self.vncviewer_threads = QtCore.QThreadPool()
        self.terminal_threads = QtCore.QThreadPool()
        self.setStyleSheet("font-size: 12px;")

    def initUI(self):
        self.menu = QtWidgets.QMenu(self)
        self.actions = {
            'open': self.open_vncviewer,
            'open_terminal': self.open_terminal,
            'open_terminal_with_cmd': self.open_terminal_with_cmd,
            # 'new_url_at_current_tab': self.new_url_at_current_tab,
            'Send F5': lambda: self._exec_command(__XDOTOOL__ + ' F5'),
            'Send Space': lambda: self._exec_command(__XDOTOOL__ + ' space'),
            'Send Escape': lambda: self._exec_command(__XDOTOOL__ + ' Escape'),
            'send_key': self.send_key,
            'new': self.new_item,
            'edit': self.open_file,
            'upload': self.upload,
            'download': self.download,
            'backup': self.backup,
            'command': self.exec_command,
            'copy_hostaddress': self.copy_hostaddress,
            'copy_ssh_cmd': self.copy_ssh_cmd,
            'refresh': self.force_reconnect,
            'reload_config': self.reload_config,
            'install_sshkey': self.install_sshkey,
            'delete': self.move_to_trash,
            'open_log': self.open_log,
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)

    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)

    def open_file(self):
        for item in self.selectedItems():
            p = str(item.get('filepath', ''))
            if not p:
                continue
            try:
                os.startfile(p)
            except Exception:
                logging.error('unable to open {}'.format(p))

    def scaleIcon(self, v):
        nw = int(ThumbnailListViewer.__LARGE_ICON_SIZE__.width() * v)
        nh = int(ThumbnailListViewer.__LARGE_ICON_SIZE__.height() * v)
        ns = QtCore.QSize(nw, nh)
        self.setIconSize(ns)

        nw = int(ThumbnailListViewer.__LARGE_GRID_SIZE__.width() * v)
        nh = int(ThumbnailListViewer.__LARGE_GRID_SIZE__.height() * v)
        self.setStyleSheet("font-size: {}px;".format(8 + int(8*v)))
        ns = QtCore.QSize(nw, nh)
        self.setGridSize(ns)

    def setIconView(self):
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setLayoutMode(QtWidgets.QListView.Batched)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.scaleIcon(0.3)
        self.setStyleSheet('border-width: 1px;border-color:black;')
        self.setSpacing(0)
        self.setUniformItemSizes(False)

    def setListView(self):
        self.setGridSize(QtCore.QSize(100, 60))
        self.setIconSize(QtCore.QSize(96, 54))
        self.setViewMode(QtWidgets.QListView.ListMode)
        self.setFlow(QtWidgets.QListView.TopToBottom)
        self.setLayoutMode(QtWidgets.QListView.SinglePass)
        self.setResizeMode(QtWidgets.QListView.Adjust)
        self.setSpacing(2)

    def contextMenuEvent(self, event):
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.exec_(QtGui.QCursor.pos())

    def __event2item__(self, event):
        row = self.rowAt(event.pos().y())
        return self.model().itemAtRow(row)

    def selectedItems(self):
        model = self.model()
        return [model.itemAtRow(i.row()) for i in self.selectedIndexes()]

    def _exec_command(self, command):
        for item in self.selectedItems():
            worker = Worker(item.exec_command, command)
            self.threadpool.start(worker)

    def exec_command(self):
        dialog = ChooseCommandDialog(parent=self)
        r = dialog.getResult()
        if not r:
            return
        for item in self.selectedItems():
            logging.info("try to send command {} to {}".format(r, str(item)))
            worker = Worker(item.exec_command, r)
            self.threadpool.start(worker)

    def new_item(self):
        dialog = SSHInputDialog(parent=self)
        r = dialog.getResult()
        if not r:
            return
        for f in r:
            item = load_ssh_file(f)
            item.info['filepath'] = str(r)
            self.model().appendItem(item)

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
            self.vncviewer_threads.start(worker)

    def open_terminal_with_cmd(self):
        text, okPressed = QtWidgets.QInputDialog.getText(
                self, "CMD", "CMD",
                QtWidgets.QLineEdit.Normal, "")
        if not okPressed:
            return
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell, text)
            self.terminal_threads.start(worker)

    def open_terminal(self, cmd=None):
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell, cmd)
            self.terminal_threads.start(worker)

    def copy_ssh_cmd(self):
        t = []
        for item in self.selectedItems():
            t.append(item.cmdline())
        t = [i.cmdline() for i in self.selectedItems()]
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard)
        clipboard.setText("\n".join(t), mode=clipboard.Clipboard)

    def copy_hostaddress(self):
        items = self.selectedItems()
        t = [i.hostaddress() for i in items]
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard)
        clipboard.setText("\n".join(t), mode=clipboard.Clipboard)

    def force_reconnect(self):
        for item in self.selectedItems():
            item.force_reconnect()

    def reload_config(self):
        for item in self.selectedItems():
            item.reloadConfig()

    def open_log(self):
        for item in self.selectedItems():
            worker = Worker(os.startfile, item.logFile)
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
                        dst_path=info['dst_path'])

            self.scp_pool.start(worker)

    def backup(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Open Files")
        if not d:
            return

        for item in self.selectedItems():
            worker = Worker(item.backup, dst_path=d)
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
                        dst_path=info['dst_path'])

            self.scp_pool.start(worker)

    def new_url_at_current_tab(self):
        text, okPressed = QtWidgets.QInputDialog.getText(
                self, "URL", "URL",
                QtWidgets.QLineEdit.Normal, "")
        url = text.strip()
        if not okPressed or not url:
            return
        cmd = '{0} key "ctrl+l" && {0} type --delay 100 "{1}" && {0} key Return'.format(__XDOTOOL__, url)
        for item in self.selectedItems():
            worker = Worker(item.exec_command, cmd)
            self.threadpool.start(worker)

    def send_key(self):
        items = ("Escape", "F5", "space", "Return", "f", "ctrl+w", "ctrl+q")
        item, okPressed = QtWidgets.QInputDialog.getItem(
                self,
                "Send key", "Key", items, 0, False)
        if okPressed and item:
            cmd = '{} key {}'.format(__XDOTOOL__, item)
            for item in self.selectedItems():
                worker = Worker(item.exec_command, cmd)
                self.threadpool.start(worker)

    def open(self):
        self.open_vncviewer()

    def close(self):
        for item in self.selectedItems():
            item.close()

    def move_to_trash(self):
        for item in self.selectedItems():
            p = item.get('filepath')
            if not p:
                continue
            dirname = os.path.join(os.path.dirname(p), 'Trash')
            os.makedirs(dirname, exist_ok=True)
            newfile = os.path.join(dirname, os.path.basename(p))
            try:
                os.rename(p, newfile)
            except Exception as e:
                logging.error(e, exc_info=True)
            try:
                self.model().removeItem(item)
            except Exception as e:
                logging.error(e, exc_info=True)

    def install_sshkey(self):
        f = QtWidgets.QFileDialog.getOpenFileName(self, "Open Files")
        if not f[0]:
            return False

        if f[0]:
            for item in self.selectedItems():
                worker = Worker(item.install_sshkey, f[0])
                self.threadpool.start(worker)


def main():
    import logging
    logging.basicConfig(
        level=logging.INFO,
        filename='log.txt',
        format='''%(asctime)s %(name)-12s %(levelname)-8s
            [%(filename)s:%(lineno)s - %(funcName)20s()] %(message)s''',
        datefmt='%m-%d %H:%M'
    )

    app = QtWidgets.QApplication(sys.argv)
    w = ThumbnailListViewer()
    w.show()
    r = app.exec_()
    common.close_all = True
    sys.exit(r)


if __name__ == "__main__":
    main()
