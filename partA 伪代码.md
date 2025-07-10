partA 伪代码
函數 make_dpid(十六进制字符串):
    用零补齐到16位，作为DPID返回

类 FatTreeTopo:
    函數 build(k):
        如果 k 不是偶数:
            抛出异常

        初始化三个列表：core_switches, agg_switches, edge_switches

        // 1. 创建 Core 交换机：共有 (k/2)^2 个
        对 j 从 1 到 k/2:
            对 i 从 1 到 k/2:
                创建交换机 core_j_i
                设置其 DPID 为 k:j:i（转为十六进制）
                加入 core_switches 列表

        // 2. 对每个 pod 执行以下操作（共有 k 个 pod）
        对 pod 从 0 到 k-1:
            初始化 pod_agg, pod_edge 列表

            // 2.1 创建 Aggregation 交换机：每个 pod 有 k/2 个
            对 i 从 0 到 k/2 - 1:
                创建 agg_pod_i，DPID 为 pod:(i + k/2):01
                加入 pod_agg 和 agg_switches

            // 2.2 创建 Edge 交换机和其连接的主机
            对 i 从 0 到 k/2 - 1:
                创建 edge_pod_i，DPID 为 pod:i:01
                加入 pod_edge 和 edge_switches

                对 h 从 0 到 k/2 - 1:
                    分配主机 IP 为 10.pod.i.h+2
                    创建主机 h_pod_i_h
                    将该主机与当前 Edge 交换机连接

            // 2.3 将该 pod 的 Edge 与 Aggregation 连接
            对 pod 中每个 agg 与每个 edge:
                建立连接（未指定端口）

        // 3. 创建 Core 与 Aggregation 的连接
        对 i 从 0 到 k/2 - 1:
            对 j 从 0 到 k/2 - 1:
                找到 core[i*(k/2) + j]
                对 pod 从 0 到 k-1:
                    找到 agg[pod*(k/2) + i]
                    将 core 与 agg 连接