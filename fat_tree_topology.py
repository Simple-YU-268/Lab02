# Fat-Tree Topology Generator with Correct DPID Assignment (k=4)
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.node import RemoteController
from mininet.cli import CLI

# Helper function to format DPID
def make_dpid(hexstr: str) -> str:
    return hexstr.zfill(16)

class FatTreeTopo(Topo):
    def build(self, k=4):
        if k % 2 != 0:
            raise Exception("k must be even")

        core_switches = []
        agg_switches = []
        edge_switches = []

        # Core Switches (grid of (k/2)x(k/2))
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

                # Add hosts to edge switch
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}'
                    host_name = f'h{pod}_{i}_{h}'
                    host = self.addHost(host_name, ip=host_ip)
                    self.addLink(sw, host)  # No port assignment

            # Edge <-> Aggregation intra-pod links
            for agg in pod_agg:
                for edge in pod_edge:
                    self.addLink(agg, edge)  # No port assignment

        # Core <-> Aggregation inter-pod links
        for i in range(k // 2):  # Each column
            for j in range(k // 2):  # Each row in core
                core = core_switches[i * (k // 2) + j]
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i]
                    self.addLink(core, agg)  # No port assignment

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
