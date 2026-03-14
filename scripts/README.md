## piper-generate-udev-rule

把 CAN0 做成“可持久识别 + 自动配置 bitrate + 可选重命名”的 udev 规则安装脚本

一次命令执行，以后即插即用，不用再像 [piper_sdk](https://github.com/agilexrobotics/piper_sdk) 中要事先初始化can连接

> source: https://github.com/Reimagine-Robotics/piper_control/blob/main/scripts/piper-generate-udev-rule  
Generating udev rules for CAN adapters  
To avoid needing to run `sudo` to set up the CAN interface, you can create a udev rule that sets the bitrate and desired name for your CAN adapter.

```bash
#!/bin/bash
sudo ./scripts/piper-generate-udev-rule -i can0 -b 1000000
```

## record_trajetories.py
重力补偿的一次尝试，但是有限位问题，不要尝试
```bash
# 收集 （采样10保证安全，防止碰撞意外，但是kp,kd参数补偿不精准，默认50会发生桌面碰撞）
uv run piper-generate-samples -o /tmp/grav_comp_samples.npz --num-sample 10
# 测试
piper-gravity-compensation --samples-path /tmp/grav_comp_samples.npz
# 示教
python scripts/record_trajectories.py --robots can0 --gravity --samples-path /tmp/grav_comp_samples.npz
```
> warming: 收集过程是全工作空间，即使是桌面上也会发生碰撞，要求固定在和底座一样大的桌面上进行默认50次的采样