import os,sys, subprocess, platform, threading, time
import json
import logging
import socket

import cv2

import paramiko
import sshtunnel
sshtunnel.SSH_TIMEOUT = 5.0

from scp import SCPClient, SCPException

from port import PortScanner
import common
import utils

__PATH__ = os.path.dirname(os.path.abspath(__file__))
__CACHE__ = os.path.join(__PATH__, 'cache')
os.makedirs(__CACHE__, exist_ok=True)

if platform.system() == "Windows":
    CMD = "ssh"
    SCP = r'C:\Windows\System32\OpenSSH\scp.exe' 
    VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'
    VNCSNAPSHOT = str(os.path.join(__PATH__, 'vncsnapshot', 'vncsnapshot' ))
    OPEN_SSH_IN_TERMINAL = ["cmd.exe", "/k", "ssh.exe", "-o", "UserKnownHostsFile=/dev/null", "-o", "StrictHostKeyChecking=no"]
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

import collections
class StoredLoggerHandler(logging.FileHandler):
    def __init__(self, **kwargs):
        logging.FileHandler.__init__(self, **kwargs)
        self.maxlen = 100
        self.__records__ = collections.deque(maxlen=self.maxlen)

    def emit(self, record):
        self.__records__.appendleft(record)
        logging.FileHandler.emit(self, record)

    def get_last_messages(self, n):
        msgs= []
        for record in self.__records__:
            msg = self.format(record).splitlines()
            msgs.extend(msg)
            if len(msgs) > n: break
        return '\n'.join(msgs)

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
    NEXT_ID = 0

    def __init__(self, info, fileConfig=None, vncthumb=True, **kwargs):
        self.info = utils.rm_empty(info)
        self.config = self.info.get('config', {})
        self.id = SSHClient.NEXT_ID
        SSHClient.NEXT_ID += 1
        self.vncthumb = vncthumb
        self.status = {'screenshot' : None,  'vncserver': []}
        self.initLogger()
        self.tunnels = []
        self.portscanner = PortScanner()
        self.processes = [] # store all child process
        self.threads = []


    def initLogger(self):
        try:
            self.logger = logging.getLogger('SSHClient_{}'.format(self.id))
            logFile = os.path.join(__CACHE__, '{}.txt'.format(self.get('hostname')))
            if not os.path.isfile(logFile): open(logFile, 'w').write('')
            fileHandler = StoredLoggerHandler(filename=logFile, mode='a', encoding='utf-8', delay=False)
            DEBUG_FORMAT = "%(asctime)s %(levelname)-8s  %(message)s"
            fileHandler.setFormatter(logging.Formatter(DEBUG_FORMAT))
            fileHandler.setLevel(logging.DEBUG)
            self.loghandler = fileHandler
            self.logger.addHandler(fileHandler)
            self.logger.propagate = False
        except Exception as e:
            self.logger = logging
            logging.error(e, exc_info=True)

    def __str__(self):
        return '{}\n{}'.format(self.config['hostname'],
                ','.join(self.info['tags']))

    def __daemon__(self):
        for  t in [self.update_vncthumnail]:
            thread = threading.Thread(target=t)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

    def __s__(self, s, level, **kwargs):
        text = '{}@{} {}'.format(self.config.get('username'), self.config.get('hostname'), s)
        if level == logging.INFO:
            logging.info(text, **kwargs)
            self.logger.info(text, **kwargs)
        elif level == logging.DEBUG:
            logging.debug(text, **kwargs)
            self.logger.debug(text, **kwargs)
        elif level == logging.ERROR:
            logging.error(text, **kwargs)
            self.logger.error(text, **kwargs)
        elif level == logging.CRITICAL:
            logging.critical(text, **kwargs)
            self.logger.critical(text, **kwargs)
        return text

    def keys(self):
        return self.config.keys()


    def get(self, k, default=None):
        if k in self.config.keys():
            return self.config[k]
        elif k in self.status.keys():
            return self.status[k]
        elif k in self.info.keys():
            return self.info[k]
        return default

    def update(self, k, v):
        if k in self.status.keys():
            self.__s__('{} is readonly', level=logging.ERROR)
            return
        self.config[k] = v


    def is_valid(self):
        for r in SSHClient.__REQUIRED__:
            if r not in self.config.keys() and self.config.get(r, '') == '':
                self.__s__('must has {}'.format(r), level=logging.ERROR)
                return False

        k  = self.config.keys()
        for ones in SSHClient.__ANY__:
            if not len(intersection(ones, k)):
                self.__s__('required one parameter in {}'.format(ones), level=logging.ERROR)
                return False
        return True

    def __eq__(self, other):
        if self.get('hostname') == other.get('hostname') \
            and self.get('username') == other.get('username'):
            return True

    def __del__(self):
        self.__s__('closing ssh client', level=logging.ERROR)
        for t in self.tunnels:
            t.stop()
        for p in self.processes:
            p.terminate()
        for t in self.threads:
            # t.stop()
            t.join()


    def close(self):
        pass


    def upload(self, files, remote_path):
        self.__s__('upload {} to {}'.format(files, remote_path), level=logging.INFO)
        results = {'done': [], 'failed' : []}
        try:
            client = self.connect()
            if not client: return  results
            scp = SCPClient(client.get_transport())
            for f in files:
                try:
                    scp.put(f, recursive=bool(os.path.isdir(file)), remote_path=remote_path)
                    results['done'].append(f)
                except SCPException as error:
                    results['failed'].append(f)
                    self.__s__(error, level=logging.ERROR, exc_info=True)
            scp.close()
            client.close()
        except SCPException as error:
            self.__s__(error, level=logging.ERROR, exc_info=True)
        finally:
            return results

    def download(self, remote_path, local_path, recursive=False, preserve_times=False):
        results = {'done': [], 'failed' : []}
        try:
            client = self.connect()
            if not client: return results
            scp = SCPClient(client.get_transport())
            try:
                scp.get(remote_path, local_path, recursive, preserve_times)
                results['done'].append(local_path)
            except SCPException as error:
                results['failed'].append(local_path)
                self.__s__(error, level=logging.ERROR)
            except Exception as error:
                results['failed'].append(local_path)
                self.__s__(error, level=logging.ERROR, exc_info=True)
            scp.close()
            client.close()
        except Exception as error:
            self.__s__(error, level=logging.ERROR, exc_info=True)
        # finally:
            # print(results)
        return results

    def scp_by_subprocess(self, src_path, dst_path, recursive=False):
        args = [SCP]
        args.extend(self.__base_opt__())
        if recursive: args.append('-r')
        args.append(src_path)
        args.append(dst_path)
        proc = subprocess.call(args, stdout=subprocess.STDOUT, stderr=subprocess.STDOUT)
        return proc

    def connect(self, client=None, tries=2):
        if not self.is_valid():
            return False
        if tries <= 0 :
            self.__s__('unable to connect', level=logging.ERROR)
            return False

        if client == None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        try:
            client.connect(**self.config, timeout=5.0)
            return client
        except TimeoutError:
            if 'icon' in self.status.keys():
                del self.status['icon']
            return self.connect(client=client, tries=tries-1)
        except socket.timeout:
            self.__delete_icon__()
            return self.connect(client=client, tries=tries-1)
        except Exception as e:
            self.__s__('unable to connect from {} configurations, because of {}'.format(self.config, e), level=logging.ERROR, exc_info=True)
            return False

    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port=None, **kwargs):
        #ERROR: Multiple ssh at same time will take the same portrint("automatic port")
        port = self.portscanner.getAvailablePort(range(6000 + self.id *5, 10000))
        self.__s__('trying open port {}'.format(port),level=logging.INFO)

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
            tunnel.start()
            if tunnel: self.tunnels.append(tunnel)
            return tunnel
        except Exception as e:
            self.__s__(e, level=logging.ERROR, exc_info=True)
            return False

    def create_tunnel_subprocess(self, port=None, **kwargs):
        #ERROR: Multiple ssh at same time will take the same portrint("automatic port")
        port = self.portscanner.getAvailablePort(range(6000 + self.id *5, 10000))
        self.__s__('trying open port {}'.format(port),level=logging.INFO)
        args = [CMD]
        args.append('-C2qTnN')
        args.extend(['-L', '{}:localhost:5901' port])
        args.extend(self.__base_opt__())
        
        proc = subprocess.Popen(args)
        return proc


    def __base_opt__(self):
        args = ['-o', "CheckHostIP=no",
                '-o', "ServerAliveInterval=60",
                '-o', "TCPKeepAlive=true",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "StrictHostKeyChecking=no"
        ]
        if self.config.get('key_filename'):
            args.extend(['-i', self.config['key_filename']])
        args.append('{}@{}'.format(self.config['username'], self.config['hostname']))
        return args

    def exec_command_by_subprocess(self, command):
        args = [CMD]
        args.extend(self.__base_opt__())
        args.append(command)
        # subprocess.Popen(args, creationflags = subprocess.CREATE_NEW_CONSOLE )
        proc = subprocess.call(args, stdout=subprocess.STDOUT, stderr=subprocess.STDOUT) 
        return proc


    def exec_command(self, command):
        self.__s__('executing {}'.format(command), level=logging.INFO)
        client = self.connect()
        if not client: return (False, [], [])

        try:
            stdin, stdout, stderr = client.exec_command(command)
        except Exception as e:
            self.__s__(e, level=logging.ERROR)
            return (False, [], [])

        while not stdout.channel.exit_status_ready() and not stderr.channel.exit_status_ready():
            try:
                line = stdout.readlines()
                if 'password' in ' '.join(line):
                    stdin.write(self.config['password'] + '\n')
                    stdin.flush()

                line.extend(stderr.readlines())

                if not len(line): continue
                self.__s__("{}\n{}".format(command, '\n'.join(line)), level=logging.INFO)
                self.status['progress'] = line
            except Exception as e:
                self.__s__(e, level=logging.ERROR)
                return (False, [], [])
        r_out, r_err = stdout.readlines(), stderr.readlines()
        client.close()
        return (command, r_out, r_err)

    def invoke_shell(self):
        args = OPEN_SSH_IN_TERMINAL.copy()
        if self.config.get("key_filename"):
            args.extend(["-i", self.config.get("key_filename")])
        args.append("{}@{}".format(self.config.get("username"), self.config.get("hostname")))
        subprocess.Popen(args, creationflags = subprocess.CREATE_NEW_CONSOLE )

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
            self.__s__("Found running tunnel", level=logging.INFO)
        if not ts:
            _  = self.create_tunnel(remote_bind_address=remote_bind_address)
            if _: ts.append(_)
        return ts


    def open_vncviewer(self):
        try:
            self.create_vncserver(1)
            ts = self.__get_vnctunnel__()
            if not ts: 
                return False
            subprocess.call([VNCVIEWER, ts[0].local_bind_address_str()])
            ts[0].stop()

        except FileNotFoundError:
            self.__s__('vncviewer not found', level=logging.ERROR)# , exc_info=True)
        except Exception as e:
            self.__s__(e, level=logging.ERROR, exc_info=True)

    def update_vncthumnail(self):
        # while (True):
        if common.close_all:
            self.__s__('close update_vncthumnail',level=logging.INFO)
        if self.vncthumb:
            # self.vncsnapshot()
            self.vncscreenshot()
            # time.sleep(self.delay)

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
        if command == False or command == None:
            try:
                os.remove(local_path)
            except:
                pass
            return self.__delete_icon__()

        time.sleep(2)
        self.download(remote_path='~/screenshot_1-thumb.jpg', local_path=local_path)

        if os.path.isfile(local_path):
            self.status['icon'] = local_path
        else: self.__delete_icon__()


    def create_vncserver(self, x):
        args = ['vncserver',
            '-geometry', '1280x720',
            "--I-KNOW-THIS-IS-INSECURE", "-securitytypes", "TLSNone,X509None,None",
            "-localhost", "yes",
            "-alwaysshared",
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

