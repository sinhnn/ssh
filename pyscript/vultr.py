import os
import re
import json
import logging

__DICT__ = {
  "config": {
    "hostname": "",
    "username": "",
    "password": "",
    "key_filename": "C:/Users/sinhnn/Documents/GitHub/ssh/linode/id_rsa"
  },
  "root": { "password": ""},
  "tags": [ "vultr"]
}



def run(path='.'):
    '''parser vultr to json login format'''
    for entry in os.scandir(path):
        if entry.is_dir(): continue
        if not re.search('Vultr.com.html$', entry.name): continue

        try:
            text = open(entry.path, 'r', encoding='utf-8') .read()
            _ = re.search('-clicktoclipboard=3D"(?P<ip>[0-9.]+)"', text)
            hostname = _.group("ip")
            username = "root"
            _p = re.search('data-password=3D"(?P<password>[^\s"]+)"', text)
            password = _p.group("password")
            info = __DICT__.copy()
            info['config']['hostname'] = hostname
            info['config']['username'] = "root"
            info['config']['password'] = password
            info['root']['password']  = password
            jpath = os.path.join(path, '{}.json'.format(hostname))
            with open(jpath, 'w') as fp:
                json.dump(info, fp, indent=4)
        except Exception as e:
            logging.error("unable to parser file {}".format(entry.path))
            logging.error(e, exc_info=True)

run()
