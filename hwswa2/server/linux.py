import logging
import paramiko
import socket
import os
import stat
import sys
import select
import signal
import termios
import tty
import time
import subprocess
import posixpath
import base64
import random
import string
import fnmatch
from ipcalc import Network
import threading
try:
    import SocketServer
except ImportError:
    import socketserver as SocketServer

import hwswa2.auxiliary as aux
import hwswa2

from hwswa2.server import (Server, ServerException, TunnelException,
                           ExecutionException, TimeoutException, TIMEOUT,
                           REBOOT_TIMEOUT)

__all__ = ['LinuxServer', 'LinuxServerException', 'TIMEOUT', 'REBOOT_TIMEOUT']

logger = logging.getLogger(__name__)
logging.getLogger("paramiko").setLevel(logging.WARNING)


class LinuxServerException(ServerException):
    pass


class LinuxServer(Server):

    def __init__(self, *args, **kwargs):
        super(LinuxServer, self).__init__(*args, **kwargs)
        self._sshclient = None
        # tunnel via gateway used for connections to this server
        self._sshtunnel = None
        # tunnels for other servers. 'name': {'sshclient': sshclient, 'tunnel': tunnel}
        self._sshtunnels = {}
        self._supath = None
        for k in ['su', 'sudo']:
            if self.account is not None and k in self.account:
                self.account['sutype'] = k
                self.account['supassword'] = self.account[k]
                break

    def cleanup(self):
        # remove ssh tunnel connections
        servers = [server for server in self._sshtunnels]
        for server in servers:
            sshclient = self._sshtunnels[server]['sshclient']
            if sshclient is not None:
                sshclient.close()
                del self._sshtunnels[server]
        # clean up temporary files/dirs and disconnect
        if self._is_connected():
            self.agent_stop()
            for tmp in self._tmp:
                self._remove(tmp)
            self._tmp = []
            self._disconnect()

    ########## Internal methods

    def _is_connected(self):
        return self._sshclient is not None

    def _address(self):
        if self.port is None:
            address = self.account['login'] + '@' + self.address
        else:
            address = self.account['login'] + '@' + self.address + ':' + str(self.port)
        return address

    def _new_sshclient(self, timeout=None):
        """Initiates connection and returns SSHClient object

        Returns None if connection fails.
        """
        timeout = timeout or TIMEOUT
        logger.debug("Trying to connect to %s" % self)
        username = self.account['login']
        password = self.decrypt_in_account('password')
        key_filename = self.account.get('key')
        # _connect_to_gateway() will initialize self._sshtunnel used later
        if not self._connect_to_gateway(timeout=timeout):
            return None
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=self.address, port=self.port or 22, username=username, password=password,
                           key_filename=key_filename, timeout=timeout, sock=self._sshtunnel)
        except paramiko.BadHostKeyException:
            self._last_connection_error = 'BadHostKeyException raised while connecting to %s' % self._address()
        except paramiko.AuthenticationException:
            self._last_connection_error = 'Authentication failure while connecting to %s' % self._address()
        except paramiko.SSHException as pe:
            self._last_connection_error = 'SSHException raised while connecting to %s: %s' % (self._address(), pe)
        except socket.error as serr:
            self._last_connection_error = 'socket.error raised while connecting to %s: %s' % (self._address(), serr)
        except Exception as e:
            self._last_connection_error = '%s raised while connecting to %s: %s' % (type(e), self._address(), e)
        else:
            logger.debug('Established connection with %s' % self)
            return client
        logger.error(self._last_connection_error)
        return None

    def _connect_to_gateway(self, timeout=None):
        """Asks gateway to create ssh tunnel to this server

        Returns true if ssh tunnel is created successfully or there is no need for it
        """
        timeout = timeout or TIMEOUT
        if self.gateway is None:
            return True
        else:
            try:
                self._sshtunnel = self.gateway.create_tunnel(self.name, self.address, self.port or 22, timeout=timeout)
            except TunnelException as te:
                self._last_connection_error = "cannot connect via gateway %s: %s" % (self.gateway, te.msg)
                logger.error(self._last_connection_error)
                return False
            else:
                logger.debug("created tunnel via %s" % self.gateway)
                return True

    def _disconnect_from_gateway(self):
        if self.gateway is not None:
            try:
                self.gateway.destroy_tunnel(self.name)
            finally:
                logger.debug("destroyed tunnel via %s" % self.gateway)
                self._sshtunnel = None

    def _connect(self, reconnect=False, timeout=None):
        """Initiate SSH connection to the server.

        Raise LinuxServerException on failure.
        """
        timeout = timeout or TIMEOUT
        if self._is_connected() and not reconnect:
            return
        else:
            if self._is_connected():  # was asked to reconnect, obviously
                self._disconnect()
                logger.debug("Will reconnect to %s" % self)
            self._sshclient = self._new_sshclient(timeout)
        if not self._is_connected():
            raise LinuxServerException("Connection to %s failed: %s" % (self, self._last_connection_error))

    def _disconnect(self):
        if self._sshclient is not None:
            self._sshclient = None
            self._disconnect_from_gateway()

    def _exists(self, path):
        self._connect()
        sftp = self._sshclient.open_sftp()
        try:
            sftp.stat(path)
            return True
        except IOError as ie:
            return False

    def _listdir(self, remotedir):
        self._connect()
        sftp = self._sshclient.open_sftp()
        return sftp.listdir(remotedir)

    def _isdir(self, remotepath):
        self._connect()
        sftp = self._sshclient.open_sftp()
        attrs = sftp.stat(remotepath)
        return stat.S_ISDIR(attrs.st_mode)

    def _isfile(self, remotepath):
        self._connect()
        sftp = self._sshclient.open_sftp()
        attrs = sftp.stat(remotepath)
        return stat.S_ISREG(attrs.st_mode)

    def _put_dir_content(self, localdir, remotedir):
        for f in os.listdir(localdir):
            lname = os.path.join(localdir, f)
            rname = os.path.join(remotedir, f)
            if os.path.isfile(lname):
                self.put(lname, rname)
            if os.path.isdir(lname):
                self.mkdir(rname)
                self._put_dir_content(lname, rname)

    def _get_dir_content(self, remotedir, localdir):
        for f in self._listdir(remotedir):
            lname = os.path.join(localdir, f)
            rname = os.path.join(remotedir, f)
            if self._isfile(rname):
                self.get(rname, lname)
            if self._isdir(rname):
                os.makedirs(lname)
                self._get_dir_content(rname, lname)

    def _remove(self, path, sftp=None):
        self._connect()
        sftp = sftp or self._sshclient.open_sftp()
        if self._isdir(path):
            for name in sftp.listdir(path):
                self._remove(path + '/' + name, sftp=sftp)
            sftp.rmdir(path)
        elif self._isfile(path):
            sftp.remove(path)

    def _bootid(self):
        return self.get_cmd_out('cat /proc/sys/kernel/random/boot_id')

    def _is_it_me(self):
        if hasattr(subprocess, 'check_output'):
            mybootid = subprocess.check_output(['cat', '/proc/sys/kernel/random/boot_id']).strip()
        else:
            mybootid = subprocess.Popen(
                ['cat', '/proc/sys/kernel/random/boot_id'],
                stdout=subprocess.PIPE
            ).communicate()[0].strip()
        server_bootid = self._bootid()
        logger.debug("Is it me? Comparing %s and %s" % (mybootid, server_bootid))
        return mybootid == server_bootid

    @staticmethod
    def _pipe_to_channel(channel):
        """redirects sys.stdin,out,err to/from channel"""
        while True:
            try:
                r, w, e = select.select([sys.stdin, channel], [], [], 0.1)
            except select.error:
                continue
            except Exception, e:
                logger.error("select.select() raised exception %s: %s"
                             % (type(e).__name__, e.args))
                raise e
            if sys.stdin in r:
                x = os.read(sys.stdin.fileno(), 1)
                logger.debug("stdin: %s" % repr(x))
                if len(x) == 0:
                    channel.shutdown_write()
                try:
                    channel.send(x)
                except socket.error:
                    pass
            if channel in r:
                if channel.recv_ready():
                    x = channel.recv(1024)
                    logger.debug("stdout: %s" % repr(x))
                    sys.stdout.write(x)
                    sys.stdout.flush()
                if channel.recv_stderr_ready():
                    x = channel.recv_stderr(1024)
                    logger.debug("stderr: %s" % repr(x))
                    sys.stderr.write(x)
                    sys.stderr.flush()
            if channel.exit_status_ready():
                logger.debug("channel exited")
                break
        while channel.recv_ready():
            x = channel.recv(1024)
            logger.debug("stdout: %s" % repr(x))
            sys.stdout.write(x)
            sys.stdout.flush()
        while channel.recv_stderr_ready():
            x = channel.recv_stderr(1024)
            logger.debug("stderr: %s" % repr(x))
            sys.stderr.write(x)
            sys.stderr.flush()

    @staticmethod
    def _interactive_shell(channel):
        # get current terminal's settings
        height, width = aux.term_winsz()
        if not channel is None and \
                not channel.closed and \
                not channel.eof_received and \
                not channel.eof_sent and \
                channel.active:
            channel.resize_pty(width=width, height=height)
        # remember current signal handler
        old_handler = signal.getsignal(signal.SIGWINCH)
        # remember old tty settings
        old_tty = termios.tcgetattr(sys.stdin)
        # set our handler for winchange signal

        def on_win_resize(signum, frame):
            if not channel is None and \
                    not channel.closed and \
                    not channel.eof_received and \
                    not channel.eof_sent and \
                    channel.active:
                height, width = aux.term_winsz()
                channel.resize_pty(width=width, height=height)

        signal.signal(signal.SIGWINCH, on_win_resize)
        try:
            # change tty settings
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            # interact
            LinuxServer._pipe_to_channel(channel)
        finally:
            signal.signal(signal.SIGWINCH, old_handler)
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

    ########## Public methods

    def Lportforward(self, bind_address, port, host, hostport):
        """Copied from paramiko demos/forward.py

        return SocketServer object
        """

        class ForwardServer (SocketServer.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        class Handler (SocketServer.BaseRequestHandler):
            def handle(self):
                try:
                    chan = self.ssh_transport.open_channel('direct-tcpip',
                                                           (self.chain_host, self.chain_port),
                                                           self.request.getpeername())
                except Exception as e:
                    logger.error('Incoming request to %s:%d failed: %s' % (self.chain_host,
                                                                      self.chain_port,
                                                                      repr(e)))
                    return
                if chan is None:
                    logger.error('Incoming request to %s:%d was rejected by the SSH server.' %
                                 (self.chain_host, self.chain_port))
                    return

                logger.debug('Connected!  Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                                    chan.getpeername(), (self.chain_host, self.chain_port)))
                while True:
                    r, w, x = select.select([self.request, chan], [], [])
                    if self.request in r:
                        data = self.request.recv(1024)
                        if len(data) == 0:
                            break
                        chan.send(data)
                    if chan in r:
                        data = chan.recv(1024)
                        if len(data) == 0:
                            break
                        self.request.send(data)

                peername = self.request.getpeername()
                chan.close()
                self.request.close()
                logger.debug('Tunnel closed from %r' % (peername,))

        class SubHandler (Handler):
            chain_host = host
            chain_port = hostport
            ssh_transport = self._sshclient.get_transport()

        try:
            server = ForwardServer((bind_address, port), SubHandler)
        except socket.gaierror, gaierror:
            logger.error("Cannot use %s to bind, socket.gaierror: %s" % (bind_address, gaierror))
        except socket.error, serr:
            logger.error("Cannot bind to %s:%s, socket.error: %s" % (bind_address, port, serr))
        else:
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            return server
        return None

    def accessible(self, retry=False):
        try:
            self._connect(reconnect=retry, timeout=TIMEOUT)
        except LinuxServerException:
            return False
        return True

    def create_tunnel(self, name, address, port, timeout=None):
        """Creates SSH tunnel via itself, using separate connection

        Returns tunnel, which can be used as socket
        Raises TunnelException in case of failure
        """
        timeout = timeout or TIMEOUT
        logger.debug("%s was asked to create tunnel to %s" % (self, name))
        if name in self._sshtunnels:
            if self._sshtunnels[name]['sshclient'] is not None:
                if self._sshtunnels[name]['tunnel'] is not None:
                    return self._sshtunnels[name]['tunnel']
                else:
                    self._sshtunnels[name]['sshclient'].close()
        self._sshtunnels[name] = {'sshclient': None, 'tunnel': None}
        sshclient = self._new_sshclient(timeout=timeout)
        if sshclient is None:
            del self._sshtunnels[name]
            raise TunnelException(self._last_connection_error)
        else:
            self._sshtunnels[name]['sshclient'] = sshclient
            transport = sshclient.get_transport()
            try:
                logger.debug("%s: about to create channel to %s:%s" % (self, address, port))
                channel = transport.open_channel('direct-tcpip', (address, port), ('127.0.0.1', 0))
                logger.debug("%s: created channel to %s:%s" % (self, address, port))
            except paramiko.ChannelException, chan_e:
                del self._sshtunnels[name]
                raise TunnelException("cannot create tunnel via %s: %s" % (self, chan_e))
            else:
                self._sshtunnels[name]['tunnel'] = channel
                return channel

    def destroy_tunnel(self, name):
        logger.debug("%s was asked to destroy tunnel to %s" % (self, name))
        try:
            self._sshtunnels[name]['sshclient'].close()
        except Exception as e:
            logger.error("trying to remove tunnel %s (sshclient.close()): exception %s: %s"
                         % (name, type(e).__name__, e.args))
            pass
        try:
            del self._sshtunnels[name]
        except Exception as e:
            logger.error("trying to remove tunnel %s (del key): exception %s: %s"
                         % (name, type(e).__name__, e.args))
            pass

    def write(self, path, data):
        self._connect()
        sftp = self._sshclient.open_sftp()
        f = sftp.open(path, 'w')
        f.write(data)
        f.close()

    def mkdir(self, path):
        self._connect()
        sftp = self._sshclient.open_sftp()
        sftp.mkdir(path)

    def exec_cmd_i(self, cmd, get_pty=False):
        """Executes command interactively"""
        self._connect()
        status, result = self.agent_cmd('exec_i ' + aux.shell_escape(cmd),
                                        interactively=True)
        if status:
            return result
        else:
            logger.error("Execution of %s failed: %s" % (cmd, result))
            raise LinuxServerException("Execution of %s failed: %s" % (cmd, result))

    def exec_cmd(self, cmd, input_data=None, timeout=None):
        """Executes command and returns tuple of stdout, stderr and status"""
        timeout = timeout or TIMEOUT
        logger.debug("Executing on %s: %s" % (self, cmd))
        self._connect()
        if not self.agent_start():
            logger.error("Failed to start agent on %s" % self)
            raise LinuxServerException("Failed to start agent on %s" % self)
        else:
            if input_data:
                i_d = base64.b64encode(input_data)
            else:
                i_d = "''"
            acmd = 'cmd_exec ' + aux.shell_escape(cmd) + ' ' + i_d + ' ' + str(timeout)
            status, result = self.agent_cmd(acmd)
            # result is "[reason:<reason of failure>] \
            # returncode:<num> stdout:<base64encoded> stderr:<base64encoded>"
            logger.debug("exec_cmd result %s" % result)
            result = dict([r.split(':') for r in result.split(' ')])
            if status:
                return (base64.b64decode(result['stdout']),
                        base64.b64decode(result['stderr']), int(result['returncode']))
            else:
                reason = base64.b64decode(result.get('reason'))
                if reason == 'timeout':
                    raise TimeoutException("Timeout %s" % timeout,
                                           cmd=cmd,
                                           output=base64.b64decode(result['stdout']),
                                           stderr=base64.b64decode(result['stderr']))
                else:
                    raise LinuxServerException("Execution of %s failed: %s" % (cmd, reason))

    def get_cmd_out(self, cmd, input_data=None, timeout=None):
        timeout = timeout or TIMEOUT
        stdout_data, stderr_data, status = self.exec_cmd(cmd, input_data, timeout=timeout)
        # remove last trailing newline
        if len(stdout_data) > 0 and stdout_data[-1] == '\n':
            stdout_data = stdout_data[:-1]
        if status == 0:
            return stdout_data
        # Exit code <> 0, raise ExecutionException
        if len(stderr_data) > 0 and stderr_data[-1] == '\n':
            stderr_data = stderr_data[:-1]
        raise ExecutionException("Exit code: %s" % status,
                                  output=stdout_data,
                                  stderr=stderr_data)

    def mktemp(self, template='hwswa2.XXXXX', ftype='d', path='/tmp', cleanup_later=True):
        """Creates directory/file using mktemp and returns its name"""
        #generate name
        prefix = template.rstrip('X')
        suffix_len = len(template) - len(prefix)
        pattern = prefix + '*'
        existing_names = fnmatch.filter(self._listdir(path), pattern)
        # try to generate random filename
        name = None
        while True:
            suffix = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(suffix_len))
            name = prefix + suffix
            if not name in existing_names:  # name is unique
                break
        full_name = path + '/' + name
        if ftype == 'd':  # directory
            self.mkdir(full_name)
        else:  # file
            self.write(full_name, '')
        if cleanup_later:
            self._tmp.append(full_name)
        return full_name

    def put(self, localpath, remotepath=None):
        if remotepath is None or remotepath == '':
            remotepath = '.'
        logger.debug("Copying %s to %s:%s" % (localpath.decode('utf-8'), self, remotepath.decode('utf-8')))
        if not os.path.exists(localpath):
            raise LinuxServerException("Local path does not exist: %s" % localpath.decode('utf-8'))
        self._connect()
        sftp = self._sshclient.open_sftp()
        if os.path.isfile(localpath):
            if self._exists(remotepath):
                attrs = sftp.stat(remotepath)
                if stat.S_ISDIR(attrs.st_mode):
                    remotepath = os.path.join(remotepath, os.path.basename(localpath))
                sftp.put(localpath, remotepath, confirm=True)
                sftp.chmod(remotepath, os.stat(localpath).st_mode)
            else:
                sftp.put(localpath, remotepath, confirm=True)
                sftp.chmod(remotepath, os.stat(localpath).st_mode)
        if os.path.isdir(localpath):
            if self._exists(remotepath):
                rname = os.path.join(remotepath, os.path.basename(localpath))
                self.mkdir(rname)
                self._put_dir_content(localpath, rname)
            else:
                self.mkdir(remotepath)
                self._put_dir_content(localpath, remotepath)

    def get(self, remotepath, localpath=None):
        if localpath is None or localpath == '':
            localpath = '.'
        logger.debug("Copying to %s from %s:%s" % (localpath.decode('utf-8'), self, remotepath.decode('utf-8')))
        self._connect()
        sftp = self._sshclient.open_sftp()
        if not self._exists(remotepath):
            raise LinuxServerException("Remote path does not exist: %s" % remotepath.decode('utf-8'))
        if self._isdir(remotepath):
            if os.path.exists(localpath):
                lname = os.path.join(localpath, os.path.basename(remotepath))
                os.makedirs(lname)
                self._get_dir_content(remotepath, lname)
            else:
                os.makedirs(localpath)
                self._get_dir_content(remotepath, localpath)
        elif self._isfile(remotepath):
            attrs = sftp.stat(remotepath)
            if os.path.exists(localpath):
                if os.path.isdir(localpath):
                    localpath = os.path.join(localpath, os.path.basename(remotepath))
                sftp.get(remotepath, localpath)
                os.chmod(localpath, attrs.st_mode)
            else:  # localpath does not exist
                sftp.get(remotepath, localpath)
                os.chmod(localpath, attrs.st_mode)

    def check_reboot(self, timeout=None):
        """Reboots the server and checks the time it takes to come up

        Returns number of seconds (int/long) or reason why check is not possible (string)
        """
        timeout = timeout or REBOOT_TIMEOUT
        try:
            if self._is_it_me():
                self.check_reboot_result = "we are running here, no reboot"
                return self.check_reboot_result
            logger.debug("Trying to reboot %s" % self)
            starttime = time.time()
            stdout, stderr, exitcode = self.exec_cmd("nohup sh -c 'sleep 1;" \
                                                     "/sbin/shutdown -r now' &",
                                                     timeout=3)
        except LinuxServerException as ex:
            self.check_reboot_result = "reboot check failed: %s" % ex
            return self.check_reboot_result
        if not exitcode == 0:
            self.check_reboot_result = "reboot command failed with exitcode %s."\
                                       " stdout: %s, stderr: %s"\
                                       % (exitcode, repr(stdout), repr(stderr))
            return self.check_reboot_result
        self.cleanup()
        logger.debug("reboot command is sent, now wait till server is down")
        # wait till shutdown:
        if aux.wait_for_not(self.accessible, [True], timeout):
            logger.debug("%s is down" % self)
            delta = time.time() - starttime
            # wait till boot
            if aux.wait_for(self.accessible, [True], timeout - delta):
                self.check_reboot_result = int(round(time.time() - starttime))
                return self.check_reboot_result
            else:
                self.check_reboot_result = "server is not accessible after %s seconds" % timeout
                return self.check_reboot_result
        else:
            # check uptime, it can be the case server reboots too fast
            uptime, space, idle = self.get_cmd_out('cat /proc/uptime').partition(' ')
            uptime = float(uptime)
            if uptime < timeout + 10:
                self.check_reboot_result = 0
                return self.check_reboot_result
            else:
                self.check_reboot_result = "server does not go to reboot: still accessible after %s seconds" % timeout
                return self.check_reboot_result

    def shell(self):
        """Opens remote SSH session"""
        self._connect()
        if hwswa2.config['Lportforward']:
            # failure to do port forwarding is not fatal error
            server = self.Lportforward(**hwswa2.config['Lportforward'])
            if not server:
                print('port forwarding failed, search logs for Lportforward errors')
        status, result = self.agent_cmd('shell', interactively=True)
        if hwswa2.config['Lportforward'] and server:
            server.shutdown()
        if status:
            return result
        else:
            logger.error("Execution of shell failed: %s" % result)
            return 1

    def agent_start(self):
        """Starts remote agent on server"""
        if self._agent is not None:
            return True
        try:
            self._connect()
            serverd_py = os.path.join(hwswa2.config['resources'], 'serverd.py')
            # remote path. No need to remove it on exit because script deletes itself.
            r_serverd_py = self.mktemp(template='serverd.XXXX', ftype='f', path='/tmp', cleanup_later=False)
            self.put(serverd_py, r_serverd_py)
            debugopt = ' -d' if hwswa2.config['remote_debug'] else ''
            stdin, stdout, stderr = self._sshclient.exec_command(r_serverd_py + debugopt, get_pty=True)
            banner = stdout.readline()
            if not banner.startswith('started_ok'):
                banner = stdout.readline()
            logger.debug('remote agent started on %s: %s' % (self, banner))
            self._agent = {'stdin': stdin,
                           'stdout': stdout,
                           'stderr': stderr}
            sutype = self.account.get('sutype')
            if sutype:
                supassword = self.decrypt_in_account('supassword')
                cmd = 'elevate_' + sutype
                if supassword:
                    cmd += ' ' + aux.shell_escape(supassword)
                elevated, reason = self.agent_cmd(cmd)
                if elevated:
                    return True
                else:
                    logger.error("Failed to elevate priviliges: %s" % reason)
                    try:
                        self.agent_stop()
                    except Exception:
                        pass
                    return False
            return True
        except Exception as e:
            logger.error("agent not started, exception %s: %s"
                         % (type(e).__name__, e.args), exc_info=True)
            return False

    def agent_stop(self):
        """Stops remote agent on server"""
        if self._agent is not None:
            try:
                self.agent_cmd('exit')
                self._agent['stdin'].close()
            except Exception as e:
                logger.error("could not stop agent, exception %s: %s"
                             % (type(e).__name__, e.args))
            finally:
                self._agent = None

    def agent_cmd(self, cmd, interactively=False):
        """Sends command to remote agent and returns tuple (status, result)"""
        if not self.agent_start():
            return False, 'agent not started'
        else:
            stdin = self._agent['stdin']
            stdout = self._agent['stdout']
            logger.debug('command: ' + cmd)
            stdin.write(cmd + '\n')
            reply = stdout.readline().strip()
            logger.debug("reply1: %s" % reply)
            if reply == cmd:  # our input echoed, need to read again
                reply = stdout.readline().strip()
                logger.debug("reply2: %s" % reply)
            logger.debug('accept reply: ' + reply)
            accepted, space, reason = reply.partition(' ')
            if accepted == 'accepted_notok':
                return False, 'command not accepted: ' + reason
            elif not accepted == 'accepted_ok':
                return False, 'wrong accept message, should start with accepted_ok/accepted_notok: ' + reply
            else:  # accepted == 'accepted_ok'
                logger.debug('command accepted on server %s: %s' % (self, reason))
                if interactively:
                    channel = stdin.channel
                    # flush stdout buffer, if any
                    l = len(stdout._rbuffer)
                    if l > 0:
                        buffer = stdout.read(l)
                        sys.stdout.write(buffer)
                    if sys.stdin.isatty():
                        LinuxServer._interactive_shell(channel)
                    else:
                        LinuxServer._pipe_to_channel(channel)
                    status = channel.recv_exit_status()
                    logger.info("exit code: %s" % status)
                    channel.close()
                    self._agent = None
                    return True, status
                else:
                    reply = stdout.readline().strip()
                    logger.debug('result reply: ' + reply)
                    result_status, space, result = reply.partition(' ')
                    if result_status == 'result_ok':
                        return True, result
                    elif result_status == 'result_notok':
                        return False, result
                    else:
                        return (False, 'wrong result message, should start with result_ok/result_notok: ' + reply)

    def agent_console(self):
        """Open agent console"""
        self._connect()
        status, result = self.agent_cmd('help', interactively=True)
        if status:
            return result
        else:
            logger.error("Execution of shell failed: %s" % result)
            return 1

    def param_cmd(self, cmd):
        """Execute cmd to obtain some server parameter

        :param cmd: raw command to execute
        :return: (status, output, failure)
        """
        try:
            output = self.get_cmd_out(cmd)
        except ServerException as se:
            output = se.details.get('output')
            stderr = se.details.get('stderr')
            return False, output, str(se) + ' |STDERR: ' + stderr
        else:
            return True, output, None

    def param_script(self, script):
        """Execute script to obtain some server parameter

        :param script: script content
        :return: (status, output, failure)
        """
        scriptpath = self.mktemp(ftype='f')
        self.write(scriptpath, script)
        self.exec_cmd('chmod +x %s' % scriptpath)
        return self.param_cmd(scriptpath)

    def get_ips(self, networks=None):
        """Obtain IPv4 addresses from server and save result to self.nw_ips.

        :param networks: [{name: '', address: '', prefix: ''}, ... ]
        :return: True, if any found IP matches some network from passed networks
        """
        cmd = "/sbin/ip -family inet -oneline address list scope global | awk '{print $4}'"
        ips = [Network(ip) for ip in self.get_cmd_out(cmd).split()]
        status = False
        for ip in ips:
            m = ip.mask
            n_a = "%s" % ip.network()
            ip_addr = "%s" % ip
            network_name = None
            if networks:
                network_name = next((n['name'] for n in networks if n['prefix'] == m and n['address'] == n_a), None)
            if network_name:
                self.nw_ips[network_name] = ip_addr
                status = True
            else:
                self.nw_ips[n_a + '/' + str(m)] = ip_addr
        return status

