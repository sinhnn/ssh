import os
import sys
import subprocess
import platform
import threading
import time
import re
import psutil
import json
import logging
import socket
# import cv2
import paramiko
import sshtunnel
from scp import SCPClient, SCPException
import collections

# My packages
# import common
from port import PortScanner
from remoteFile import EncryptedRemoteFile
import utils

sshtunnel.SSH_TIMEOUT = 10.0
__PATH__ = os.path.dirname(os.path.abspath(__file__))
__CWD__ = os.getcwd()
__CACHE__ = os.path.join(__CWD__, 'cache')
__BACKUP__ = os.path.join(__CWD__, 'BACKUP')

SSHCLIENT_CONFIG_FILE = os.path.join(__PATH__, 'ssh.json')
__CONFIGS__ = {}
if os.path.isfile(SSHCLIENT_CONFIG_FILE):
    try:
        fp = open(SSHCLIENT_CONFIG_FILE, 'r')
        __CONFIGS__ = json.load(fp)
        fp.close()
    except Exception as e:
        logging.error(e, exc_info=True)


SSH_MAX_FAILED = __CONFIGS__.get("maxFailed", 100)
# REMOTE_BIND_ADDRESS = __CONFIGS__.get("remoteBindAddress", ["127.0.0.1", 5901])
REMOTE_BIND_ADDRESS = ("127.0.0.1", 5901)
# SSH_CONFIG_FILE = __CONFIGS__.get("sshConfigFile")

# SSH_PUBLIC_KEY_FILE = os.path.join(__PATH__, 'id_rsa.pub')
#  Using ssh config file
# SSH_COMMON_OPTS = [
#     "-o", "CheckHostIP=no",
#     "-o", "StrictHostKeyChecking=no"
# ]
#

SSH_KEEP_ALIVE_OPTS = [
    '-o', "ServerAliveInterval=60",
    '-o', "TCPKeepAlive=true"
]


SCREENSHOT_FILE = '~/screenshot_1'
SCREENSHOT_THUMB = '~/screenshot_1-thumb.jpg'
CMD_SCREENSHOT = 'DISPLAY=:1 scrot -z --thumb 20 ~/screenshot_1.jpg'
CMD_CHECK_VNCSERVER = '[[ $(vncserver -list | grep "^:1\s\+[0-9]\+") ]]'
CMD_START_VNCSERVER = 'vncserver -geometry  1280x720' \
    + ' --I-KNOW-THIS-IS-INSECURE' \
    + ' -securitytypes  TLSNone,X509None,None' \
    + ' -localhost yes' \
    + ' -blacklisttimeout 0' \
    + ' -alwaysshared :1'
CMD_RUN_VNCSERVER_IF_NEED = "{} || {}".format(
        CMD_CHECK_VNCSERVER,
        CMD_START_VNCSERVER)

# REQUIREMENTS = [
#     "xorg", "xserver-xorg",
#     "openbox", "obmenu",
#     "tigervnc*", "wget", "curl",
#     "firefox", "cifs-utils",
#     "caja", "mate-terminal", "caja-open-terminal",
#     "ffmpeg", "scrot", "xsel", "xdotool"
# ]
# CMD_INSTALL_REQUIREMENT = 'sudo apt update && pgrep -f "apt\s+install"'  \
#                + ' || sudo apt install -y {}'.format(' '.join(REQUIREMENTS))


if platform.system() == "Windows":
    CMD = r'C:\Windows\System32\OpenSSH\ssh.exe'
    SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
    RSYNC = r'rsync.exe'
    SSHFS = r'sshfs.exe'
    VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'
    VNCSNAPSHOT = str(os.path.join(__PATH__, 'vncsnapshot', 'vncsnapshot'))
    OPEN_IN_TERMINAL = ["cmd.exe", "/k"]
    OPEN_SSH_IN_TERMINAL = OPEN_IN_TERMINAL + ["ssh.exe"]
elif platform.system() == "Linux":
    CMD = "ssh"
    SCP = 'scp'
    RSYNC = r'rsync'
    SSHFS = r'sshfs'
    OPEN_IN_TERMINAL = []
    VNCVIEWER = 'vncviewer'
    VNCSNAPSHOT = 'vncsnapshot'
else:
    print("unsupported platform " + platform.system())
    sys.exit(1)


def intersection(l1, l2):
    tmp = set(l2)
    return [v for v in l1 if v in tmp]


def delete_file(path):
    if os.path.isfile(str(path)):
        os.remove(str(path))


class FakeStdOut(object):
    def __init__(self, name, file_, maxlen=10, parent=None):
        super(FakeStdOut, self).__init__()
        self.name = name
        self.file = file_
        self.changed = True
        self.parent = parent
        self.__records__ = collections.deque(maxlen=maxlen)

    def __str__(self):
        try:
            return str(self.__records__[0])
        except Exception:
            return ""

    def write(self, str):
        self.__records__.appendleft(str.strip())
        self.changed = True
        if self.name not in self.parent.changed:
            self.parent.changed.append(self.name)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return str(self) < str(other)

    def __le__(self, other):
        return str(self) <= str(other)

    def __gt__(self, other):
        return str(self) > str(other)

    def __ge__(self, other):
        return str(self) >= str(other)
        pass


class StoredLoggerHandler(logging.FileHandler):
    def __init__(self, **kwargs):
        logging.FileHandler.__init__(self, **kwargs)
        self.maxlen = 100
        self.__records__ = collections.deque(maxlen=self.maxlen)

    def emit(self, record):
        self.__records__.appendleft(record)
        logging.FileHandler.emit(self, record)

    def get_last_messages(self, n):
        msgs = []
        for record in self.__records__:
            msg = self.format(record).splitlines()
            msgs.extend(msg)
            if len(msgs) > n:
                break
        return '\n'.join(msgs)


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
        args.extend(SSH_KEEP_ALIVE_OPTS)
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


class SSHClient(object):
    ''' SSH, SCP, SSH tunnel, VNCViewer via SSH tunnel '''
    __REQUIRED__ = ['hostname', 'username']
    __ANY__ = [['password', 'key_filename', 'pkey']]
    NEXT_ID = 0

    def __init__(self, info, fileConfig=None, **kwargs):
        self.info = utils.rm_empty(info)
        self.config = self.info.get('config', {})
        self.fileConfig = fileConfig
        if self.config.get('key_filename') == 'id_rsa':
            self.config['key_filename'] = os.path.join(
                    os.path.dirname(self.fileConfig),
                    'id_rsa'
                    )

        self.storeDir = os.path.join(
                os.path.dirname(fileConfig),
                self.config.get('hostname')
                )

        self.dirs = {
            'backup': os.path.join(self.storeDir, 'backup'),
            'cache': os.path.join(self.storeDir, 'cache')
        }
        self.files = {
            'disabled': os.path.join(self.storeDir, 'disabled'),
            'failed': os.path.join(self.storeDir, 'failed')
        }
        self.create_data_dir()

        self.id = SSHClient.NEXT_ID
        SSHClient.NEXT_ID += 1

        self.initLogger()
        self.portscanner = PortScanner()

        # self._client = self.connect()
        self.changed = []
        self.status = {
            'lastcmd': FakeStdOut(
                name='lastcmd',
                file_=self.cached_path('lastcmd'),
                parent=self),
            'ytvlog': FakeStdOut(
                name='ytvlog',
                file_=self.cached_path('ytvlog'),
                parent=self),
            'msg': FakeStdOut(
                name='msg',
                file_=self.cached_path('msg'),
                parent=self),
            'error': FakeStdOut(
                name='error',
                file_=self.cached_path('error'),
                parent=self)
        }

        self.encrypted = {
            'next_data': EncryptedRemoteFile(
                name='next_data',
                remote_path='~/.ytv/update.bin',
                local_path=self.cached_path(),
                parent=self),
            'email': EncryptedRemoteFile(
                name='email',
                remote_path='~/.ytv/email.bin',
                local_path=self.cached_path(),
                parent=self),
            'data': EncryptedRemoteFile(
                name='data',
                remote_path='~/.ytv/data.bin',
                local_path=self.cached_path(),
                parent=self)
        }

        self.tunnels = []
        self.tunnel_proc = []

        # there is current update thumbnail process
        self.updating_thumbnail = False
        # store all child process
        self.processes = []
        # store all child process
        self.exec_command_list = []
        self.exec_command_cid = 0

        self.threads = []

        self.__failedConnect__ = 0
        # self.update_server_info()

    def create_data_dir(self):
        try:
            # for d in [__BACKUP__, __CACHE__]:
            for k, v in self.dirs.items():
                os.makedirs(v, exist_ok=True)
            return True
        except Exception as e:
            self.log(e, exc_info=True, level=logging.ERROR)
        return False

    def update_server_info(self):
        paths = ' '.join([v.remote_path for k, v in self.encrypted.items()])
        remote_path = '"{}"'.format(paths)
        self.download_by_subprocess(
            src_path=remote_path,
            store=True,
            dst_path=self.cached_path()
        )
        for k, v in self.encrypted.items():
            v.decrypt()
            self.changed.append(k)
        return True

    def cached_path(self, name=None):
        if name is None:
            return self.dirs['cache']
        return os.path.join(self.dirs['cache'], name)

    def backup_path(self, name):
        if name is None:
            return self.dirs['backup']

        return os.path.join(self.dirs['backup'], name)

    def loadFileConfig(self, path):
        try:
            with open(path, 'r') as fp:
                info = utils.rm_empty(json.load(fp))
                config = info.get("config")
        except Exception as e:
            logging.error(e, exc_info=True)

        self.info = info
        self.config = config

    def reloadConfig(self):
        if os.path.isfile(self.fileConfig):
            self.loadFileConfig(self.fileConfig)
        elif os.path.isfile(self.get('filepath')):
            self.loadFileConfig(self.get('filepath'))
            self.fileConfig = self.get('filepath')

    def initLogger(self):
        try:
            self.logger = logging.getLogger('SSHClient_{}'.format(self.id))
            logFile = os.path.join(
                    __CACHE__,
                    '{}.txt'.format(self.get('hostname')))
            self.logFile = logFile
            if not os.path.isfile(logFile):
                open(logFile, 'w').write('')
            fileHandler = StoredLoggerHandler(
                    filename=logFile,
                    mode='a', encoding='utf-8', delay=False)
            DEBUG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
            fileHandler.setFormatter(logging.Formatter(DEBUG_FORMAT))
            fileHandler.setLevel(logging.DEBUG)
            self.loghandler = fileHandler
            self.logger.addHandler(fileHandler)
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False

        except Exception as e:
            self.logger = logging
            logging.error(e, exc_info=True)

    def getLog(self, path='~/.ytv/log.txt'):
        cmd = 'tail --lines=1 {}'.format(path)
        (rcmd, out, err) = self.exec_command(cmd)
        self.status['ytvlog'].write(''.join(out + err))

    def __str__(self):
        return '{}\n{}'.format(
                self.config['hostname'],
                ','.join(self.info['tags']))

    def __daemon__(self):
        for t in [self.update_vncthumnail]:
            thread = threading.Thread(target=t)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

    def log(self, s, level=logging.INFO, **kwargs):
        try:
            s = s.encode('utf-8', 'ignore').decode('utf-8')
            text = '{}@{} {}'.format(
                    self.config.get('username'),
                    self.config.get('hostname'),
                    s)
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
        except Exception:
            pass

    def keys(self):
        return list(self.config.keys()) \
                + list(self.status.keys()) \
                + list(self.encrypted.keys())

    def get(self, k, default=None):
        '''get status/configuration key'''
        if k in self.config.keys():
            return self.config[k]
        elif k in self.status.keys():
            return self.status[k]
        elif k in self.info.keys():
            return self.info[k]
        elif k in self.encrypted.keys():
            return self.encrypted[k]
        return default

    def update(self, k, v):
        '''update configuration keys'''
        if k in self.status.keys():
            self.log('{} is readonly', level=logging.ERROR)
            return
        self.config[k] = v

    def is_valid(self):
        for r in SSHClient.__REQUIRED__:
            if r not in self.config.keys() and self.config.get(r, '') == '':
                self.log('must has {}'.format(r), level=logging.ERROR)
                return False

        k = self.config.keys()
        for ones in SSHClient.__ANY__:
            if not len(intersection(ones, k)):
                self.log(
                        'required one parameter in {}'.format(ones),
                        level=logging.ERROR)
                return False
        return True

    def force_reconnect(self):
        self.updating_thumbnail = False
        self.__failedConnect__ = 0
        self.exec_command_list.clear()
        self.processes.clear()
        thread = threading.Thread(target=self.update_vncthumnail)
        thread.daemon = True
        thread.start()
        self.threads.append(thread)

    def __eq__(self, other):
        if all([
          self.get('hostname') == other.get('hostname'),
          self.get('username') == other.get('username'),
          self.id == other.id]):
            return True

    def __del__(self):
        try:
            self.log('closing ssh client', level=logging.DEBUG)
            for t in self.tunnels:
                t.stop()
            for p in self.processes:
                p.terminate()
            for t in self.threads:
                t.join()
            for t in self.tunnel_proc + self.exec_command_list:
                t.terminate()
        except Exception as e:
            self.log(e, level=logging.DEBUG, exc_info=True)
            pass

    def abs_path(self, path):
        def is_valid_path(path):
            return os.path.isfile(path) or os.path.isdir(path)

        if is_valid_path(path):
            return os.path.abspath(path)

        path = os.path.join(self.storeDir, path)
        if is_valid_path(path):
            return os.path.abspath(path)

        return None

    def upload(self, files, remote_path, recursive):
        self.log(
                'upload {} to {}'.format(files, remote_path),
                level=logging.INFO)
        results = {'done': [], 'failed': []}
        try:
            client = self.connect()
            if not client:
                return results
            scp = SCPClient(client.get_transport())
            for f in files:
                try:
                    r = bool(os.path.isdir(f))
                    scp.put(f, recursive=r, remote_path=remote_path)
                    results['done'].append(f)
                except SCPException as error:
                    results['failed'].append(f)
                    self.log(error, level=logging.ERROR, exc_info=True)
            scp.close()
            client.close()
        except SCPException as error:
            self.log(error, level=logging.ERROR, exc_info=True)
        finally:
            return results

    def download(self, remote_path, local_path, recursive=False, preserve_times=False):
        results = {'done': [], 'failed': []}
        try:
            client = self.connect()
            if not client:
                return results
            scp = SCPClient(client.get_transport())
            try:
                scp.get(remote_path, local_path, recursive, preserve_times)
                results['done'].append(local_path)
            except SCPException as error:
                results['failed'].append(local_path)
                self.log(error, level=logging.ERROR)
            except Exception as error:
                results['failed'].append(local_path)
                self.log(error, level=logging.ERROR, exc_info=True)
            scp.close()
            client.close()
        except Exception as error:
            self.log(error, level=logging.ERROR, exc_info=True)
        return results

    def check_failed_connection(self):
        if os.path.isfile(self.files['disabled']):
            return False

        if self.__failedConnect__ > SSH_MAX_FAILED:
            open(self.files['disabled'], 'w').write('')

        return True

    def __rm_terminated_process__(self):
        self.processes = [proc for proc in self.processes if proc.is_running()]

    def run_processes(self, args, store=False, **kwargs):
        try:
            if not self.check_failed_connection():
                return False
            self.__rm_terminated_process__()
            for proc in self.processes:
                if proc.is_running() and args == proc.cmdline():
                    self.log("ignore {} because of duplicated".format(args))
                    return True

            if kwargs.get('creationflags') == subprocess.CREATE_NEW_CONSOLE:
                args = OPEN_IN_TERMINAL + args
            proc = psutil.Popen(args, **kwargs)
            if kwargs.get('creationflags') == subprocess.CREATE_NEW_CONSOLE:
                return 0
            self.processes.append(proc)

            if kwargs.get('stdout') == subprocess.PIPE:
                o, e = proc.communicate(timeout=30)
                if store is True:
                    self.status['msg'].write(o)
                    self.status['error'].write(e)
                if kwargs.get('stdout') == subprocess.PIPE:
                    if o:
                        self.log('{}\n{}'.format(" ".join(args), o))
                if kwargs.get('stderr') == subprocess.PIPE:
                    if e:
                        self.log(
                            '{}\n{}'.format(" ".join(args), e.decode('utf-8')),
                            level=logging.ERROR)

            proc.wait()
            return proc.returncode
        except Exception as e:
            if store is True:
                self.status['error'].write(e)
            return -1

    def scp_by_subprocess(self, src_path, dst_path, recursive=False, quiet=False, tries=3, **kwargs):
        if tries <= 0:
            self.log(
                    'unable copy {} to {}'.format(src_path, dst_path),
                    level=logging.ERROR)
            return -1

        args = [SCP]
        args.extend(self.__base_opt_scp__())
        if recursive:
            args.append('-r')
        if isinstance(src_path, list):
            args.extend(src_path)
        else:
            args.append(src_path)
        args.append(dst_path)

        returncode = self.run_processes(args, **kwargs)
        if returncode not in [0, True]:
            self.log(
                    "retry copy with code {} {} to {}".format(
                        returncode,
                        src_path,
                        dst_path),
                    level=logging.ERROR)
            return self.scp_by_subprocess(
                    src_path=src_path,
                    dst_path=dst_path,
                    recursive=recursive,
                    quiet=quiet,
                    tries=tries-1,
                    **kwargs)
        else:
            return returncode

    def upload_by_subprocess(self, src_path, dst_path, recursive=False, store=True, **kwargs):
        if store:
            self.status['msg'].write('UPLOADING {} --> {}'.format(src_path, dst_path))
        p = self.__hostaddress_path__(dst_path)
        self.log('uploading {}'.format(src_path))
        r = self.scp_by_subprocess(src_path, p, recursive,  **kwargs)

        if store is True:
            if r in [0, True]:
                self.status['msg'].write(
                        '{} --> {}'.format(src_path, dst_path))
            else:
                self.status['error'].write(
                    '[{}] - FAILED UPLOAD: {} --> {}'.format(
                        r,
                        src_path,
                        dst_path))
        return r

    def __hostaddress_path__(self, path):
        return '{}:{}'.format(self.hostaddress(), path)

    def download_by_subprocess(self, src_path, dst_path, recursive=False, store=False, **kwargs):
        if store:
            self.status['msg'].write(
                    'DOWNLOADING {} --> {}'.format(src_path, dst_path))
        if isinstance(src_path, list):
            p = [self.__hostaddress_path__(p) for p in src_path]
        else:
            p = self.__hostaddress_path__(src_path)

        self.log('downloading {}'.format(src_path))
        r = self.scp_by_subprocess(p, dst_path, recursive, **kwargs)

        if store is True:
            if r in [0, True]:
                self.status['msg'].write(
                        '{} --> {}'.format(src_path, dst_path))
            else:
                self.status['error'].write(
                        '[{}] - FAILED UPLOAD: {} --> {}'.format(
                            r,
                            src_path,
                            dst_path))
        return r

    def connect(self, client=None, tries=2):
        if not self.is_valid():
            return False
        if tries <= 0:
            self.__failedConnect__ += 1
            self.__delete_icon__()
            self.log('paramiko: unable to connect', level=logging.ERROR)
            return False

        if client is None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        try:
            client.connect(timeout=5.0, **self.config)
            self.__failedConnect__ = 0
            return client
        except TimeoutError:
            if 'icon' in self.status.keys():
                del self.status['icon']
            return self.connect(client=client, tries=tries-1)
        except socket.timeout:
            return self.connect(client=client, tries=tries-1)
        except paramiko.ssh_exception.SSHException:
            return self.connect(client=client, tries=tries-1)
        except Exception:
            self.log(
                    'unable to connect from {}'.format(self.config),
                    level=logging.ERROR, exc_info=True)
            return False

    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port=None, **kwargs):
        # ERROR: Multiple ssh at same time will take the same port
        port = self.portscanner.getAvailablePort(range(6000+self.id*5, 10000))
        self.log(
                'creating tunnel via port {}'.format(port),
                level=logging.INFO)
        try:
            local_bind_address = ('127.0.0.1', port)
            tunnel = SSHTunnelForwarder(
                ssh_address_or_host=(
                    self.config['hostname'],
                    self.config.get('port', 22)),
                ssh_pkey=self.config.get('key_filename'),
                ssh_username=self.config['username'],
                ssh_password=self.config.get('password'),
                local_bind_address=local_bind_address,
                **kwargs
            )
            tunnel.start()
            time.sleep(1)
            if tunnel:
                self.tunnels.append(tunnel)
            return tunnel
        except Exception as e:
            self.log(e, level=logging.ERROR, exc_info=True)
            return False

    def __ssh_config_file__(self):
        d = os.path.dirname(self.fileConfig)
        files = [
            os.path.join(d, self.get('hostname'), '.ssh', 'config'),
            os.path.join(d, self.get('hostname'), 'config'),
            os.path.join(d, 'config')
        ]
        for f in files:
            if os.path.isfile(f):
                return str(f)
        return None

    def __base_opt__(self):
        args = []

        p = self.__ssh_config_file__()
        if p:
            args.extend(['-F', p])

        if self.config.get('key_filename'):
            args.extend(['-i', self.config['key_filename']])
        args.append(self.hostaddress())
        return args

    def cmdline(self):
        args = [CMD]
        args.extend(self.__base_opt__())
        return ' '.join(args)

    def ssh_tunnel_cmd(self):
        args = [CMD]
        args.extend(self.__base_opt__())
        args.extend(['-C2qTnN', '-D', str(22000)])
        return ' '.join(args)

    def __base_opt_scp__(self):
        # args = SSH_COMMON_OPTS.copy()
        args = []
        if self.config.get('key_filename'):
            args.extend(['-i', self.config['key_filename']])
        return args

    def hostaddress(self):
        return '{}@{}'.format(self.config['username'], self.config['hostname'])

    # ERROR: hangout when running
    def exec_command_subprocess(self, command, log=True, **kwargs):
        if not self.check_failed_connection():
            return False

        args = [CMD]
        args.append('-f')
        args.extend(self.__base_opt__())
        args.append(command)
        self.log('subprocess.call: {}'.format(args))
        returncode = subprocess.call(args, **kwargs)
        # proc.wait()
        return returncode

    def __is_command_in_runnning_list__(self, command):
        for c in self.exec_command_list:
            if command != c[1]:
                continue
            # if command == c[1]:
            if c[2] < 10:
                self.log("paramiko: ignore run {}, duplicated".format(command))
                c[2] += 1
                return True
            elif c[2] > 10:
                self.exec_command_list.remove(c)
                #  need to close process
                return False
        return False

    def __rm_exec_command_list_id__(self, id):
        for c in self.exec_command_list:
            if c[0] == id:
                self.exec_command_list.remove(c)
                return

    def exec_command(self, command, new=True, store=False, background=False, log=True):
        if not self.check_failed_connection():
            return (False, [], [])

        if self.__is_command_in_runnning_list__(command):
            return (False, [], [])

        if new is True:
            client = self.connect()
        else:
            client = self._client

        if not client:
            return (False, [], [])

        if re.search(r'&\s*$', command):
            command = re.sub(r'&\s*$', '', command)
            background = True

        cid = self.exec_command_cid
        self.exec_command_cid += 1
        self.exec_command_list.append([cid, command, 0])

        self.log('paramiko: {}'.format(command), level=logging.INFO)
        try:
            stdin, stdout, stderr = client.exec_command(command)
        except Exception as e:
            self.log(e, level=logging.ERROR)
            self.__rm_exec_command_list_id__(cid)
            return (False, [], [])
        if store:
            self.status['lastcmd'].write(command)
            self.status['msg'].write(command)

        if background is True:
            self.status['msg'].write("run in background")
            if new is True:
                client.close()
            self.__rm_exec_command_list_id__(cid)
            return (command, [], [])

        r_out = []
        r_err = []

        def is_done(*args):
            return all([s.channel.exit_status_ready() for s in args])
        i = 0
        r = True
        while r:
            try:
                out = []
                out = stdout.readlines()
                r_out.extend(out)
                if 'password' in ' '.join(out):
                    self.log("fill passwd: {}".format(self.config['password']))
                    stdin.write(self.config['password'] + '\n')
                    stdin.flush()
                if len(out):
                    i = 0
                    self.log("{}\n{}".format(command, ''.join(out)))

                err = []
                err = stderr.readlines()
                r_err.extend(err)
                if len(err):
                    i = 0
                    self.log("{}\n{}".format(
                        command, ''.join(err)),
                        level=logging.ERROR)

                if store:
                    if len(out):
                        # m = min(10, len(out))
                        self.status['msg'].write(''.join(out).strip())
                    if len(err):
                        self.status['error'].write(''.join(err).strip())
                    else:
                        self.status['error'].write('')

                r = not is_done(stdout, stderr)
                i += 1
                if i > 10000:
                    break
            except Exception as e:
                self.log(e, level=logging.ERROR, exc_info=True)
                self.__rm_exec_command_list_id__(cid)
                return (False, [], [])

        if str(self.status['msg']) == str(self.status['lastcmd']):
            self.status['msg'].write('')
        if i >= 10000:
            self.log('timeout to execute command')
        if new is True:
            client.close()
        self.__rm_exec_command_list_id__(cid)
        return (command, r_out, r_err)

    def invoke_shell(self, command=None):
        '''open ssh in new terminal'''
        args = OPEN_SSH_IN_TERMINAL.copy()
        args.extend(self.__base_opt__())
        if command is not None:
            args.append('"{}"'.format(command))
        print(' '.join(args))
        psutil.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)

    def exec_file(self, file):
        '''copy script file to slaver and run it'''
        p = '~/.cache'
        self.upload(file, remote_path=p)
        r = self.exec_command("bash {}/{}".format(p, os.path.basename(file)))
        return r

    def __get_vnctunnel__(self):
        '''searching for running ssh tunnel'''
        ts = []
        for t in self.tunnels:
            if not isinstance(t, SSHTunnelForwarder):
                continue
            if all([
              t.is_alive(),
              t.get("remote_bind_address") == REMOTE_BIND_ADDRESS
              ]):
                ts.append(t)
        ts += [t for t in self.tunnel_proc if t.is_running()]

        if ts:
            self.log("Found running tunnel", level=logging.INFO)
        if not ts:
            _ = self.create_tunnel(remote_bind_address=REMOTE_BIND_ADDRESS)
            # _  = self.create_tunnel_subprocess()
            if _:
                ts.append(_)
        return ts

    def open_vncviewer(self):
        try:
            self.create_vncserver(1)
            ts = self.__get_vnctunnel__()
            if not ts:
                return False
            if ts[0]:
                self.log("Openning vncviewer")
                subprocess.call([VNCVIEWER, ts[0].local_bind_address_str()])
                try:
                    ts[0].stop()
                except Exception as e:
                    logging.debug(e, exc_info=True)
                    ts[0].terminate()

        except FileNotFoundError:
            self.log('vncviewer not found', level=logging.ERROR)
        except Exception as e:
            self.log(e, level=logging.ERROR, exc_info=True)

    def update_vncthumnail(self):
        if not self.updating_thumbnail:
            self.log("updating thumbnail", level=logging.DEBUG)
            self.updating_thumbnail = True
            self.vncscreenshot_subprocess()
            self.updating_thumbnail = False
            return True
        else:
            self.log("another update thumbnail's running", level=logging.DEBUG)
            return False

    def __delete_icon__(self):
        if 'icon' in self.status.keys():
            del self.status['icon']

    def vncscreenshot(self):
        local_path = self.cached_path(self.config['hostname'] + '.jpg')
        command = self.exec_command(CMD_SCREENSHOT, log=False)[0]
        if command in [False, None]:
            delete_file(local_path)
            return self.__delete_icon__()

        time.sleep(1)
        self.download(
                remote_path='~/screenshot_1-thumb.jpg',
                local_path=local_path)

        if os.path.isfile(local_path):
            self.status['icon'] = local_path
        else:
            self.__delete_icon__()

    def vncscreenshot_subprocess(self):
        local_path = self.cached_path(self.config['hostname'] + '.jpg')
        (command, out, err) = self.exec_command(CMD_SCREENSHOT, log=False)

        msg = "giblib error: Can't open X display. It *is* running, yeah?\n"
        if msg in err:
            self.create_vncserver(1)
            time.sleep(1)

        if command in [False, None]:
            delete_file(local_path)
            return self.__delete_icon__()

        returncode = self.download_by_subprocess(
                src_path='screenshot_1-thumb.jpg',
                dst_path=local_path,
                stdout=subprocess.DEVNULL)

        if returncode != 0:
            delete_file(local_path)
            return self.__delete_icon__()

        self.status['icon'] = local_path

    def create_vncserver(self, x):
        (c, out, err) = self.exec_command(CMD_RUN_VNCSERVER_IF_NEED, log=False)
        if 'bash: vncserver: command not found\n' in err:
            self.exec_command(CMD_INSTALL_REQUIREMENT)
        return c

    def backup(self, dst_path=None, new=True, tries=3):
        if new:
            files = ['~/.ytv', '~/.config/google-chrome']
            cmd = 'tar -zcvf ~/backup.tar.gz {}'.format(' '.join(files))
            (command, out, err) = self.exec_command(cmd, store=True)
            if command != cmd:
                self.log('unable to create backup file', level=logging.ERROR)
                self.backup(dst_path=dst_path, new=True, tries=tries-1)

        if dst_path is None:
            dst_path = self.backup_path()
        r = self.download_by_subprocess(
                src_path='~/backup.tar.gz',
                dst_path=dst_path,
                store=True)
        return r

    def install_sshkey(self, path=None):
        if path is None:
            path = self.get("key_filename")

        if path is None:
            return False
        key = open(path, 'r').read()

        cmd = 'mkdir -p ~/.ssh' \
            + ' && echo -e "\n{}" >> ~/.ssh/authorized_keys'.format(key)
        (command, out, err) = self.exec_command(cmd)
        return cmd != command

    def vncserver_list(self):
        ''' Get list of vncserver on slaver '''
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


if __name__ == "__main__":
    pass
