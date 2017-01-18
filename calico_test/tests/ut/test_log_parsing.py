# Copyright 2016 Tigera, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import copy
import functools
import json
import logging
import netaddr
import subprocess
import time
import unittest
import yaml
from nose_parameterized import parameterized
from multiprocessing.dummy import Pool

from tests.st.test_base import TestBase
from tests.st.enterprise.utils.ipfix_monitor import IpfixFlow, IpfixMonitor
from tests.st.utils.docker_host import DockerHost
from tests.st.utils.exceptions import CommandExecError
from tests.st.utils.utils import assert_network, assert_profile, \
    assert_number_endpoints, get_profile_name, ETCD_CA, ETCD_CERT, \
    ETCD_KEY, ETCD_HOSTNAME_SSL, ETCD_SCHEME, get_ip

_log = logging.getLogger(__name__)
_log.setLevel(logging.DEBUG)

POST_DOCKER_COMMANDS = []

if ETCD_SCHEME == "https":
    ADDITIONAL_DOCKER_OPTIONS = "--cluster-store=etcd://%s:2379 " \
                                "--cluster-store-opt kv.cacertfile=%s " \
                                "--cluster-store-opt kv.certfile=%s " \
                                "--cluster-store-opt kv.keyfile=%s " % \
                                (ETCD_HOSTNAME_SSL, ETCD_CA, ETCD_CERT,
                                 ETCD_KEY)
else:
    ADDITIONAL_DOCKER_OPTIONS = "--cluster-store=etcd://%s:2379 " % \
                                get_ip()

felix_logfile = "/var/log/calico/felix/current"
before_data = """2017-01-12 19:19:04.419 [INFO][87] ipip_mgr.go 75: Setting local IPv4 address on link. addr=192.168.151.0 link="tunl0"
2017-01-12 19:19:04.419 [INFO][87] int_dataplane.go 389: Received interface update msg=&intdataplane.ifaceUpdate{Name:"lo", State:"up"}
2017-01-12 19:19:04.419 [INFO][87] ipip_mgr.go 95: Removing old address addr=192.168.151.0 link="tunl0" oldAddr=192.168.151.0/32 tunl0
2017-01-12 19:19:04.416 [INFO][87] syncer.go 247: etcd watch thread started.
2017-01-12 19:19:04.419 [INFO][87] int_dataplane.go 378: Received update from calculation graph msg=config:<key:"ClusterGUID" value:"328b9309c07447db893cd7c155f2547b" > config:<key:"DefaultEndpointToHostAction" value:"RETURN" > config:<key:"EtcdAddr" value:"" > config:<key:"EtcdCaFile" value:"" > config:<key:"EtcdCertFile" value:"" > config:<key:"EtcdEndpoints" value:"http://10.96.232.136:6666" > config:<key:"EtcdKeyFile" value:"" > config:<key:"EtcdScheme" value:"" > config:<key:"FelixHostname" value:"tigera-lwr-kubetest-02" > config:<key:"InterfacePrefix" value:"cali" > config:<key:"IpInIpEnabled" value:"true" > config:<key:"IpInIpTunnelAddr" value:"192.168.151.0" > config:<key:"IpfixCollectorAddr" value:"192.168.67.75" > config:<key:"IpfixCollectorPort" value:"4739" > config:<key:"LogFilePath" value:"None" > config:<key:"LogSeverityFile" value:"None" > config:<key:"LogSeverityScreen" value:"info" > config:<key:"MetadataAddr" value:"None" > config:<key:"ReportingIntervalSecs" value:"0" > config:<key:"marker" value:"created" >
2017-01-12 19:19:04.419 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"lo", Addrs:set.mapSet{"127.0.0.1":set.empty{}, "::1":set.empty{}}}
2017-01-12 19:19:04.419 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"ens4", Addrs:set.mapSet{"fe80::4001:aff:fef0:30":set.empty{}, "10.240.0.48":set.empty{}}}
2017-01-12 19:19:04.419 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"calic50350b9abf", Addrs:set.mapSet{"fe80::a077:a7ff:fe1c:8436":set.empty{}}}
2017-01-12 19:19:04.420 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"calie9054722202", Addrs:set.mapSet{"fe80::d046:64ff:fe86:c21":set.empty{}}}
2017-01-12 19:19:04.420 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"cali076a4d2f51a", Addrs:set.mapSet{"fe80::2c6e:f7ff:fe0d:2b86":set.empty{}}}
2017-01-12 19:19:04.420 [INFO][87] syncer.go 261: Polled etcd for initial watch index. index=0x3f85
2017-01-12 19:19:04.420 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"cali76b1299437f", Addrs:set.mapSet{"fe80::30f3:a9ff:fe6e:2d22":set.empty{}}}
2017-01-12 19:19:04.420 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"cali477d4934e36", Addrs:set.mapSet{"fe80::70d6:51ff:feca:1b41":set.empty{}}}
2017-01-12 19:19:04.419 [INFO][87] iface_monitor.go 120: Netlink address update. addr="192.168.151.0" exists=false ifIndex=14
2017-01-12 19:19:04.421 [INFO][87] int_dataplane.go 389: Received interface update msg=&intdataplane.ifaceUpdate{Name:"ens4", State:"up"}
2017-01-12 19:19:04.421 [INFO][87] int_dataplane.go 288: Linux interface addrs changed. addrs=set.mapSet{} ifaceName="tunl0"
2017-01-12 19:19:04.420 [INFO][87] syncer.go 461: Watcher out-of-sync, starting to track deletions
2017-01-12 19:19:04.421 [INFO][87] int_dataplane.go 389: Received interface update msg=&intdataplane.ifaceUpdate{Name:"calic50350b9abf", State:"up"}
2017-01-12 19:19:04.421 [INFO][87] ipip_mgr.go 103: Address wasn't present, adding it. addr=192.168.151.0 link="tunl0"
2017-01-12 19:19:04.421 [INFO][87] int_dataplane.go 398: Received interface addresses update msg=&intdataplane.ifaceAddrsUpdate{Name:"cali3b05e50a7e8", Addrs:set.mapSet{"fe80::94d3:2bff:fe26:e4fe":set.empty{}}}
2017-01-12 19:19:04.421 [INFO][87] iface_monitor.go 120: Netlink address update. addr="192.168.151.0" exists=true ifIndex=14
2017-01-12 19:19:04.421 [INFO][87] syncer.go 500: Watcher is out-of-sync but no snapshot in progress, starting one.
"""

def parallel_host_setup(num_hosts):
    makehost = functools.partial(DockerHost,
                                 additional_docker_options=ADDITIONAL_DOCKER_OPTIONS,
                                 post_docker_commands=POST_DOCKER_COMMANDS,
                                 start_calico=False)
    hostnames = []
    for i in range(num_hosts):
        hostnames.append("host%s" % i)
    pool = Pool(num_hosts)
    hosts = pool.map(makehost, hostnames)
    pool.close()
    pool.join()
    return hosts


def wipe_etcd():
    _log.debug("Wiping etcd")
    # Delete /calico if it exists. This ensures each test has an empty data
    # store at start of day.
    curl_etcd(get_ip(), "calico", options=["-XDELETE"])

    # Disable Usage Reporting to usage.projectcalico.org
    # We want to avoid polluting analytics data with unit test noise
    curl_etcd(get_ip(),
              "calico/v1/config/UsageReportingEnabled",
              options=["-XPUT -d value=False"])
    curl_etcd(get_ip(),
              "calico/v1/config/LogSeverityScreen",
              options=["-XPUT -d value=debug"])


def curl_etcd(ip, path, options=None, recursive=True):
    """
    Perform a curl to etcd, returning JSON decoded response.
    :param ip: IP address of etcd server
    :param path:  The key path to query
    :param options:  Additional options to include in the curl
    :param recursive:  Whether we want recursive query or not
    :return:  The JSON decoded response.
    """
    if options is None:
        options = []
    if ETCD_SCHEME == "https":
        # Etcd is running with SSL/TLS, require key/certificates
        command = "curl --cacert %s --cert %s --key %s " \
                  "-sL https://%s:2379/v2/keys/%s?recursive=%s %s" % \
                  (ETCD_CA, ETCD_CERT, ETCD_KEY, ETCD_HOSTNAME_SSL, path,
                   str(recursive).lower(), " ".join(options))
    else:
        command = "curl -sL http://%s:2379/v2/keys/%s?recursive=%s %s" % \
                  (ip, path, str(recursive).lower(), " ".join(options))
    _log.debug("Running: %s", command)
    rc = subprocess.check_output(command, shell=True)
    return json.loads(rc.strip())


class MultiHostIpfix(TestBase):
    @classmethod
    def setUpClass(cls):
        cls.log_banner("TEST SET UP STARTING: %s", cls.__name__)

        # Wipe etcd before setting up a new test rig for this class.
        wipe_etcd()

        cls.hosts = []
        cls.hosts.append(DockerHost("host1",
                                    additional_docker_options=ADDITIONAL_DOCKER_OPTIONS,
                                    post_docker_commands=POST_DOCKER_COMMANDS,
                                    start_calico=False))
        cls.hosts.append(DockerHost("host2",
                                    additional_docker_options=ADDITIONAL_DOCKER_OPTIONS,
                                    post_docker_commands=POST_DOCKER_COMMANDS,
                                    start_calico=False))
        cls.log_analyzers = []
        for host in cls.hosts:
            host.execute("mkdir -p /var/log/calico/felix/")
            host.writefile(felix_logfile, before_data)
        cls.expect_errors = False

    @classmethod
    def tearDownClass(cls):
        # Tidy up
        for host in cls.hosts:
            host.cleanup()
            del host

    def setUp(self):
        # This method is REQUIRED or else the TestBase setUp() method will wipe etcd before
        # every test.
        self.log_banner("starting %s", self._testMethodName)

        _log.debug("Setup Log Analyzers")
        for host in self.hosts:
            _log.info("Attaching LA for host %s", host.name)
            self.attach_log_analyzer(host)

    def tearDown(self):
        # import pdb; pdb.set_trace()
        _log.info("Checking logs for exceptions")
        failed = False
        if self.expect_errors:
            try:
                self.check_logs_for_exceptions()
                _log.debug("No exceptions found, setting failed=True")
                failed = True
            except AssertionError:
                _log.debug("Hit the error we expected.  Good.")
            _log.debug("Failed = %s", failed)
            assert not failed, "Did not hit error! Fail."
        else:
            self.check_logs_for_exceptions()

        while len(self.log_analyzers) > 0:
            la = self.log_analyzers.pop()
            del la

    def test_no_logs(self):
        """
        Tests that the scenario with no new logs works OK
        """
        _log.debug("\n")
        self.expect_errors = False

    @parameterized.expand([
        ("ERROR",
         "2017-01-12 19:19:05.421 [ERROR][87] syncer.go 500: Watcher is out-of-sync.",
         True),
        ("INFO",
         "2017-01-12 19:19:05.421 [INFO][87] syncer.go 500: Watcher is out-of-sync.",
         False),
    ])
    def test_newlog(self, name, log, expect_error):
        """
        Tests that the scenario with a new log works OK
        """
        self.__name__ = name
        _log.debug("\n")
        self.expect_errors = expect_error
        self.hosts[0].execute("echo %s >> %s" % (log, felix_logfile))


class IpNotFound(Exception):
    pass
