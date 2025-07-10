partB拓扑伪代码
函數 make_dpid(十六进制字符串):
    返回补足16位的字符串（用于DPID）

类 FatTreeTopo:
    函數 build(k):
        如果 k 不是偶数：抛出异常

        初始化核心(core)、聚合(agg)、接入(edge)交换机列表

        // 1. 创建 (k/2)^2 个 Core 交换机，编号 core_j_i
        对 j 从 1 到 k/2:
            对 i 从 1 到 k/2:
                构建交换机名 core_j_i
                DPID 为 k:j:i（十六进制）
                添加该交换机并加入 core_switches

        // 2. 每个 pod 内构建交换机和主机
        对 pod 从 0 到 k-1:
            初始化该 pod 的 pod_agg 和 pod_edge 列表

            // 2.1 构建 k/2 个 Aggregation 交换机
            对 i 从 0 到 k/2 - 1:
                名字为 agg_pod_i
                DPID 为 pod:(i + k/2):01（十六进制）
                添加交换机并加入 pod_agg 和 agg_switches

            // 2.2 构建 k/2 个 Edge 交换机，以及每个交换机连接 k/2 个主机
            对 i 从 0 到 k/2 - 1:
                名字为 edge_pod_i
                DPID 为 pod:i:01
                添加交换机并加入 pod_edge 和 edge_switches

                对 h 从 0 到 k/2 - 1:
                    主机 IP = 10.pod.i.(h+2)
                    名字为 h_pod_i_h
                    添加主机
                    将主机连接到 edge，
                    指定：edge 使用端口 h+1，主机端口为0

            // 2.3 在该 pod 内连接所有 Edge <-> Agg（指定端口）
            对 a, agg in pod_agg:
                对 e, edge in pod_edge:
                    agg 用端口 e+1 连接 edge
                    edge 用端口 a + k/2 + 1 连接 agg

        // 3. 连接 Core <-> Aggregation 交换机（跨 pod）
        对 i 从 0 到 k/2 - 1:
            对 j 从 0 到 k/2 - 1:
                获取 core[j * (k/2) + i] （按 row-major 排列）
                对 pod 从 0 到 k-1:
                    获取 agg[pod * (k/2) + i]
                    core 用端口 pod+1 连接 agg
                    agg 用端口 j + k/2 + 1 连接 core