# Fat-Tree Topology Generator with Correct DPID Encoding and Port Binding (k=4)
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import RemoteController
from mininet.cli import CLI

def encode_dpid(z: int, y: int, x: int = 0x01) -> str:
    """Encodes DPID as 0xZZYYXX (z=pod or k, y=id, x=0x01)"""
    return f"{z:02x}{y:02x}{x:02x}".zfill(16)

class FatTreeTopo(Topo):
    def build(self, k=4):
        if k % 2 != 0:
            raise Exception("k must be even")

        core_switches = []
        agg_switches = []
        edge_switches = []

        # Core Switches (k/2 x k/2 grid)
        for j in range(k // 2):
            for i in range(k // 2):
                name = f'core_{j}_{i}'
                dpid = encode_dpid(k, j * (k // 2) + i)
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                core_switches.append(sw)

        # Pods
        for pod in range(k):
            pod_agg = []
            pod_edge = []

            # Aggregation switches
            for i in range(k // 2):
                name = f'agg_{pod}_{i}'
                dpid = encode_dpid(pod, i + k // 2)
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_agg.append(sw)
                agg_switches.append(sw)

            # Edge switches and hosts
            for i in range(k // 2):
                name = f'edge_{pod}_{i}'
                dpid = encode_dpid(pod, i)
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_edge.append(sw)
                edge_switches.append(sw)

                # Hosts: port 0,1 on edge
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}'
                    host_name = f'h{pod}_{i}_{h}'
                    host = self.addHost(host_name, ip=host_ip)
                    self.addLink(sw, host, port1=h)

            # Edge <-> Agg intra-pod links
            for a, agg in enumerate(pod_agg):
                for e, edge in enumerate(pod_edge):
                    self.addLink(agg, edge,
                                 port1=e,               # agg uses port 0,1 for edge
                                 port2=a + k // 2)      # edge uses port 2,3 for agg

        # Core <-> Agg inter-pod links
        for i in range(k // 2):
            for j in range(k // 2):
                core = core_switches[j * (k // 2) + i]  # row-major
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i]
                    self.addLink(core, agg,
                                 port1=pod,             # core uses port=pod
                                 port2=j + k // 2)      # agg uses port 2,3 for core

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