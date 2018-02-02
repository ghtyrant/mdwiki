import re


def split_path(path):
    """ Split a path string by separator in all components. """
    return path.strip('/').split('/')


def natural_sort_key(key, _nsre=re.compile('([0-9]+)')):
    """ Taken from http://stackoverflow.com/a/16090640 """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, key.decode("utf-8"))]
