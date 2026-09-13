# D435i RGB 灯带检测系统 - 重构版

## 🎯 重构完成

所有核心文件已完成重构：

- ✅ `core/config.py` - 新的评分机制和参数
- ✅ `core/detector.py` - 候选检测+评分系统  
- ✅ `core/geometry.py` - 统一角点排序TL→TR→BR→BL
- ✅ `core/pose.py` - PnP重投影误差验证
- ✅ `core/camera_realsense.py` - D435i真实内参读取
- ✅ `core/main_rgb.py` - 完整主程序

---

## 📋 系统要求

### 硬件
- Intel RealSense D435i
- USB 3.0接口（蓝色）

### 软件
- Ubuntu 22.04
- Python 3.7+
- OpenCV
- pyrealsense2
- NumPy

---

## 🚀 安装依赖

```bash
# 安装Python依赖
pip install opencv-python numpy pyrealsense2

# 验证安装
python -c "import cv2; import numpy; import pyrealsense2; print('✅ 依赖安装成功')"
```

---

## ⚙️ 配置步骤

### 第1步：检查D435i连接

```bash
# 查看USB设备
lsusb | grep Intel

# 应该看到类似输出：
# Bus 002 Device 003: ID 8086:0b3a Intel Corp. RealSense D435
```

### 第2步：测试相机（可选）

```bash
# 使用RealSense官方工具测试
realsense-viewer
```

### 第3步：**关键！HSV参数标定**

这是最重要的步骤！

```bash
python -m test.hsv_tuner_realsense
```

**标定目标**：
- ✅ Mask窗口只显示两条竖直灯带（白色）
- ❌ 白色纸张、窗户、机械零件都应该是黑色
- ✅ Contours: 2

**推荐起始参数**：
```
H Min: 0
H Max: 20
S Min: 80      ← 关键！提高S_min排除白色物体
S Max: 255
V Min: 200
V Max: 255
```

**调整技巧**：
1. 先调整 **S Min**（饱和度最小值）排除白色
2. 再调整 **H 范围**限定红/橙色
3. 最后微调 **V Min**（亮度）

按 **'q'** 退出后，记录输出的HSV值！

### 第4步：更新 core/config.py

将HSV值填入 `core/config.py`：

```python
HSV_LOWER_RED1 = np.array([H_min, S_min, V_min])
HSV_UPPER_RED1 = np.array([H_max, S_max, V_max])
```

### 第5步：确认灯带尺寸

用尺子测量灯带：

```python
# 在 core/config.py 中
LIGHT_LENGTH = 0.26  # 你的实际长度（米）
LIGHT_WIDTH = 0.011   # 你的实际宽度（米）
```

---

## 🎮 运行程序

```bash
python main_rgb.py
```

### 预期输出

**终端输出**：
```
==============================================================
正在初始化 Intel RealSense D435i (RGB Only)...
==============================================================

==============================================================
✅ Intel RealSense D435i 已成功启动
==============================================================

📷 D435i RGB Camera Intrinsics:
------------------------------------------------------------
分辨率: 640 × 480
帧率: 30 FPS

内参矩阵 (Camera Matrix):
  fx = 615.67
  fy = 616.02
  cx = 324.45
  cy = 237.89

畸变系数 (Distortion Coefficients):
  k1 = 0.000000
  k2 = 0.000000
  p1 = 0.000000
  p2 = 0.000000
  k3 = 0.000000
==============================================================

==============================================================
  🚀 D435i RGB 灯带跟踪系统已启动
==============================================================

操作说明：
  按 'q' - 退出程序
  按 's' - 保存当前帧
  按 'r' - 重置初始位置
==============================================================

[Detector] 总候选数: 2
[Detector] 有效候选数: 2
  候选 #1:
    颜色: red
    面积: 3245.8
    长宽比: 22.3
    矩形度: 0.89
    角度: 88.5
    亮度: 235.2
    得分: 0.856

[Geometry] 角点排序:
  P1(TL): (123.4, 56.7)
  P2(TR): (245.6, 58.9)
  P3(BR): (243.2, 289.1)
  P4(BL): (121.8, 287.3)

[PnP] 输入:
  2D角点:
    P1: (123.4, 56.7)
    P2: (245.6, 58.9)
    P3: (243.2, 289.1)
    P4: (121.8, 287.3)

[PnP] 初步结果:
  X = 0.045 m
  Y = -0.023 m
  Z = 0.512 m
  重投影误差: 2.34 px
  Roll  = -5.23°
  Pitch = 68.45°
  Yaw   = 1.87°

[PnP] ✅ 有效
```

**窗口显示**：
- ✅ 检测到的灯带（绿色轮廓）
- ✅ 旋转矩形（紫色框）
- ✅ 4个角点P1-P4（不同颜色标注）
- ✅ 坐标轴（X红、Y绿、Z蓝）
- ✅ 候选信息（得分、长宽比、角度）
- ✅ PnP状态（VALID/INVALID）
- ✅ 重投影误差
- ✅ 位置（X, Y, Z）
- ✅ 位移（dX, dY, dZ, Distance）
- ✅ 姿态（Roll, Pitch, Yaw）

### 操作

- **按 'q'**：退出
- **按 's'**：保存当前帧到 `results/`
- **按 'r'**：重置初始位置

---

## ✅ 验证清单

### 1. D435i连接成功
```bash
lsusb | grep Intel
# 应该看到Intel RealSense设备
```

### 2. RGB正常
- 运行程序后能看到实时图像
- 图像清晰、无延迟

### 3. 真实内参读取成功
- 终端显示fx, fy, cx, cy等参数
- fx和fy应该在600左右（640x480分辨率）

### 4. 灯带检测成功
- 终端显示 `[Detector] 有效候选数: 1-2`
- 窗口显示绿色轮廓标注灯带

### 5. 角点排序正确
- 窗口显示P1(TL)在左上
- P2(TR)在右上
- P3(BR)在右下
- P4(BL)在左下

### 6. PnP有效
- 终端显示 `[PnP] ✅ 有效`
- 窗口显示 `PnP: VALID`
- 重投影误差 < 5px

### 7. 重投影误差正常
- 重投影误差通常在 0.5-3 px
- 如果 > 5 px，说明检测不准确

### 8. XYZ可信
- Z值（距离）在合理范围（0.1-5米）
- X, Y, Z 都是有限值（非nan/inf）

---

## 🐛 故障排查

### 问题1：检测不到灯带

**现象**：`No valid light candidates`

**原因**：HSV参数不对

**解决**：
```bash
python -m test.hsv_tuner_realsense
# 重新标定HSV
```

### 问题2：误检太多

**现象**：`Valid Candidates: 5-10`

**原因**：HSV范围太宽或候选评分阈值太低

**解决**：
1. 提高 `core/config.py` 中的 `MIN_CANDIDATE_SCORE`
2. 缩小HSV范围
3. 提高 `S_min`（排除低饱和度）

### 问题3：PnP INVALID

**现象**：`PnP: INVALID`，终端显示失败原因

**可能原因**：
- 重投影误差过大：角点检测不准
- 距离不合理：Z值异常
- 数值无效：nan/inf

**解决**：
1. 检查角点P1-P4是否正确标注在灯带四角
2. 重新标定HSV，提高检测精度
3. 检查灯带尺寸 `LIGHT_LENGTH` 和 `LIGHT_WIDTH` 是否准确

### 问题4：角点顺序混乱

**现象**：P1不在左上，或角点跳变

**原因**：几何特征不稳定

**解决**：
1. 确保检测到完整的灯带轮廓
2. 提高 `MIN_RECTANGULARITY`
3. 调整形态学kernel大小

---

## 🔧 参数调优指南

### core/config.py 关键参数

```python
# 1. HSV范围（最重要！）
HSV_LOWER_RED1 = np.array([0, 80, 200])    # 提高S_min排除白色
HSV_UPPER_RED1 = np.array([20, 255, 255])

# 2. 亮度阈值
BRIGHTNESS_THRESHOLD = 240  # 过曝中心检测

# 3. 候选筛选
MIN_CONTOUR_AREA = 500      # 太小会误检噪点
MAX_CONTOUR_AREA = 50000    # 太大会检测到大片区域

MIN_ASPECT_RATIO = 8.0      # 灯带应该很细长
MIN_RECTANGULARITY = 0.6    # 灯带应该接近矩形

# 4. 方向约束
EXPECTED_ANGLE = 90.0       # 竖直方向
ANGLE_TOLERANCE = 35.0      # 允许偏差

# 5. 候选评分
MIN_CANDIDATE_SCORE = 0.4   # 提高可减少误检

# 6. PnP验证
MAX_REPROJECTION_ERROR = 5.0  # 重投影误差阈值
MIN_DISTANCE = 0.1            # 最小距离
MAX_DISTANCE = 5.0            # 最大距离
```

---

## 📊 DEBUG模式

在 `core/config.py` 中启用：

```python
DEBUG = True                # 打印详细信息
DEBUG_SHOW_MASKS = True     # 显示中间mask
DEBUG_SHOW_CANDIDATES = True # 显示所有候选
```

启用后，终端会打印：
- 每个候选的详细特征
- 角点坐标
- PnP中间结果
- 重投影误差细节

---

## 📝 总结

重构后的系统特点：

✅ **过曝处理** - 红色光晕+高亮中心联合检测  
✅ **候选评分** - 综合几何、亮度、颜色多维度评分  
✅ **角点规范** - 严格TL→TR→BR→BL顺序  
✅ **PnP验证** - 重投影误差+距离合理性检查  
✅ **真实内参** - D435i RGB自动读取  
✅ **调试友好** - 详细的终端输出和可视化  

---

**祝你使用顺利！** 🎉

如有问题，检查：
1. HSV参数是否正确标定
2. 灯带尺寸是否准确测量
3. DEBUG模式下的终端输出
