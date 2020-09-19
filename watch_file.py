#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  watch_file.py Author "sinhnn <sinhnn.92@gmail.com>" Date 06.04.2020

import os
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import tailer


class FileHander(FileSystemEventHandler):
    """Docstring for FileHander. """
    def __init__(self, parent, **kwargs):
        FileSystemEventHandler.__init__(self, **kwargs)
        self._parent = parent

    def on_any_event(self, event):
        self._parent.update()

    def on_modified(self, event):
        self._parent.update()


class WatchFile(object):
    """Monitoring/Watch/Refesh value in file. """

    def __init__(self, path, **kwargs):
        self._path = path
        self._last_modified = -1
        self._delay = 1
        # store data in memory
        self._value = None
        self._list = []
        self.threads = []
        self.changed = True
        self.update()
        # self.daemon(self.monitoring)

    def daemon(self, *args):
        for f in args:
            t = threading.Thread(target=f)
            t.daemon = True
            t.start()
            self.threads.append(t)

    def monitoring(self):
        self._observer = Observer()
        event_handler = FileSystemEventHandler()
        event_handler.on_any_event = self.update
        self._observer.schedule(event_handler, self._path, False)
        self._observer.start()
        while True:
            time.sleep(self.delay)
        self._observer.stop()
        self._observer.join()

    @property
    def path(self):
        return self._path

    @property
    def delay(self):
        return self._delay

    @property
    def modified_time(self):
        try:
            return os.path.getmtime(self._path)
        except FileNotFoundError:
            return -1

    def update(self, event=None):
        if os.path.isfile(self._path):
            fp = open(self._path, 'r', encoding='utf-8-sig', errors='ignore')
            self._value = fp.read()
            self._list = self._value.splitlines()
            fp.close()
        else:
            self._value = ''
        self._last_modified = self.modified_time

    @property
    def value(self):
        if self._last_modified != self.modified_time:
            self.changed = True
            self.update()
        return self._value

    def __str__(self):
        return self._value

    def to_list(self):
        return self._list

    def tail(self, lines=10):
        self.update()
        s = int(max(len(self._list) - lines, 0))
        return self._list[s:]
        return tailer.tail(open(self._path), lines)


if __name__ == "__main__":
    import sys
    import time
    argv = sys.argv

    t = WatchFile(argv[1])
    while (True):
        print(t.value)
        time.sleep(1)
