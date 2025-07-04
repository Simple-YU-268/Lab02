from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp

class FatTreeRouting(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FatTreeRouting, self).__init__(*args, **kwargs)
        self.k = None  # 稍后通过DPID自动识别

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        ofproto = dp.ofproto
        parser = dp.ofproto_parser
        dpid = dp.id

        if self.k is None:
            self.k = self.infer_k_from_dpid(dpid)
            self.logger.info(f"Inferred k = {self.k} from DPID = {format(dpid, '016x')}")

        sw_type, pos = self.identify_switch(dpid)
        self.logger.info(f"Switch connected: DPID={format(dpid, '016x')} TYPE={sw_type} POS={pos}")

        # Table-miss drop
        match = parser.OFPMatch()
        self.add_flow(dp, 0, match, [], hard_timeout=0)

        # ARP flooding
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(dp, 1, match, actions)

        if sw_type == 'edge':
            self.install_edge_flows(dp, *pos)
        elif sw_type == 'agg':
            self.install_agg_flows(dp, *pos)
        elif sw_type == 'core':
            self.install_core_flows(dp)

    def infer_k_from_dpid(self, dpid):
        # Core switch: format = 0x00kkjji (e.g., 0x00040102 for core_1_2)
        z = (dpid >> 16) & 0xff
        return z

    def identify_switch(self, dpid):
        x = dpid & 0xff
        y = (dpid >> 8) & 0xff
        z = (dpid >> 16) & 0xff

        if z == self.k:
            return 'core', (y, x)
        elif y >= self.k // 2:
            return 'agg', (z, y - self.k // 2)
        else:
            return 'edge', (z, y)

    def install_edge_flows(self, dp, pod, edge):
        parser = dp.ofproto_parser

        # 下发到本地主机
        for h in range(self.k // 2):
            ip = f'10.{pod}.{edge}.{h + 2}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "255.255.255.255"))
            actions = [parser.OFPActionOutput(h + 1)]
            self.add_flow(dp, 10, match, actions)

        # 上行发送到 agg（按主机末尾轮转）
        for pod_ in range(self.k):
            for edge_ in range(self.k // 2):
                for x in range(2, 2 + self.k // 2):
                    dst_ip = f'10.{pod_}.{edge_}.{x}'
                    port = (x - 2 + edge) % (self.k // 2) + (self.k // 2) + 1
                    match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(dst_ip, "255.255.255.255"))
                    actions = [parser.OFPActionOutput(port)]
                    self.add_flow(dp, 1, match, actions)

    def install_agg_flows(self, dp, pod, agg):
        parser = dp.ofproto_parser

        # 向下转发到同pod的 edge
        for edge in range(self.k // 2):
            subnet_ip = f'10.{pod}.{edge}.0'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(subnet_ip, "255.255.255.0"))
            actions = [parser.OFPActionOutput(edge + 1)]
            self.add_flow(dp, 10, match, actions)

        # 向上传送到 core，使用主机末尾轮转
        for pod_ in range(self.k):
            for edge_ in range(self.k // 2):
                for x in range(2, 2 + self.k // 2):
                    dst_ip = f'10.{pod_}.{edge_}.{x}'
                    port = (x - 2 + agg) % (self.k // 2) + (self.k // 2) + 1
                    match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(dst_ip, "255.255.255.255"))
                    actions = [parser.OFPActionOutput(port)]
                    self.add_flow(dp, 1, match, actions)

    def install_core_flows(self, dp):
        parser = dp.ofproto_parser

        # 根据 pod 号匹配 /16 前缀
        for pod in range(self.k):
            ip_prefix = f'10.{pod}.0.0'
            port = pod + 1
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip_prefix, "255.255.0.0"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                buffer_id=buffer_id,
                                hard_timeout=hard_timeout)
        datapath.send_msg(mod)
