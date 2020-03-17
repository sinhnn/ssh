import os
import crypt
import json


class RemoteFile(object):

    """Docstring for RemoteFile. """

    def __init__(self, parent, remote_path, local_path, **kwargs):
        """TODO: to be defined.

        :parent: TODO
        :path: TODO
        :**kwargs: TODO

        """
        self._parent = parent
        self.remote_path = remote_path
        self.local_path = local_path

    def download(self):
        r = self._parent.download_by_subprocess(
                src_path=self.remote_path,
                dst_path=self.local_path
        )
        return r

    def update(self):
        return self.download()


class EncryptedRemoteFile(RemoteFile):

    """Docstring for EncryptedRemoteFile. """

    def __init__(self, parent, remote_path, local_path, **kwargs):
        """TODO: to be defined.

        :parent: TODO
        :path: TODO
        :**kwargs: TODO

        """
        RemoteFile.__init__(self, parent, remote_path, local_path)
        self._parent = parent

    def __str__(self):
        if os.path.isdir(self._local_path):
            fpath = os.path.join(
                    self._local_path,
                    os.path.basename(self._remote_path))
        else:
            fpath = self._local_path
        return crypt.decryptFile(fpath)

    def __dict__(self):
        return json.dumps(self.__str__())

    def __eq__(self, other):
        return self.__str__() == str(other)

    def __ne__(self, other):
        return self.__str__() != str(other)

    def __lt__(self, other):
        return self.__str__() < str(other)

    def __le__(self, other):
        return self.__str__() <= str(other)

    def __gt__(self, other):
        return self.__str__() > str(other)

    def __ge__(self, other):
        return self.__str__() >= str(other)
