======
HWSWA2
======

Automatization of hardware/software check
=========================================

.. sectnum:
   :depth: 1
   :suffix: .
.. contents:

Creating distribution
---------------------

Distribuition is created from git repo with the use of virtualenv and pyinstaller.

1. Obtain the latest source

   - from git::

     $ git clone https://github.com/alexnsl/hwswa2.git
     $ cd hwswa2


2. Prepare virtualenv::

   $ yum install python-setuptools
   $ easy_install virtualenv
   $ easy_install pip
   $ virtualenv --no-site-packages env
   $ source env/bin/activate

3. Install requirements::

   (env)$ pip install -r requirements.txt

4. Create distribution with pyinstaller

   .. code-block:: shell

      (env)$ which rst2pdf >/dev/null && \
             { for d in README.rst CHANGELOG.rst docs/*rst;
                 do rst2pdf $d; done; }
      (env)$ rm -rf pyinstaller/hwswa2 && \
             pyinstaller --distpath=pyinstaller/hwswa2/ \
                         --workpath=pyinstaller/build/ \
                         --clean pyinstaller/hwswa2.spec && \
             \cp -af README* LICENSE CHANGELOG* config/ resources/ roles/ docs/ \
                     pyinstaller/hwswa2/ && \
             pushd pyinstaller/ && tar zcf hwswa2.tgz hwswa2 && popd

Distribution archive will be stored in pyinstaller/hwswa2.tgz

Requirements: python >=2.7, virtualenv, gcc + glibc-headers,
python-dev, libssl-dev, libkrb5-dev, libffi-dev, libyaml-dev ..

on CentOS 6:

sudo yum install gcc python27-scldevel openssl-devel krb5-devel libffi-devel libyaml-devel

Installation
------------

1. Upload distribution to the server which has access to all checked servers.
2. Unpack.
3. Edit configuration according to your needs.
4. Populate networks.yaml and servers.yaml with information about environment to check.
5. Create missing role.yaml files in roles/, if needed.
6. Prepare convenient alias

.. code-block:: shell

   # mkdir somedir && cd somedir
   # wget -Nc https://bitbucket.org/gorilych/hwswa2/downloads/hwswa2-centos6x64.tgz
   # # or https://bitbucket.org/gorilych/hwswa2/downloads/hwswa2-centos5x64.tgz
   # # or https://bitbucket.org/gorilych/hwswa2/downloads/hwswa2-debian7x64.tgz
   # tar zxf hwswa2-*.tgz

   # cp -a hwswa2/config cfg
   # vim cfg/main.cfg
   # vim cfg/networks.yaml
   # vim cfg/servers.yaml

   # cp roles/mysql.yaml roles/newrole.yaml
   # vim roles/newrole.yaml

   alias hwswa2="`pwd`/hwswa2/hwswa2 -c `pwd`/cfg/main.cfg -s
                 `pwd`/cfg/servers.yaml -n `pwd`/cfg/networks.yaml
                 -r `pwd`/reports"


Usage
-----

All possible options are shown by '-h' switch:

.. code-block:: shell

   $ ./hwswa2 -h
   usage: hwswa2 [-h] [--version] [-c CONFIGFILE] [-s SERVERSFILE]
                 [-n NETWORKSFILE] [-l LOGFILE] [-r REPORTSDIR] [-d]

                 {check,c,prepare,p,checkall,ca,prepareall,pa,shell,s,reboot,
                  exec,e,ni_exec,ne,put,get,g,firewall,f,lastreport,lr,
                  report,r,reports,rs,reportdiff,rd}
                 ...

   HWSWA: tool for automatization of hardware/software check

   optional arguments:
     -h, --help            show this help message and exit
     --version             show program's version number and exit
     -c CONFIGFILE, --config CONFIGFILE
                           path to config file
     -s SERVERSFILE, --servers SERVERSFILE
                           path to servers file
     -n NETWORKSFILE, --networks NETWORKSFILE
                           path to networks file
     -l LOGFILE, --log LOGFILE
                           path to log file
     -r REPORTSDIR, --reports REPORTSDIR
                           directory to store reports
     -d, --debug           enable debug

   Subcommands:
     {check,c,prepare,p,checkall,ca,prepareall,pa,shell,s,reboot,exec,e,
      ni_exec,ne,put,get,g,firewall,f,lastreport,lr,report,r,reports,rs,
      reportdiff,rd}
       Run `hwswa2 <subcommand> -h` for usage
       check (c)           check specific servers
       prepare (p)         prepare specific servers
       checkall (ca)       check all servers
       prepareall (pa)     prepare all servers
       shell (s)           open shell to server
       reboot              reboot server(s) and measure reboot time
       exec (e)            execute command interactively
       ni_exec (ne)        execute command non-interactively
       put (p)             copy file to server
       get (g)             copy file from server
       firewall (f)        check connections between servers
       lastreport (lr)     show last report for the server
       report (r)          show particular report for server
       reports (rs)        show all generated reports for the server
       reportdiff (rd)     show difference between reports


Configuration
-------------     

Main configuration file is hwswa2/config/main.cfg, variables are self-explanatory.

hwswa2/config/servers.yaml and hwswa2/config/networks.yaml are examples of servers access info and networks info, it should be modified with actual information prior to running.

Advanced
--------

You can modify roles/\*.yaml or roles/remote-scripts/ files for your own needs.

Debugging
---------

HWSWA2 can be debugged with PDB. To start debugging, send SIGUSR1 to the main
process. Pdb console can be accessed with telnet on 127.0.0.1:4444::

  $ ps ax | grep hwswa
  19956 pts/2    Sl+    0:00 python ./hwswa2.py -dc ../tests/main.cfg.test shell -L localhost:2000:localhost:22 localhost
  19981 pts/3    S+     0:00 grep hwswa

  $ kill -SIGUSR1 19956

  $ telnet localhost 4444
  ...
  (Pdb) 

Source files
------------

::
   
   hwswa2$ ls -F
   CHANGELOG.rst  config/  hwswa2.py*  logs/    requirements.txt  TODO
   roles/         docs/    hwswa2/     LICENSE     pyinstaller/  README.rst

   hwswa2$ ls -F roles/
   branding.yaml  linpgh.yaml          paci_pcs.yaml     poa.managed.fw.yaml
   common.yaml    linpps.yaml          paci_sn_pcs.yaml  pvclin.yaml
   helb.yaml      linwdg.yaml          pbalinbe.yaml     remote-scripts/
   henas.yaml     misclin.yaml         pbalinfe.yaml     sysbu.yaml
   hewsl.yaml     mysql.yaml           pbalinos.yaml     ui.yaml
   lindns.yaml    ngwebserver.fw.yaml  pcs.fw.yaml       webserver.pub.fw.yaml
   linmndb.yaml   paci_imdb.yaml       pgsql.yaml        wsng.yaml
   linmn.yaml     paci_im.yaml         poadb.yaml

   hwswa2$ ls -F roles/remote-scripts/
   bin32/  bin64/

   hwswa2$ ls -F config/
   main.cfg  networks.yaml  servers.yaml

   hwswa2$ ls -F logs/
   hwswa2.log  reports/

   hwswa2$ ls -F logs/reports/
   localhost

hwswa2.py
  script to run directly from source, without building binary distribution

roles/
  location of role check description files: `<role name (lowercase)>.yaml`

roles/remote-scripts/{bin32,bin64}
  location of binaries copied to remote server in order to run
  specific checks (like nc binary)

config/main.cfg
  main configuration file. Basically, it is not needed to
  modify, except for specific cases, like for debug.

config/networks.yaml
  contains network definitions

config/servers.yaml
  contains server definitions (with access details)

logs/hwswa2.log
  application log

logs/reports/
  directory to store reports to

KNOWN ISSUES
------------

- Interactive execution combines stdout and stderr
