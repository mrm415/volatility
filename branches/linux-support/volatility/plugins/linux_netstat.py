# Volatility
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details. 
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

"""
@author:       Andrew Case
@license:      GNU General Public License 2.0 or later
@contact:      atcuno@gmail.com
@organization: Digital Forensics Solutions
"""

import volatility.obj as obj

import linux_common, linux_flags
import volatility.plugins.linux_list_open_files as lof

import socket

class linux_netstat(lof.linux_list_open_files):

    ''' lists open files '''

    def calculate(self):
        openfiles = lof.linux_list_open_files.calculate(self)

        for (task, filp, _i, _addr_space) in openfiles:
            # its a socket!
            if filp.f_op == self.smap["socket_file_ops"]:

                iaddr = filp.f_path.dentry.d_inode
                skt = self.SOCKET_I(iaddr)
                inet_sock = obj.Object("inet_sock", offset = skt.sk, vm = self.addr_space)

                yield task, inet_sock

    def render_text(self, outfd, data):

        for task, inet_sock in data:

            (daddr, saddr, dport, sport) = self.format_ip_port(inet_sock)
            proto = self.get_proto_str(inet_sock)
            state = self.get_state_str(inet_sock) if proto == "TCP" else ""

            if proto in ("TCP", "UDP"):
                outfd.write("{0:8s} {1}:{2:<5} {3}:{4:<5} {5:s} {6:>17s}/{7:<5d}\n".format(proto, saddr, sport, daddr, dport, state, task.comm, task.pid))

    # this is here b/c python is retarded and its inet_ntoa can't handle integers...
    def ip2str(self, ip):

        a = ip & 0xff
        b = (ip >> 8) & 0xff
        c = (ip >> 16) & 0xff
        d = (ip >> 24) & 0xff

        return "%d.%d.%d.%d" % (a, b, c, d)

    def format_ip_port(self, inet_sock):

        daddr = self.ip2str(inet_sock.daddr.v())
        saddr = self.ip2str(inet_sock.rcv_saddr.v())
        dport = socket.htons(inet_sock.dport)
        sport = socket.htons(inet_sock.sport)

        return (daddr, saddr, dport, sport)

    def get_state_str(self, inet_sock):

        state = inet_sock.sk.sk_common.skc_state

        return linux_flags.tcp_states[state]

    def get_proto_str(self, inet_sock):

        proto = inet_sock.sk.sk_protocol

        # VTYPE BUG - remove when vtypes handle bit fields
        proto = ((proto.v() & 0xff00) >> 8) & 0xff

        if proto in linux_flags.protocol_strings:
            ret = linux_flags.protocol_strings[proto]
        else:
            ret = "UNKNOWN"

        return ret

    # has to get the struct socket given an inode (see SOCKET_I in sock.h)
    def SOCKET_I(self, inode):
        backsize = linux_common.sizeofstruct("socket", self.profile)
        addr = inode - backsize

        return obj.Object('socket', offset = addr, vm = self.addr_space)
