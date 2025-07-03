# Fat-Tree Topology Generator with Port Binding (k=4)
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import RemoteController
from mininet.cli import CLI

def make_dpid(hexstr: str) -> str:
    return hexstr.zfill(16)

class FatTreeTopo(Topo):
    def build(self, k=4):
        if k % 2 != 0:
            raise Exception("k must be even")

        core_switches = []
        agg_switches = []
        edge_switches = []

        # Core Switches
        for j in range(1, k // 2 + 1):
            for i in range(1, k // 2 + 1):
                name = f'core_{j}_{i}'
                dpid = make_dpid(f'{k:02x}{j:02x}{i:02x}')
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                core_switches.append(sw)

        # Aggregation and Edge Switches
        for pod in range(k):
            pod_agg = []
            pod_edge = []

            # Aggregation switches
            for i in range(k // 2):
                name = f'agg_{pod}_{i}'
                dpid = make_dpid(f'{pod:02x}{(i + k//2):02x}01')
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_agg.append(sw)
                agg_switches.append(sw)

            # Edge switches and hosts
            for i in range(k // 2):
                name = f'edge_{pod}_{i}'
                dpid = make_dpid(f'{pod:02x}{i:02x}01')
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_edge.append(sw)
                edge_switches.append(sw)

                # Hosts: port1 = h (0,1), edge端口固定为0/1
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}'
                    host_name = f'h{pod}_{i}_{h}'
                    host = self.addHost(host_name, ip=host_ip)
                    self.addLink(sw, host, port1=h)  # ✅ 明确绑定 port 0/1

            # Edge <-> Agg：port1=agg侧 port=(k//2 + edge_index)，port2=edge侧 port=edge_index
            for a, agg in enumerate(pod_agg):
                for e, edge in enumerate(pod_edge):
                    self.addLink(agg, edge,
                                 port1=e + k // 2,  # agg 侧使用上半部分端口
                                 port2=a + k // 2)  # edge 侧使用下半部分端口

        # Core <-> Agg：每个core列连接每个pod的agg
        for i in range(k // 2):  # 每列
            for j in range(k // 2):  # 每行 core
                core = core_switches[i * (k // 2) + j]
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i]
                    self.addLink(core, agg,
                                 port1=pod,     # core输出端口 = pod编号
                                 port2=j)       # agg输入端口 = core行号

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run Fat-Tree topology with specified k.')
    parser.add_argument('--k', type=int, default=4, help='Number of ports per switch (must be even)')
    args = parser.parse_args()

    if args.k % 2 != 0:
        raise ValueError("k must be even")

    topo = FatTreeTopo(k=args.k)
    net = Mininet(topo=topo, link=TCLink, controller=None,
                  autoSetMacs=True, autoStaticArp=True)

    net.addController('controller', controller=RemoteController,
                      ip='127.0.0.1', port=6633, protocols='OpenFlow13')

    net.start()
    CLI(net)
    net.stop()
