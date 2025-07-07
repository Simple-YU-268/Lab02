# Fat-Tree Topology Generator with Correct Port Bindings (k=4, all ports from 1)
from mininet.topo import Topo                         # 从mininet.topo导入Topo基类
from mininet.net import Mininet                       # 导入Mininet类用于创建网络
from mininet.link import TCLink                       # 导入TCLink类用于创建链路
from mininet.node import RemoteController             # 导入远程控制器类
from mininet.cli import CLI                           # 导入命令行接口

def make_dpid(hexstr: str) -> str:
    return hexstr.zfill(16)       # 把输入的字符串补足16位，用作DPID

class FatTreeTopo(Topo):          # 定义一个继承自Topo的类
    def build(self, k=4):         # build方法用于搭建拓扑
        if k % 2 != 0:
            raise Exception("k must be even")  # 如果k不是偶数则抛出异常

        core_switches = []     # 核心交换机列表
        agg_switches = []      # 聚合交换机列表
        edge_switches = []     # 接入交换机列表

        # Core Switches (grid of (k/2)x(k/2)) 创建核心交换机（(k/2)*(k/2)个）（//是整除，省略后面小数部分）
        for j in range(1, k // 2 + 1):         # j从1到k//2+1
            for i in range(1, k // 2 + 1):     # i从1到k//2+1
                name = f'core_{j}_{i}'         # 核心交换机名字
                dpid = make_dpid(f'{k:02x}{j:02x}{i:02x}')  # 核心交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')  # 添加交换机
                core_switches.append(sw)       # 加入列表

        # Aggregation and Edge Switches 遍历（loop over）k个Pod
        for pod in range(k):
            pod_agg = []                       # 当前Pod的聚合交换机列表
            pod_edge = []                      # 当前Pod的接入交换机列表

            # Aggregation switches 创建聚合交换机
            for i in range(k // 2):            # i从0到k//2
                name = f'agg_{pod}_{i}'        # 聚合交换机名字
                dpid = make_dpid(f'{pod:02x}{(i + k//2):02x}01')  # 聚合交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')   # 添加交换机
                pod_agg.append(sw)             # 加入列表
                agg_switches.append(sw)        # 加入列表

            # Edge switches and hosts 创建接入交换机和主机
            for i in range(k // 2):            # i从0到k//2
                name = f'edge_{pod}_{i}'       # 边缘交换机名字
                dpid = make_dpid(f'{pod:02x}{i:02x}01')  # 接入交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')   # 添加交换机
                pod_edge.append(sw)            # 加入列表
                edge_switches.append(sw)       # 加入列表

                # Hosts: connect to ports 1, 2
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}'   # 主机IP
                    host_name = f'h{pod}_{i}_{h}'       # 主机名称
                    host = self.addHost(host_name, ip=host_ip)    # 添加主机
                    self.addLink(sw, host,
                                 port1=h + 1,     # 接入交换机端口
                                 port2=0)         # 主机端口

            # Edge <-> Agg intra-pod links     # 接入交换机与聚合交换机相连（pod内部）
            for a, agg in enumerate(pod_agg):               #遍历当前pod里的所有聚合交换机，a是索引(0,1,...), agg是交换机对象。
                for e, edge in enumerate(pod_edge):         #这个循环遍历当前pod里的接入交换机，e是索引，edge是交换机对象。
                    self.addLink(agg, edge,                 #把聚合交换机和接入交换机连接起来，port1设置为e+1，port2设置为a+k//2+1，分别代表两端口号。
                                 port1=e + 1,               # 接入交换机端口
                                 port2=a + k // 2 + 1)       # 主机端口

        # Core <-> Agg inter-pod links       # 核心交换机与聚合交换机相连（pod之间）
        for i in range(k // 2):
            for j in range(k // 2):
                core = core_switches[(j) * (k // 2) + i]  # row-major 通过行优先顺序取出一个核心交换机
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i] #取出对应pod中第i个聚合交换机
                    self.addLink(core, agg,                #把聚合交换机和核心交换机连接起来
                                 port1=pod + 1,
                                 port2=j + k // 2 + 1)

if __name__ == '__main__':
    import argparse              # 导入参数解析模块

    parser = argparse.ArgumentParser(description='Run Fat-Tree topology with specified k.')     # 创建解析器
    parser.add_argument('--k', type=int, default=4, help='Number of ports per switch (must be even)')   # 添加k参数
    args = parser.parse_args()           # 解析命令行参数

    if args.k % 2 != 0:
        raise ValueError("k must be even")           # 验证k必须是偶数

    topo = FatTreeTopo(k=args.k)         # 创建拓扑对象
    net = Mininet(topo=topo, link=TCLink, controller=None,
                  autoSetMacs=True, autoStaticArp=True)        # 创建Mininet网络

    net.addController('controller', controller=RemoteController,
                      ip='127.0.0.1', port=6633, protocols='OpenFlow13')       # 添加远程控制器

    net.start()          # 启动网络
    CLI(net)             # 启动命令行接口
    net.stop()           # 停止网络

