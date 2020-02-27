import subprocess
import unittest



import ssh


class TestSSH(unittest.TestCase):
    def test_sshtunnel(self):
        args = [ssh.CMD]
        args.extend(ssh.COMMON_SSH_OPTS)
        args.extend(ssh.KEEP_ALIVE_SSH_OPTS)
        args.extend(['-f', '-C2qTnN'])

        
