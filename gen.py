import os
import json
import argparse
import subprocess
import ssh

import getpass




def send_sshkey(config):

    args = [ssh.CMD]
    args.extend(ssh.COMMON_SSH_OPTS)
    args.append("{}@{}".format(config["username"], config["hostname"]))
    command  = ' '.join(args)

    key = open(config['key_filename'], 'r').read()
    clien_cmd = '[[ -f {0} ]] || mkdir -p ~/.ssh && touch {0} && echo "{1}" >> {0}'.format('~/.ssh/authorized_keys', key)
    args.append(clien_cmd)

    command += '\'{}\''.format(clien_cmd)

    proc = subprocess.Popen(args,stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    bp = ("{}\n".format(config['password'])).encode()
    proc.communicate(input=bp)

    o, e = proc.communicate()
    print("STDOUT: " + str(o))
    print("STDERROR: " + str(e))
    # proc.communicate(input=bp)
    while proc.poll() is None:
        o = proc.stdout.readline()
        e = proc.stderr.readline()
        print("STDOUT: {}".format(o))
        print("STDERR: {}".format(e))
        if 'password' in o:
            proc.communicate(input=bp)
            break
        if 'Warning' in e:
            time.sleep(2)
            proc.communicate(input=bp)
            break


    # for i in range(0, 10):
    #     o, e = proc.communicate()
    #     print(o,e)
    #     if 'password' in o or 'password' in e:
    #         break
    #     if 'Warning: Per'
    #     time.sleep(1)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('infile', help="infile")
    parser.add_argument('--username', help="default username", default="root")
    parser.add_argument('--password', help="default username password", default="Hieunguyen123@")
    parser.add_argument('--root', help="default root password", default="Hieunguyen123@")
    parser.add_argument('--identify', help="default identify file", default="C:/Users/sinhnn/Documents/GitHub/ssh/linode/id_rsa")
    args = parser.parse_args()

    dargs = vars(args)

    dirname  = os.path.dirname(args.infile)

    __DICT__ = {
        "config": {
            "hostname": "",
            "username": dargs.get("username"),
            "password": dargs.get("password"),
            "key_filename" : dargs.get("identify")
        },
        "root" : {"password": dargs.get("root")},
        "tags": [ "us", "vps", "linode"]
            
    }

    fp = open(args.infile, 'r') 
    for line in fp.readlines():
        info = line.strip()
        if not info: continue
        of = os.path.join(dirname, info + '.json')
        with open(of, 'w') as lp:
            d = __DICT__.copy()
            d ["config"]['hostname']  = info
            json.dump(d, lp, indent=2)
