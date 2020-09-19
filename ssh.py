import os
import subprocess
import datetime
import threading
import time
import re
from pathlib import Path, PurePath
import psutil
import json
import logging
import socket
import paramiko
from scp import SCPClient, SCPException
import collections
import ping3
import traceback

# My packages
# import common
from port import PortScanner
from remoteFile import EncryptedRemoteFile
from watch_file import WatchFile
import utils

from tunnel import SSHTunnelForwarder
from ssh_options import KEEP_ALIVE
from platform_ssh import (
    CMD,
    SCP,
    # RSYNC,
    # SSHFS,
    VNCVIEWER,
    # VNCSNAPSHOT,
    OPEN_IN_TERMINAL,
    OPEN_SSH_IN_TERMINAL,
    FIREFOX,
    CHROME,
)

SSH_MAX_FAILED = 20
SSH_TUNNEL_START = 6000
SSH_TUNNEL_END = 10000
REMOTE_BIND_ADDRESS = ("127.0.0.1", 5901)
SCREENSHOT_FILE = '~/screenshot_{}'
SCREENSHOT_THUMB = '~/screenshot_{}-thumb.jpg'
CMD_SCREENSHOT = 'DISPLAY=:{0} scrot -z --thumb 20 ~/screenshot_{0}.jpg'
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

REQUIREMENTS = [
    "xorg", "xserver-xorg",
    "openbox", "obmenu",
    "tigervnc*", "wget", "curl",
    "firefox", "cifs-utils",
    "caja", "mate-terminal", "caja-open-terminal",
    "ffmpeg", "scrot", "xsel", "xdotool"
]

CMD_INSTALL_REQUIREMENT = 'sudo apt update && pgrep -f "apt\s+install"'  \
               + ' || sudo apt install -y {}'.format(' '.join(REQUIREMENTS))


def intersection(l1, l2):
    tmp = set(l2)
    return [v for v in l1 if v in tmp]


def delete_file(path):
    if os.path.isfile(str(path)):
        os.remove(str(path))


# def stem(path):
    # return str(PurePath(path).stem)


def __open_vncviewer__(*args):
    try:
        print(args)
        print(list(args))
        nargs = [VNCVIEWER] + list(args)
        print(nargs)
        logging.debug(nargs)
        subprocess.call(nargs)
    except FileNotFoundError:
        logging.error('vncviewer not found')
    except Exception as e:
        logging.error(e, exc_info=True)


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


WATCH_FILES = ['account.txt']
ENCRYPTED_FILES = ['data.bin',]
WATCH_DIRS = ['backup', 'cache']


class SSHClient(object):
    ''' SSH, SCP, SSH tunnel, VNCViewer via SSH tunnel '''
    __REQUIRED__ = ['hostname', 'username']
    __ANY__ = [['password', 'key_filename', 'pkey']]
    NEXT_ID = 0

    def __init__(self, info, fileConfig=None, **kwargs):
        self.info = utils.rm_empty(info)
        self.config = self.info.get('config', {})
        self.fileConfig = fileConfig
        self.info['createdDate'] = datetime.datetime.fromtimestamp(os.path.getmtime(self.fileConfig)).strftime("%Y%m%d-%H%M")
        # relative path or absolute path
        if self.config.get('key_filename') == 'id_rsa':
            self.config['key_filename'] = os.path.join(os.path.dirname(self.fileConfig), 'id_rsa')

        self.root = os.path.join(
                os.path.dirname(fileConfig),
                self.config.get('hostname')
        )

        self.watch_files = {PurePath(f).stem: WatchFile(self.path(f)) for f in WATCH_FILES}
        for d in WATCH_DIRS:
            os.makedirs(self.path(d), exist_ok=True)

        self.id = SSHClient.NEXT_ID
        SSHClient.NEXT_ID += 1

        self.initLogger()
        self.portscanner = PortScanner()

        self._client = None
        # self._ssh_client = None
        self._thumbnail_session = None
        self.changed = []

        self.status = {
            'path': self.root,
            'disabled': self.disabled,
            'lastupdate': None,
            'ping': -1,
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
                parent=self),
            'socks5': [],

        }

        self.encrypted = {
            'next_data': EncryptedRemoteFile(
                name='next_data',
                remote_path='~/.ytv/update.bin',
                local_path=self.cached_path(),
                parent=self),
            'email': EncryptedRemoteFile(
                name='email',
                remote_path='~/.ytv/email',
                local_path=self.cached_path(),
                parent=self),
            'data': EncryptedRemoteFile(
                name='data',
                remote_path='~/.ytv/data.bin',
                local_path=self.cached_path(),
                parent=self)
        }

        self.remoteFiles = ['~/.ytv/record.txt']

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

    def __str__(self):
        if self.get("X", 1) == 1:
            return '{}'.format(self.config['hostname'])
        return '{}_{}'.format(self.config['hostname'], self.get("X"))

    def get(self, k, default=None):
        '''get status/configuration key'''
        r = default
        if k in self.config.keys():
            r = self.config[k]
        elif k == 'allproc':
            r = self.allproc()
        elif k in self.status.keys():
            r = self.status[k]
        elif k in self.watch_files.keys():
            r = self.watch_files[k].value
        elif k in self.encrypted.keys():
            r = self.encrypted[k]
        elif k in self.info.keys():
            r = self.info[k]
        if callable(r):
            return r()
        else:
            return r

    @property
    def disabled(self):
        return os.path.isfile(self.path('disabled'))

    def setEnabled(self, enable):
        f = self.path('disabled')

        if enable is True:
            delete_file(f)

        if enable is False:
            if not os.path.isfile(f):
                open(self.path('disabled'), 'w').write(str(True))

    def full(self):
        ''' return all information '''
        infos = [str(v) for k, v in self.config.items()]
        infos.extend([str(v.value) for k, v in self.watch_files.items()])
        infos.extend([str(v) for k, v in self.status.items()])
        return ' '.join(infos)

    def path(self, *args):
        return os.path.join(self.root, *args)

    def cached_path(self, *args):
        return self.path('cache', *args)

    def backup_path(self, *args):
        return self.path('backup', *args)

    def ping(self):
        r = ping3.ping(self.get("hostname"), unit='ms')
        try:
            self.status['ping'] = int(r)
        except TypeError:
            self.status['ping'] = -1
        self.changed.append('ping')
        return self.status['ping']

    def watch_file(self, name, cmd, tries=2):
        if tries <= 0:
            self.status[name] = 'no ssh session'
            return self.status[name]

        if not self._client:
            self._client = self.create_new_connection()
            self.watch_file(name, cmd, tries-1)

        (rcmd, rout, rerr) = self.exec_command(command=cmd, new=False)
        self.status[name] = ''.join(rout + rerr)
        self.changed.append(name)
        return self.status[name]

    def update_encrypted_info(self):
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

    def update_server_info(self):
        command = 'bash ~/.ytv/script/update_info.sh'
        (rcmd, rout, rerr) = self.exec_command(
                command=command,
                pclient=self._client
        )
        if rcmd == command:
            tr = (''.join(rout)).strip()
            try:
                d = json.loads(tr)
                self.status.update(d)
                self.changed.extend(d.keys())
            except Exception:
                self.status['raw'] = ''.join(rout + rerr)
                self.changed.append('raw')
        return True

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

        for f in self.watch_files.keys():
            self.status[f] = self.watch_files[f].value

    def initLogger(self):
        try:
            self.logger = logging.getLogger('SSHClient_{}'.format(self.id))
            logFile = os.path.join(self.root, 'log.txt')
            if not os.path.isfile(logFile):
                open(logFile, 'w').write('')

            DEBUG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"

            fileHandler = StoredLoggerHandler(
                    filename=logFile,
                    mode='a', encoding='utf-8', delay=False)
            fileHandler.setFormatter(logging.Formatter(DEBUG_FORMAT))
            fileHandler.setLevel(logging.DEBUG)
            self.loghandler = fileHandler
            self.logger.addHandler(fileHandler)
            self.logger.setLevel(logging.DEBUG)
            # self.logger.propagate = True
            self.logFile = logFile
        except Exception as e:
            self.logger = logging
            logging.error(e, exc_info=True)

    def getLog(self, path='~/.ytv/log.txt'):
        cmd = 'tail --lines=1 {}'.format(path)
        (rcmd, out, err) = self.exec_command(cmd)
        self.status['ytvlog'].write(''.join(out + err))

    def allproc(self):
        allproc = []
        for p in [self.tunnels, self.tunnel_proc, self.processes, self.exec_command_list]:
            if len(p):
                allproc.extend(p)
        text = ''.join(list(map(str, allproc)))
        return text

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

        # return default

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
                        level=logging.ERROR
                )
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
        self.changed.append('allproc')

    def __eq__(self, other):
        if all([
          self.get('hostname') == other.get('hostname'),
          self.get('username') == other.get('username'),
          self.id == other.id]):
            return True

    def __del__(self):
        print('closing all child processes')
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

        path = os.path.join(self.root, path)
        if is_valid_path(path):
            return os.path.abspath(path)

        return None

    def upload(self, files, remote_path, recursive):
        self.log(
                'upload {} to {}'.format(files, remote_path),
                level=logging.INFO)
        results = {'done': [], 'failed': []}
        try:
            client = self.create_new_connection()
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

    def download(self, remote_path,  local_path, pclient=None, recursive=False, preserve_times=False):
        results = {'done': [], 'failed': []}
        try:
            if pclient:
                client = pclient
            else:
                client = self.create_new_connection()
            if not client:
                self.log('no valid client to download file!')
                return results
            scp = SCPClient(client.get_transport(), socket_timeout=50)
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
            if not pclient:
                client.close()
        except Exception as error:
            self.log(error, level=logging.ERROR, exc_info=True)
        return results

    def check_failed_connection(self):
        if self.disabled:
            return False

        if self.__failedConnect__ > SSH_MAX_FAILED:
            self.setEnabled(False)

        return True

    def __rm_terminated_process__(self):
        self.processes = [proc for proc in self.processes if proc.is_running()]
        self.changed.append('allproc')

    def run_processes(self, args, store=False, method="Popen", timeout=None, **kwargs):
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

            if method == "Popen":
                proc = psutil.Popen(args, **kwargs)
                if kwargs.get('creationflags') == subprocess.CREATE_NEW_CONSOLE:
                    return 0
                self.processes.append(proc)
                self.changed.append('allproc')

                if kwargs.get('stdout') == subprocess.PIPE:
                    o, e = proc.communicate(timeout=30)
                    if store is True:
                        self.status['msg'].write(o)
                        self.status['error'].write(e)
                    if kwargs.get('stdout') == subprocess.PIPE and o:
                        self.log('{}\n{}'.format(" ".join(args), o))
                    if kwargs.get('stderr') == subprocess.PIPE and e:
                        self.log('{}\n{}'.format(" ".join(args), e.decode('utf-8')), level=logging.ERROR)
                if timeout is not None:
                    proc.wait(timeout)
                else:
                    proc.wait()
                self.changed.append('allproc')
                return proc.returncode
            else:
                returncode = subprocess.call(args, **kwargs)
                return returncode
        except Exception as e:
            if store is True:
                self.status['error'].write(e)
            self.changed.append('allproc')
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

    def create_new_connection(self, client=None, tries=2):
        if not self.is_valid():
            return False
        if tries <= 0:
            self.__failedConnect__ += 1
            self.__delete_screen__()
            self.log('paramiko: unable to connect', level=logging.ERROR)
            return False

        if client is None:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
        try:
            client.connect(timeout=5.0, banner_timeout=60, **self.config)
            self.__failedConnect__ = 0
            return client
        except TimeoutError:
            self.__delete_screen__()
            return self.create_new_connection(client=client, tries=tries-1)
        except socket.timeout:
            return self.create_new_connection(client=client, tries=tries-1)
        except paramiko.ssh_exception.SSHException:
            return self.create_new_connection(client=client, tries=tries-1)
        except Exception:
            self.log(
                    'unable to connect from {}'.format(self.config),
                    level=logging.ERROR, exc_info=True)
            return False

    # https://sshtunnel.readthedocs.io/en/latest/
    def create_tunnel(self, port=None, **kwargs):
        # ERROR: Multiple ssh at same time will take the same port
        print('scaning local port ...')
        port = self.portscanner.getAvailablePort(
                range(SSH_TUNNEL_START+self.id*5, SSH_TUNNEL_END)
        )
        print('creating tunnel via port {} and {}'.format(port, kwargs))
        self.log('creating tunnel via port {} and {}'.format(port, kwargs))
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
            traceback.print_exc()
            self.log(e, level=logging.ERROR, exc_info=True)
            return False

    def create_socks5(self, port=None, **kwargs):
        port = self.portscanner.getAvailablePort(
                range(SSH_TUNNEL_START+self.id*5+2, SSH_TUNNEL_END)
        )
        fp = open(self.path('tunnel.log'), 'w')
        args = [CMD]
        args.extend(self.__base_opt__())
        args.extend(KEEP_ALIVE)
        args.extend(['-C2vTnN'])
        args.extend(['-D', str(port)])
        proc = psutil.Popen(args, stdout=fp, stderr=fp) #, creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.tunnel_proc.append(proc)
        time.sleep(1)
        self.changed.append('socks5')
        self.status['socks5'].append(port)
        return (proc, port)

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
        args.extend(['-C2TnN', '-D', str(22000)])
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

    def check_client_connection(self, client):
        if not isinstance(client, paramiko.SSHClient):
            return None
        if not client:
            return False
        if client.get_transport() is None:
            return False
        if not client.get_transport().is_active():
            return False

        return True

    def exec_command(self, command, new=True, pclient=None, store=False, background=False, log=True, tries=2):
        if not self.check_failed_connection():
            if store:
                self.status['msg'].write('failed to connect')
            return (False, [], [])

        if self.__is_command_in_runnning_list__(command):
            if store:
                self.status['msg'].write('duplicated task')
            return (False, [], [])

        if pclient:
            client = pclient
        elif new is True:
            client = self.create_new_connection()
        else:
            client = self._client

        if self.check_client_connection(client) is None:
            client = self.create_new_connection()
        elif self.check_client_connection(client) is False:
            client.connect(timeout=5.0, **self.config)

        if re.search(r'&\s*$', command):
            command = re.sub(r'&\s*$', '', command)
            background = True

        cid = self.exec_command_cid
        self.exec_command_cid += 1
        self.exec_command_list.append([cid, command, 0])
        self.changed.append('allproc')

        self.log('paramiko: {}'.format(command), level=logging.INFO)
        try:
            stdin, stdout, stderr = client.exec_command(command)
        except Exception as e:
            self.log(e, level=logging.ERROR)
            self.__rm_exec_command_list_id__(cid)
            self.changed.append('allproc')
            return (False, [], [e])
        if store:
            self.status['lastcmd'].write(command)
            self.status['msg'].write(command)

        if background is True:
            self.status['msg'].write("run in background")
            if new is True:
                client.close()
            self.__rm_exec_command_list_id__(cid)
            self.changed.append('allproc')
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
                    self.log("{}\n{}".format(command, ''.join(err)), level=logging.ERROR)
                if store:
                    if len(out):
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
                self.changed.append('allproc')
                return (False, [], [])

        if str(self.status['msg']) == str(self.status['lastcmd']):
            self.status['msg'].write('')
        if i >= 10000:
            self.log('timeout to execute command')
        if new is True:
            client.close()
        self.__rm_exec_command_list_id__(cid)
        self.changed.append('allproc')
        return (command, r_out, r_err)

    def invoke_shell(self, command=None):
        '''open ssh in new terminal'''
        args = OPEN_SSH_IN_TERMINAL.copy()
        args.extend(self.__base_opt__())
        if command is not None:
            args.append('{}'.format(command))
        psutil.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)

    def exec_file(self, file):
        '''copy script file to slaver and run it'''
        p = '~/.cache'
        self.upload(file, remote_path=p)
        r = self.exec_command("bash {}/{}".format(p, os.path.basename(file)))
        return r

    @property
    def remote_bind_port(self):
        return 5900 + int(self.get("X", 1))

    @property
    def remote_bind_address(self):
        return ("127.0.0.1", self.remote_bind_port)

    def __get_vnctunnel__(self):
        '''searching for running ssh tunnel'''
        ts = []
        for t in self.tunnels:
            if not isinstance(t, SSHTunnelForwarder):
                continue
            self.log("validating tunnel {}".format(str(t)))
            if all([t.get("remote_bind_address") == self.remote_bind_address]):
                if not t.alive():
                    self.log('restartting tunnel {}'.format(str(t)))
                    t.start()
                    time.sleep(1)
                ts.append(t)
        # ts += [t for t in self.tunnel_proc if t.is_running()]
        self.log("availabel tunnels: {} ".format(ts), level=logging.DEBUG)
        if len(ts) == 0:
            print("creating new tunnel")
            _ = self.create_tunnel(remote_bind_address=self.remote_bind_address)
            if _:
                ts.append(_)
        return ts

    def open_vncviewer(self):
        print("Opening vncviewer")
        if self.get("direct") is not True:
            print("opening vncviewer via tunnel ... ")
            try:
                self.create_vncserver(self.get("X", 1))
                ts = self.__get_vnctunnel__()
                if not len(ts):
                    print("no tunnel found")
                    self.log("no tunnel found", level=logging.ERROR)
                    return False
                tunnel = ts[0]
                if tunnel:
                    self.log('open vncviewer via {}'.format(str(tunnel)))
                    # subprocess.call([VNCVIEWER, tunnel.local_bind_address_str()])
                    __open_vncviewer__(tunnel.local_bind_address_str())
                    tunnel.stop()
            except Exception as e:
                self.log(e, level=logging.ERROR, exc_info=True)
        else:
            __open_vncviewer__('{}:{}'.format(
                    self.get("hostname"),
                    self.remote_bind_port
                    )
            )
        self.changed.append('allproc')

    def update_vncthumnail(self):
        if not self.updating_thumbnail:
            self.log("updating thumbnail", level=logging.DEBUG)
            self.updating_thumbnail = True

            if not self._thumbnail_session:
                self._thumbnail_session = self.create_new_connection()
            try:
                if self._thumbnail_session.get_transport() is None:
                    self._thumbnail_session = self.create_new_connection()
            except Exception:
                self._thumbnail_session = self.create_new_connection()

            r = self.vncscreenshot_subprocess()
            if r:
                self.status['lastupdate'] = datetime.datetime.now().strftime("%H:%M:%S")
            self.updating_thumbnail = False
            return True
        else:
            self.log("another update thumbnail's running", level=logging.DEBUG)
            return False

    def __delete_screen__(self):
        if 'screen' in self.status.keys():
            del self.status['screen']

    def vncscreenshot(self):
        local_path = self.cached_path(self.__str__() + '.jpg')
        command = self.exec_command(CMD_SCREENSHOT.format(self.get("X", 1)), log=False)[0]
        if command in [False, None]:
            delete_file(local_path)
            return self.__delete_screen__()

        time.sleep(1)
        self.download(
                remote_path='~/screenshot_{}-thumb.jpg'.format(self.get("X", 1)),
                local_path=local_path)

        if os.path.isfile(local_path):
            self.status['screen'] = local_path
        else:
            self.__delete_screen__()

    def vncscreenshot_subprocess(self):
        local_path = self.cached_path(self.__str__() + '.jpg')
        (command, out, err) = self.exec_command(
                CMD_SCREENSHOT.format(self.get("X", 1)),
                pclient=self._thumbnail_session,
                log=False)
        msg = "giblib error: Can't open X display. It *is* running, yeah?\n"
        if msg in err:
            self.create_vncserver(self.get("X", 1))
            time.sleep(1)

        if command in [False, None]:
            delete_file(local_path)
            return self.__delete_screen__()

        returncode = self.download_by_subprocess(
                src_path='screenshot_{}-thumb.jpg'.format(self.get("X", 1)),
                dst_path=local_path,
                stdout=subprocess.DEVNULL,
                timeout=30
        )

        if returncode != 0:
            delete_file(local_path)
            return self.__delete_screen__()

        self.status['screen'] = local_path
        return (returncode == 0)

    def create_vncserver(self, x):
        (c, out, err) = self.exec_command(CMD_RUN_VNCSERVER_IF_NEED, log=False)
        if 'bash: vncserver: command not found\n' in err:
            self.exec_command(CMD_INSTALL_REQUIREMENT)
        return c

    def backup(self, dst_path=None, new=True, tries=3):
        if new:
            files = ['~/.ytv', '~/.config/google-chrome']
            excludes = [
                'exclude=~/.ytv/extensions',
                'exclude=~/.ytv/script',
                'exclude=~/.ytv/download'
            ]
            cmd = 'tar {} -zcvf ~/backup.tar.gz {}'.format(excludes, ' '.join(files))
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
        (command, out, err) = self.exec_command(cmd, store=True)
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

    def firefox_via_sshtunnel(self):
        profile_dir = self.path('ffprofile')
        os.makedirs(profile_dir, exist_ok=True)
        (proc, port) = self.create_socks5()
        configs = [
            'user_pref("media.peerconnection.enabled", false);',
            'user_pref("network.proxy.socks", "127.0.0.1");',
            'user_pref("network.proxy.socks", "127.0.0.1");',
            'user_pref("network.proxy.socks_port", {});'.format(port),
            'user_pref("network.proxy.socks_remote_dns", true);'
            'user_pref("network.proxy.type", 1);'
        ]
        fp = open(self.path('ffprofile', 'user.js'), 'w')
        fp.write('\n'.join(configs))
        fp.close()
        ffproc = subprocess.call([
            FIREFOX,
            '-new-instance',
            '-profile',
            profile_dir, 'https://iplocation.com/'
        ])
        # ffproc = subprocess.Popen([FIREFOX, '-new-instance', '-profile', profile_dir, 'https://iplocation.com/'])
        # while True:
        #     print(ffproc)
        #     print(ffproc.poll())
        #     # print(ffproc.status())
        #     time.sleep(2)
        # print('killing tunnel process {} at port {}'.format(proc, port))
        # proc.kill()

    def chrome_via_sshtunnel(self):
        os.makedirs(self.path('chrome'), exist_ok=True)
        (tunnel_proc, port) = self.create_socks5()
        proxy_server = '--proxy-server=socks5://127.0.0.1:' + str(port)
        args = [CHROME]
        args.append(proxy_server)
        args.append('--user-data-dir={}'.format(self.path('chrome')))
        args.extend(['https://iplocation.com', 'https://whoer.net'])
        chproc = subprocess.call(args)
        tunnel_proc.terminate()
        # create tunnel

def load_ssh_dir(dir):
    results = []
    for entry in os.scandir(dir):
        if entry.is_dir():
            continue
        if not re.search(r'.json$', entry.name):
            continue

        try:
            server = load_ssh_file(entry.path)
            if server:
                server.info['filepath'] = os.path.abspath(entry.path)
                results.append(server)
        except Exception:
            pass
    return results


def load_ssh_file(path):
    try:
        fp = open(path, 'r')
        info = json.load(fp)
        fp.close()
        client = SSHClient(info=info, fileConfig=path)
        if client.is_valid():
            return client
        return {}
    except Exception:
        logging.error('unable to load file {}\n{}'.format(path), exc_info=True)
        return {}
    # return None


if __name__ == "__main__":
    pass
