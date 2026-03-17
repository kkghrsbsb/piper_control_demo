# 03.14

todo: 检查代码，继续实现把 host、port、打印频率、零位阈值做成命令行参数。  

现在的情况是  
tests/pybullet_socket_stream_sender.py 作为socket发送端  
tests/socket_joint_realtime_follow.py 作为socket接收端

后续合并方案是在运动到零位后启动发送端程序（即线程开启），同时在接收端等待几帧确认后进入实时跟随，以pybullet的窗口关闭（即线程关闭）替换按键“q”停止，然后再确定是否失能。


# 03.15

昨天的todo暂缓，今天做了夹爪方面的工作

move_debug.py 做了夹爪控制（使能，控制）

slider_arm_gripper.py 做了滑动条控制夹爪

todo: 明确后面做 7目标位 socket流 传输 添加功能在 tests/ 中 socket_joint_realtime_follow.py 和 pybullet_socket_stream_sender.py
还有就是这种流式目标位传输相关的代码要重构新建一个 socket 运行库在 src/ 中
以后可以传输 socket 流数据 给机械臂控制 （socket数据库可以通过具身智能模型预测给出目标位流）


# 03.16

重构 move_debug.py 把关键复用模块整理进 src/ 中，搞定掉了碰撞保护和程序上的类碰撞保护
重构代码 move_debug.py ,关键函数总结抽出至 src/piper_control_demo/ 中
现在刚把一版新格式 {"t": 0.000, "q": [j1, j2, j3, j4, j5, j6], "gripper": 0.8}
总结为 帧定义程序 src/piper_socket_bridge/protocol.py
这一次改动新 workflow 总结在了 docs/src/explain 中了，明天看；注意但前 piper_socket_bridge 的定义结构只是初版

有几点后面要明确的
1. 要么经验总结出，要么采样测试出函数关系式： 仿真环境的速度控制和真实机械臂的所谓定义的JOINT_SAFE_SPEED的关系式，做到追踪的同时真正同步；只是为了关节效果更好
2. 后面做机械臂到仿真环境的流传输，需要明确的速度帧是否能匹配上，pybullet能否接受这个格式帧做正确的控制。已总结文档在同级目录下
3. 夹爪的范围是 [0, 0.1]，但是仿真环境还是 urdf定义范围是 [0, 0.17]还是什么，虽然影响不大
4. 我还没有看物理机械臂作为接受端是怎么稳定接受关节流做控制的（是仿真环境？还是在默认控制方式本身中？）

codex resume 019ceaaa-5fbb-7da2-b2dd-ce3ecf983f3d

# 03.17

针对昨天要明确的问题，其中第 1 条

已修复仿真夹爪和真实的语义差，见 docs/src/explain/pybullet_true_state_stream_sender_2026-03-17.md 
现在 src/piper_pybullet_sim/slider_arm_gripper.py 采用的是线性映射方案：
  - 对外滑条显示语义：[0.0, 0.1]
  - 仿真内部实际控制语义：[0.0, 0.175]
  - 换算关系：1.75
    
针对第 2 条
src/piper_socket_bridge/sim_adapter 中有个很关键的设计点：它不是“读仿真当前关节角再发送”，而是读滑条目标值再发送。也就是说，发送出去的是命令目标，不是机器人动力学仿真后的真实反馈状态。这是个很重要的语义区别。因为 setJointMotorControl2(... POSITION_CONTROL, targetPosition=...) 只是告诉 PyBullet “往这里走”，但这一时刻实际关节角可能还没完全到位。如果接收端拿这个流当“目标命令流”是对的；如果误以为这是“真实状态流”，那语义就错了。
已修复，改为“真实状态流”，见 docs/src/explain/pybullet_true_state_stream_sender_2026-03-17.md
