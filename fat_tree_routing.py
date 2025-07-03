from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4
import struct

class FatTreeRouting(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FatTreeRouting, self).__init__(*args, **kwargs)
        self.k = 4  # 可改为从配置读取
        self.hosts_per_edge = self.k // 2

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        dpid = datapath.id
        dpid_str = format(dpid, '016x')

        role, detail = self.identify_switch(dpid)
        self.logger.info(f"Switch connected: DPID={dpid_str}, Role={role}, Detail={detail}")

        # 默认丢包规则
        match = datapath.ofproto_parser.OFPMatch()
        self.add_flow(datapath, 0, match, [])

        if role == 'edge':
            self.install_edge_flows(datapath, *detail)
        elif role == 'agg':
            self.install_agg_flows(datapath, *detail)
        elif role == 'core':
            self.install_core_flows(datapath, *detail)

    def identify_switch(self, dpid):
        """
        根据 DPID 区分交换机类型：
        - core_{j}_{i}  => DPID: kjjii
        - agg_{pod}_{i} => DPID: pod, agg = (i + k/2), 01
        - edge_{pod}_{i} => DPID: pod, i, 01
        """
        x = dpid & 0xff
        y = (dpid >> 8) & 0xff
        z = (dpid >> 16) & 0xff

        if x == 0x01:
            if y >= self.k // 2:
                return 'agg', (z, y - self.k // 2)  # pod, i
            else:
                return 'edge', (z, y)              # pod, i
        else:
            j = (dpid >> 8) & 0xff
            i = dpid & 0xff
            return 'core', (j, i)

    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofproto = dp.ofproto
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst)
        dp.send_msg(mod)

    def install_edge_flows(self, dp, pod, edge):
        parser = dp.ofproto_parser
        for i in range(self.hosts_per_edge):
            ip_dst = f'10.{pod}.{edge}.{i + 2}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=ip_dst)
            actions = [parser.OFPActionOutput(i)]
            self.add_flow(dp, 100, match, actions)

        for i in range(self.k // 2):
            ip_src = f'0.0.0.{i + 2}'
            port = i + self.hosts_per_edge
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip_src)
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

    def install_agg_flows(self, dp, pod, agg):
        parser = dp.ofproto_parser
        for edge in range(self.k // 2):
            for i in range(self.k // 2):
                ip_dst = f'10.{pod}.{edge}.{i + 2}'
                match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=ip_dst)
                actions = [parser.OFPActionOutput(edge)]
                self.add_flow(dp, 100, match, actions)

        for i in range(self.k // 2):
            ip_src = f'0.0.0.{i + 2}'
            y = agg
            port = ((i - 2 + y) % (self.k // 2)) + (self.k // 2)
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=ip_src)
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

    def install_core_flows(self, dp, j, i):
        parser = dp.ofproto_parser
        for pod in range(self.k):
            for edge in range(self.k // 2):
                for h in range(self.k // 2):
                    ip_dst = f'10.{pod}.{edge}.{h + 2}'
                    match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=ip_dst)
                    actions = [parser.OFPActionOutput(pod)]
                    self.add_flow(dp, 100, match, actions)
