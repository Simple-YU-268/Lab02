# Fat-Tree Topology Generator with Correct Port Bindings (k=4, all ports from 1)
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

        # Core Switches (grid of (k/2)x(k/2)) 创建核心交换机（(k/2)*(k/2)个）
        for j in range(1, k // 2 + 1):         # j从1到k/2
            for i in range(1, k // 2 + 1):     # i从1到k/2
                name = f'core_{j}_{i}'         # 核心交换机名字
                dpid = make_dpid(f'{k:02x}{j:02x}{i:02x}')  # 核心交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                core_switches.append(sw)

        # Aggregation and Edge Switches 遍历（loop over）k个Pod
        for pod in range(k):
            pod_agg = []                       # 当前Pod的聚合交换机列表
            pod_edge = []                      # 当前Pod的接入交换机列表

            # Aggregation switches 创建聚合交换机
            for i in range(k // 2):
                name = f'agg_{pod}_{i}'
                dpid = make_dpid(f'{pod:02x}{(i + k//2):02x}01')  # 聚合交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_agg.append(sw)
                agg_switches.append(sw)

            # Edge switches and hosts 创建接入交换机和主机
            for i in range(k // 2):
                name = f'edge_{pod}_{i}'
                dpid = make_dpid(f'{pod:02x}{i:02x}01')  # 接入交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_edge.append(sw)
                edge_switches.append(sw)

                # Hosts: connect to ports 1, 2
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}'
                    host_name = f'h{pod}_{i}_{h}'
                    host = self.addHost(host_name, ip=host_ip)
                    self.addLink(sw, host,
                                 port1=h + 1,
                                 port2=0)

            # Edge <-> Agg intra-pod links
            for a, agg in enumerate(pod_agg):
                for e, edge in enumerate(pod_edge):
                    self.addLink(agg, edge,
                                 port1=e + 1,
                                 port2=a + k // 2 + 1)

        # Core <-> Agg inter-pod links
        for i in range(k // 2):
            for j in range(k // 2):
                core = core_switches[(j) * (k // 2) + i]  # row-major
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i]
                    self.addLink(core, agg,
                                 port1=pod + 1,
                                 port2=j + k // 2 + 1)

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

