from PyQt5.QtWidgets import (
        QMainWindow, QApplication, QWidget, QAction,
        QTableView, QTableWidget,QTableWidgetItem, QHeaderView,
        QVBoxLayout, QGridLayout,
        QPushButton, QLineEdit, QShortcut, QPlainTextEdit, QTextEdit, QComboBox,
        QMenu, QAbstractItemView,QStyle, QStyleOptionTitleBar,
        )
from PyQt5.QtGui import *
from PyQt5 import QtCore
from PyQt5.QtCore import *

def cformat(color, style=''):
    """Return a QTextCharFormat with the given attributes.
    """
    _color = QColor()
    _color.setNamedColor(color)
 
    _format = QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)
 
    return _format
	
STYLES = {
    'good': cformat('green'),
    'error': cformat('red'),
    'warn': cformat('orange'),
    'info': cformat('blue')
}
 
class KeywordHighlighter (QSyntaxHighlighter):
    keywords = {
        "good" : ["successfully", "successful", "ok"],
        "error" : ["error"],
        "warn" : ["warn", "warning", "unable"],
        "info" : ["info", "information"]
    }
    def __init__( self, document):
        QSyntaxHighlighter.__init__( self, document )
        self.parent = document
        _rules = []
        for k, v in STYLES.items():
            _rules += [(r'\b%s\b' % w, 0, v) for w in self.keywords[k]]
        self.rules = [(QRegExp(pat, cs=Qt.CaseInsensitive), index, fmt) for (pat, index, fmt) in _rules]
		
    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, format in self.rules:
            index = expression.indexIn(text, 0)
        
            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)
        # Do multi-line strings
        # in_multiline = self.match_multiline(text, *self.tri_single)
        # if not in_multiline:
        #     in_multiline = self.match_multiline(text, *self.tri_double)


