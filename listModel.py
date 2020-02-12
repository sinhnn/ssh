import os, sys, threading, subprocess
from PyQt5 import QtWidgets, QtCore, QtGui

from worker import Worker
from threading import Thread

class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    def __init__(self, data=[], parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.__data__ = data


    def rowCount(self, parent):
        return len(self.__data__)

    def itemAtRow(self, i):
        return self.__data__[i]
        
    def data(self, index, role = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        item = self.__data__[index.row()]
        if role == QtCore.Qt.DisplayRole:
            return item.get('hostname')

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


from sshTable import ChooseCommandDialog, load_ssh_dir

__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ =  os.path.join(__PATH__, 'ssh')
class ThumbnailListViewer(QtWidgets.QListView):
    """Docstring for ThumbnailListViewer. """
    def __init__(self, dir=__SSH_DIR__, parent=None, **kwargs):
        """TODO: to be defined. """
        QtWidgets.QListView.__init__(self, parent, **kwargs)
        self.dir = dir

        self.setViewMode(QtWidgets.QListView.IconMode)
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setLayoutMode(QtWidgets.QListView.SinglePass)
        self.setResizeMode(QtWidgets.QListView.Adjust)

        self.setIconSize(QtCore.QSize(320, 180))
        self.setSpacing(5)
        self.setUniformItemSizes(True)

        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.doubleClicked.connect(self.open)

        self.threadpool = QtCore.QThreadPool()
        self.initUI()

    def initUI(self):
        model = ListModel(load_ssh_dir(self.dir))
        self.setModel(model)
        self.setSpacing(5)
        self.setUniformItemSizes(True)

        self.menu = QtWidgets.QMenu(self)
        self.actions = {
            'open' : self.open_vncviewer,
            'edit' : self.open_vncviewer,
            'upload' : self.upload,
            'command' : self.exec_command, # from file or command
        }
        for k, v in self.actions.items():
            self.menu.addAction(k, v)


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
            # (din, out, err) = item.exec_command(r)
            # # print(din, out, err)

    def open_vncviewer(self):
        for item in self.selectedItems():
            worker = Worker(item.open_vncviewer)
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
    logging.basicConfig(level=logging.INFO,
        format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s', datefmt='%m-%d %H:%M')

    app = QtWidgets.QApplication(sys.argv) 
    w = ThumbnailListViewer() 
    # w.setFixedWidth(1800)
    # w.setFixedHeight(1000)
    w.show() 
    sys.exit(app.exec_()) 
	
if __name__ == "__main__": 
    main()

