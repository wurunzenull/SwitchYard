#!/usr/bin/env python

from switchyard.lib.userlib import *
from copy import deepcopy


def get_raw_pkt(pkt, xlen):
    pkt = deepcopy(pkt)
    i = pkt.get_header_index(Ethernet)
    if i >= 0:
        del pkt[i]
    b = pkt.to_bytes()[:xlen]
    return b


def mk_arpreq(hwsrc, ipsrc, ipdst):
    arp_req = Arp()
    arp_req.operation = ArpOperation.Request
    arp_req.senderprotoaddr = IPAddr(ipsrc)
    arp_req.targetprotoaddr = IPAddr(ipdst)
    arp_req.senderhwaddr = EthAddr(hwsrc)
    arp_req.targethwaddr = EthAddr("ff:ff:ff:ff:ff:ff")
    ether = Ethernet()
    ether.src = EthAddr(hwsrc)
    ether.dst = EthAddr("ff:ff:ff:ff:ff:ff")
    ether.ethertype = EtherType.ARP
    return ether + arp_req


def mk_arpresp(arpreqpkt, hwsrc, arphwsrc=None, arphwdst=None):
    if arphwsrc is None:
        arphwsrc = hwsrc
    if arphwdst is None:
        arphwdst = arpreqpkt.get_header(Arp).senderhwaddr
    ether = Ethernet()
    ether.src = EthAddr(hwsrc)
    ether.dst = arpreqpkt.get_header(Arp).senderhwaddr
    ether.ethertype = EtherType.ARP
    arp_reply = Arp()
    arp_reply.operation = ArpOperation.Reply
    arp_reply.senderprotoaddr = IPAddr(
        arpreqpkt.get_header(Arp).targetprotoaddr)
    arp_reply.targetprotoaddr = IPAddr(
        arpreqpkt.get_header(Arp).senderprotoaddr)
    arp_reply.senderhwaddr = EthAddr(arphwsrc)
    arp_reply.targethwaddr = EthAddr(arphwdst)
    return ether + arp_reply


def mk_ping(hwsrc, hwdst, ipsrc, ipdst, reply=False, ttl=64, payload=''):
    ether = Ethernet()
    ether.src = EthAddr(hwsrc)
    ether.dst = EthAddr(hwdst)
    ether.ethertype = EtherType.IP
    ippkt = IPv4()
    ippkt.src = IPAddr(ipsrc)
    ippkt.dst = IPAddr(ipdst)
    ippkt.protocol = IPProtocol.ICMP
    ippkt.ttl = ttl
    ippkt.ipid = 0
    if reply:
        icmppkt = ICMP()
        icmppkt.icmptype = ICMPType.EchoReply
        icmppkt.icmpcode = ICMPCodeEchoReply.EchoReply
    else:
        icmppkt = ICMP()
        icmppkt.icmptype = ICMPType.EchoRequest
        icmppkt.icmpcode = ICMPCodeEchoRequest.EchoRequest
    icmppkt.icmpdata.sequence = 42
    icmppkt.icmpdata.data = payload
    return ether + ippkt + icmppkt


def mk_icmperr(hwsrc,
               hwdst,
               ipsrc,
               ipdst,
               xtype,
               xcode=0,
               origpkt=None,
               ttl=64):
    ether = Ethernet()
    ether.src = EthAddr(hwsrc)
    ether.dst = EthAddr(hwdst)
    ether.ethertype = EtherType.IP
    ippkt = IPv4()
    ippkt.src = IPAddr(ipsrc)
    ippkt.dst = IPAddr(ipdst)
    ippkt.protocol = IPProtocol.ICMP
    ippkt.ttl = ttl
    ippkt.ipid = 0
    icmppkt = ICMP()
    icmppkt.icmptype = xtype
    icmppkt.icmpcode = xcode
    if origpkt is not None:
        xpkt = deepcopy(origpkt)
        i = xpkt.get_header_index(Ethernet)
        if i >= 0:
            del xpkt[i]
        icmppkt.icmpdata.data = xpkt.to_bytes()[:28]
        icmppkt.icmpdata.origdgramlen = len(xpkt)

    return ether + ippkt + icmppkt


def mk_udp(hwsrc,
           hwdst,
           ipsrc,
           ipdst,
           ttl=64,
           srcport=10000,
           dstport=10000,
           payload=''):
    ether = Ethernet()
    ether.src = EthAddr(hwsrc)
    ether.dst = EthAddr(hwdst)
    ether.ethertype = EtherType.IP
    ippkt = IPv4()
    ippkt.src = IPAddr(ipsrc)
    ippkt.dst = IPAddr(ipdst)
    ippkt.protocol = IPProtocol.UDP
    ippkt.ttl = ttl
    ippkt.ipid = 0
    udppkt = UDP()
    udppkt.src = srcport
    udppkt.dst = dstport
    return ether + ippkt + udppkt + RawPacketContents(payload)


def icmp_tests():
    s = TestScenario("IP forwarding and ARP requester tests")
    s.add_interface('router-eth0', '10:00:00:00:00:01', '192.168.1.1',
                    '255.255.255.0')
    s.add_interface('router-eth1', '10:00:00:00:00:02', '10.10.0.1',
                    '255.255.0.0')
    s.add_interface('router-eth2', '10:00:00:00:00:03', '172.16.42.1',
                    '255.255.255.252')
    s.add_file(
        'forwarding_table.txt',
        '''172.16.0.0 255.255.0.0 192.168.1.2 router-eth0
172.16.128.0 255.255.192.0 10.10.0.254 router-eth1
172.16.64.0 255.255.192.0 10.10.1.254 router-eth1
10.100.0.0 255.255.0.0 172.16.42.2 router-eth2
''')

    nottinyttl = '''lambda pkt: pkt.get_header(IPv4).ttl >= 8'''
    icmp_reply_data='''lambda pkt: pkt.get_header(ICMP).icmpdata.data==b'hello icmp request' '''
    icmp_error_data = '''lambda pkt: pkt.get_header(ICMP).icmpdata.data[:8]==b'E' '''
    # Your tests here
    # case0  172.16.128.1 ping 10.10.0.1 (eh1 interface)
    icmp_request = mk_ping('ff:ff:ff:ff:ff:ff', '10:00:00:00:00:01',
                           '172.16.128.1', '172.16.42.1', False, 10,
                           'hello icmp request')
    s.expect(
        PacketInputEvent('router-eth0', icmp_request, display=ICMP),
        "send a ping request to 172.16.42.1(interface eth2) arrive on router-eth0"
    )
    arp_request = mk_arpreq('10:00:00:00:00:02', '10.10.0.1', '10.10.0.254')
    s.expect(PacketOutputEvent('router-eth1', arp_request, display=Arp),
             "send Arp request for 10.10.1.254 leave out on router-eth1")
    arp_reply = mk_arpresp(arp_request, '20:00:00:00:00:00')
    s.expect(
        PacketInputEvent('router-eth1', arp_reply, display=Arp),
        "Router receive an ARP response for 10.10.0.254 on router-eth1 and prepare send ping reply to 10.10.1.254"
    )
    icmp_reply = mk_ping('10:00:00:00:00:02',
                         '20:00:00:00:00:00',
                         '172.16.42.1',
                         '172.16.128.1',
                         reply=True,
                         )
    s.expect(PacketOutputEvent('router-eth1', icmp_reply, exact=False,predicates=(nottinyttl,icmp_reply_data),display=ICMP),
             "router eth1 send the icmp reply to 10.10.0.254")

    #case1 ping router but the
    icmp_request = mk_ping('ff:ff:ff:ff:ff:ff', '10:00:00:00:00:01',
                           '172.16.128.1', '172.16.42.1', True, 10,
                           '123')
    s.expect(
        PacketInputEvent('router-eth0', icmp_request, display=ICMP),
        "send a ping reply to 172.16.42.1(interface eth2) arrive on router-eth0"
    )

    icmp_error = mk_icmperr('10:00:00:00:00:02', '20:00:00:00:00:00',
                            '10.10.0.1', '172.16.128.1',
                            ICMPType.DestinationUnreachable,
                            ICMPCodeDestinationUnreachable.PortUnreachable,icmp_request)
    # print
    s.expect(PacketOutputEvent('router-eth1', icmp_error, exact=False,predicates=(nottinyttl,icmp_error_data),display=ICMP),
             "router eth1 send the icmp error packet to 10.10.0.254")
    return s


scenario = icmp_tests()
