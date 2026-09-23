# CV_Problem

Intel RealSense D435i RGB 视觉程序：用 OpenCV 检测两根红色灯带，用 PnP 估计目标位置、姿态和位移。

## 目录

```text
CV_Problem/
├── main_rgb.py          # 实时程序入口
├── core/
│   ├── config.py        # 现场常改参数
│   ├── camera_realsense.py
│   ├── detector.py      # OpenCV 灯带检测和配对
│   ├── geometry.py      # 灯带几何模型
│   ├── pose.py          # PnP 位姿估计
│   └── main_rgb.py      # 实时画面与按键控制
├── test/                # HSV、距离标定和算法测试
├── results/             # 按 s 保存的图像
└── requirements.txt
```

## 安装和运行

使用 Python 3.10+。安装 RealSense SDK，连接 D435i，然后在项目根目录执行：

```bash
pip install -r requirements.txt
pip install pyrealsense2
python main_rgb.py
```

按 `q` 退出，`s` 保存画面，`r` 重设位移起点，`d` 切换候选调试显示。

## 常改参数

只修改 [`core/config.py`](core/config.py)：

- `LIGHT_LENGTH`、`LIGHT_WIDTH`、`LIGHT_SPACING`：实测灯带长度、宽度及中心距，单位米。
- `HSV_LOWER_RED1`、`HSV_UPPER_RED1`：红灯 HSV 范围。运行 `python -m test.hsv_tuner_realsense`，让 Mask 窗口只保留灯带后填入。
- `PNP_MODEL_SCALE`：距离修正比例。运行 `python -m test.calibrate_distance_scale 1.00:1.09 1.30:1.42 1.60:1.73` 获取建议值；未标定时设为 `1.0`。
- `MAX_REPROJECTION_ERROR`：PnP 重投影误差上限。
- `DEBUG`：排查问题时打印详细信息。

其他固定阈值放在对应模块顶部，日常无需修改。

## 验证

```bash
python -m unittest test.test_optimizations
python -m test.test_modules
```

这些检查不需要连接相机。实际图像与测距精度仍需在现场验证。
