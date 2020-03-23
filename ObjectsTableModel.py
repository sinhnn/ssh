#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  ObjectsTableModel.py Author "sinhnn <sinhnn.92@gmail.com>" Date 16.12.2019

# from PyQt5 import QtGui
# from PyQt5 import QtWidgets
from PyQt5.QtCore import (Qt, QAbstractTableModel, QModelIndex, QVariant)
from PyQt5 import QtCore
import logging
import threading
import time


class ComboBoxModel(QtCore.QAbstractItemModel):
    '''
        Model list of item for Combobox
            - name
            - value
    '''
    def __init__(self, data=[], parent=None, **kwargs):
        QtCore.QAbstractItemModel.__init__(self, **kwargs)
        self._header = ['name', 'value']
        self._parent = parent
        self._data = data

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        return QModelIndex()
        self.createIndex(index.row(), 0, self._parent)

    def index(self, row, col, parent):
        return self.createIndex(row, col, parent)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            logging.debug("invalid index")
            return QVariant()
        elif not 0 <= index.row() < len(self._data):
            logging.debug("row is out of data range")
            return QVariant()
        elif role not in [Qt.DisplayRole, Qt.EditRole]:
            return QVariant()
        elif role in [Qt.DisplayRole, Qt.EditRole]:
            try:
                name = self._data[index.row()]['name']
                return str(name)
            except Exception:
                return ''
        return QVariant()

    def columnCount(self, parent=QModelIndex()):
        return 1

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def insertRows(self, position, rows=1, index=QModelIndex()):
        self.beginInsertRows(QModelIndex(), position, position + rows - 1)
        for row in range(rows):
            self._data.insert(
                    position + row,
                    {key: None for key in self._header})
        self.endInsertRows()
        return True

    def itemAtRow(self, row):
        if row >= self.rowCount() or row < 0:
            logging.error('invalid index', exc_info=True)
            return None
        return self._data[row]

    def appendItem(self, item):
        self.beginInsertRows(
                QModelIndex(),
                self.rowCount() - 1,
                self.rowCount() - 1)
        self._data.append(item)
        self.endInsertRows()
        return True

    def flags(self, index):
        """ Set the item flags at the given index. Seems like we're
            implementing this function just to see how it's done, as we
            manually adjust each tableView to have NoEditTriggers.
        """
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(
            QtCore.QAbstractItemModel.flags(self, index) | Qt.ItemIsEditable)


class ObjectsTableModel(QtCore.QAbstractTableModel):
    fupate = QtCore.pyqtSignal(QtCore.QModelIndex)

    def __init__(self, data, **kwargs):
        super(ObjectsTableModel, self).__init__(**kwargs)
        self._header = [
                'hostname',
                'lastupdate',
                'status',
                'robot',
                'allproc',
                'data',
                'next_data',
                'email',
                'ytvlog',
                'lastcmd',
                'msg',
                'error']

        self._data = data
        self.__check_update__()

    def __update_header__(self):
        for item in self._data:
            self.__add_header_(item)

    def __add_header_(self, item):
        for k in item.keys():
            if k not in self._header:
                self._header.append(k)

    def __check_update__(self):
        threads = []
        for t in [self._dataChanged]:
            threads.append(threading.Thread(target=t))
            threads[-1].daemon = True
            threads[-1].start()

    def _dataChanged(self):
        while True:
            for i, c in enumerate(self._data):
                for info in c.changed + ['robot', 'url']:
                    if info not in self._header:
                        continue
                    index3 = self.createIndex(i, self._header.index(info))
                    self.dataChanged.emit(index3, index3, [])
                    try:
                        self.fupate.emit(index3)
                    except AttributeError:
                        pass
                    c.changed.remove(info)
            time.sleep(1)

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._header)

    def headername(self, index):
        return self._header[index.column()]

    def objectData(self, index):
        return self._data[index.row()]

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return QVariant()
        else:
            if orientation == Qt.Horizontal:
                return self._header[section]
            elif orientation == Qt.Vertical:
                return section + 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            logging.debug("invalid index")
            return QVariant()
        elif not 0 <= index.row() < len(self._data):
            logging.debug("row is out of data range")
            return QVariant()
        elif role not in [Qt.DisplayRole, Qt.EditRole]:
            return QVariant()
        elif role in [Qt.DisplayRole, Qt.EditRole]:
            try:
                value = self._data[index.row()].get(self.headername(index), '')
                return str(value)
            except Exception:
                return ''
        return QVariant()

    def insertRows(self, position, rows=1, index=QModelIndex()):
        self.beginInsertRows(QModelIndex(), position, position + rows - 1)
        for row in range(rows):
            self._data.insert(
                    position + row,
                    {key: None for key in self._header})
        self.endInsertRows()
        return True

    def removeRows(self, position, rows=1, index=QModelIndex()):
        self.beginRemoveRows(QModelIndex(), position, position + rows - 1)
        del self._data[position:position+rows]
        self.endRemoveRows()
        return True

    def appendItem(self, item):
        s = self.rowCount() - 1
        self.beginInsertRows(QModelIndex(), s, s)
        self._data.append(item)
        # self.__update_header__()
        self.endInsertRows()
        return True

    def itemAlreadyExist(self, item):
        return item in self._data

    def itemAtRow(self, row):
        return self._data[row]

    def setData(self, index, value, role=Qt.EditRole):
        if role != Qt.EditRole:
            return False
        if index.isValid() and 0 <= index.row() < len(self._data) and not value:
            try:
                self._data[index.row()].update(self.headername(index), value)
                self.dataChanged.emit(index, index)
                return True
            except Exception as e:
                logging.error('unable to set data\n{}'.format(e), exc_info=True)
                pass
        return False

    def flags(self, index):
        """ Set the item flags at the given index. Seems like we're
            implementing this function just to see how it's done, as we
            manually adjust each tableView to have NoEditTriggers.
        """
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemFlags(QAbstractTableModel.flags(self, index) |
                            Qt.ItemIsEditable)

    def sort(self, col, order):
        try:
            self.layoutAboutToBeChanged.emit()
            self._data.sort(
                    key=lambda item: item.get(self._header[col], ''),
                    reverse=not order)
            self.layoutChanged.emit()
        except Exception as e:
            logging.error(e, exc_info=True)

    def removeItem(self, item):
        row = self.__data__.index(item)
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.__data__.remove(item)
        self.endRemoveRows()
