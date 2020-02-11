import os,sys,subprocess, platform, threading, time
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
    VNCSNAPSHOT = str(os.path.join(__PATH__, 'vncsnapshot', 'vncsnapshot' ))
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


class SSHTunnelForwarder(sshtunnel.SSHTunnelForwarder):
    """Docstring for SSHTunnelForwarder. """
    def __init__(self, **kwargs):
        sshtunnel.SSHTunnelForwarder.__init__(self, **kwargs)
        self.config = kwargs

    def get(self, key, default=None):
        return self.config.get(key, default)

    def local_bind_address_str(self):
        return '{}:{}'.format(self.local_bind_host, self.local_bind_port)
    def __eq__(self, other):
        for info in ['remote_bind_address']:
            n = self.get(info)
            o = other.get(info)
            if n != o:
                return False
        return True

class SSHClient(object):
    '''
        SSH, SCP, SSH tunnel, VNCViewer via SSH tunnel
    '''
    __REQUIRED__ = ['hostname', 'username']
    __ANY__ = [['password', 'key_filename', 'pkey']]

    def __init__(self, config, fileConfig=None, vncthumb=True, **kwargs):
        self.config = config
        self.vncthumb = vncthumb
        self.status = {'screenshot' : None,  'vncserver': []}
        self.client = paramiko.SSHClient()

        self.tunnels = []

        self.portscanner = PortScanner()
        self.processes = [] # store all child process

        self.__daemon__()


    def __daemon__(self):
        self.threads = []
        for  t in [self.update_vncthumnail]:
            thread = threading.Thread(target=t)
            thread.daemon = True
            thread.start()

    def keys(self):
        return self.config.keys()


    def get(self, k, default=None):
        if k in self.config.keys():
            return self.config[k]
        elif k in self.status.keys():
            return self.status[k]
        return default

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
        for t in self.tunnels:
            t.stop()
        for p in self.processes:
            p.terminate()
        for t in self.threads:
            t.stop()
            t.join()


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
        # if not port:
        print("automatic port")
        port = self.portscanner.getAvailablePort(range(5000, 6000))

        try:
            local_bind_address = ('127.0.0.1', port)
            tunnel = SSHTunnelForwarder(
                ssh_address_or_host = (self.config['hostname'], self.config.get('port', 22)), \
                ssh_pkey = self.config.get('key_filename'), \
                ssh_username = self.config['username'], \
                ssh_password = self.config.get('password'), \
                set_keepalive=30, \
                local_bind_address = local_bind_address, \
                **kwargs
            )
            p = tunnel.start()
            if tunnel:
                self.tunnels.append(tunnel)
            return tunnel
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


    def __get_vnctunnel__(self):
        remote_bind_address = ('127.0.0.1', 5901)
        ts = []
        for t in self.tunnels:
            if isinstance(t, SSHTunnelForwarder):
                if t.is_alive and t.get('remote_bind_address') == remote_bind_address:
                    ts.append(t)

        if ts: print("Found running tunnel")
        if not ts:
            _  = self.create_tunnel(remote_bind_address=remote_bind_address)
            if _: ts.append(_)
        return ts


    def open_vncviewer(self):
        try:
            print(self.config['hostname'])
            ts = self.__get_vnctunnel__()
            subprocess.Popen([VNCVIEWER, ts[0].local_bind_address_str()])

        except FileNotFoundError:
            logging.error('vncviewer not found')
        except Exception as e:
            logging.error(e, exc_info=True)

    def update_vncthumnail(self):
        while (True):
            if self.vncthumb: self.vncsnapshot()
            time.sleep(60)

    def vncsnapshot(self):
        # vncsnapshot -tunnel only available in Linux
        def create_thumbnail(image):
            idata = cv2.imread(image)
            resize = cv2.resize(idata, (320,180), interpolation = cv2.INTER_AREA)
            thumbnailFile =  os.path.splitext(image)[0] + '.thumbnail.jpg'
            cv2.imwrite(thumbnailFile)
            return thumbnailFile

        ts = self.__get_vnctunnel__()
        screenshotFile = '{}.jpg'.format(self.config['hostname'])
        args = [VNCSNAPSHOT, ts[0].local_bind_address_str(), screenshotFile]
        p = subprocess.call(args)
        if os.path.isfile(screenshotFile):
            self.status['icon'] = create_thumbnail(screenshotFile)
        elif 'icon' in self.status.keys():
            del self.status['icon']


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

