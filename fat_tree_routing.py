from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import ipv4


class FatTreeRouting(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FatTreeRouting, self).__init__(*args, **kwargs)
        self.k = 4  # Fat-tree parameter
        self.hosts_per_edge = self.k // 2

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        dpid = dp.id
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        self.logger.info(f"Switch connected: DPID={format(dpid, '016x')}")

        # (0) Table-miss: drop everything else
        match = parser.OFPMatch()
        self.add_flow(dp, 0, match, [])

        # (1) Allow ARP broadcast
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(dp, 1, match, actions)

        # (2) Install role-specific flow rules
        role, detail = self.identify_switch(dpid)
        if role == 'edge':
            self.install_edge_flows(dp, *detail)
        elif role == 'agg':
            self.install_agg_flows(dp, *detail)
        elif role == 'core':
            self.install_core_flows(dp)

    def identify_switch(self, dpid):
        x = dpid & 0xff
        y = (dpid >> 8) & 0xff
        z = (dpid >> 16) & 0xff
        if x == 0x01:
            if y >= self.k // 2:
                return 'agg', (z, y - self.k // 2)
            else:
                return 'edge', (z, y)
        else:
            return 'core', ()

    def add_flow(self, dp, priority, match, actions):
        parser = dp.ofproto_parser
        ofproto = dp.ofproto
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst)
        dp.send_msg(mod)

        self.logger.info(f"Flow added: DPID={format(dp.id, '016x')} prio={priority}, match={match}, actions={actions}")

    # === Edge Switch Rules ===
    def install_edge_flows(self, dp, pod, edge):
        parser = dp.ofproto_parser

        # (1) Prefix /32: Forward packets to local host (host-specific rules)
        for h in range(self.k // 2):
            ip = f'10.{pod}.{edge}.{h + 2}'
            port = h
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, 32))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

        # (2) Suffix /32: Match returning traffic using destination suffix (0.0.0.X)
        for h in range(self.k // 2):
            last_octet = h + 2
            port = h + 2  # Return traffic from core/agg
            suffix_ip = f'0.0.0.{last_octet}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(suffix_ip, 32))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 1, match, actions)

    # === Aggregation Switch Rules ===
    def install_agg_flows(self, dp, pod, agg):
        parser = dp.ofproto_parser

        # (1) Prefix /24: Forward packets to correct edge switch based on third octet
        for edge in range(self.k // 2):
            subnet_ip = f'10.{pod}.{edge}.0'
            port = edge
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(subnet_ip, 24))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

        # (2) Suffix /8: Return traffic from core using suffix matching and load balancing
        for i in range(2, 2 + self.k // 2):
            port = (i - 2 + agg) % (self.k // 2) + (self.k // 2)
            suffix_ip = f'0.0.0.{i}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(suffix_ip, 8))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 1, match, actions)

    # === Core Switch Rules ===
    def install_core_flows(self, dp):
        parser = dp.ofproto_parser

        # (1) Prefix /16: Forward packets to destination pod
        for pod in range(self.k):
            ip_prefix = f'10.{pod}.0.0'
            port = pod  # Assuming core port i connects to pod i
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip_prefix, 16))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

