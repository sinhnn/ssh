import socket
import collections 
import multiprocessing

PORT = collections.namedtuple('PORT', ['port', 'opening'])
__MIN_PORT__ = int(1)
__MAX_PORT__ = int(2**16 -1)
__CPU_COUNT__ = multiprocessing.cpu_count()

class PortScanner(object):
    def __init__(self, host='127.0.0.1', **kwarg):
        super(PortScanner, self).__init__()
        self.host = host
        self.timeout = 1/10000.0

    def isOpen(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        r = sock.connect_ex((self.host, port))
        opening = (r==0)
        sock.close()
        return PORT(port, opening)

    def scan(self, pRange=range(__MIN_PORT__, __MAX_PORT__)):
        if __CPU_COUNT__ <= 2:
            results = [self.isOpen(i) for i in pRange]
        with multiprocessing.Pool(int(__CPU_COUNT__ * 2/3)) as pool:
            results = pool.map(self.isOpen, pRange)
        return list(filter(lambda p : p[1] == True, results))

    def getAvailablePort(self, pRange=range(__MIN_PORT__, __MAX_PORT__)):
        for i in pRange:
            if self.isOpen(i)[1] == False:
                return i
        return None

import psutil
def find_proc(afilter, break_on_matched=True):
    matched = []
    for proc in psutil.process_iter():
        try:
            if afilter(proc):
                matched.append(proc)
                if break_on_matched: break
        except PermissionError:
            pass
    return matched

if __name__ == "__main__":
    p = PortScanner()
    r = p.scan()
    print(r)
