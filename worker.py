from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QPushButton, QWidget
from PyQt5.QtCore import QObject, QRunnable, QThreadPool,pyqtSlot, pyqtSignal

import time
import traceback, sys
import logging

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.
    Supported signals are:
    - finished: No data
    - error:`tuple` (exctype, value, traceback.format_exc() )
    - result: `object` data returned from processing, anything
    - progress: `tuple` indicating progress metadata
    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(tuple)


class Worker(QRunnable):
    '''
    Worker thread
    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.
    '''
    id = 0
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self._name = fn.__name__
        self.id = id
        Worker.id += 1
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self.done = False

        # Add the callback to our kwargs
        # self.kwargs['progress_callback'] = self.signals.progress

    def __str__(self):
        # return '[{}] Worker({}, {}, {})'.format(self.done, self._name, self.args, self.kwargs)
        return '[{}] {}({}, {})'.format(self.done, self._name, self.args, self.kwargs)

    def __eq__(self, other):
        return (self.id == other.id)

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        try:
            # Retrieve args/kwargs here; and fire processing using them
            try:
                result = self.fn(*self.args, **self.kwargs)
            except:
                traceback.print_exc()
                exctype, value = sys.exc_info()[:2]
                self.signals.error.emit((exctype, value, traceback.format_exc()))
            else:
                try:
                    self.signals.result.emit(result)  # Return the result of the processing
                except AttributeError:
                    pass
            finally:
                try:
                    self.signals.finished.emit()  # Done
                except AttributeError:
                    pass
        except RuntimeError as e:
            logging.error("RuntimeError: wrapped C/C++ object of type WorkerSignals has been deleted")
        try:
            self.done =True
        except Exception:
            pass

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.counter = 0

        layout = QVBoxLayout()

        self.l = QLabel("Start")
        b = QPushButton("DANGER!")
        b.pressed.connect(self.oh_no)

        layout.addWidget(self.l)
        layout.addWidget(b)

        w = QWidget()
        w.setLayout(layout)

        self.setCentralWidget(w)

        self.show()

        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    def progress_fn(self, progress):
        p, m = (progress)
        print("%d%% done %s" % (p, m))

    def execute_this_fn(self, progress_callback):
        for n in range(0, 5):
            time.sleep(1)
            progress_callback.emit((n*100/4, 'blabla'))
        return "Done."

    def print_output(self, s):
        print(s)

    def thread_complete(self):
        print("THREAD COMPLETE!")

    def oh_no(self):
        # Pass the function to execute
        worker = Worker(self.execute_this_fn) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.progress_fn)
        # Execute
        self.threadpool.start(worker)


class MThreadPool(QThreadPool):
    """docstring for MThreadPool"""
    def __init__(self, tasklist, parent=None, **kwargs):
        QThreadPool.__init__(self, parent, **kwargs)
        self.tasklist = tasklist

    def start(self, worker):
        self.tasklist.append(worker)
        QThreadPool.start(worker)


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    app.exec_()
