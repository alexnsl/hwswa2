#!/usr/bin/env python
import logging
import os
import sys


### Run pdb on `kill -SIGUSR1 <pid>`
# to debug, run telnet 127.0.0.1 4444
# from https://dzone.com/articles/remote-debugging-python-using
import signal
import socket
import pdb


class Rdb(pdb.Pdb):

  def __init__(self, port=4444):
    self.old_stdout = sys.stdout
    self.old_stdin = sys.stdin
    self.skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.skt.bind(('127.0.0.1', port))
    self.skt.listen(1)
    (clientsocket, address) = self.skt.accept()
    handle = clientsocket.makefile('rw')
    pdb.Pdb.__init__(self, completekey='tab', stdin=handle, stdout=handle)
    sys.stdout = sys.stdin = handle

  def do_continue(self, arg):
    sys.stdout = self.old_stdout
    sys.stdin = self.old_stdin
    self.skt.close()
    self.set_continue()
    return 1

  do_c = do_cont = do_continue


def handler(signum, frame):
    remote_debug = Rdb()
    remote_debug.set_trace()

signal.signal(signal.SIGUSR1, handler)
###

import hwswa2
from hwswa2.functions import read_configuration, read_servers, read_networks, run_subcommand


def init_logger():
    logdir = os.path.dirname(os.path.abspath(hwswa2.config['logfile']))
    if not os.path.exists(logdir):
        os.makedirs(logdir)
    logging.basicConfig(filename=hwswa2.config['logfile'], filemode='a', level=logging.INFO,
                        format="%(asctime)s %(levelname)s " +
                        "[%(process)d:%(processName)s:%(name)s.%(funcName)s():%(lineno)d] " +
                               "%(message)s")
    if sys.hexversion >= 0x2070000:
        logging.captureWarnings(True)
    logger = logging.getLogger("hwswa2")
    if hwswa2.config['debug']:
        logger.setLevel(logging.DEBUG)
    return logger


def main():
    read_configuration()
    logger = init_logger()
    logger.debug("Application started")
    logger.debug("Configuration: %s" % hwswa2.config)
    read_servers()
    read_networks()
    run_subcommand()
    logger.debug("Application finished")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
