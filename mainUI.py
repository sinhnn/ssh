import sys,traceback,os, time
from PyQt5.QtCore import pyqtSignal
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QWidget
import logging

from listModel import ThumbnailListViewer, ListModel
from sshTable import SSHTable
from logWidget import LogWidget, PlainTextEditLogger

import common

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

from sshTable import ChooseCommandDialog, load_ssh_dir, load_ssh_file
__PATH__ = os.path.dirname(os.path.abspath(__file__))
__SSH_DIR__ =  os.path.join(__PATH__, 'ssh')
class MainFrame(QtWidgets.QMainWindow):
    MODE_ACTIVE = 2
    # signalActive = pyqtSignal()
    
    def __init__(self, dir=__SSH_DIR__):
        self.dir = dir
        self.__initalMode = 0
        super(MainFrame, self).__init__()
        self.setWindowIcon(getAppIcon())
        # self.settings = SettingsModel(self)
        self.initUI()
        # self._widgets = self.initUI()
        self.centerWindow()
        self.setMinimumSize(1800,1000)
   
        # self._update_timer = QtCore.QTimer()
        # self._update_timer.start(1000)
        # self._update_timer.timeout.connect(self.repaint)


    def initUI(self):
        mWidgets = QtWidgets.QWidget()
        mlayout = QtWidgets.QVBoxLayout()
        widgets = ThumbnailListViewer(parent=self)
        model = ListModel(load_ssh_dir(self.dir), parent=self)
        widgets.setModel(model)
        mlayout.addWidget(widgets)
        mWidgets.setLayout(mlayout)
        self._widgets = widgets
        self._widgets.setIconView()
        self._widgets.model().fupate.connect(self._widgets.force_update)

        self.search = QtWidgets.QLineEdit(self) 
        self.search.setPlaceholderText("Enter address/tags to search")
        self.search.textChanged.connect(self.on_search)

        self.scale =  QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.scale.setMinimum(10)
        self.scale.setMaximum(100)
        self.scale.setTickInterval(10)
        self.scale.setTickPosition(QtWidgets.QSlider.TicksBothSides)
        self.scale.setFixedWidth(150)
        self.scale.setValue(50)
        self.scale.valueChanged.connect(self.on_scale)

        self.sort_order = True
        self.sort_order_button = QtWidgets.QToolButton() 
        self.sort_order_button.setArrowType(QtCore.Qt.DownArrow)
        self.sort_order_button.clicked.connect(self.re_sort)
        self.sort_by = QtWidgets.QLineEdit(self) 
        self.sort_by.setPlaceholderText("Enter key to sort")
        self.sort_by.editingFinished.connect(self.on_sort)
        self.sort_by.setMaximumWidth(300)

        self.table = SSHTable(widgets.model().getData())
        self.table.setMinimumSize(800,600)
        self.table.setWindowTitle('SSH Table')
        self.setCentralWidget(mWidgets);

        # self.exitAction = QtWidgets.QAction('Exit', self)
        # self.exitAction.setShortcut('Ctrl+Q')
        # self.exitAction.triggered.connect(self.on_exit)

        self.loadAction = QtWidgets.QAction('Load Directory', self)
        self.loadAction.triggered.connect(self.loadDir)

        self.iconViewAction = QtWidgets.QAction('Icon View', self)
        self.iconViewAction.triggered.connect(self._widgets.setIconView)

        self.detailViewAction = QtWidgets.QAction('List View', self)
        self.detailViewAction.triggered.connect(self._widgets.setListView)

        self.sortByNameAction = QtWidgets.QAction('Sort by Name', self)
        self.sortByNameAction.triggered.connect(self.on_sort_by_name)

        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"),
                self).activated.connect(lambda : self.search.setFocus())

        QtWidgets.QShortcut(QtGui.QKeySequence("escape"),
                self).activated.connect(lambda : self.search.clear())

        self.openSSHTableAction = QtWidgets.QAction('Open Table', self)
        self.openSSHTableAction.triggered.connect(lambda : self.table.setVisible(True))

        self.toolbar = self.addToolBar('Main')
        self.toolbar.addAction(self.iconViewAction)
        self.toolbar.addAction(self.detailViewAction)
        self.toolbar.addAction(self.openSSHTableAction)
        self.toolbar.addWidget(self.scale)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.search)
        self.toolbar.addAction(self.sortByNameAction)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.sort_by)
        self.toolbar.addWidget(self.sort_order_button)
        self.toolbar.addSeparator()
                              
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(self.loadAction)
        fileMenu.addSeparator();
        # fileMenu.addAction(self.exitAction)

        self.setWindowTitle("....")

    def on_exit(self):
        common.close_all = True
        QApplication.quit()

    def closeEvent(self, event):
        common.close_all = True
        quit_msg = "Are you sure you want to exit the program?"
        reply = QtWidgets.QMessageBox.question(self, 'Message', quit_msg,
                QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


    def on_scale(self, value):
        self._widgets.scaleIcon(float(value/100.0))

    def re_sort (self):
        if self.sort_order:
            self.sort_order_button.setArrowType(QtCore.Qt.DownArrow)
        else:
            self.sort_order_button.setArrowType(QtCore.Qt.UpArrow)
        self.sort_order = not self.sort_order
        self.on_sort()

    def on_sort_by_name(self):
        self.sort_order = not self.sort_order
        self._widgets.model().sort(self.sort_order)

    def on_sort(self):
        self._widgets.model().sort_by(self.sort_by.text(), self.sort_order)

    def on_search(self, event):
        for i in range(self._widgets.model().count()):
            item = self._widgets.model().itemAtRow(i)
            hide = not (str(event) in str(item.config))
            self._widgets.setRowHidden(i, hide)
    
    def centerWindow(self):
        frameGm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        centerPoint = QApplication.desktop().screenGeometry(screen).center()
        frameGm.moveCenter(centerPoint)
        self.move(frameGm.topLeft())
    
    def updateWindowTitle(self, text):
        self.setWindowTitle("VideoCut - " + text)
    
    
    def showWarning(self, aMessage):
        pad = '\t'
        QtWidgets.QMessageBox.warning(self, "Warning!", aMessage + pad)
    
    #-------- ACTIONS ----------
    def loadDir(self):
        pass
            
    def getErrorDialog(self, text, infoText, detailedText):
        dlg = QtWidgets.QMessageBox(self)
        dlg.setIcon(QtWidgets.QMessageBox.Warning)
        dlg.setWindowModality(QtCore.Qt.WindowModal)
        dlg.setWindowTitle("Error")
        dlg.setText(text)
        dlg.setInformativeText(infoText)
        dlg.setDetailedText(detailedText)
        dlg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
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
        spacer = QtWidgets.QSpacerItem(300, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout = dlg.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        
        # dlg.setMinimumSize(450, 0)
        return dlg;


if __name__ == '__main__':
    DEBUG_FORMAT = "%(asctime)s %(name)-12s %(levelname)-8s [%(filename)s:%(lineno)s - %(funcName)20s() ] %(message)s"
    if os.path.isfile('log.txt'): open('log.txt', 'w').write('')
    # logging.basicConfig(level=logging.INFO, format=DEBUG_FORMAT)
    fileHandler = logging.FileHandler('log.txt', mode='a', encoding=None, delay=False)
    fileHandler.setFormatter(logging.Formatter(DEBUG_FORMAT))
    fileHandler.setLevel(logging.INFO)
    logging.getLogger().addHandler(fileHandler)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().propagate = True
    argv = sys.argv
    app = QApplication(argv)
    app.setWindowIcon(getAppIcon())
    w = MainFrame()
    # screenrect = QApplication::desktop().screenGeometry();
    w.move(0,0)
    if os.path.isfile('stylesheet.css'):
        with open('stylesheet.css', 'r') as fp:
            # w.setStyleSheet("QToolTip{ border: 1px solid white; font-family: 'Courier New';}")
            w.setStyleSheet(fp.read())
    w.show()
    app.exec_()
