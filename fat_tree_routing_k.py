from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3

class FatTreeRouting(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FatTreeRouting, self).__init__(*args, **kwargs)
        self.k = None  # 稍后通过DPID自动识别


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        dpid = dp.id
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        self.logger.info(f"Switch connected: DPID={format(dpid, '016x')}")

        # ✅ 先识别 k
        if self.k is None:
            self.k = self.infer_k_from_dpid(dpid)
            self.logger.info(f"Inferred k = {self.k} from DPID = {format(dpid, '016x')}")

        # (0) Table-miss: drop everything else
        match = parser.OFPMatch()
        self.add_flow(dp, 0, match, [])

        # (1) Allow ARP broadcast
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(dp, 1, match, actions)

        # (2) 安全调用 identify_switch
        role, detail = self.identify_switch(dpid)
        if role == 'edge':
            self.install_edge_flows(dp, *detail)
        elif role == 'agg':
            self.install_agg_flows(dp, *detail)
        elif role == 'core':
            self.install_core_flows(dp)

    
    
    def infer_k_from_dpid(self, dpid):
        z = (dpid >> 16) & 0xff
        return z

    # === Switch Identification ===
    def identify_switch(self, dpid):
        x = dpid & 0xff               # i (列号)
        y = (dpid >> 8) & 0xff        # j (行号)
        z = (dpid >> 16) & 0xff       # pod 或 k

        if z == self.k:
            return 'core', (y, x)
        elif y >= self.k // 2:
            return 'agg', (z, y - self.k // 2)
        else:
            return 'edge', (z, y)


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
        # (1) Host-specific规则: 10.pod.edge.(2/3) -> 本地端口1/2
        for h in range(self.k // 2):
            ip = f'10.{pod}.{edge}.{h + 2}'
            port = h + 1
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "255.255.255.255"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)
        # (2) 上行: 其它IP包全部上送agg
        for x in range(2, 2 + self.k // 2):  # host ID x
            port = (x - 2 + edge) % (self.k // 2) + (self.k // 2) + 1  # 上行端口
            ip = f'0.0.0.{x}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "0.0.0.255"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 1, match, actions)



    # === Aggregation Switch Rules ===
    def install_agg_flows(self, dp, pod, agg):
        parser = dp.ofproto_parser
        # (1) 下行: 10.pod.edge.0/24 -> 对应edge端口
        for edge in range(self.k // 2):
            subnet_ip = f'10.{pod}.{edge}.0'
            port = edge + 1
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(subnet_ip, "255.255.255.0"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)
         # (2) 后缀分流：遍历所有主机IP，末尾为x的都下发到指定上行端口
        for x in range(2, 2 + self.k // 2):
            port = (x - 2 + agg) % (self.k // 2) + (self.k // 2) + 1
            ip = f'0.0.0.{x}'
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "0.0.0.255"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 1, match, actions)
    # === Core Switch Rules ===
    def install_core_flows(self, dp):
        parser = dp.ofproto_parser
        # (1) 10.pod.0.0/16 -> pod对应端口
        for pod in range(self.k):
            ip_prefix = f'10.{pod}.0.0'
            port = pod + 1
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip_prefix, "255.255.0.0"))
            actions = [parser.OFPActionOutput(port)]
            self.add_flow(dp, 10, match, actions)


