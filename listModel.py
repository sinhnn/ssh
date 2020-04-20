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
from sshContextMenu import SSHActions, XDOTOOL

__PATH__ = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, 'frozen', False):
    __PATH__ = os.path.abspath(os.path.dirname(sys.executable))
elif __file__:
    __PATH__ = os.path.abspath(os.path.dirname(__file__))

__SSH_DIR__ = os.path.join(__PATH__, 'ssh')


class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    fupate = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, data=[], auto_update=True, parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.parent = parent
        self.__data__ = data
        self.__auto_update__ = auto_update

        self._updatePeriod = 60
        self.threadpool = QtCore.QThreadPool()
        self.threadpool.setMaxThreadCount(50)
        self.threadpool.waitForDone(-1)
        self.threadpool.start(Worker(self.update_thumbnail))
        self.threads = []
        # self.__daemon__()

        self.__updating_item__ = []
        self.__role__ = [QtCore.Qt.DecorationRole | QtCore.Qt.DisplayRole]

    def setUpdatePeriod(self, second):
        self._updatePeriod = second

    def updatePeriod(self):
        return self._updatePeriod

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
                    # self.dataChanged.emit(topLeft, topLeft, self.__role__)
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

            time.sleep(self.updatePeriod())

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


class ThumbnailListViewer(SSHActions, QtWidgets.QListView):
    """Docstring for ThumbnailListViewer. """
    __DEFAULT_ICON_SIZE__ = QtCore.QSize(160, 65)
    __DEFAULT_GRID_SIZE__ = QtCore.QSize(160, 130)
    __LARGE_ICON_SIZE__ = QtCore.QSize(320, 180)
    __LARGE_GRID_SIZE__ = QtCore.QSize(320, 260)

    def __init__(self, parent=None, **kwargs):
        """TODO: to be defined. """
        SSHActions.__init__(self, parent=parent, **kwargs)
        QtWidgets.QListView.__init__(self, parent, **kwargs)

        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setIconView()
        self.doubleClicked.connect(self.open_vncviewer)
        self.setDragEnabled(False)
        self.initUI()

        self.setStyleSheet("font-size: 12px;")

    def initUI(self):
        self.menu = QtWidgets.QMenu(self)
        self.actions = {
            'open': self.open_vncviewer,
            'open_terminal': self.open_terminal,
            'open_folder': self.open_folder,
            'debot': self.debot,
            'Send F5': lambda: self.exec_command(XDOTOOL + ' key F5'),
            'Send Space': lambda: self.exec_command(XDOTOOL + ' key space'),
            'Send Escape': lambda: self.exec_command(XDOTOOL + ' key Escape'),
            'send_key': self.send_key,
            'open_terminal_with_cmd': self.open_terminal_with_cmd,
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

    def selectedItems(self, select_all=False):
        model = self.model()
        if select_all is True:
            return [model.itemAtRow(i) for i in range(0, model.rowCount())]
        return [model.itemAtRow(i.row()) for i in self.selectedIndexes()]

    def contextMenuEvent(self, event):
        self.menu.popup(QtGui.QCursor.pos())
        self.menu.exec_(QtGui.QCursor.pos())

    def force_update(self, index):
        rect = self.visualRect(index)
        self.viewport().update(rect)

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

    def __event2item__(self, event):
        row = self.rowAt(event.pos().y())
        return self.model().itemAtRow(row)


class ThumbnailWidget(QtWidgets.QWidget):

    """Docstring for ThumbnailWidget. """

    def __init__(self, parent, model, **kwargs):
        QtWidgets.QWidget.__init__(self, parent)

        self._parent = parent
        self._layout = QtWidgets.QVBoxLayout()
        self.thumbnailListView = ThumbnailListViewer(parent=self)
        self.thumbnailListView.setModel(model)
        self.thumbnailListView.setIconView()
        self.thumbnailListView.model().fupate.connect(self.thumbnailListView.force_update)
        self._layout.addWidget(self.thumbnailListView)
        self.setLayout(self._layout)

        self.initOpts()

    def initOpts(self):
        setUpdatePeriod = QtWidgets.QLineEdit(self)
        setUpdatePeriod.setPlaceholderText(str(self.thumbnailListView.model().updatePeriod()))
        setUpdatePeriod.setMaximumWidth(40)
        setUpdatePeriod.editingFinished.connect(self.set_updatePeriod)

        self.scale = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.scale.setMinimum(10)
        self.scale.setMaximum(100)
        self.scale.setTickInterval(10)
        self.scale.setTickPosition(QtWidgets.QSlider.TicksBothSides)
        self.scale.setFixedWidth(150)
        self.scale.setValue(30)
        self.scale.valueChanged.connect(self.on_scale)

        self.sort_order = True
        self.sort_order_button = QtWidgets.QToolButton()
        self.sort_order_button.setArrowType(QtCore.Qt.DownArrow)
        self.sort_order_button.clicked.connect(self.re_sort)
        self.sort_by = QtWidgets.QLineEdit(self)
        self.sort_by.setPlaceholderText("Enter key to sort")
        self.sort_by.editingFinished.connect(self.on_sort)
        self.sort_by.setMaximumWidth(300)

        self.iconViewAction = QtWidgets.QAction('Icon View', self)
        self.iconViewAction.triggered.connect(self.thumbnailListView.setIconView)

        self.detailViewAction = QtWidgets.QAction('List View', self)
        self.detailViewAction.triggered.connect(self.thumbnailListView.setListView)

        self.sortByNameAction = QtWidgets.QAction('Sort by Name', self)
        self.sortByNameAction.triggered.connect(self.on_sort_by_name)

        self.sortByStatusAction = QtWidgets.QAction('Sort by Status', self)
        self.sortByStatusAction.triggered.connect(self.on_sort_by_status)

        QtWidgets.QShortcut(
                QtGui.QKeySequence("Ctrl+F"),
                self).activated.connect(lambda: self.search.setFocus())

        QtWidgets.QShortcut(
                QtGui.QKeySequence("escape"),
                self).activated.connect(lambda: self.search.clear())

        self.toolbar = QtWidgets.QToolBar(self)
        self.toolbar.addAction(self.iconViewAction)
        self.toolbar.addAction(self.detailViewAction)
        self.toolbar.addWidget(self.scale)

        self.toolbar.addSeparator()
        self.toolbar.addWidget(setUpdatePeriod)
        self.toolbar.addWidget(QtWidgets.QLabel("Update Period"))

        self.toolbar.addSeparator()
        # self.toolbar.addWidget(self.search)

        self.toolbar.addAction(self.sortByNameAction)
        self.toolbar.addAction(self.sortByStatusAction)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.sort_by)
        self.toolbar.addWidget(self.sort_order_button)
        self.toolbar.addSeparator()

        self._layout.setMenuBar(self.toolbar)

    def on_scale(self, value):
        self.thumbnailListView.scaleIcon(float(value/100.0))

    def re_sort(self):
        if self.sort_order:
            self.sort_order_button.setArrowType(QtCore.Qt.DownArrow)
        else:
            self.sort_order_button.setArrowType(QtCore.Qt.UpArrow)
        self.sort_order = not self.sort_order
        self.on_sort()

    def on_sort_by_name(self):
        self.sort_order = not self.sort_order
        self.thumbnailListView.model().sort(self.sort_order)

    def on_sort_by_status(self):
        self.sort_order = not self.sort_order
        self.thumbnailListView.model().sort_by("icon", self.sort_order)

    def on_sort(self):
        self.thumbnailListView.model().sort_by(self.sort_by.text(), self.sort_order)

    def on_search(self, event):
        for i in range(self.thumbnailListView.model().count()):
            item = self.thumbnailListView.model().itemAtRow(i)
            hide = not (str(event) in str(item.config))
            self.thumbnailListView.setRowHidden(i, hide)

    def set_updatePeriod(self):
        try:
            d = int(self.setUpdatePeriod.text())
            self.thumbnailListView.model().setUpdatePeriod(d)
        except Exception:
            return




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
