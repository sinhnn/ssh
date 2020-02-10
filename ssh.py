import os,sys,subprocess
import json
import logging

import paramiko
import sshtunnel
from scp import SCPClient, SCPException

def intersection(l1, l2):
    tmp = set(l2)
    return [v for v in l1 if v in tmp]

CMD = 'ssh'

class SSHClient(object):
    __REQUIRED__ = ['hostname', 'username']
    __ONE__ = [['password', 'key_filename', 'pkey']]

    def __init__(self, config, fileConfig=None, **kwargs):
        self.config = config
        self.client = paramiko.SSHClient()
        self.tunnel = None
        self.processes = [] # store all child process

    def keys(self):
        return self.config.keys()

    def get(self, k):
        return self.config.get(k)

    def is_open(self):
        p = PortScanner(self.config['hostname'])
        p.timeout = 1.0
        port = self.config.get('port', 22)
        return p.isOpen(port)

    def update(self, k, v):
        self.config[k] = v


    def __valid__(self):
        for r in SSHClient.__REQUIRED__:
            if r not in self.config.keys():
                logging.error('must has {}'.format(r))
                return False

        k  = self.config.keys()
        for ones in SSHClient.__ONE__:
            if not len(intersection(ones, k)):
                logging.error('required one parameter in {}'.format(ones))
                return False
        return True


    def __del__(self):
        self.close()
        if self.tunnel: self.tunnel.stop()
        for p in self.processes:
            p.terminate()


    def close(self):
        self.client.close()


    def upload(self, files, remote_path):
        results = {'done': [], 'failed' : []}
        try:
            scp = SCPClient(self.client.get_transport())
            for f in files:
                try:
                    self.scp.put(f, recursive=bool(os.path.isdir(file)), remote_path=remote_path)
                    self.results['done'].append(f)
                except SCPException as error:
                    self.results['failed'].append(f)
                    logging.error()
        except SCPException as error:
            logging.error(error)
        finally:
            scp.close()
            return results


    def connect(self):
        if not self.__valid__():
            return False
        self.client.connect(**self.config)


    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port):
        self.tunnel = sshtunnel.SSHTunnelForwarder(
            (self.config['hostname'], self.config['port']),
            ssh_pkey = self.config['key_filename'],
            remote_bind_address=('127.0.0.1', 8080)
        )
        self.tunnel.start()


    def create_tunnel_2(self, port):
        args = [CMD,
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'StrictHostKeyChecking=no',
                '-o', "ServerAliveInterval=60",
                '-o', "ServerAliveInterval=60",
                '-o', "TCPKeepAlive=true",
                '-i', self.config['key_filename'],
                '-f', '-C2qTnN',
                '-D', port,
                '{}@{}'.format(self.config['username'], self.config['hostname'])
        ]
        return subprocess.Popen(args)


    def exec_command(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return (stdin, stdout, stderr)


    def exec_file(self, file):
        self.upload(file, remote_path='~/.cache')
        return self.exec_command("bash ~/.cache/{}".format(os.path.basename(file)))


