import os,sys, subprocess, platform, threading, time
import json
import logging

import cv2

import paramiko
import sshtunnel
from scp import SCPClient, SCPException


from port import PortScanner
from common import close_all

__PATH__ = os.path.dirname(os.path.abspath(__file__))
__CACHE__ = os.path.join(__PATH__, 'cache')
os.makedirs(__CACHE__, exist_ok=True)

if platform.system() == "Windows":
    CMD = "ssh"
    SCP = r'C:\Windows\System32\OpenSSH\scp.exe' 
    VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'
    VNCSNAPSHOT = str(os.path.join(__PATH__, 'vncsnapshot', 'vncsnapshot' ))
elif platform.system() == "Linux":
    CMD = "ssh"
    SCP = 'scp' 
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

    def remote_bind_address_str(self):
        remote_bind_address = self.get('remote_bind_address', (None,None))
        return '{}:{}'.format(remote_bind_address[0],remote_bind_address[1])

    def __eq__(self, other):
        for info in ['remote_bind_address']:
            n = self.get(info)
            o = other.get(info)
            if n != o:
                return False
        return True

    def start_by_subprocess(self):
        args = [CMD,
                '-o', "CheckHostIP=no",
                '-o', "ServerAliveInterval=60",
                '-o', "TCPKeepAlive=true",
                '-f', '-C2qTnN',
        ]
        if self.config.get('ssh_pkey'):
            args.extend(['-i'], self.config.get('ssh_pkey'))

        elif self.config.get('ssh_password'):
            logging.error('ssh third party doest not support password on command line')
            return None

        if self.config.get('remote_bind_address'):
            args.extend(['-L', '{}:{}'.format(self.config['local_bind_address'][1], self.remote_bind_address_str()),
                '{}@{}'.format(self.config['ssh_username'],
                self.config['ssh_address_or_host'][0])
            ])
        else:
            args.extend([
                '-D', str(self.config['local_bind_port']),
                '{}@{}'.format(self.config['ssh_username'],
                self.config['ssh_address_or_host'][0])
            ])

        return subprocess.Popen(args)


COMMON_SSH_OPTS = [
    '-o', "CheckHostIP=no",
    '-o', "ServerAliveInterval=60",
    '-o', "TCPKeepAlive=true",
]

class SSHClient(object):
    '''
        SSH, SCP, SSH tunnel, VNCViewer via SSH tunnel
    '''
    __REQUIRED__ = ['hostname', 'username']
    __ANY__ = [['password', 'key_filename', 'pkey']]

    def __init__(self, info, fileConfig=None, vncthumb=True, **kwargs):
        self.info = info
        self.config = self.info.get('config', {})
        self.vncthumb = vncthumb
        self.status = {'screenshot' : None,  'vncserver': []}
        self.client = paramiko.SSHClient()

        self.tunnels = []

        self.portscanner = PortScanner()
        self.processes = [] # store all child process

        self.threads = []
        self.__daemon__()

    def __str__(self):
        return '{}\n{}'.format(self.config['hostname'],
                ','.join(self.info['tags']))

    def __daemon__(self):
        for  t in [self.update_vncthumnail]:
            thread = threading.Thread(target=t)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

    def __s__(self, s):
        return '{}@{} {}'.format(self.config.get('username'), self.config.get('hostname'), s)


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
            logging.error(self.__s__('{} is readonly'))
            return
        self.config[k] = v


    def is_valid(self):
        for r in SSHClient.__REQUIRED__:
            # if r not in self.config.keys():
            if r not in self.config.keys() and self.config.get(r, '') == '':
                logging.error(self.__s__('must has {}'.format(r)))
                return False

        k  = self.config.keys()
        for ones in SSHClient.__ANY__:
            if not len(intersection(ones, k)):
                logging.error(self.__s__('required one parameter in {}'.format(ones)))
                return False
        return True


    def __del__(self):
        logging.error(self.__s__('closing ssh client'))
        self.close()
        for t in self.tunnels:
            t.stop()
        for p in self.processes:
            p.terminate()
        for t in self.threads:
            # t.stop()
            t.join()


    def close(self):
        self.client.close()


    def upload(self, files, remote_path):
        results = {'done': [], 'failed' : []}
        try:
            self.connect()
            scp = SCPClient(self.client.get_transport())
            for f in files:
                try:
                    scp.put(f, recursive=bool(os.path.isdir(file)), remote_path=remote_path)
                    results['done'].append(f)
                except SCPException as error:
                    results['failed'].append(f)
                    logging.error(self.__s__(error), exc_info=True)
            scp.close()
            self.close()
        except SCPException as error:
            logging.error(self.__s__(error), exc_info=True)
        finally:
            return results

    def download(self, remote_path, local_path, recursive=False, preserve_times=False):
        results = {'done': [], 'failed' : []}
        logging.info(self.__s__('downloading {} to {}'.format(remote_path, local_path)))
        try:
            self.connect()
            scp = SCPClient(self.client.get_transport())
            try:
                scp.get(remote_path, local_path, recursive, preserve_times)
                results['done'].append(local_path)
            except SCPException as error:
                results['failed'].append(local_path)
                logging.error(self.__s__(e), exc_info=True)
            scp.close()
            self.close()
        except SCPException as error:
            logging.error(self.__s__(error), exc_info=True)
        # finally:
            # print(results)
        return results

    def scp_by_subprocess(self, src_path, dst_path, recursive=False):
        args = [SCP,  
            '-o', 'CheckHostIP=no',
            '-i', self.config['key_filename']
        ]
        if recursive: args.append('-r')
        args.append(src_path)
        args.append(dst_path)
        return subprocess.call(args, stdout=subprocess.STDOUT, stderr=subprocess.STDOUT) 

    def connect(self, tries=2):
        if not self.is_valid():
            return False
        if tries <= 0 :
            logging.error(self.__s__('unable to connect'))
            return False

        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        try:
            self.client.connect(**self.config)
            return True
        except TimeoutError:
            if 'icon' in self.status.keys():
                del self.status['icon']
            return self.connect(tries-1)
        except Exception as e:
            logging.error(self.__s__('unable to connect because of {}'.format(e)), exc_info=True)
            return False


    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port=None, **kwargs):
        #ERROR: Multiple ssh at same time will take the same portrint("automatic port")
        port = self.portscanner.getAvailablePort(range(6000, 7000))
        logging.info('trying open port {}'.format(port))

        try:
            local_bind_address = ('127.0.0.1', port)
            tunnel = SSHTunnelForwarder(
                ssh_address_or_host = (self.config['hostname'], self.config.get('port', 22)), \
                ssh_pkey = self.config.get('key_filename'), \
                ssh_username = self.config['username'], \
                ssh_password = self.config.get('password'), \
                local_bind_address = local_bind_address, \
                **kwargs
            )
            # p = tunnel.start_by_subprocess()
            # if p: self.processes.append(p)
            tunnel.start()
            if tunnel: self.tunnels.append(tunnel)
            return tunnel
        except Exception as e:
            logging.error(self.__s__(e), exc_info=True)
            return False


    def exec_command_by_subprocess(self, command):
        args = [CMD,
                '-o', "CheckHostIP=no",
                '-o', "ServerAliveInterval=60",
                '-o', "TCPKeepAlive=true",
                '-i', self.config['key_filename'],
                '{}@{}'.format(self.config['username'], self.config['hostname']),
                command
        ]
        return subprocess.call(args, stdout=subprocess.STDOUT, stderr=subprocess.STDOUT) 


    def exec_command(self, command):
        if not self.connect():
            return (False, [], [])
        try:
            # logging.info('{}@{}:{}'.format(self.config['username'], self.config['hostname'], command))
            _, ss_stdout, ss_stderr = self.client.exec_command(command)
            r_out, r_err = ss_stdout.readlines(), ss_stderr.readlines()
            self.client.close()
            # logging.info('{}\n\n{}'.format(r_out, r_err))
        except Exception as e:
            logging.error(self.__s__(e), exc_info=True)
            return (None, None, None)
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

        if ts:
            logging.info("Found running tunnel")
        if not ts:
            _  = self.create_tunnel(remote_bind_address=remote_bind_address)
            if _: ts.append(_)
        return ts


    def open_vncviewer(self):
        try:
            ts = self.__get_vnctunnel__()
            if not ts: 
                logging.error(self.__s__('unable to create tunnel for VNC'))
                return False
            logging.debug(self.__s__('opened'))
            subprocess.call([VNCVIEWER, ts[0].local_bind_address_str()])
            ts[0].stop()
            logging.debug(self.__s__('closed'))

        except FileNotFoundError:
            logging.error(self.__s__('vncviewer not found'), exc_info=True)
        except Exception as e:
            logging.error(self.__s__(e), exc_info=True)

    def update_vncthumnail(self):
        while (True):
            if close_all:
                logging.error(self.__s__('close update_vncthumnail'))
                break
            if self.vncthumb:
                # self.vncsnapshot()
                self.vncscreenshot()
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
        p = subprocess.call(args, stdout=subprocess.STDOUT, stderr=subprocess.STDOUT)
        if os.path.isfile(screenshotFile):
            self.status['icon'] = create_thumbnail(screenshotFile)
        elif 'icon' in self.status.keys():
            del self.status['icon']

    def __delete_icon__(self):
        if 'icon' in self.status.keys():
            del self.status['icon']

    def vncscreenshot(self):
        local_path=os.path.join(__CACHE__, self.config['hostname'] + '.jpg')
        command = self.exec_command('DISPLAY=:1 scrot --thumb 20 ~/screenshot_1.jpg')[0]
        if command == False:
            try: os.remove(local_path)
            except: pass
            return self.__delete_icon__()

        time.sleep(2)
        self.download(remote_path='~/screenshot_1-thumb.jpg', local_path=local_path)

        if os.path.isfile(local_path): self.status['icon'] = local_path
        else: self.__delete_icon__()


    def vncserver(self, x):
        args = ['vncserver',
            '-geometry', '1280x720',
            "--I-KNOW-THIS-IS-INSECURE", "-securitytypes", "TLSNone,X509None,None",
            "-localhost", "yes",
            "-alwaysshared"
            ':{}'.format(x)
        ]
        command = ' '.join(args)
        (c, out, err) = self.exec_command(command)
        return c


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

