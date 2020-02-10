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
VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'

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

    def get(self, k, default=None):
        return self.config.get(k, default)

    def is_open(self):
        p = PortScanner(self.config['hostname'])
        p.timeout = 1.0
        port = self.config.get('port', 22)
        return p.isOpen(port)

    def update(self, k, v):
        self.config[k] = v


    def is_valid(self):
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
        if not self.is_valid():
            return False
        # self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        self.client.connect(**self.config)


    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port):
        self.tunnel = sshtunnel.SSHTunnelForwarder(
            (self.config['hostname'], self.config['port']),
            ssh_pkey = self.config['key_filename'],
            remote_bind_address=('127.0.0.1', port)
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
        self.connect()
        try:
            _, ss_stdout, ss_stderr = self.client.exec_command(command)
            r_out, r_err = ss_stdout.readlines(), ss_stderr.readlines()
        except Exception as e:
            logging.error(e)
            return (None, None, None)

        self.close()
        return (command, r_out, r_err)


    def exec_file(self, file):
        self.upload(file, remote_path='~/.cache')
        return self.exec_command("bash ~/.cache/{}".format(os.path.basename(file)))



    def open_vncviewer(self):
        subprocess.Popen([VNCVIEWER,
            '{}:{}'.format(self.config['hostname'], 5901)
        ])


    def vncserver_list(self):
        (din, out, err) = self.exec_command('vncserver -list')
        if not out: return []
        return out

