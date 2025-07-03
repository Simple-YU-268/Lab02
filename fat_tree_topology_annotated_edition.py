# Fat-Tree Topology Generator with Correct DPID Assignment (k=4)
from mininet.topo import Topo                  # 从mininet导入拓扑基类，定义网络结构
from mininet.net import Mininet                # 从mininet导入Mininet网络类，启动仿真网络
from mininet.link import TCLink                # 从mininet导入TCLink，用于支持链路参数（如带宽）
from mininet.node import RemoteController      # 从mininet导入RemoteController，表示外部控制器
from mininet.cli import CLI                    # 从mininet导入CLI，提供命令行操作

# Helper function to format DPID 定义一个辅助函数，生成16位DPID字符串
def make_dpid(hexstr: str) -> str:
    return hexstr.zfill(16)                    # 把字符串前面补0直到16位

class FatTreeTopo(Topo):                       # 创建FatTreeTopo类，继承自Topo类
    def build(self, k=4):                      # build方法：构建拓扑结构，k为参数
        if k % 2 != 0:                         # 如果k不是偶数，抛出异常
            raise Exception("k must be even")

        core_switches = []                     # 存储所有核心交换机 方括号表示这是一个列表(list)
        agg_switches = []                      # 存储所有聚合交换机
        edge_switches = []                     # 存储所有接入交换机

        # Core Switches (grid of (k/2)x(k/2)) 创建核心交换机（(k/2)*(k/2)个）
        for j in range(1, k // 2 + 1):         # j从1到k/2
            for i in range(1, k // 2 + 1):     # i从1到k/2
                name = f'core_{j}_{i}'         # 核心交换机名字
                dpid = make_dpid(f'{k:02x}{j:02x}{i:02x}')  # 核心交换机DPID 标识符identifier
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13') # 创建核心交换机
                core_switches.append(sw)       # 加入核心交换机列表  append() 是Python中列表(list)的方法(method)，表示在列表末尾添加一个元素(element)。例如：mylist.append(x)会把x放到mylist的最后一个位置。

        # Aggregation and Edge Switches 遍历（loop over）k个Pod
        for pod in range(k):
            pod_agg = []                       # 当前Pod的聚合交换机列表
            pod_edge = []                      # 当前Pod的接入交换机列表

            # Aggregation switches 创建聚合交换机
            for i in range(k // 2):
                name = f'agg_{pod}_{i}'        # 聚合交换机名字 【这里f开头表示f-string，叫格式化字符串(f-string)，Python3.6+的语法，写f'...'可以在字符串里直接把变量用{}嵌入。例如f'agg_{pod}_{i}'会把pod和i的值填进去。】
                dpid = make_dpid(f'{pod:02x}{(i + k//2):02x}01')  # 聚合交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_agg.append(sw)             # 加入当前Pod聚合交换机列表
                agg_switches.append(sw)        # 加入总聚合交换机列表

            # Edge switches and hosts 创建接入交换机和主机
            for i in range(k // 2):
                name = f'edge_{pod}_{i}'       # 接入交换机名字
                dpid = make_dpid(f'{pod:02x}{i:02x}01') # 接入交换机DPID
                sw = self.addSwitch(name, dpid=dpid, protocols='OpenFlow13')
                pod_edge.append(sw)            # 加入当前Pod接入交换机列表
                edge_switches.append(sw)       # 加入总接入交换机列表

                # Add hosts to edge switch 给接入交换机添加主机
                for h in range(k // 2):
                    host_ip = f'10.{pod}.{i}.{h + 2}' # 主机IP地址
                    host_name = f'h{pod}_{i}_{h}'     # 主机名字
                    host = self.addHost(host_name, ip=host_ip)  # 创建主机
                    self.addLink(sw, host)  # No port assignment 将主机连接到接入交换机

            # Edge <-> Aggregation intra-pod links Pod内聚合<->接入交换机两两相连
            for agg in pod_agg:
                for edge in pod_edge:
                    self.addLink(agg, edge)  # No port assignment

        # Core <-> Aggregation inter-pod links 核心交换机<->聚合交换机连接
        for i in range(k // 2):  # Each column
            for j in range(k // 2):  # Each row in core
                core = core_switches[i * (k // 2) + j]
                for pod in range(k):
                    agg = agg_switches[pod * (k // 2) + i]
                    self.addLink(core, agg)  # No port assignment

if __name__ == '__main__':  # 主程序入口
    import argparse                            # 导入argparse模块，解析命令行参数

    parser = argparse.ArgumentParser(description='Run Fat-Tree topology with specified k.') # 这里创建一个ArgumentParser对象(object)，用来处理命令行参数(command-line arguments)。description参数是描述信息，用来帮助说明这个程序的用途。
    parser.add_argument('--k', type=int, default=4, help='Number of ports per switch (must be even)') # 这行是给parser添加一个参数，叫--k，类型是整数(int)，默认值是4，help是这个参数的提示说明。运行程序时可以输入--k 6来指定k=6。
    args = parser.parse_args()                 # 解析命令行参数

    if args.k % 2 != 0:                        # 检查k是否为偶数（%取余数，!非）
        raise ValueError("k must be even")

    topo = FatTreeTopo(k=args.k)               # 创建FatTreeTopo实例
    net = Mininet(topo=topo, link=TCLink, controller=None,
                  autoSetMacs=True, autoStaticArp=True) # 创建Mininet网络  ARP:把ip转换成mac


    net.addController('controller', controller=RemoteController,
                      ip='127.0.0.1', port=6633, protocols='OpenFlow13') # 添加远程控制器

    net.start()                                # 启动网络
    CLI(net)                                   # 启动命令行界面
    net.stop()                                 # 停止网络
