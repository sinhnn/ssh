import os
import re
import json
import argparse

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('infile', help="infile")
args = parser.parse_args()


__DICT__ = {
    "urls" : ["https://www.youtube.com/watch?v=zCHj1SM2FmQ", "https://www.youtube.com/watch?v=aXwBhcJdMco", "https://www.youtube.com/watch?v=hKBKE0umI7s", "https://www.youtube.com/watch?v=ABGHnTCQHLw", "https://www.youtube.com/watch?v=2MjFvIx1pRY", "https://www.youtube.com/watch?v=605Tyo87YbI"],
    "email": {"username": "example.com", "password": "password"}
}


fp = open(args.infile, 'r') 
for line in fp.readlines():
    info = line.strip()
    if not info:
        continue


    data = re.split(r'\s+', info)
    print(data)
    continue
    with open(data[0].replace("@",'__') + '.json', 'w') as lp:
        d = __DICT__.copy()
        d ["email"]['username']  = data[0]
        d ["email"]['password']  = data[1]

        d ["email2"] = {}
        d ["email2"]['username']  = data[2]
        d ["email2"]['password']  = data[1]
        json.dump(d, lp, indent=2)
