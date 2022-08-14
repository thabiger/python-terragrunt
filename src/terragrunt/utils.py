import os
import re
import logging

logger = logging.getLogger(__name__)

# this function are recursively looking for files that meet certain
# testing citeria up or down from the specified directory

def listfiles(dir=".", way="down", depth=100, regex=None):
    f = []

    dir = os.path.abspath(dir)
    searchfunc = lambda x: re.search(regex, x) if regex else lambda x: True

    if way == "up" and depth > 0 and dir != "/":
        f += listfiles(os.path.abspath(os.path.join(dir, "../")), way, depth - 1, regex)

    for i in os.listdir(dir):
        p = "%s/%s" % (dir, i)
        if os.path.isfile(p) and searchfunc(p):
            f.append(os.path.abspath(p))

        if way == "down" and depth > 0 and os.path.isdir(p):
            f += listfiles(p, way, depth - 1, regex)

    return f
