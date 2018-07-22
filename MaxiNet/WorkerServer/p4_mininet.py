# Copyright 2013-present Barefoot Networks, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from mininet.net import Mininet
from mininet.node import Switch, Host
from mininet.log import setLogLevel, info, error, debug
from mininet.moduledeps import pathCheck
from sys import exit
import os
import tempfile
import socket
from time import sleep

from netstat import check_listening_on_port
# Added by RB
from parse_exp_cfg import *
import pdb # Added by RB

SWITCH_START_TIMEOUT = 10 # seconds

class P4Host(Host):

    def config(self, **params):
        r = super(Host, self).config(**params)

        self.defaultIntf().rename("eth0")

        for off in ["rx", "tx", "sg"]:
            cmd = "/sbin/ethtool --offload eth0 %s off" % off
            self.cmd(cmd)

        # disable IPv6
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        return r

    def describe(self):
        print "**********"
        print self.name
        print "default interface: %s\t%s\t%s" %(
            self.defaultIntf().name,
            self.defaultIntf().IP(),
            self.defaultIntf().MAC()
        )
        print "**********"

class P4Switch(Switch):
    """P4 virtual switch"""
    device_id = 0

    def __init__(self, name, sw_path = None, json_path = None,
                 thrift_port = None,
                 pcap_dump = False,
                 log_console = False,
                 verbose = False,
                 device_id = None,
                 enable_debugger = False,
                 **kwargs):
        Switch.__init__(self, name, **kwargs)
        assert(sw_path)
        assert(json_path)
        # make sure that the provided sw_path is valid
        pathCheck(sw_path)
        # make sure that the provided JSON file exists
        if not os.path.isfile(json_path):
            error("Invalid JSON file.\n")
            exit(1)
        self.sw_path = sw_path
        self.json_path = json_path
        self.verbose = verbose
        logfile = "/tmp/p4s.{}.log".format(self.name)
        self.output = open(logfile, 'w')
        self.thrift_port = thrift_port
        if check_listening_on_port(self.thrift_port):
            error('%s cannot bind port %d because it is bound by another process\n' % (self.name, self.grpc_port))
            exit(1)
        self.pcap_dump = pcap_dump
        self.enable_debugger = enable_debugger
        self.log_console = log_console
        if device_id is not None:
            self.device_id = device_id
            P4Switch.device_id = max(P4Switch.device_id, device_id)
        else:
            self.device_id = P4Switch.device_id
            P4Switch.device_id += 1
        self.nanomsg = "ipc:///tmp/bm-{}-log.ipc".format(self.device_id)

        if "operating_mode" in kwargs :
            self.operating_mode = kwargs["operating_mode"]
        else :
            self.operating_mode = "NORMAL"

        if "rel_cpu_speed" in kwargs :
            self.rel_cpu_speed = kwargs["rel_cpu_speed"]
        else:
            self.rel_cpu_speed = 1.0

        if "n_round_insns" in kwargs :
            self.n_round_insns = kwargs["n_round_insns"]
        else:
            self.n_round_insns = 1000000

        self.tracer_path = "/usr/bin/tracer"
        self.switch_pid = None

    @classmethod
    def setup(cls):
        pass

    def check_switch_started(self, pid):
        """While the process is running (pid exists), we check if the Thrift
        server has been started. If the Thrift server is ready, we assume that
        the switch was started successfully. This is only reliable if the Thrift
        server is started at the end of the init process"""
        while True:
            if not os.path.exists(os.path.join("/proc", str(pid))):
                return False
            if check_listening_on_port(self.thrift_port):
                return True
            sleep(0.5)

    def start(self, controllers):
        "Start up a new P4 switch"
        info("Starting P4 switch {}.\n".format(self.name))
        args = [self.sw_path]
        for port, intf in self.intfs.items():
            # print "Mininet switch start ..."
            # print "switch name ...", self.name
            # print "Port ...", port
            # print "Intf ...", intf
            if not intf.IP():
                # print "Args Extend ..."
                # print "Port ...", str(port)
                # print "Intf Name ...", intf.name 
                args.extend(['-i', str(port) + "@" + intf.name])
        #if self.pcap_dump:
        #    my_pcap_dir = get_exp_pcap_dir()
        #    pcap_arg = "--pcap="+my_pcap_dir
        #    args.append(pcap_arg)  # Modified by RB
            # args.append("--pcap")
            # args.append("--useFiles")
        if self.thrift_port:
            args.extend(['--thrift-port', str(self.thrift_port)])
        #if self.nanomsg:
        #    args.extend(['--nanolog', self.nanomsg])
        args.extend(['--device-id', str(self.device_id)])
        P4Switch.device_id += 1
        
        if self.enable_debugger:
            args.append("--debugger")
        if self.log_console:
            #args.append("--log-console")
            sw_log_file = "/tmp/{}.log".format(self.name)
            args.append("--log-file " + sw_log_file)
            args.append("--log-flush")

        args.append(self.json_path)
        logfile = "/tmp/p4s.{}.log".format(self.name)
        info(' '.join(args) + "\n")

        if self.operating_mode == "NORMAL" :
            pid = None
            with tempfile.NamedTemporaryFile() as f:
                # self.cmd(' '.join(args) + ' > /dev/null 2>&1 &')
                self.cmd(' '.join(args) + ' > ' + logfile + ' 2>&1 & echo $! >> ' + f.name)
                pid = int(f.read())
                self.switch_pid = pid
        else :
            tracer_args = [self.tracer_path]
            tracer_args.extend(["-i", str(self.device_id)])
            tracer_args.extend(["-r", str(self.rel_cpu_speed)])
            tracer_args.extend(["-n", str(self.n_round_insns)])
            #tracer_args.extend(["-c", "\"" + ' '.join(args) + ' > ' + logfile +"\""])
            tracer_args.extend(["-c","\"" + ' '.join(args) + "\""])
            tracer_args.append("-s")
            with tempfile.NamedTemporaryFile() as f:
                tracer_cmd = ' '.join(tracer_args) + ' > ' + logfile + ' 2>&1 & echo $! >> ' + f.name
                print "Switch : %s Tracer cmd : %s " %(self.name,tracer_cmd)
                self.cmd(tracer_cmd)
                #self.cmd(' '.join(tracer_args) + ' & echo $! >> ' + f.name)
                pid = int(f.read())
                self.switch_pid = pid

        debug("P4 switch {} PID is {}.\n".format(self.name, self.switch_pid))
        #if not self.check_switch_started(self.switch_pid):
        #    error("P4 switch {} did not start correctly.\n".format(self.name))
        #    exit(1)
        info("P4 switch {} has been started.\n".format(self.name))

    def stop(self):
        "Terminate P4 switch."
        self.output.flush()
        self.cmd('kill %' + self.sw_path)
        if self.operating_mode == "NORMAL" :
            self.cmd('wait')
        self.deleteIntfs()

    def attach(self, intf):
        "Connect a data port"
        assert(0)

    def detach(self, intf):
        "Disconnect a data port"
        assert(0)