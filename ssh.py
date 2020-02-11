import os,sys,subprocess, platform
import json
import logging

import cv2

import paramiko
import sshtunnel
from scp import SCPClient, SCPException


from port import PortScanner

__PATH__ = os.path.dirname(os.path.abspath(__file__))
if platform.system() == "Windows":
    CMD = "ssh"
    VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'
    VNCSNAPSHOT = os.path.join(__PATH__, 'vncsnapshot', 'vncsnapshot' )
elif platform.system() == "Linux":
    CMD = "ssh"
    VNCVIEWER = 'vncviewer'
    VNCSNAPSHOT = 'vncsnapshot'
else:
    print("unsupported platform "  + platform.system())
    sys.exit(1)


def intersection(l1, l2):
    tmp = set(l2)
    return [v for v in l1 if v in tmp]


MAP_SSHTUNNEL_SSHCLIENT = {'ssh_pkey' : 'key_filename',
    'ssh_pkey' : 'pkey',
    'ssh_password' : 'password',
    'ssh_private_key_password' : 'passphrase'
}


from collections import namedtuple
TunnelPath = namedtuple('TunnelPath', ['SSHTunnelForwarder', 'path'])

class SSHClient(object):
    '''
        SSH, SCP, SSH tunnel, VNCViewer via SSH tunnel
    '''
    __REQUIRED__ = ['hostname', 'username']
    __ANY__ = [['password', 'key_filename', 'pkey']]

    # running tunnel port
    __RUNNING_PORT__ = []

    def __init__(self, config, fileConfig=None, **kwargs):
        self.config = config
        self.status = {'screenshot' : None,  'vncserver': []}
        self.client = paramiko.SSHClient()

        self.tunnels = []

        self.tunnel = None
        self.tunnel_port = 0

        self.tunnel4vnc = None
        self.tunnel4vnc_port = None

        self.portscanner = PortScanner()
        self.processes = [] # store all child process

    def keys(self):
        return self.config.keys()


    def get(self, k, default=None):
        if k in self.config.keys():
            return self.config[k]
        elif k in self.status.keys():
            return self.status[k]
        return default

    # def is_open(self):
    #     p = PortScanner(self.config['hostname'])
    #     p.timeout = 1.0
    #     port = self.config.get('port', 22)
    #     return p.isOpen(port)

    def update(self, k, v):
        if k in self.status.keys():
            logging.error('{} is readonly')
            return
        self.config[k] = v


    def is_valid(self):
        for r in SSHClient.__REQUIRED__:
            if r not in self.config.keys():
                logging.error('must has {}'.format(r))
                return False

        k  = self.config.keys()
        for ones in SSHClient.__ANY__:
            if not len(intersection(ones, k)):
                logging.error('required one parameter in {}'.format(ones))
                return False
        return True


    def __del__(self):
        self.close()
        if self.tunnel:
            self.tunnel.stop()
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


    def connect(self, tries=3):
        if not self.is_valid():
            return False
        if tries <= 0 : return False

        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        try:
            self.client.connect(**self.config)
            return True
        except TimeoutError:
            logging.error('request timeout')
            return self.connect(tries-1)
        except Exception as e:
            logging.error('unable to connect because of {}'.format(e))
            return False


    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port=None, **kwargs):
        if not port:
            port = self.portscanner.getAvailablePort(range(5000, 6000))
        try:
            # sshtunnel pick a randome port
            # ssh_password = 'empty', \
            # ssh_private_key_password = 'empty',
            local_bind_address = ('127.0.0.1', port)
            tunnel = sshtunnel.SSHTunnelForwarder(
                (self.config['hostname'], self.config.get('port', 22)), \
                ssh_pkey = self.config['key_filename'], \
                set_keepalive=30,
                **kwargs
            )
            tunnel.start()
            self.tunnels.append(tunnel)
            return True
        except Exception as e:
            logging.error(e, exc_info=True)
            return False

    def create_tunnel_by_subprocess(self, port):
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
        if not self.connect():
            return (False, [], [])
        try:
            logging.info('{}@{}:{}'.format(self.config['username'], self.config['hostname'], command))
            _, ss_stdout, ss_stderr = self.client.exec_command(command)
            r_out, r_err = ss_stdout.readlines(), ss_stderr.readlines()
            logging.info('{}\n\n{}'.format(r_out, r_err))
        except Exception as e:
            logging.error(e, exc_info=True)
            return (None, None, None)
        self.close()
        return (command, r_out, r_err)


    def exec_file(self, file):
        self.upload(file, remote_path='~/.cache')
        return self.exec_command("bash ~/.cache/{}".format(os.path.basename(file)))


    def open_vncviewer(self):
        try:
            self.create_tunnel(remote_bind_address=('127.0.0.1', 5901))
            subprocess.Popen([VNCVIEWER, '{}:{}'.format('127.0.0.1', 5901)])
        except FileNotFoundError:
            logging.error('vncviewer not found')
        except Exception as e:
            logging.error(e, exc_info=True)

    def vncsnapshot(self, port):
        def create_thumbnail(image):
            idata = cv.imread(image)
            resize = cv2.resize(idata, (320,180), interpolation = cv2.INTER_AREA)
            thumbnailFile =  os.path.splitext(image)[0] + '.thumbnail.jpg'
            cv.imwrite(thumbnailFile)
            return thumbnailFile

        # create ssh tunnel mapting localport:server:5901
        self.create_tunnel4vnc()
        if not self.tunnel4vnc:
            return False

        screenshotFile = '{}.jpg'.format(self.config['hostname'])
        args = [VNCSNAPSHOT,
                '127.0.0.1:{}'.format(self.tunnel4vnc_port),
                screenshotFile
        ]
        subprocess.Popen(args)
        self.status['icon'] = create_thumbnail(screenshotFile)


    def vncserver(self, x):
        args = ['vncserver',
            '-geometry', '1400x900',
            "--I-KNOW-THIS-IS-INSECURE", "-securitytypes", "TLSNone,X509None,None",
            "-localhost", "yes",
            "-alwaysshared"
            ':{}'.format(x)
        ]
        command = ' '.join(args)
        (c, out, err) = self.exec_command(command)
        if c == False: return False


    def vncserver_list(self):
        def parser(line):
            matched = re.match(r':(?P<display>[1-9])\s+(?P<pid>[0-9]+)$')
            if not matched:
                return (None, None)
            return (matched.group('display'), matched.group('pid'))

        (din, out, err) = self.exec_command('vncserver -list')

        result = []
        for line in out:
            (display, pid) = parser(line)
            if display and pid:
                result.append((display, pid))
        return result

