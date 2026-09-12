# 题目一：灯带识别与目标位移解算 - 项目完成报告

## 📋 项目概述

本项目完成了**题目一：基于OpenCV的灯带识别与自标位移解算**的全部要求，实现了一个完整的计算机视觉系统，能够：
- 识别场景中的灯带目标
- 估计目标的3D位姿
- 计算目标的位移信息

---

## ✅ 完成情况

### 任务要求对照表

| 任务 | 要求 | 完成状态 |
|------|------|---------|
| **(1) 灯带识别** | 使用OpenCV进行图像处理，识别并提取细长灯带 | ✅ 已完成 |
| **(2) 矩形拟合与角点提取** | 对识别的灯带进行矩形拟合，获得旋转矩形的4个角点 | ✅ 已完成 |
| **(3) 建立目标三维模型** | 根据灯带实际尺寸建立三维角点坐标系 | ✅ 已完成 |
| **(4) 目标位姿解算** | 使用cv2.solvePnP()求解旋转向量rvec和平移向量tvec | ✅ 已完成 |
| **(5) 目标位移计算** | 连续获取目标位置并通过位置差异获取位移 | ✅ 已完成 |

### 输出要求对照表

| 输出项 | 要求 | 完成状态 |
|--------|------|---------|
| 1. 原始相机图像 | 实时显示 | ✅ |
| 2. 检测得到的灯带 | 绿色框标注 | ✅ |
| 3. 旋转矩形框 | 红色框标注 | ✅ |
| 4. 灯带的4个角点 | P1-P4标注 | ✅ |
| 5. 当前目标位置 | X, Y, Z (米) | ✅ |
| 6. 目标位移 | dX, dY, dZ, Distance (米) | ✅ |

---

## 📁 项目文件结构

```
CV_Problem/
├── main.py                  # 主程序入口
├── camera.py                # 相机模块
├── detector.py              # 灯带检测模块
├── geometry.py              # 几何计算模块
├── pose.py                  # 姿态估计模块
├── config.py                # 配置文件
├── calibrate_camera.py      # 相机标定辅助工具
├── test_modules.py          # 模块测试脚本
├── requirements.txt         # Python依赖
├── README.md                # 项目说明文档
├── USAGE.txt                # 使用指南
├── PROJECT_SUMMARY.md       # 本文件（项目总结）
├── data/                    # 数据目录
└── results/                 # 结果保存目录
```

---

## 🔧 技术实现细节

### 1. 灯带识别 (detector.py)

**实现方法：**
- BGR → HSV 颜色空间转换
- 颜色阈值分割（支持红色和蓝色灯带）
- 形态学操作：闭运算（填充孔洞）+ 开运算（去除噪声）
- 轮廓检测：`cv2.findContours()`
- 轮廓筛选：根据面积和长宽比过滤

**关键代码：**
```python
# HSV阈值分割
mask = cv2.inRange(hsv, lower_bound, upper_bound)

# 形态学操作
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

# 轮廓检测
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
```

### 2. 矩形拟合与角点提取 (geometry.py)

**实现方法：**
- 最小外接旋转矩形：`cv2.minAreaRect()`
- 获取矩形4个角点：`cv2.boxPoints()`
- 角点排序：按左上、右上、右下、左下顺序

**关键代码：**
```python
# 获取旋转矩形
rect = cv2.minAreaRect(contour)
box = cv2.boxPoints(rect)

# 角点排序
sorted_corners = self.sort_corners(box)
```

### 3. 三维模型建立 (geometry.py)

**实现方法：**
- 根据灯带物理尺寸（长度L、宽度W）定义3D坐标
- 世界坐标系：以灯带中心为原点，Z=0平面

**3D模型示例：**
```python
object_points = np.array([
    [-L/2, -W/2, 0],  # 左上
    [L/2, -W/2, 0],   # 右上
    [L/2, W/2, 0],    # 右下
    [-L/2, W/2, 0]    # 左下
], dtype=np.float32)
```

### 4. 位姿解算 (pose.py)

**实现方法：**
- 使用PnP算法：`cv2.solvePnP()`
- 输入：2D图像点、3D世界点、相机内参、畸变系数
- 输出：旋转向量rvec、平移向量tvec

**关键代码：**
```python
success, rvec, tvec = cv2.solvePnP(
    object_points,      # 3D点
    image_points,       # 2D点
    camera_matrix,      # 内参
    dist_coeffs,        # 畸变
    flags=cv2.SOLVEPNP_ITERATIVE
)
```

**旋转向量转欧拉角：**
```python
rmat, _ = cv2.Rodrigues(rvec)
roll = np.arctan2(rmat[2, 1], rmat[2, 2])
pitch = np.arctan2(-rmat[2, 0], sy)
yaw = np.arctan2(rmat[1, 0], rmat[0, 0])
```

### 5. 位移计算 (pose.py)

**实现方法：**
- 保存初始位置tvec_initial
- 计算当前位置与初始位置的差值

**关键代码：**
```python
dx = tvec_curr[0, 0] - tvec_initial[0, 0]
dy = tvec_curr[1, 0] - tvec_initial[1, 0]
dz = tvec_curr[2, 0] - tvec_initial[2, 0]
distance = np.sqrt(dx**2 + dy**2 + dz**2)
```

---

## 🎯 核心功能演示

### 运行主程序
```bash
python main.py
```

### 程序界面显示内容
1. **实时视频流**：显示相机捕获的图像
2. **检测标注**：
   - 绿色矩形框：检测到的灯带轮廓
   - 红色矩形框：最小外接旋转矩形
   - 红色圆点：矩形的4个角点（P1-P4）
3. **坐标轴可视化**：
   - 红色箭头：X轴
   - 绿色箭头：Y轴
   - 蓝色箭头：Z轴
4. **文字信息**：
   - 检测到的灯带数量
   - 当前位置 (X, Y, Z)
   - 相对位移 (dX, dY, dZ)
   - 总位移距离

### 交互操作
- **按 'q'**：退出程序
- **按 's'**：保存当前帧到results/目录
- **按 'r'**：重置初始位置

---

## 🛠️ 使用说明

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 相机标定（重要！）
```bash
python calibrate_camera.py
```
- 使用棋盘格标定板
- 至少拍摄10张不同角度的图像
- 获得相机内参和畸变系数
- 将结果复制到config.py

### 3. 配置参数
编辑 `config.py`：
- 填入相机内参矩阵和畸变系数
- 设置灯带物理尺寸（米）
- 根据灯带颜色调整HSV阈值

### 4. 运行程序
```bash
python main.py
```

---

## 📊 测试验证

### 模块测试
```bash
python test_modules.py
```
结果：✅ 所有模块测试通过

---

## 🔍 算法流程图

```
输入图像
    ↓
[1. 灯带识别]
├─ HSV颜色空间转换
├─ 阈值分割
├─ 形态学操作
└─ 轮廓检测与筛选
    ↓
[2. 矩形拟合与角点提取]
├─ 最小外接旋转矩形
└─ 提取并排序4个角点
    ↓
[3. 建立3D模型]
└─ 根据物理尺寸定义3D坐标
    ↓
[4. PnP位姿解算]
├─ 匹配2D-3D点对
└─ 求解rvec和tvec
    ↓
[5. 位移计算]
├─ 计算dX, dY, dZ
└─ 计算总位移距离
    ↓
可视化输出
```

---

## 📝 关键算法说明

### PnP (Perspective-n-Point) 算法
**目的**：已知n个3D点及其在图像中的2D投影，求解相机位姿

**输入：**
- N个3D点：P_i^w = [X_i, Y_i, Z_i] (世界坐标系)
- N个2D点：p_i = [u_i, v_i] (图像坐标系)
- 相机内参矩阵K
- 畸变系数D

**输出：**
- 旋转向量rvec（3×1）
- 平移向量tvec（3×1）

**数学模型：**
```
s * [u, v, 1]^T = K * [R | t] * [X, Y, Z, 1]^T
```
其中：
- s：尺度因子
- K：相机内参矩阵
- R：旋转矩阵（由rvec转换而来）
- t：平移向量tvec

---

## 🎓 项目亮点

1. ✅ **完整实现了所有要求**：从检测到位姿估计到位移计算
2. ✅ **模块化设计**：各功能独立封装，便于维护和扩展
3. ✅ **实时可视化**：直观显示检测结果和位姿信息
4. ✅ **辅助工具**：提供相机标定工具，降低使用门槛
5. ✅ **详细文档**：包含README、使用指南和代码注释
6. ✅ **可配置性强**：参数集中管理，易于调整

---

## 🚀 可能的改进方向

1. **多灯带联合估计**：使用多条灯带的角点进行联合PnP求解，提高精度
2. **卡尔曼滤波**：对位姿估计结果进行滤波，减少抖动
3. **轨迹记录**：记录目标运动轨迹并可视化
4. **视频文件支持**：支持读取视频文件进行离线分析
5. **自动HSV调参**：通过交互式界面调整HSV阈值
6. **性能优化**：使用多线程或GPU加速

---

## 📚 参考资料

- OpenCV官方文档：https://docs.opencv.org/
- PnP算法：https://en.wikipedia.org/wiki/Perspective-n-Point
- 相机标定：Zhang's Method

---

## 👨‍💻 开发信息

- **开发日期**：2026-09-11
- **编程语言**：Python 3.14
- **主要库**：OpenCV 5.0, NumPy 2.5
- **测试状态**：✅ 所有模块通过测试

---

## 📧 联系方式

如有问题或建议，欢迎提交Issue或Pull Request。

---

**项目完成度：100%** ✅
