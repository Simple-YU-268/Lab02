from ryu.base import app_manager        # 从Ryu库导入应用基类
from ryu.controller import ofp_event    # 导入OpenFlow事件
from ryu.controller.handler import CONFIG_DISPATCHER  # 定义交换机配置阶段常量
from ryu.controller.handler import set_ev_cls         # 用于标记事件处理器 
from ryu.ofproto import ofproto_v1_3    # 引入OpenFlow 1.3协议支持

class FatTreeRouting(app_manager.RyuApp):       # 定义一个类FatTreeRouting，继承RyuApp
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]        # 声明支持的OpenFlow版本

    def __init__(self, *args, **kwargs):             # 初始化方法
        super(FatTreeRouting, self).__init__(*args, **kwargs)     # 调用父类的初始化方法
        self.k = None  # 初始化k为None，后面根据DPID自动推断


    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)    # 当交换机连接并发送功能信息时调用
    def switch_features_handler(self, ev):       # 处理交换机功能事件
        dp = ev.msg.datapath                     # 获取交换机数据路径对象
        dpid = dp.id                     # 获取交换机的DPID（数据路径ID）
        parser = dp.ofproto_parser       # 获取OpenFlow协议解析器
        ofproto = dp.ofproto             # 获取OpenFlow协议常量

        self.logger.info(f"Switch connected: DPID={format(dpid, '016x')}")         # 打印交换机连接日志

        # ✅ 先识别 k
        if self.k is None:   # 如果k未设置
            self.k = self.infer_k_from_dpid(dpid)        # 根据DPID推断k
            self.logger.info(f"Inferred k = {self.k} from DPID = {format(dpid, '016x')}")     # 打印推断结果

        # (0) Table-miss: drop everything else
        match = parser.OFPMatch()                # 创建匹配所有数据包的条件
        self.add_flow(dp, 0, match, [])          # 添加默认丢弃流表

        # (1) Allow ARP broadcast
        match = parser.OFPMatch(eth_type=0x0806)   # 匹配ARP包
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]    # 定义动作：洪泛广播
        self.add_flow(dp, 1, match, actions)       # 添加ARP流表

        # (2) 安全调用 identify_switch
        role, detail = self.identify_switch(dpid)   # 判断交换机角色
        if role == 'edge':                          # 如果是接入交换机
            self.install_edge_flows(dp, *detail)    # 安装接入规则
        elif role == 'agg':                         # 如果是汇聚交换机
            self.install_agg_flows(dp, *detail)     # 安装汇聚规则
        elif role == 'core':                        # 如果是核心交换机
            self.install_core_flows(dp)             # 安装核心规则

    
    
    def infer_k_from_dpid(self, dpid):              # 根据DPID推断k
        z = (dpid >> 16) & 0xff                     # DPID右移16位取低8位
        return z                                    # 返回k

    # === Switch Identification ===
    def identify_switch(self, dpid):                # 判断交换机角色
        x = dpid & 0xff               # i (列号)
        y = (dpid >> 8) & 0xff        # j (行号)
        z = (dpid >> 16) & 0xff       # pod 或 k

        if z == self.k:               # 如果z==k
            return 'core', (y, x)     # 是核心交换机
        elif y >= self.k // 2:        # 如果y大于等于k/2
            return 'agg', (z, y - self.k // 2)     # 是汇聚交换机
        else:
            return 'edge', (z, y)     # 是接入交换机


    def add_flow(self, dp, priority, match, actions):    # 添加流表
        parser = dp.ofproto_parser                       # 获取解析器
        ofproto = dp.ofproto                             # 协议常量
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]              # 创建动作指令
        mod = parser.OFPFlowMod(datapath=dp, priority=priority, match=match, instructions=inst)  # 创建流表消息
        dp.send_msg(mod)       # 发送到交换机
        self.logger.info(f"Flow added: DPID={format(dp.id, '016x')} prio={priority}, match={match}, actions={actions}")           # 打印日志

    # === Edge Switch Rules ===
    def install_edge_flows(self, dp, pod, edge):        # 安装接入交换机流表
        parser = dp.ofproto_parser                      # 获取解析器
        # (1) Host-specific规则: 10.pod.edge.(2/3) -> 本地端口1/2
        for h in range(self.k // 2):                    # 遍历本地端口
            ip = f'10.{pod}.{edge}.{h + 2}'             # 构造目标IP
            port = h + 1                                # 端口编号
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "255.255.255.255"))       # 匹配精确IP
            actions = [parser.OFPActionOutput(port)]    # 输出到本地端口    
            self.add_flow(dp, 10, match, actions)       # 安装流表       
        # (2) 上行: 其它IP包全部上送agg
        for x in range(2, 2 + self.k // 2):  # host ID x
            port = (x - 2 + edge) % (self.k // 2) + (self.k // 2) + 1  # 计算上行端口号
            ip = f'0.0.0.{x}'                           # 匹配IP后缀
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "0.0.0.255"))             # 匹配条件
            actions = [parser.OFPActionOutput(port)]    # 输出到本地端口
            self.add_flow(dp, 1, match, actions)        # 安装流表 



    # === Aggregation Switch Rules ===
    def install_agg_flows(self, dp, pod, agg):       # 安装汇聚交换机流表
        parser = dp.ofproto_parser                   # 获取解析器
        # (1) 下行: 10.pod.edge.0/24 -> 对应edge端口
        for edge in range(self.k // 2):              # 下行规则
            subnet_ip = f'10.{pod}.{edge}.0'         # 子网
            port = edge + 1
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(subnet_ip, "255.255.255.0"))    # 匹配精确IP
            actions = [parser.OFPActionOutput(port)] # 输出到本地端口
            self.add_flow(dp, 10, match, actions)    # 安装流表
         # (2) 后缀分流：遍历所有主机IP，末尾为x的都下发到指定上行端口
        for x in range(2, 2 + self.k // 2):          # 上行规则
            port = (x - 2 + agg) % (self.k // 2) + (self.k // 2) + 1   # 端口编号
            ip = f'0.0.0.{x}'                        # 构造目标IP                
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip, "0.0.0.255"))       # 匹配精确IP
            actions = [parser.OFPActionOutput(port)] # 输出到本地端口
            self.add_flow(dp, 1, match, actions)     # 安装流表
    # === Core Switch Rules ===
    def install_core_flows(self, dp):                # 安装核心交换机流表
        parser = dp.ofproto_parser                   # 获取解析器
        # (1) 10.pod.0.0/16 -> pod对应端口
        for pod in range(self.k):                    # 给每个pod添加规则
            ip_prefix = f'10.{pod}.0.0'              # 匹配目的IP地址前两段（10.pod.*.*）
            port = pod + 1                           # 端口编号
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=(ip_prefix, "255.255.0.0"))
            actions = [parser.OFPActionOutput(port)] # 输出到本地端口
            self.add_flow(dp, 10, match, actions)    # 安装流表


