import os, sys, threading, subprocess, time, logging
from PyQt5 import QtWidgets, QtCore, QtGui

from worker import Worker
from threading import Thread

import common
from sshDialogForm import SSHInputDialog, SCPDialog


class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    fupate = QtCore.pyqtSignal(QtCore.QModelIndex)
    def __init__(self, data=[], auto_update=True, parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.parent = parent
        self.__data__ = data
        self.__auto_update__ = auto_update

        self.delay = 2
        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(100)
        self.threadpool.waitForDone(-1)
        uworker = Worker(self.force_update)
        self.threadpool.start(Worker(self.force_update))
        self.threads = []
        # self.__daemon__()
        self.__updating_item__ = []

    def __daemon__(self):
        for  t in [self.force_update]:
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
                logging.debug('updating thumbnail of {}'.format(item.get('hostname')))
                self.__updating_item__.append(item)
                item.update_vncthumnail()
                self.dataChanged.emit(topLeft, topLeft, [QtCore.Qt.DecorationRole | QtCore.Qt.DisplayRole ])
                self.fupate.emit(topLeft)
                self.__updating_item__.remove(item)
            else:
                logging.debug('updating thumbnail of {} has already in queue'.format(item.get('hostname')))
        except Exception as e:
            logging.error(e, exc_info=True)

    def force_update(self):
        while True:
            if common.close_all:
                logging.info("Recieved close signal")
                time.sleep(1)
                break
            if self.__auto_update__ == True:
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
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount() - 1, self.rowCount() - 1)
        self.__data__.append(item)
        self.endInsertRows()
        return True
        
    def data(self, index, role = QtCore.Qt.DecorationRole):
        if not index.isValid():
            print("invalid index")
            return None
        if index.row() > self.rowCount():
            return None

        item = self.__data__[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return str(item)

        elif role == QtCore.Qt.ToolTipRole:
            try:
                text = []
                for t in item.tunnel_proc + item.processes + item.exec_command_list:
                    text.append(str(t))
                # text.extend(item.processes)
                # text.extend(item.exec_command_list)
                text.append(item.loghandler.get_last_messages(10))
                return '\n'.join(text)
            except Exception as e:
                return str( e)

        elif role == QtCore.Qt.DecorationRole:
            img = QtGui.QIcon(item.get('icon', 'icon/computer.png'))
            return img

        return None	

    def flags(self, idx):
        return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

    def sort(self, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self.__data__.sort(key=lambda item : item.get('hostname'),  reverse=not order)
            self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)

    def sort_by(self, key, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self.__data__.sort(key=lambda item : item.get(key, 'Z'),  reverse=not order)
            self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)

    def find(self, key, value):
        try:
            pass
            # self.layoutAboutToBeChanged.emit()
            # self.__data__.sort(key=lambda item : item.get(key, 'Z'),  reverse=not order)
            # self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)


from sshTable import ChooseCommandDialog, load_ssh_dir, load_ssh_file
__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ =  os.path.join(__PATH__, 'ssh')
class ThumbnailListViewer(QtWidgets.QListView):
    """Docstring for ThumbnailListViewer. """
    __DEFAULT_ICON_SIZE__ = QtCore.QSize(160, 65)
    __DEFAULT_GRID_SIZE__ = QtCore.QSize(160, 130 )
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

        self.vncviewer_threads = QtCore.QThreadPool()
        self.terminal_threads = QtCore.QThreadPool()
        self.setStyleSheet("font-size: 12px;")

    def initUI(self):
        self.menu = QtWidgets.QMenu(self)
        self.actions = {
            'open' : self.open_vncviewer,
            'open_terminal' : self.open_terminal,
            'new_url_at_current_tab' : self.new_url_at_current_tab,
            'Send F5' : lambda : self._exec_command('DISPLAY=:1 xdotool key F5'),
            'Send Space' : lambda : self._exec_command('DISPLAY=:1 xdotool key space'),
            'Send Escape' : lambda : self._exec_command('DISPLAY=:1 xdotool key Escape'),
            'send_key' : self.send_key,
            'new' : self.new_item,
            'edit' : self.open_file,
            'upload' : self.upload,
            'download' : self.download,
            'command' : self.exec_command, # from file or command
            'copy_hostaddress' : self.copy_hostaddress, # from file or command
            'refresh' : self.force_reconnect, # from file or command
            'reload_config' : self.reload_config, # from file or command
            'install_sshkey' : self.install_sshkey, # from file or command
            'delete' : self.move_to_trash, # from file or command
            'open_log' : self.open_log, # from file or command
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)

    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)
    
    def open_file(self):
        for item in self.selectedItems():
            if item.get('filepath'):
                os.startfile(str(item.get('filepath')))

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

        self.scaleIcon(0.5)
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
        return [self.model().itemAtRow(i.row()) for i in self.selectedIndexes()]

    def _exec_command(self, command):
        for item in self.selectedItems():
            worker = Worker(item.exec_command, command)
            self.threadpool.start(worker)


    def exec_command(self):
        dialog = ChooseCommandDialog(parent=self)
        r = dialog.getResult()
        if not r: return
        for item in self.selectedItems():
            logging.info("try to send command {} to {}".format(r, str(item)))
            worker = Worker(item.exec_command, r)
            self.threadpool.start(worker)

    def new_item(self):
        dialog = SSHInputDialog(parent=self)
        r = dialog.getResult()
        if not r: return
        for f in r:
            item = load_ssh_file(f)
            item.info['filepath'] = str(r)
            self.model().appendItem(item)

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
            self.vncviewer_threads.start(worker)

    def open_terminal(self):
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell)
            self.terminal_threads.start(worker)


    def copy_hostaddress(self):
        t = ["{}@{}".format(i.get('username'), i.get("hostname")) for i in self.selectedItems()]
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.clear(mode=clipboard.Clipboard )
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


    def upload(self):
        dialog = SCPDialog(download=False)
        info = dialog.getResult()
        if not info: return
        for item in self.selectedItems():
            worker = Worker(item.upload_by_subprocess, 
                        recursive=False,
                        src_path=info['src_path'],
                        dst_path=info['dst_path'])

            self.threadpool.start(worker)

    def download(self):
        dialog = SCPDialog(download=True)
        info = dialog.getResult()
        if not info:
            return None
        for item in self.selectedItems():
            worker = Worker(item.download_by_subprocess, 
                        recursive=False,
                        src_path=info['src_path'],
                        dst_path=info['dst_path'])

            self.threadpool.start(worker)

    def new_url_at_current_tab(self):
        text, okPressed = QtWidgets.QInputDialog.getText(self, "URL", "URL", QtWidgets.QLineEdit.Normal, "")
        url = text.strip()
        if okPressed and url:
            cmd = '{0} key "ctrl+l" && {0} type --delay 100 "{1}" && {0} key Return'.format("DISPLAY=:1 xdotool", url)
            for item in self.selectedItems():
                worker = Worker(item.exec_command, cmd)
                self.threadpool.start(worker)


    def install_sshkey(self):
        text, okPressed = QtWidgets.QInputDialog.getText(self, "Install SSH Key", "SSHKEY", QtWidgets.QLineEdit.Normal, "")
        key = text.strip()
        if okPressed and key:
            cmd = '[[ -f {0} ]] || mkdir -p ~/.ssh && touch {0} && echo "{1}" >> {0}'.format('~/.ssh/authorized_keys', key)
            for item in self.selectedItems():
                worker = Worker(item.exec_command, cmd)
                self.threadpool.start(worker)



    def send_key(self):
        items = ("Escape", "F5", "space", "Return", "f", "ctrl+w", "ctrl+q")
        item, okPressed = QtWidgets.QInputDialog.getItem(self, "Send key","Key", items, 0, False)
        if okPressed and item:
            cmd = '{} key {}'.format("DISPLAY=:1 xdotool", item)
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
            dirname = os.path.join(os.path.dirname(item.get('filepath')), 'Trash')
            os.makedirs(dirname, exist_ok=True)
            newfile = os.path.join(dirname, os.path.basename(item.get('filepath')))
            try:
                os.rename(item.get('filepath'), newfile)
            except Exception as e:
                logging.error(e, exc_info=True)
            try:
                self.model().removeItem(item)
            except Exception as e:
                logging.error(e, exc_info=True)

# class DirectoryListModel(QtCore.QAbstractListModel):
#     def __init__(self):
#         QtCore.QAbstractListModel.__init__(self)
# 
# 
# class GroupThumbnailListViewer(QtWidgets.QListView):
#     def __init__(self, dir, parent=None, **kwargs):
#         """TODO: to be defined. """
#         QtWidgets.QtWidgets.__init__(self, parent, **kwargs)
#         self.root_dir = dir
# 
#         self.guidict = {
#             "layout": QtWidgets.QHBoxLayout(),
#             "grouplist": QtWidgets.QtWidgets.QListView(self),
#             "thumnailview": ThumbnailListViewer(self)
#         }
# 
#     def initUI(self):
#         layout = self.guidict["layout"]
# 
#         self.initGroupList()
#         self.guidict["grouplist"].setFixeWidth(200)
#         self.guidict["grouplist"].doubleClicked.connect(self.switchModel)
#         layout.addWidget(self.guidict['grouplist'])
# 
#         layout.addWidget(self.guidict['thumnailview'])
#         self.initThumbnailView()
# 
# 
#     def initModels(self):
#         for entry in os.scandir(self.root_dir):
#             if entry.is_dir():
#                 m = ListModel(load_ssh_dir(entry.path), parent=self)
#                 self.models.append(m)
# 
# 
#     def selectedItems(self):
#         # return [self.model().itemAtRow(i.row()) for i in self.selectedIndexes()][0]
#         model = self.guidict['grouplist'].model()
#         return model().itemAtRow(i.row()) for i in self.selectedIndexes()
# 
# 
#     def switchModel(self, index):
#         self.current_model.setAutoUpdate(False)
#         self.current_model = self.models[index]
#         self.current_model.setAutoUpdate(True)
#         self.listview.setModel(self.current_model)
# 
#     def initGroupList(self):
#         self.initModels()
# 
#     def initThumbnailView(self):
#         self.current_model = self.models[0]
#         self.current_model.setAutoUpdate(True)
#         self.listview = ThumbnailListViewer(parent=self)
#         self.listview.setModel(self.current_model)



def main(): 
    import logging
    logging.basicConfig(level=logging.INFO, filename='log.txt',
        format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s', datefmt='%m-%d %H:%M')

    app = QtWidgets.QApplication(sys.argv) 
    w = ThumbnailListViewer() 
    # w.setFixedWidth(1800)
    # w.setFixedHeight(1000)
    w.show() 
    r = app.exec_()
    common.close_all = True
    sys.exit(r) 
	
if __name__ == "__main__": 
    main()

