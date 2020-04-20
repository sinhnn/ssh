import sys
# import traceback
import os
# import time
# from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication
import logging

# My modules ==================================================================
import common
from listModel import (
        ThumbnailListViewer,
        ListModel,
        ThumbnailWidget,
)
from sshTable import (
        # SSHTable,
        SSHWidget,
        load_ssh_dir
)

__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ = os.path.join(__PATH__, 'ssh')
if getattr(sys, 'frozen', False):
    __PATH__ = os.path.abspath(os.path.dirname(sys.executable))
elif __file__:
    __PATH__ = os.path.abspath(os.path.dirname(__file__))


def changeBackgroundColor(widget, colorString):
    widget.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    style = "background-color: %s;" % colorString
    widget.setStyleSheet(style)


def getAppIcon():
    return QtGui.QIcon('icons/computer.png')


def timedeltaToString(deltaTime):
    s = deltaTime.seconds
    hours, remainder = divmod(s, 3600)
    minutes, seconds = divmod(remainder, 60)
    return '%s:%s:%s' % (hours, minutes, seconds) 

class MainFrame(QtWidgets.QMainWindow):
    MODE_ACTIVE = 2

    def __init__(self, dir=[__SSH_DIR__]):
        self.dir = dir
        self._name = ','.join(self.dir)
        self._data = []
        for d in self.dir:
            self._data.extend(load_ssh_dir(d))

        self.__initalMode = 0
        super(MainFrame, self).__init__()
        self.setWindowTitle(self._name)
        self.setWindowIcon(getAppIcon())
        self.initUI()
        self.centerWindow()

    def initUI(self):

        self.tabWidget = QtWidgets.QTabWidget(self)
        self.tabWidget.setTabsClosable(True)

        # Main thumbnail widgets
        self.models = []
        model = ListModel(data=self._data, parent=self)
        self.models.append(model)

        self._thumbnailWidget = ThumbnailWidget(parent=self, model=model)
        self.table = SSHWidget(self._thumbnailWidget.thumbnailListView.model().getData())

        self.tabWidget.addTab(self._thumbnailWidget, "Thumbnail")
        self.tabWidget.addTab(self.table, "SSHTable - {}".format(self._name))
        self.setCentralWidget(self.tabWidget)

        self.exitAction = QtWidgets.QAction('Exit', self)
        self.exitAction.setShortcut('Ctrl+Q')
        self.exitAction.triggered.connect(self.on_exit)

        self.loadAction = QtWidgets.QAction('Load Directory', self)
        self.loadAction.triggered.connect(self.loadDir)

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.loadAction)
        fileMenu.addSeparator()

        self.setWindowTitle("SSH-VNC {}".format(self._name))

    def loadDir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "VPS directory", "", QtWidgets.QFileDialog.ShowDirsOnly)
        if not d:
            return
        data = load_ssh_dir(d)
        model = ListModel(data=data, parent=self)
        self.models.append(model)
        thumbnailWidget = ThumbnailWidget(parent=self, model=model)
        table = SSHWidget(model.getData())
        self.tabWidget.addTab(thumbnailWidget, "Thumbnail - " + str(d))
        self.tabWidget.addTab(table, "SSHTable - " + str(d))
        return


    def on_exit(self):
        common.close_all = True
        QApplication.quit()

    def closeEvent(self, event):
        common.close_all = True
        quit_msg = "Are you sure you want to exit the program?"
        reply = QtWidgets.QMessageBox.question(
                self,
                'Message',
                quit_msg,
                QtWidgets.QMessageBox.Yes,
                QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(
                QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())

    def updateWindowTitle(self, text):
        self.setWindowTitle("VideoCut - " + text)

    def showWarning(self, aMessage):
        pad = '\t'
        QtWidgets.QMessageBox.warning(self, "Warning!", aMessage + pad)


    def getErrorDialog(self, text, infoText, detailedText):
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(
                300, 0,
                QtWidgets.QSizePolicy.Minimum,
                QtWidgets.QSizePolicy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        return dlg

    def getMessageDialog(self, text, infoText):
        # dlg = DialogBox(self)
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Information)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Notice")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        # Workaround to resize a qt dialog. WTF!
        spacer = QtWidgets.QSpacerItem(
                300, 0,
                QtWidgets.QSizePolicy.Minimum,
                QtWidgets.QSizePolicy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())

        # dlg.setMinimumSize(450, 0)
        return dlg


if __name__ == '__main__':

    DEBUG_FORMAT = """%(asctime)s %(name)-12s %(levelname)-8s
    [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"""
    argv = sys.argv
    logfile = 'log.txt'
    if len(argv) == 2:
        logfile = os.path.dirname(argv[1]) + '.' + logfile
    open(logfile, 'w', encoding='utf-8').write('')
    logging.basicConfig(
            filename=logfile,
            filemode='a',
            level=logging.DEBUG,
            format=DEBUG_FORMAT)
    logging.propagate = True

    app = QApplication(argv)
    app.setWindowIcon(getAppIcon())
    if len(argv) == 2:
        w = MainFrame(dir=[argv[1]])
    elif len(argv) > 2:
        w = MainFrame(dir=argv[1:])
    else:
        w = MainFrame()

    w.move(0, 0)
    w.setGeometry(0, 0, 1000, 1000)

    if os.path.isfile('stylesheet.css'):
        with open('stylesheet.css', 'r') as fp:
            w.setStyleSheet(fp.read())
    w.show()
    app.exec_()
