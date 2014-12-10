import sys
import os
import os.path
import unittest
import copy
import time
from io import StringIO
from contextlib import ContextDecorator
import re

from switchyard.switchy_test import run_tests, main_test
from switchyard.lib.common import ScenarioFailure, setup_logging
from switchyard.lib.testing import Scenario,PacketInputEvent,PacketOutputEvent,compile_scenario,uncompile_scenario,get_test_scenario_from_file
from switchyard.lib.packet import *
from switchyard.lib.address import *

from contextlib import ContextDecorator

class redirectio(ContextDecorator):
    def __init__(self):
        self.iobuf = StringIO()

    def __enter__(self):
        self.stdout = getattr(sys, 'stdout')
        self.stderr = getattr(sys, 'stderr')
        setattr(sys, 'stdout', self.iobuf)
        setattr(sys, 'stderr', self.iobuf)
        return self

    def __exit__(self, *exc):
        setattr(sys, 'stdout', self.stdout)
        setattr(sys, 'stderr', self.stderr)
        return False

    @property 
    def contents(self):
        return self.iobuf.getvalue()


class TestFrameworkTests(unittest.TestCase):
    CONTENTS1 = '''
from switchyard.lib.testing import *
from switchyard.lib.address import *
from switchyard.lib.packet import *

s = Scenario("ARP request")
s.add_interface('router-eth0', '40:00:00:00:00:00', '192.168.1.1', '255.255.255.0')
s.add_interface('router-eth1', '40:00:00:00:00:01', '192.168.100.1', '255.255.255.0')
s.add_interface('router-eth2', '40:00:00:00:00:02', '10.0.1.2', '255.255.255.0')
s.add_interface('router-eth3', '40:00:00:00:00:03', '10.1.1.2', '255.255.255.0')

# arp coming from client
arpreq = create_ip_arp_request("30:00:00:00:00:01", "10.1.1.1", "10.1.1.2")
arprep = create_ip_arp_reply("40:00:00:00:00:03", "30:00:00:00:00:01", "10.1.1.2", "10.1.1.1")

s.expect(PacketInputEvent("router-eth3", arpreq), "Incoming ARP request")
s.expect(PacketOutputEvent("router-eth3", arprep), "Outgoing ARP reply (1)")
s.expect(PacketInputTimeoutEvent(3), "Timeout on recv")
s.expect(PacketOutputEvent("router-eth3", arprep), "Outgoing ARP reply (2)")

scenario = s
'''

    USERCODE1 = '''
def main(obj):
    pass
'''

    USERCODE2 = '''
def main(obj):
    obj.recv_packet()
'''

    USERCODE3 = '''
def main(obj):
    obj.recv_packet()
    obj.recv_packet()
'''

    USERCODE4 = '''
from time import sleep
def main(obj):
    obj.recv_packet()
    sleep(30)
    obj.recv_packet()
'''

    USERCODE5 = '''
from switchyard.lib.packet import *
from switchyard.lib.address import *
from switchyard.lib.testing import *

def main(obj):
    obj.recv_packet()
    pkt = create_ip_arp_reply("40:00:00:00:00:03", "30:00:00:00:00:01", "10.1.1.2", "10.1.1.1")
    obj.send_packet('router-eth3', pkt)
    try:
        obj.recv_packet()
    except NoPackets:
        pass

    obj.send_packet('router-eth3', pkt)
'''

    USERCODE6 = '''
from switchyard.lib.packet import *
from switchyard.lib.address import *
from switchyard.lib.testing import *

def main(obj):
    obj.recv_packet()
    pkt = create_ip_arp_reply("40:00:00:00:00:03", "30:00:00:00:00:01", "10.1.1.2", "10.1.1.1")
    obj.send_packet('router-eth3', pkt)
    try:
        obj.recv_packet()
    except NoPackets:
        pass

    obj.send_packet('router-eth3', pkt)
    obj.recv_packet()
'''

    USERCODE7 = '''
from switchyard.lib.packet import *
from switchyard.lib.address import *
from switchyard.lib.testing import *

def main(obj):
    obj.recv_packet()
    pkt = create_ip_arp_reply("40:00:00:00:00:03", "30:00:00:00:00:01", "10.1.1.2", "10.1.1.1")
    obj.send_packet('router-eth3', pkt)
    try:
        obj.recv_packet()
    except NoPackets:
        pass

    obj.send_packet('router-eth3', pkt)
    obj.send_packet('router-eth3', pkt)
'''

    USERCODE8 = '''
def main(obj):
    1/0 # epic fail
'''

    USERCODE9 = '''
from switchyard.lib.packet import *
from switchyard.lib.address import *
from switchyard.lib.testing import *

def main(obj):
    obj.recv_packet()
    pkt = create_ip_arp_reply("40:00:00:00:00:AB", "30:00:00:00:00:CD", "10.1.1.2", "10.1.1.1")
    obj.send_packet('router-eth2', pkt)
'''

    USERCODE10 = '''
from switchyard.lib.packet import *
from switchyard.lib.address import *
from switchyard.lib.testing import *

def main(obj):
    obj.recv_packet()
    pkt = create_ip_arp_reply("40:00:00:00:00:AB", "30:00:00:00:00:CD", "10.1.1.2", "10.1.1.1")
    obj.send_packet('router-eth3', pkt)
'''

    def setUp(self):
        self.writeFile('stest.py', TestFrameworkTests.CONTENTS1)
        self.writeFile('ucode1.py', TestFrameworkTests.USERCODE1)
        self.writeFile('ucode2.py', TestFrameworkTests.USERCODE2)
        self.writeFile('ucode3.py', TestFrameworkTests.USERCODE3)
        self.writeFile('ucode4.py', TestFrameworkTests.USERCODE4)
        self.writeFile('ucode5.py', TestFrameworkTests.USERCODE5)
        self.writeFile('ucode6.py', TestFrameworkTests.USERCODE6)
        self.writeFile('ucode7.py', TestFrameworkTests.USERCODE7)
        self.writeFile('ucode8.py', TestFrameworkTests.USERCODE8)
        self.writeFile('ucode9.py', TestFrameworkTests.USERCODE9)
        self.writeFile('ucode10.py', TestFrameworkTests.USERCODE10)
        sys.path.append('.')
        sys.path.append(os.getcwd())
        sys.path.append(os.path.join(os.getcwd(),'tests'))
        sys.path.append(os.path.join(os.getcwd(),'..'))
    
    def tearDown(self):
        self.removeFile('stest')
        self.removeFile('ucode1')
        self.removeFile('ucode2')
        self.removeFile('ucode3')
        self.removeFile('ucode4')
        self.removeFile('ucode5')
        self.removeFile('ucode6')
        self.removeFile('ucode7')
        self.removeFile('ucode8')
        self.removeFile('ucode9')
        self.removeFile('ucode10')

    def writeFile(self, name, contents):
        outfile = open(name, 'w')
        outfile.write(contents)
        outfile.close()

    def removeFile(self, name):
        try:
            os.unlink(name + '.py')
        except:
            pass
        try:
            os.unlink(name + '.pyc')
        except:
            pass
        try:
            os.unlink(name + '.switchy')
        except:
            pass

    def testDryRun(self):
        with self.assertLogs(level='INFO') as cm:
            main_test(False, ['stest'], 'ucode1.py', True, True, False)
        self.assertIn('Imported your code successfully', cm.output[0])
        with self.assertLogs(level='INFO') as cm:
            main_test(False, ['stest'], 'ucode1', True, True, False)
        self.assertIn('Imported your code successfully', cm.output[0])

    def testNoScenario(self):
        with self.assertLogs(level='ERROR') as cm:
            main_test(False, [], 'ucode1', True, True, False)
        self.assertIn('no scenarios', cm.output[0])

    def testCompileOutput(self):
        with self.assertLogs(level='INFO') as cm:
            main_test(True, ['stest'], 'ucode1', True, True, False)
        self.assertIn('Compiling', cm.output[0])
        self.assertIsNotNone(os.stat('stest.switchy'))

    def testEmptyUserProgram(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode1', False, True, False)
        self.assertIn('0 passed, 1 failed, 3 pending', xio.contents)
        self.assertNotIn('All tests passed', xio.contents)

    def testCleanScenario(self):
        scen = get_test_scenario_from_file('stest')
        self.assertFalse(scen.done())
        self.assertEqual(len(scen.pending_events), 4)
        self.assertListEqual(scen.completed_events, [])

    def testOneRecvCall(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode2', False, True, False)
        self.assertIn('1 passed, 1 failed, 2 pending', xio.contents)
        self.assertRegex(xio.contents, re.compile('Passed:\s*1\s*Incoming ARP request', re.M))
        self.assertRegex(xio.contents, re.compile('Failed:\s*Outgoing ARP reply',re.M))

    def testTwoRecvCalls(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode3', False, True, False)
        self.assertIn('1 passed, 1 failed, 2 pending', xio.contents)
        self.assertRegex(xio.contents, re.compile('Passed:\s*1\s*Incoming ARP request', re.M))
        self.assertRegex(xio.contents, re.compile('Failed:\s*Outgoing ARP reply',re.M))
        self.assertRegex(xio.contents, re.compile('recv_packet\s+called,\s+but\s+I\s+was\s+expecting\s+send_packet', re.M))

    def testDelayedSent(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode4', False, True, False)
        self.assertIn('1 passed, 1 failed, 2 pending', xio.contents)
        self.assertRegex(xio.contents, re.compile('Passed:\s*1\s*Incoming ARP request', re.M))
        self.assertRegex(xio.contents, re.compile('Failed:\s*Outgoing ARP reply',re.M))
        self.assertRegex(xio.contents, re.compile('1\s+Timeout on recv', re.M))

    def testScenarioTimeoutHandledCorrectly(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode5', False, True, False) 
        self.assertIn('4 passed, 0 failed, 0 pending', xio.contents)
        self.assertIn('All tests passed', xio.contents)

    def testShutdownSignal(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode6', False, True, False) 
        self.assertIn('4 passed, 0 failed, 0 pending', xio.contents)
        self.assertIn('All tests passed', xio.contents)

    def testTooManySends(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode7', False, True, False) 
        self.assertIn('4 passed, 0 failed, 0 pending', xio.contents)
        self.assertRegex(xio.contents, 
            re.compile('Your\s+code\s+didn\'t\s+crash,\s+but\s+something\s+unexpected\s+happened.', re.M))
        self.assertNotIn('All tests passed', xio.contents)

    def testEpicFail(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode8', False, True, False) 
        self.assertNotIn('All tests passed', xio.contents)
        self.assertIn('0 passed, 1 failed, 3 pending', xio.contents)
        self.assertRegex(xio.contents, 
            re.compile('Your\s+code\s+crashed', re.M))

    def testDeviceMatchFail(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode9', False, True, False) 
        self.assertIn('1 passed, 1 failed, 2 pending', xio.contents)
        self.assertRegex(xio.contents, 
            re.compile('output\s+on\s+device\s+router-eth2\s+unexpected', re.M))

    def testPacketMatchFail(self):
        with redirectio() as xio:
            with self.assertLogs(level='INFO') as cm:
                main_test(False, ['stest'], 'ucode10', False, True, False) 
        self.assertIn('1 passed, 1 failed, 2 pending', xio.contents)
        self.assertRegex(xio.contents, 
            re.compile('an\s+exact\s+match\s+failed', re.M | re.I))

if __name__ == '__main__':
    setup_logging(False)
    unittest.main() 