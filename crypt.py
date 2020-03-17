import pyAesCrypt
import os
import io
from io import BytesIO

bufferSize = 64 * 1024
password = "ryar$r!aYB8?=)"


def encryptFile(ifile, ofile, password=password, bufferSize=bufferSize):
    pyAesCrypt.encryptFile(ifile, ofile, password, bufferSize)


def encrypt(s, password=password):
    bufferSize = 64 * 1024
    fIn = io.BytesIO(s.encode('utf-8'))
    fCiph = io.BytesIO()
    pyAesCrypt.encryptStream(fIn, fCiph, password, bufferSize)

    ctlen = len(fCiph.getvalue())
    fCiph.seek(0)
    fDec = io.BytesIO()
    pyAesCrypt.decryptStream(fCiph, fDec, password, bufferSize, ctlen)

    if s != fDec.getvalue().decode('utf-8'):
        return None
    return fCiph


def decrypt(encrypted, password, buffer_size=64*1024):
    stream_length = len(encrypted.getvalue())
    encrypted.seek(0)

    decrypted = BytesIO()
    pyAesCrypt.decryptStream(
            encrypted,
            decrypted,
            password,
            buffer_size,
            stream_length
            )
    return decrypted.getvalue()


def decryptFile(file, password=password):
    buffer_size = 64 * 1024  # 64K decryption buffer
    with open(str(file), "rb") as store_in:
        lines = b''
        for line in store_in.readlines():
            lines = lines + line
        encrypted = BytesIO(lines)
    # Decrypt the stream
    stream_length = len(encrypted.getvalue())
    decrypted = BytesIO()
    encrypted.seek(0)
    pyAesCrypt.decryptStream(
            encrypted,
            decrypted,
            password,
            buffer_size,
            stream_length)
    return decrypted.getvalue().decode("utf-8")


def decryptFile2Variable(file, password):
    return decryptFile(file, password)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='crypt')
    parser.add_argument('file', help='')
    parser.add_argument('-force', help='Force overwrite', action="store_true")
    parser.add_argument(
            '-decrypt',
            help=argparse.SUPPRESS,
            action="store_true")
    args = parser.parse_args()

    if args.decrypt is False:
        ofile = os.path.splitext(args.file)[0] + '.bin'
        if os.path.isfile(ofile) and args.force is False:
            print("File alreay exist")
        else:
            pyAesCrypt.encryptFile(args.file, ofile, password, bufferSize)
    else:
        print(decryptFile(args.file, password))
