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
