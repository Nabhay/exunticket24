import json

def parse(path):
    env = {}
    lines = open(path).read().split("\n")
    for x in lines:
        x = x.strip()
        if "=" in x:
            env[x.split("=", 1)[0]] = json.loads(x.split("=", 1)[1])
    print(env)
    return env