# Lab02

**PartA**
1. terminalA: ryu-manager testryu.py

2. terminalB: sudo python3 fat_tree_topology.py --k 6

3. terminalB:mininet> pingall

**PartB**
1. terminalA: ryu-manager fat_tree_routing.py
2. terminalB: sudo python3 fat_tree_topology.py2 --k 4
3. terminalB: pingall

**调试代码**
sh ovs-ofctl -O OpenFlow13 dump-flows edge_0_0
sh ovs-ofctl -O OpenFlow13 dump-flows agg_0_0
sh ovs-ofctl -O OpenFlow13 dump-flows core_1_1