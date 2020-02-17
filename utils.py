

def rm_empty(dict_):
    empty = []
    for k, v in dict_.items():
        if isinstance(v, bool):
            continue
        elif isinstance(v, str):
            if v == '':
                empty.append( k )
        elif isinstance(v, list):
            if v == []: empty.append( k )
        elif isinstance(v, dict):
            if v == {}:
                empty.append( k )
            else:
                rm_empty(v)

    for k in empty:
        del dict_[k]

    return dict_


if __name__ == "__main__":
    import json
    with open('ssh/192.168.1.144.json', 'r') as fp:
        d = json.load(fp)
    print(rm_empty(d))
