import os, sys, threading, subprocess
from PyQt5 import QtWidgets, QtCore, QtGui



class ListModel(QtCore.QAbstractListModel):
    """Docstring for ListModel. """
    def __init__(self, data=[], parent=None, **kwargs):
        QtCore.QAbstractListModel.__init__(self, parent, **kwargs)
        self.__data__ = data


    def rowCount(self, parent):
        return len(self.__data__)

        
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

        self.initUI()

    def initUI(self):
        model = ListModel(load_ssh_dir(self.dir))
        self.setModel(model)
        self.setSpacing(5)
        self.setUniformItemSizes(True)



def main(): 
    import logging
    logging.basicConfig(level=logging.INFO,
            format='%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s %(message)s', datefmt='%m-%d %H:%M')

    app = QtWidgets.QApplication(sys.argv) 
    w = ThumbnailListViewer() 
    # w.setFixedWidth(1800)
    # w.setFixedHeight(1000)
    w.show() 
    sys.exit(app.exec_()) 
	
if __name__ == "__main__": 
    main()

