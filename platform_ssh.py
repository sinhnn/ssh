#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#  platform_ssh.py Author "sinhnn <sinhnn.92@gmail.com>" Date 19.03.2020
import platform
import sys

if platform.system() == "Windows":
    CMD = r'C:\Windows\System32\OpenSSH\ssh.exe'
    SCP = r'C:\Windows\System32\OpenSSH\scp.exe'
    RSYNC = r'rsync.exe'
    SSHFS = r'sshfs.exe'
    VNCVIEWER = r'C:\Program Files\RealVNC\VNC Viewer\vncviewer'
    OPEN_IN_TERMINAL = ["cmd.exe", "/k"]
    OPEN_SSH_IN_TERMINAL = OPEN_IN_TERMINAL + ["ssh.exe"]
    CHROME = r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    FIREFOX = r'C:\Program Files\Mozilla Firefox\firefox.exe'
elif platform.system() == "Linux":
    CMD = "ssh"
    SCP = 'scp'
    RSYNC = r'rsync'
    SSHFS = r'sshfs'
    OPEN_IN_TERMINAL = []
    VNCVIEWER = 'vncviewer'
    VNCSNAPSHOT = 'vncsnapshot'
    CHROME = r'google-chrome-stable'
    FIREFOX = r'firefox'
else:
    print("unsupported platform " + platform.system())
    sys.exit(1)
