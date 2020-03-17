@ECHO Off
set USER="root"
set SERVER="34.95.189.211"
set IdentityFile="id_rsa"
set SRC_DIR="~/.ytv"
set DST_DIR="%~dp0\rsync\%SERVER%"

md %DST_DIR%
REM rsync.exe -avz -e "ssh -i %IdentityFile%" %USER%@%SERVER%:%SRC_DIR% %DST_DIR%

