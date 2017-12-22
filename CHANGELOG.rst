
Version History
===============

0.7.2 (2017-11?)
    - Change: updated roles according requirements of OAP 7.2
    - Change: removed pyinstaller-based distribution
    - Added: support for CircleCI
    - Added: PGHA roles
    - Added: WebHosting Plesk roles

0.7.0 (2016-03-01)
    - Added: new options for report: --xlsx
    - Added: new options for bulk_exec: --stdout and --stderr
    - Added: port forwarding for LinuxServer for shell subcommand like in openssh -L
    - Added: scalar type for role parameter
    - Added: debugging with PDB on SIGUSR1 (PDB console: telnet localhost 4444)
    - Added: example of script to build distribution: build.sh
    - Added: support for encrypted passwords in servers.yaml (can be passed via --askpass or environment variable HWSWA2_ENC_PWD)
    - Added: helper subcommands encrypt and decrypt for passwords
    - Added: requirement for CPU virtualization support features for VZ roles
    - Added: subcommand show-reqs 
    - Added: configuration documentation
    - Change: roles directory renamed from 'checks' to 'roles'
    - Change: remote scripts are imbed into role files
    - Change: support for Python 2.6 dropped!!!
    - Improved: winrmlib is used instead of external hwswa2_wagent for Windows
    - Improved: multiprocessing used instead of multithreading (can help eliminate underground knocks)
    - Improved: subcommand report can show reports for multiple servers
    - Bugfix: list-servers, --all for other subcommands were not working
    - Bugfix: reboot -a didn't show server names
    - Bugfix: check ignores /dev/xvd* block devices
    - Bugfix: bulk_exec fails with timeout exception 
    - Bugfix: hwswa does not fail if wrong gateway name is specified
    - Bugfix: requirement for disabled selinux for oa-managed linux nodes
    - Bugfix: parameter failures are generated in reports in case of non-zero exit code
    - Bugfix: show-firewall shows publicly available ports

0.6.0 (2015-10-09)
    - Added: license, software distributions, SSL certificate requirements are added to roles
    - Added: roles for VZ storage, custbackup, wpedb, etc
    - Added: subcommand bulk_exec
    - Added: subcommand reportshistory
    - Added: subcommand list-servers
    - Added: support for _command inside dictionary parameter in role files
    - Added: is_admin check in roles to check privileges
    - Added: hw_id is stored in report
    - Added: check if ipv6 is disabled on linmn
    - Added: adjusted 90% of roles to conform with OSA 6.0 docs
    - Improved: check now understand bond-slave links
    - Improved: performance tweaks by postponing initialization or memoization
    - Improved: added defaults for firewall rules
    - Fixed: #113: disk req should check small partitions

0.5.0 (2015-04-17)
    - Added: documentation for role files
    - Added: remote_debug option in main.cfg
    - Added: reboot_timeout option in main.cfg
    - Added: guess requirement type as disk if it starts with / or C:, D:, etc
    - Added: option --all for subcommands firewall, show-firewall, reboot, reports
    - Added: reports subcommand can show reports for several servers
    - Added: subcommand agent to run agent console
    - Added: support for windows, with numerous (~50) windows roles. Without possibility to check firewall.
    - Added: updated requirements in roles
    - Added: ostype field in role file
    - Added: new requirement types: manual and networks
    - Added: password strength check based on zxcvbn library
    - Improvement: merged subcommands check and checkall
    - Improvement: command execution made via remote agent now
    - Improvement: logging reworked, now important messages are recorded
    - Improvement: su/sudo passwords are not passed in plain text in commandline anymore
    - Improvement: speed-up: application is refactored to postpone initialization of unneeded objects
    - Improvement: report does not show IPv6 addresses (can be found in raw report, if needed)
    - Improvement: report output is improved (ordering, coloured, indented, etc)
    - Fixed: disk requirement is false positive if disk size is not integer
    - Fixed: remove empty failures from reports
    - Fixed: handle keyerror exceptions in hwswa2.functions.read_servers()
    - Fixed: reboot check improved, it could hang in previous version
    - Fixed: command execution timeout option works now
    - Fixed: 'No such file or directory' while specifying logfile without a path in command line
    - Fixed: wrong mount point can be used while checking disk requirements
    - Fixed: firewall should not check only if both ends has dontcheck enabled
    - Fixed: some other bugs

0.4.0 (2014-11-22)
    - Added: requirements (ram, disk, cpu, etc) in role files
    - Added: subcommand show-firewall
    - Added: put and get subcommands allow to omit remotepath and localpath, respectively
    - Added: subcommand list-roles
    - Added: check for virtualization
    - Added: role aliases
    - Added: role linwdg
    - Added: adjusted firewall checks for role linmn
    - Added: updated firewall rules in role pbalinfe
    - Added: check for pba account in pbalinfe
    - Added: check noexec for /tmp
    - Added: requirements for roles: helb hewsl wsng ui paci_pcs paci_sn_pcs pvclin
    - Fixed: multiply roles are not printed in report
    - Fixed: NameError: global name 'se' is not defined
    - Fixed: name is missing in report
    - Fixed: firewall does not work if role is not lowercase in servers.yaml
    - Fixed: incorrect vlan names in report
    - Fixed: exception is not handled in _new_sshclient()
    - Fixed: check fails for server with empty role

0.3.0 (2014-06-29)
    - Removed: check_reboot option. Use reboot subcommand instead
    - Fixed: firewall does not fail if server is not accessible
    - Added: check and checkall use the same time string for report file names of all servers
    - Fixed: dontcheck option is ignored sometimes
    - Fixed: check subcommand: timeout exception is not handled
    - Removed: ability to use keyword _uses in <role>.yaml
    - Added: --raw option for report and lastreport subcommands
    - Added: firewall will convert ip.add.re.ss/net.add.re.ss/prefix to ip.add.re.ss/networkname
      automatically if networks.yaml is updated, no need to rerun checks
    - Fixed: long remote output can be truncated by exec subcommand
    - Added: firewall subcommand: progress is reported every 10 seconds (configurable value)
    - Added: check subcommand: progress is reported every 5 seconds (configurable value)
    - Added: firewall subcommand: will stop after 10 failures or 500 closed/filtered ports discovered
      (per servers pair, configurable values)
    - Added: cli option to specify network (-k, --network)
    - Added: firewall subcommand: added checks for access to hosts on Internet
    - Added: PACI roles
    - Added: firewall subcommand: pre-generated reports are not required now

0.2.1 (2014-06-25)
    - Added: subcommand aliases
    - Added: subcommand get
    - Fixed: firewall subcommand does not work at all
    - Fixed: timeout value is not used by firewall
    - Added: in firewall: ability to specify number of concurrently checked ports
      in configuration (main.cfg: section [firewall], max_open_sockets)
    - Added: firewall rules for roles linpps, sysbu, ui, branding
    - Fixed: log messages show 'logging.info()' instead of 'calling-module.calling-function()'
    - Fixed: other minor bugs

0.2 (2014-06-08)
    - Added: dontcheck option for servers
    - Added: subcommand reboot: ability to specify more than one server
    - Fixed: reportdiff: unresolvable variable servername is used in error message
    - Added: subcommand check: --with-reboot/--wo-reboot options
    - Added: thread name is shown in log
    - Fixed: subcommand check: not found role is handled properly
    - Fixed: subcommand check: replaced waiting for active threads with waiting for alive threads
    - Fixed: subcommands lastreport, reports, lastreport: server is checked for existence in configuration
    - Fixed: subcommand check: size for swap partitions is not gathered
    - Fixed: subcommand firewall: handle properly case if no udp messages received
    - Added: SSH jump host (gateway) support
    - Added: subcommand report
    - Added: subcommand check: new roles henas, linmndb, linpps
    - Added: subcommand check: updated firewall rules in helb, hewsl, lindns, pbalinbe, pbalinfe, pbalinos, wsng

0.1 (2014-05-24)
    Initial release.

