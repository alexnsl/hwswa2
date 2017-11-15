import os
import sys
import re
import argparse
import logging
from configobj import ConfigObj
from validate import Validator
import yaml
import getpass

import hwswa2
import hwswa2.subcommands as subcommands
from hwswa2.server.factory import servers_context
from hwswa2.parser import AliasedSubParsersAction
from hwswa2.parser import Parser

__version__ = '0.7.0'

__all__ = ['read_configuration', 'read_servers', 'read_networks', 'run_subcommand']

logger = logging.getLogger(__name__)


def read_servers():
    try:
        hwswa2.config['servers'] = yaml.load(open(hwswa2.config['serversfile']))['servers']
    except KeyError:
        msg = "Cannot find section servers in " + hwswa2.config['serversfile']
        logger.error(msg)
        print(msg)
        sys.exit(1)
    else:
        logger.debug("Read info from servers file: %s" % hwswa2.config['servers'])
        # check for dups
        names = [elem['name'] for elem in hwswa2.config['servers']]
        if len(names) != len(set(names)):
            msg = "Found duplicates in servers file! Exiting ..."
            logger.error(msg)
            print(msg)
            sys.exit(1)


def read_networks():
    logger.debug("Read networks from cli: %s" % hwswa2.config['networks'])
    networks_from_file = yaml.load(open(hwswa2.config['networksfile']))['networks']
    logger.debug("Read info from networks file: %s" % networks_from_file)
    hwswa2.config['networks'].extend(networks_from_file)
    logger.debug("Resulting networks: %s" % hwswa2.config['networks'])


def run_subcommand():
    with servers_context(hwswa2.config['servers']):
        hwswa2.config['subcommand']()


def _network(string):
    """Convert 'network:addr/prefix' to 
    {name: 'network', address: 'addr', prefix: 'prefix'}"""
    regex = re.compile("^(\w+):((?:\d{1,3}\.){3}\d{1,3})/(\d{1,2})$")
    match = regex.match(string)
    if not match:
        raise argparse.ArgumentTypeError("Network not in format name:addr/prefix: %s" % string)
    else:
        return {'name': match.group(1), 'address': match.group(2), 'prefix': match.group(3)}


def int_above_one(value):
    ivalue = int(value)
    if ivalue < 2:
        raise argparse.ArgumentTypeError("%s is not integer > 1" % value)
    return ivalue


def comma_separated_list(string):
    return string.split(',')


def ipport(string):
    try:
        port = int(string)
    except Exception:
        raise argparse.ArgumentTypeError("%s is not integer" % string)
    if not (1 < port < 65534):
        raise argparse.ArgumentTypeError("port %s not in range [1, 65534]" % port)
    return port


def Lportforward(string):
    """[bind_address:]port:host:hostport"""
    args = string.split(':')
    if len(args) == 3:
        bind_address = ''
    elif len(args) == 4:
        bind_address = args[0]
        args = args[1:]  # remove bind_address from args. args now is [port, host, hostport]
    else:
        raise argparse.ArgumentTypeError("%s not in form [bind_address:]port:host:hostport" % string)
    host = args[1]
    port = ipport(args[0])
    hostport = ipport(args[2])
    return {'bind_address': bind_address, 'port': port,
            'host': host, 'hostport': hostport}


def read_configuration():
    """Reads configuration from command line args and main.cfg"""
    global hwswa2
    ### Parsing commandline options
    parser = Parser(
        prog='hwswa2.py', argument_default=argparse.SUPPRESS,
        description='HWSWA: tool for automatization of hardware/software check')
    parser.register('action', 'parsers', AliasedSubParsersAction)

    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + __version__)
    parser.add_argument('-c', '--config', help='path to config file',
                        dest='configfile')
    parser.add_argument('-s', '--servers', help='path to servers file',
                        dest='serversfile')
    parser.add_argument('-n', '--networks', help='path to networks file',
                        dest='networksfile')
    parser.add_argument('-k', '--network', help='network in format name:addr/prefix',
                        type=_network, action='append', metavar='NETWORK',
                        dest='networks',
                        default=[])
    parser.add_argument('-l', '--log', help='path to log file', dest='logfile')
    parser.add_argument('-r', '--reports', help='directory to store reports',
                        dest='reportsdir')
    parser.add_argument('-d', '--debug', help='enable debug', action='store_true')
    parser.add_argument('-a', '--askpass', help='ask encryption password',
            action='store_true', default=False)

    subparsers = parser.add_subparsers(title='Subcommands',
                                       help='Run `hwswa2 <subcommand> -h` for usage')

    subparser = subparsers.add_parser('encrypt', help='encrypt password')
    subparser.set_defaults(subcommand=subcommands.encrypt)

    subparser = subparsers.add_parser('decrypt', help='decrypt password')
    subparser.set_defaults(subcommand=subcommands.decrypt)

    subparser = subparsers.add_parser('list-roles', help='show available roles')
    subparser.set_defaults(subcommand=subcommands.list_roles)

    subparser = subparsers.add_parser('list-servers', help='list servers', aliases=('ls',))
    subparser.set_defaults(subcommand=subcommands.list_servers)

    subparser = subparsers.add_parser('check', help='check servers',
                                      aliases=('ck',))
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.check)

    subparser = subparsers.add_parser('show-reqs', help='show requirements for servers',
                                      aliases=('sr',))
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.show_reqs)

    subparser = subparsers.add_parser('prepare', help='prepare servers (not implemented)',
                                      aliases=('pr',))
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.prepare)

    subparser = subparsers.add_parser('shell', help='open shell to server',
                                      aliases=('sh',))
    subparser.add_argument('-L', help='local port forwarding as in openssh client',
                            type=Lportforward, dest='Lportforward',
                            metavar='[bind_address:]port:host:hostport')
    subparser.add_argument('servername', metavar='server')
    subparser.set_defaults(subcommand=subcommands.shell)

    subparser = subparsers.add_parser('reboot',
                                      help='reboot server(s) and measure reboot time')
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.reboot)

    subparser = subparsers.add_parser('exec', help='execute command interactively',
                                      aliases=('e',))
    subparser.add_argument('-t', '--tty', help='enable pseudo-tty allocation',
                           action='store_true')
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('sshcmd', nargs=argparse.REMAINDER, metavar='cmd')
    subparser.set_defaults(subcommand=subcommands.exec_cmd)

    subparser = subparsers.add_parser('ni_exec',
                                      help='execute command non-interactively',
                                      aliases=('ne',))
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('sshcmd', nargs=argparse.REMAINDER, metavar='cmd')
    subparser.set_defaults(subcommand=subcommands.ni_exec_cmd)

    subparser = subparsers.add_parser('bulk_exec',
        help='execute command non-interactively on few servers in parallel',
        aliases=('be',))
    subparser.add_argument('-o', '--stdout', help='show stdout', action='store_true')
    subparser.add_argument('-e', '--stderr', help='show stderr', action='store_true')
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames',
        type=comma_separated_list, help='specific server(s)',
        metavar='server1,server2,..')
    subparser.add_argument('sshcmd', nargs=argparse.REMAINDER, metavar='cmd')
    subparser.set_defaults(subcommand=subcommands.bulk_exec_cmd)

    subparser = subparsers.add_parser('put', help='copy file to server',
                                      aliases=('p',))
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('localpath')
    subparser.add_argument('remotepath', nargs='?', default=None)
    subparser.set_defaults(subcommand=subcommands.put)

    subparser = subparsers.add_parser('get', help='copy file from server',
                                      aliases=('g',))
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('remotepath')
    subparser.add_argument('localpath', nargs='?', default=None)
    subparser.set_defaults(subcommand=subcommands.get)

    subparser = subparsers.add_parser('firewall',
                                      help='check connections between servers',
                                      aliases=('fw',))
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.firewall)

    subparser = subparsers.add_parser('show-firewall',
                                      help='show firewall requirements for servers',
                                      aliases=('sfw',))
    formatgroup = subparser.add_mutually_exclusive_group(required = True)
    formatgroup.add_argument('-c', '--compact', help='compact output',
                             action='store_true')
    formatgroup.add_argument('-v', '--csv', help='csv output', action='store_true')
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.show_firewall)

    subparser = subparsers.add_parser('lastreport',
                                      help='show/save last report for the servers',
                                      aliases=('lr',))
    formatgroup = subparser.add_mutually_exclusive_group()
    formatgroup.add_argument('-r', '--raw', help='show raw file content',
            action='store_true')
    formatgroup.add_argument('-x', '--xlsx', help='save to <reportsdir>/reportYYYYMMDD-HHMM.xlsx file',
            action='store_true')
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.lastreport)

    subparser = subparsers.add_parser('report',
                                      help='show particular report for server',
                                      aliases=('r',))
    subparser.add_argument('-r', '--raw', help='show raw file content',
                           action='store_true')
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('reportname', metavar='report')
    subparser.set_defaults(subcommand=subcommands.show_report)

    subparser = subparsers.add_parser('reports',
                                      help='list reports for server(s)',
                                      aliases=('rs',))
    servergroup = subparser.add_mutually_exclusive_group(required = True)
    servergroup.add_argument('-a', '--all', dest='allservers',
                             help='all servers', action='store_true')
    servergroup.add_argument('-s', '--servers', dest='servernames', nargs='+',
                             help='specific server(s)', metavar='server')
    subparser.set_defaults(subcommand=subcommands.reports)

    subparser = subparsers.add_parser('reportdiff',
                                      help='show difference between reports',
                                      aliases=('rd',))
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('oldreport')
    subparser.add_argument('newreport')
    subparser.set_defaults(subcommand=subcommands.reportdiff)

    subparser = subparsers.add_parser('reports-history',
        help='show history of reports, by diffs',
        aliases=('rh',))
    subparser.add_argument('servername', metavar='server')
    subparser.add_argument('-n', '--reports-number',
            type=int_above_one, default=5, dest='reportsnumber',
            help='compare last <n> reports, 5 by default')
    subparser.set_defaults(subcommand=subcommands.reportshistory)

    subparser = subparsers.add_parser('agent', help="open agent console")
    subparser.add_argument('servername', metavar='server')
    subparser.set_defaults(subcommand=subcommands.agent_console)

    args = parser.parse_args()

    ### Parse configuration file
    if hasattr(args, 'configfile'):
        hwswa2.config['configfile'] = args.configfile
    hwswa2.config = ConfigObj(hwswa2.config['configfile'],
                              interpolation='Template',
                              configspec=hwswa2.configspec)

    # validation is required
    # to convert values to correct type, say, from string to boolean
    # and to set default values
    val = Validator()
    hwswa2.config.validate(val)

    # convert from ConfigObj into dict
    # so we can update it later easily
    hwswa2.config = hwswa2.config.dict()

    # values from command line take precedence over configuration file options
    hwswa2.config.update(vars(args))

    # ask encryptionn password
    if hwswa2.config['askpass']:
        hwswa2.password = getpass.getpass(prompt="Servers.yaml encryption password: ")
    else:
        hwswa2.password = os.environ.get('HWSWA2_ENC_PWD') or hwswa2.password

    # create reports directory
    if not os.path.exists(hwswa2.config['reportsdir']):
        os.makedirs(hwswa2.config['reportsdir'])

    # set global ssh and reboot timeouts
    import hwswa2.server.linux
    import hwswa2.server.windows
    import hwswa2.server
    hwswa2.server.linux.TIMEOUT = hwswa2.config['ssh_timeout']
    hwswa2.server.windows.TIMEOUT = hwswa2.config['win_timeout']
    hwswa2.server.linux.REBOOT_TIMEOUT = hwswa2.config['reboot_timeout']
    hwswa2.server.windows.REBOOT_TIMEOUT = hwswa2.config['reboot_timeout']
    hwswa2.server.REBOOT_TIMEOUT = hwswa2.config['reboot_timeout']
