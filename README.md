# D435i 双灯条识别与位姿测量系统

本项目使用 Intel RealSense D435i 的 RGB 图像识别一对灯条，通过 OpenCV 完成颜色分割、轮廓筛选、双灯条配对和 IPPE PnP 位姿解算，实时输出目标位置、姿态及相对初始位置的位移。

当前现场配置默认检测亮红色灯条，目标物理尺寸为：灯条有效长度 300 mm、含光晕宽度 14 mm、两灯条中心距 165 mm。

## 当前功能

- 自动读取 D435i RGB 相机内参和畸变系数。
- 相机启动后预热 30 帧并锁定曝光、增益和白平衡，减少人员入镜引起的 HSV 漂移。
- 使用 HSV、亮度和颜色邻域响应提取亮红色灯条。
- 根据面积、长宽比、矩形度、方向和亮度筛选单灯条。
- 根据颜色、长度、宽度、平行度、垂直重叠、中心距及上一帧位置对灯条进行配对。
- 使用填充轮廓像素拟合中心线，并通过投影分位数获得抗光晕毛刺的上下端点。
- 使用两根灯条的 4 个中心线端点建立平面模型。
- 使用 `solvePnPGeneric(..., SOLVEPNP_IPPE)` 获取平面候选解，结合重投影误差和帧间连续性选择结果，再用 LM 优化。
- 使用 EMA 平滑位置与姿态；短暂丢检时最多保留最近结果 2 帧。
- 显示原始标注图、黑色背景灯条图和独立测量窗口。
- 支持多距离尺度标定。

## 算法流程

```text
D435i RGB 图像
    ↓
锁定曝光、增益和白平衡
    ↓
HSV/亮度分割 + 形态学处理
    ↓
轮廓查找与单灯条几何筛选
    ↓
双灯条几何评分 + 帧间关联
    ↓
中心线拟合 + 稳健端点提取
    ↓
IPPE 多解 PnP + LM 优化
    ↓
重投影误差与距离有效性检查
    ↓
EMA 滤波、短时丢帧保持
    ↓
输出位置、位移、Range 和姿态角
```

## 项目结构

```text
CV_Problem/
├── core/
│   ├── camera_realsense.py       # D435i RGB 采集、内参读取和曝光锁定
│   ├── config.py                 # 目标尺寸、HSV、筛选、跟踪和 PnP 参数
│   ├── detector.py               # 灯条候选提取、筛选和配对
│   ├── geometry.py               # 3D 平面模型和角点工具
│   ├── pose.py                   # IPPE PnP、验证、姿态与位移计算
│   └── main_rgb.py               # 实时处理和界面显示
├── test/
│   ├── hsv_tuner_realsense.py    # RealSense HSV 调参工具
│   ├── calibrate_distance_scale.py # 多距离尺度标定
│   ├── test_optimizations.py     # 无相机算法测试
│   ├── test_modules.py           # 模块导入测试
│   └── test_system.py            # 系统结构验证
├── docs/
│   ├── PROJECT_SUMMARY.md
│   └── debug/                    # 安装、调参和故障排查文档
├── data/                         # 测试数据
├── results/                      # 保存的检测结果
├── main_rgb.py                   # 程序启动入口
├── requirements.txt
└── README.md
```

## 环境与安装

建议使用 Python 3.8 或更高版本，并安装 Intel RealSense SDK/udev 规则。

```bash
pip install -r requirements.txt
pip install pyrealsense2
```

确认相机能够被系统识别：

```bash
lsusb | grep -i Intel
```

## 运行

在项目根目录执行：

```bash
python main_rgb.py
```

启动时应看到 RGB 参数锁定信息：

```text
RGB 参数已锁定: Exposure=..., Gain=..., WhiteBalance=...
```

相机启动后的约 1 秒预热期间，应让目标正常出现在画面中，并避免手或其他大物体进入画面。

快捷键：

- `q`：退出程序。
- `s`：保存当前标注帧到 `results/`。
- `r`：把当前位置设为新的位移参考点。
- `d`：显示或隐藏全部候选调试标记。

## 实时输出

程序打开三个窗口：

1. `Light Bar Detection + Matching + PnP`
   - 原始 RGB 图像；
   - 两根灯条的旋转矩形；
   - 每根灯条的 4 个角点；
   - PnP 使用的中心线端点；
   - 目标坐标轴、位置、位移、姿态和重投影误差。
2. `Processed Light Bars`
   - 黑色背景；
   - 仅显示已经确认的目标灯条。
3. `Pose Measurement`
   - `X / Y / Z`；
   - `dX / dY / dZ / Distance`；
   - `Range`；
   - `Roll / Pitch / Yaw`。

其中：

```text
Range = sqrt(X² + Y² + Z²)
Distance = sqrt(dX² + dY² + dZ²)
```

`HOLD 1/2` 或 `HOLD 2/2` 表示当前帧检测失败，界面暂时保留最近一次有效位姿；连续失败超过 2 帧后结果失效。

## 当前现场参数

主要参数位于 `core/config.py`：

```python
LIGHT_LENGTH = 0.3       # 300 mm
LIGHT_WIDTH = 0.014      # 14 mm，包含可见光晕
LIGHT_SPACING = 0.165    # 165 mm，两灯条中心距

HSV_LOWER_RED1 = np.array([3, 0, 212])
HSV_UPPER_RED1 = np.array([42, 73, 255])

PNP_MODEL_SCALE = 1.028057
POSE_EMA_ALPHA = 0.6
POSE_HOLD_FRAMES = 2
MAX_REPROJECTION_ERROR = 15.0
```

`POSE_EMA_ALPHA` 越大响应越快，越小越平滑。当前 `0.6` 偏向快速响应。

## HSV 标定

运行 RealSense HSV 工具：

```bash
python -m test.hsv_tuner_realsense
```

调整时让二值掩膜稳定覆盖两根灯条，同时尽量排除窗户和反光。当前检测使用的是高亮灯芯区域，不要求把整个红色光晕全部包含进去。记录最终的 H、S、V 范围后写入 `core/config.py`。

默认目标颜色是：

```python
TARGET_LIGHT_COLOR = "red"
```

检测器预留了蓝色掩膜和颜色分类分支。使用蓝灯时需要重新标定 `HSV_LOWER_BLUE`、`HSV_UPPER_BLUE` 并把目标颜色改为 `blue`；黑底显示目前仍按红色输出设计。

## 多距离标定结果

本项目使用 1.0、1.3、1.6、2.0 m 四个距离完成统一尺度标定：

| 真实距离 | 标定前 Range | 标定后预计 Range | 残差 |
|---:|---:|---:|---:|
| 1.000 m | 1.012 m | 0.996 m | -0.004 m |
| 1.300 m | 1.335 m | 1.313 m | +0.013 m |
| 1.600 m | 1.609 m | 1.583 m | -0.017 m |
| 2.000 m | 2.040 m | 2.007 m | +0.007 m |

统一修正倍率为 `0.983786`，最终 `PNP_MODEL_SCALE = 1.028057`，四点 RMSE 约为 `0.0116 m`。

重新标定时，每个距离稳定采集约 20 帧，使用 Range 中位数，然后运行：

```bash
python -m test.calibrate_distance_scale \
  1.00:程序读数 \
  1.30:程序读数 \
  1.60:程序读数 \
  2.00:程序读数
```

把工具输出的 `PNP_MODEL_SCALE` 写回 `core/config.py`。如果标定后的 RMSE 仍超过约 3 cm，应检查相机内参、灯条有效长度、中心距以及轮廓端点是否完整。

## 坐标系和角度

目标模型原点位于两根灯条中心连线的中点：

- X 轴：沿两灯条连线向右；
- Y 轴：沿灯条向下；
- Z 轴：垂直目标平面；
- 相机坐标 X 向右、Y 向下、Z 向前。

Roll、Pitch、Yaw 来自目标三维旋转矩阵，不是单根灯条在图像中的二维倾角。目标正对相机且保持竖直时，三个角度应接近零。

## 测试

运行不依赖相机的算法测试：

```bash
python -m unittest test.test_optimizations -v
```

运行模块与系统结构检查：

```bash
python -m test.test_modules
python -m test.test_system
```

调试和参数说明见 `docs/debug/TUNING_GUIDE.md`。

## 常见问题

### 手进入画面后检测失败

程序默认在启动预热后锁定 RGB 曝光和白平衡。重新启动程序，并在预热期间保持目标可见且不要让手进入画面。如果终端没有打印 RGB 参数锁定信息，检查相机控制是否被其他程序占用。

### 只检测到半根灯条

通常是 HSV 阈值、曝光或轮廓断裂造成。系统会拒绝长度差异过大的 PnP 输入，并短时保持上一次有效结果，避免输出明显错误的距离。应优先改善掩膜完整性，不应单纯放宽重投影误差。

### 窗户高光被识别

检查 HSV 掩膜是否包含低饱和白光，并观察候选是否满足双灯条的同色、平行、长度、重叠和真实间距约束。可临时开启 `DEBUG`、`DEBUG_SHOW_FILTERED` 和 `DEBUG_SHOW_PAIRS` 查看淘汰原因。

### 车辆移动时结果闪烁或延迟

- 闪烁明显：适当减小 `POSE_EMA_ALPHA`，或将 `POSE_HOLD_FRAMES` 从 2 增加到 3。
- 响应偏慢：适当增大 `POSE_EMA_ALPHA`，建议不超过 `0.8`。
- 修改时一次只调整一个参数，并在相同路线和速度下比较。

更多安装与排查内容位于 `docs/debug/`。
