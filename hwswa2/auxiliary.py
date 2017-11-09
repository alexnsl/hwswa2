import time
import copy
import struct
import sys
import os
import fcntl
import termios
import argparse

__all__ = ['wait_for', 'wait_for_not', 'shell_escape', 'term_winsz',
           'range2list', 'range_len', 'list2range', 'splitlist', 'splitrange',
           'joinlists', 'joinranges', 'differenceranges',
           'BLACK', 'RED', 'GREEN', 'YELLOW',
           'BLUE', 'MAGENTA', 'CYAN', 'WHITE', 'printout',
           'encrypt', 'decrypt'
           ]


def wait_for(condition_fn, args, timeout=60):
    """Waits for condition or timeout

    Return True if condition is met within timeout period
    """
    starttime = time.time()
    while not condition_fn(*args):
        if time.time() - starttime > timeout:
            return False
        time.sleep(1)
    return True


def wait_for_not(condition_fn, args, timeout=60):
    """Waits till condition became false or timeout

    Return True if condition become False within timeout period
    """
    def not_condition():
        return not condition_fn(*args)
    return wait_for(not_condition, tuple(), timeout)


def shell_escape(string):
    """
    Return string so it can be passed as argument in shell

    For example::

        >>> print shell_escape('abc$')
        'abc$'
        >>> print shell_escape('I don\'t know')
        'I don'"'"'t know'
    """
    return "'" + string.replace("'", "'\"'\"'") + "'"


def term_winsz():
    """Return terminal window size (height, width)"""
    winsz_fmt = "HHHH"
    winsz_arg = " " * struct.calcsize(winsz_fmt)
    if not sys.stdin.isatty():
        # raise type("NotConnectToTTYDevice", (Exception,), {})()
        return (25, 80)
    return struct.unpack(winsz_fmt, fcntl.ioctl(sys.stdin, termios.TIOCGWINSZ, winsz_arg))[:2]


def range2list(rstr):
    """Converts range to list, f.e. 1-3,5,7-9 -> [1,2,3,5,7,8,9]"""
    if rstr == '':
        return []
    ls = []
    for subrange in rstr.split(','):
        start, minus, end = subrange.partition('-')
        if minus == '':  # single port
            ls.append(int(start))
        else:  # port range start-end
            ls.extend(range(int(start), int(end) + 1))
    return sorted(list(set(ls)))


def range_len(rstr):
    """Count numbers in range.

    Example: 1-3,5,7-9 -> 7
    """
    return len(range2list(rstr))


def list2range(ls):
    """Converts list ls to range string, f.e. [1,2,3,5,7,8,9] -> 1-3,5,7-9"""
    if len(ls) == 0:
        return ''
    sls = sorted(ls)
    previous = start = sls[0]
    result = '%s' % start
    for p in sls[1:]:
        if p == previous + 1:
            previous = p
        else:
            if start == previous:
                result = result + ',%s' % p
            else:
                result = result + '-%s,%s' % (previous, p)
            start = previous = p
    if previous > start:
        result = result + '-%s' % previous
    return result


def splitlist(ls, chunksize):
    """Split list into chunks of maximum chunksize"""
    return [ls[i:i + chunksize] for i in range(0, len(ls), chunksize)]


def splitrange(rg, chunksize):
    """Split range into chunks of maximum chunksize"""
    ls = range2list(rg)
    if len(ls) == 0:
        return ['', ]
    return [list2range(e) for e in splitlist(ls, chunksize)]


def joinlists(ls1, ls2):
    return sorted(list(set(ls1 + ls2)))


def joinranges(rg1, rg2):
    return list2range(joinlists(range2list(rg1), range2list(rg2)))


def differenceranges(rg1, rg2):
    s1 = set(range2list(rg1))
    s2 = set(range2list(rg2))
    return list2range(list(s1.difference(s2)))


######## print in color
# from http://blog.mathieu-leplatre.info/colored-output-in-console-with-python.html

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

def printout(text, colour=WHITE, stream=None, nonewline=False):
    newline = '\n'
    if nonewline:
        newline = ''
    stream = stream or sys.stdout
    if not hasattr(printout, 'has_colours'):
        if not hasattr(stream, "isatty"):
            printout.has_colours = False
        elif not stream.isatty():
            printout.has_colours = False  # auto color only on TTYs
        else:
            try:
                import curses
                curses.setupterm()
                printout.has_colours = curses.tigetnum("colors") > 2
            except:
                # guess false in case of error
                printout.has_colours = False
    if printout.has_colours:
        seq = "\x1b[1;%dm" % (30+colour) + text + "\x1b[0m" + newline
        stream.write(seq)
    else:
        stream.write(text + newline)


# Encryption

import base64
import hashlib
from Crypto import Random
from Crypto.Cipher import AES

class AESCipher(object):

    def __init__(self, key):
        self.bs = 32
        self.key = hashlib.sha256(key.encode()).digest()

    def encrypt(self, raw):
        raw = self._pad(raw)
        iv = Random.new().read(AES.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(raw))

    def decrypt(self, enc):
        enc = base64.b64decode(enc)
        iv = enc[:AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(enc[AES.block_size:])).decode('utf-8')

    def _pad(self, s):
        return s + (self.bs - len(s) % self.bs) * chr(self.bs - len(s) % self.bs)

    @staticmethod
    def _unpad(s):
        return s[:-ord(s[len(s)-1:])]


def encrypt(key, password):
    return AESCipher(key).encrypt(password)


def decrypt(key, password):
    return AESCipher(key).decrypt(password)


# Parser

