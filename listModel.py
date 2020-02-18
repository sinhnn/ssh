import os, sys, threading, subprocess, time, logging
from PyQt5 import QtWidgets, QtCore, QtGui

from worker import Worker
from threading import Thread

from common import close_all
from sshDialogForm import SSHInputDialog


class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    def __init__(self, data=[], parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.parent = parent
        self.__data__ = data


    # def force_update(self, delay=1):
    #     # tableview->rect().bottomRight()
    #     bottomRight = self.parent.indexAt(slf.parent.rect().bottomRight())
    #     while (True):
    #         self.dataChanged.emit(QtCore.QModelIndex(), bottomRight, [])
    #         time.sleep(delay)

    def force_update(self):
        while True:
            try:
                self.layoutAboutToBeChanged.emit()
                # self.__data__.sort(key=lambda item : item.get(key, 'Z'),  reverse=not order)
                self.__data__.sort(key=lambda item : item.get('hostname'),  reverse=not order)
                # self.dataChanged.emit(QtCore.QModelIndex(), QtCore.QModelIndex((1, 0)), [])
                # self.setFocus()
                self.layoutChanged.emit()
            except Exception as e:
                logging.error(e, exc_info=True)
            time.sleep(1)


    def getData(self):
        return self.__data__

    def count(self):
        return len(self.__data__)

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.__data__)

    def itemAtRow(self, i):
        return self.__data__[i]

    def appendItem(self, item):
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount() - 1, self.rowCount() - 1)
        self.__data__.append(item)
        self.endInsertRows()
        return True
        
    def data(self, index, role = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        item = self.__data__[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return str(item)#item.get('hostname') + '\n' + item.get('tag','')

        elif role == QtCore.Qt.DecorationRole:
            return QtGui.QIcon(item.get('icon', 'icon/computer.png'))

        return None	

    def flags(self, idx):
        if idx.isValid():
            return QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled |\
                   QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        else:
            return QtCore.Qt.ItemIsDropEnabled |\
                   QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled

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


from sshTable import ChooseCommandDialog, load_ssh_dir, load_ssh_file
__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ =  os.path.join(__PATH__, 'ssh')
class ThumbnailListViewer(QtWidgets.QListView):
    """Docstring for ThumbnailListViewer. """
    __DEFAULT_ICON_SIZE__ = QtCore.QSize(320, 260)
    def __init__(self, dir=__SSH_DIR__, parent=None, **kwargs):
        """TODO: to be defined. """
        QtWidgets.QListView.__init__(self, parent, **kwargs)
        self.dir = dir

        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setIconView()

        self.doubleClicked.connect(self.open)
        self.setDragEnabled(False)

        self.threadpool = QtCore.QThreadPool()
        self.initUI()

    def initUI(self):
        model = ListModel(load_ssh_dir(self.dir), self)
        self.setModel(model)
        # worker = Worker(model.force_update)
        # self.threadpool.start(worker)

        self.menu = QtWidgets.QMenu(self)
        self.actions = {
            'open' : self.open_vncviewer,
            'open_terminal' : self.open_terminal,
            'new' : self.new_item,
            'edit' : self.open_file,
            'upload' : self.upload,
            'command' : self.exec_command, # from file or command
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)

    def open_file(self):
        for item in self.selectedItems():
            if item.get('filepath'):
                os.startfile(str(item.get('filepath')))

    def scaleIcon(self, v):
        nw = int(ThumbnailListViewer.__DEFAULT_ICON_SIZE__.width() * v)
        nh = int(ThumbnailListViewer.__DEFAULT_ICON_SIZE__.height() * v)
        ns = QtCore.QSize(nw, nh)
        self.setGridSize(ns)
        self.setIconSize(ns)

    def setIconView(self):
        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setLayoutMode(QtWidgets.QListView.SinglePass)
        self.setResizeMode(QtWidgets.QListView.Adjust)

        self.setGridSize(ThumbnailListViewer.__DEFAULT_ICON_SIZE__)
        self.setIconSize(ThumbnailListViewer.__DEFAULT_ICON_SIZE__)
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

    def exec_command(self):
        dialog = ChooseCommandDialog(parent=self)
        r = dialog.getResult()
        if not r: return
        for item in self.selectedItems():
            worker = Worker(item.exec_command, r)
            self.threadpool.start(worker)

    def new_item(self):
        dialog = SSHInputDialog(parent=self)
        r = dialog.getResult()
        if not r: return
        item = load_ssh_file(r)
        item.info['filepath'] = str(r)
        self.model().appendItem(item)

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
            self.threadpool.start(worker)

    def open_terminal(self):
        for item in self.selectedItems():
            worker = Worker(item.invoke_shell)
            self.threadpool.start(worker)

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
        self.open_vncviewer()
            
    def close(self):
        for item in self.selectedItems():
            item.close()

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
    close_all = True
    sys.exit(r) 
	
if __name__ == "__main__": 
    main()

