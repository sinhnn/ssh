import subprocess
import unittest



import ssh

SERVER="192.168.1.75"
USERNAME="sinhnn"

class TestSSH(unittest.TestCase):
    def test_sshtunnel(self):
        args = [ssh.CMD]
        args.extend(ssh.COMMON_SSH_OPTS)
        args.extend(ssh.KEEP_ALIVE_SSH_OPTS)
        args.extend(['-f', '-C2qTnN'])
        args.exe

        
