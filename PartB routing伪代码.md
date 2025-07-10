PartB routing伪代码
定义类 FatTreeRouting（继承 RyuApp）:
    指定使用 OpenFlow13

    函数 __init__:
        初始化，k 默认为 None（稍后自动从 DPID 推断）

    函数 switch_features_handler(ev):
        获取 datapath, dpid, parser, ofproto
        如果 self.k 是 None:
            调用 infer_k_from_dpid(dpid) 推断 k 值

        添加两个默认流表项：
            - Table-miss（优先级0，丢弃）
            - ARP 广播（优先级1，Flood）

        调用 identify_switch(dpid)，判断当前交换机是 edge/agg/core
        根据角色分别调用 install_edge_flows / install_agg_flows / install_core_flows

    函数 infer_k_from_dpid(dpid):
        取 DPID 的高位（第3字节）作为 k 返回

    函数 identify_switch(dpid):
        解析 DPID 得到 x（列号），y（行号），z（pod 或 core 行）
        如果 z == k → core 交换机
        如果 y >= k/2 → aggregation
        否则 → edge

    函数 add_flow(dp, priority, match, actions):
        构造 FlowMod 消息，下发至 datapath

    函数 install_edge_flows(dp, pod, edge):
        for 每个本地 host:
            匹配目标 IP 为 10.pod.edge.(h+2)，优先级10，输出端口 h+1
        for 每个 host ID x ∈ [2, 2 + k/2):
            匹配目标 IP 尾段为 x（掩码 0.0.0.255），优先级1，输出端口根据 suffix 算法计算：
            port = [(x - 2 + edge) mod (k/2)] + (k/2) + 1

    函数 install_agg_flows(dp, pod, agg):
        for 每个下连 edge：
            匹配目标 IP 为 10.pod.edge.0/24，优先级10，转发到 edge 端口
        for 每个 host 尾段 x：
            匹配目标 IP 尾段为 x（0.0.0.255），优先级1，输出端口按 suffix 算法计算：
            port = [(x - 2 + agg) mod (k/2)] + (k/2) + 1

    函数 install_core_flows(dp):
        for 每个 pod：
            匹配目标 IP 为 10.pod.0.0/16，优先级10，输出端口为 pod+1