import logging
import subprocess
import psutil
import time
import sshtunnel

# My modules ==================================================================
from platform_ssh import (
    CMD,
)
from ssh_options import KEEP_ALIVE


class SSHTunnelForwarder(sshtunnel.SSHTunnelForwarder):
    """Docstring for SSHTunnelForwarder. """
    def __init__(self, **kwargs):
        sshtunnel.SSHTunnelForwarder.__init__(self, **kwargs)
        self.config = kwargs
        self.tunnel_proc = []
        if 'local_bind_port' not in self.config.keys():
            self.config['local_bind_port'] = self.config.get(
                    'local_bind_address',
                    ('127.0.0,1', None))[1]
            logging.info(self.config['local_bind_port'])

    def get(self, key, default=None):
        return self.config.get(key, default)

    def local_bind_address_str(self):
        key = 'local_bind_address'
        if self.get(key):
            return '{}:{}'.format(self.get(key)[0], self.get(key)[1])
        else:
            host = self.get('local_bind_host')
            port = self.get('local_bind_port')
            return '{}:{}'.format(host, port)

    def remote_bind_address_str(self):
        key = 'remote_bind_address'
        remote_bind_address = self.get(key, (None, None))
        return '{}:{}'.format(remote_bind_address[0], remote_bind_address[1])

    def __eq__(self, other):
        for info in ['remote_bind_address']:
            n = self.get(info)
            o = other.get(info)
            if n != o:
                return False
        return True

    def start_by_subprocess(self):
        args = [CMD]
        # args.extend(SSH_COMMON_OPTS)
        args.extend(KEEP_ALIVE)
        args.extend(['-C2qTnN'])

        if self.config.get('ssh_pkey'):
            args.extend(['-i', self.config.get('ssh_pkey')])

        if self.config.get('remote_bind_address'):
            args.extend([
                '-L', '{}:{}'.format(
                    self.get('local_bind_port'),
                    self.remote_bind_address_str())
                ])
        else:
            args.extend(['-D', str(self.get('local_bind_port'))])

        args.append('{}@{}'.format(
            self.config['ssh_username'],
            self.config['ssh_address_or_host'][0]))
        logging.info("starting new tunnel: {}".format(' '.join(args)))
        if not self.config.get('ssh_pkey'):
            proc = psutil.Popen(
                    args,
                    creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            proc = psutil.Popen(args)
        self.tunnel_proc.append(proc)
        time.sleep(1)
        return proc

    def is_alive(self):
        try:
            return sshtunnel.SSHTunnelForwarder.is_alive()
        except Exception as e:
            logging.debug(e, exc_info=True)
            for proc in self.tunnel_proc:
                if proc.is_running():
                    return True
        return False
