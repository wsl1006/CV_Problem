# 参数调优速查表

## 🎯 问题 → 参数对照表

| 问题现象 | 可能原因 | 调整参数 | 建议值 |
|---------|---------|---------|--------|
| **检测不到任何灯条** | 通道差分阈值太高 | `RED_CHANNEL_DIFF_THRESHOLD` | 30→20 |
| | 亮度阈值太高 | `BRIGHTNESS_THRESHOLD` | 200→150 |
| **检测到灯条但全被过滤** | 长宽比要求太严 | `MIN_LIGHT_BAR_ASPECT_RATIO` | 2.0→1.5 |
| | 矩形度要求太严 | `MIN_LIGHT_BAR_RECTANGULARITY` | 0.5→0.3 |
| | 亮度要求太高 | `MIN_LIGHT_BAR_BRIGHTNESS` | 150→100 |
| **误检白色物体** | 亮度阈值太低 | `MIN_LIGHT_BAR_BRIGHTNESS` | 150→180 |
| | 矩形度太低 | `MIN_LIGHT_BAR_RECTANGULARITY` | 0.5→0.7 |
| **灯条配对失败** | 配对得分阈值太高 | `MIN_PAIR_SCORE` | 0.5→0.3 |
| | 距离约束太严 | `MAX_PAIR_DISTANCE_RATIO` | 8.0→12.0 |
| | 垂直对齐太严 | `MAX_VERTICAL_OFFSET_RATIO` | 1.0→1.5 |
| **配对到错误的两个灯条** | 配对得分阈值太低 | `MIN_PAIR_SCORE` | 0.3→0.6 |
| | 需要调整权重 | `WEIGHT_*` | 根据实际调整 |
| **PnP重投影误差大** | 灯条检测不准 | 提高检测精度 | 先优化检测 |
| | 误差阈值太严 | `MAX_REPROJECTION_ERROR` | 8.0→10.0 |

---

## 🔧 快速调参流程

### Step 1: 确保能检测到灯条

**目标**: 终端显示 `检测到 N 个灯条候选`, N ≥ 2

**如果N=0**:
```python
# 降低检测阈值
RED_CHANNEL_DIFF_THRESHOLD = 20  # 从30降到20
BRIGHTNESS_THRESHOLD = 150        # 从200降到150
```

---

### Step 2: 确保灯条不被过滤

**目标**: 终端显示 `筛选后剩余 N 个有效灯条`, N ≥ 2

**如果N=0**，查看被过滤原因：
- 长宽比不满足 → 降低 `MIN_LIGHT_BAR_ASPECT_RATIO`
- 矩形度不满足 → 降低 `MIN_LIGHT_BAR_RECTANGULARITY`  
- 角度不满足 → 增大 `LIGHT_BAR_ANGLE_TOLERANCE`
- 亮度不满足 → 降低 `MIN_LIGHT_BAR_BRIGHTNESS`

---

### Step 3: 确保能配对成功

**目标**: 终端显示 `配对成功，得分: X.XXX`

**如果配对失败**:
```python
MIN_PAIR_SCORE = 0.3  # 从0.5降到0.3
```

开启配对调试:
```python
DEBUG_SHOW_PAIRS = True
```

查看所有配对尝试的得分，找到最高分配对失败的原因。

---

### Step 4: 验证PnP结果

**目标**: 窗口显示 `PnP: VALID`

**如果显示 INVALID**，查看失败原因：
- `重投影误差过大` → 检查角点位置是否正确
- `距离不合理` → 检查Z值是否异常

---

## 📊 典型场景参数

### 场景1: 近距离（<0.5m），灯条很亮

```python
RED_CHANNEL_DIFF_THRESHOLD = 40
BRIGHTNESS_THRESHOLD = 220
MIN_LIGHT_BAR_BRIGHTNESS = 180
MIN_LIGHT_BAR_ASPECT_RATIO = 3.0
MIN_PAIR_SCORE = 0.6
```

### 场景2: 远距离（>1m），灯条较小

```python
RED_CHANNEL_DIFF_THRESHOLD = 20
BRIGHTNESS_THRESHOLD = 150
MIN_LIGHT_BAR_AREA = 30          # 降低最小面积
MIN_LIGHT_BAR_ASPECT_RATIO = 1.5
MIN_PAIR_SCORE = 0.3
```

### 场景3: 复杂背景，误检多

```python
MIN_LIGHT_BAR_BRIGHTNESS = 180      # 提高亮度要求
MIN_LIGHT_BAR_RECTANGULARITY = 0.7  # 提高矩形度
MIN_LIGHT_BAR_ASPECT_RATIO = 3.0    # 提高长宽比
MIN_PAIR_SCORE = 0.6                # 提高配对得分
```

---

## 🎓 参数含义详解

### 通道差分

```python
RED_CHANNEL_DIFF_THRESHOLD = 30
```
- **作用**: 检测红色LED（R-G通道差）
- **原理**: 红色LED的R通道比G通道高
- **调整**: 值越小→检测越多（包括弱红色）

### 灯条长宽比

```python
MIN_LIGHT_BAR_ASPECT_RATIO = 2.0
```
- **作用**: 过滤不细长的物体
- **实际**: 灯条 260mm÷11mm ≈ 23.6
- **调整**: 值越大→越严格（只要很细长的）

### 矩形度

```python
MIN_LIGHT_BAR_RECTANGULARITY = 0.5
```
- **作用**: 轮廓面积 / 外接矩形面积
- **范围**: 0-1，完美矩形=1
- **调整**: 值越大→越接近矩形

### 配对距离比

```python
MAX_PAIR_DISTANCE_RATIO = 8.0
```
- **作用**: 两灯条中心距离 / 平均灯条长度
- **实际**: 如果灯条间距15cm，灯条长26cm，比值≈0.58
- **调整**: 根据实际目标几何结构

### 重投影误差

```python
MAX_REPROJECTION_ERROR = 8.0
```
- **作用**: PnP结果可信度检查
- **单位**: 像素
- **含义**: 3D点投影回2D的误差
- **经验**: <3px=优秀，<5px=良好，<8px=可接受

---

## 💡 调参技巧

1. **从宽松到严格**: 先让系统能检测到，再逐步提高要求
2. **一次调一个**: 不要同时改多个参数
3. **查看终端输出**: DEBUG=True时会打印详细信息
4. **使用'd'键**: 切换显示所有候选，直观看到哪些被检测/过滤
5. **保存好的帧**: 按's'保存，用于离线调试

### 时序稳定与响应速度

```python
POSE_EMA_ALPHA = 0.45
POSE_HOLD_FRAMES = 2
TRACK_ASSOCIATION_SIGMA = 0.75
```

- `POSE_EMA_ALPHA` 越大响应越快，越小数值越平滑；建议在 `0.35~0.70` 内调整。
- `POSE_HOLD_FRAMES` 只在短暂丢检时保留最近有效结果，超过该帧数立即失效。
- `TRACK_ASSOCIATION_SIGMA` 越小越偏向上一帧目标，车辆快速运动时不宜过小。

### 多距离尺度标定

目标正对相机，在多个距离各记录约 20 帧 Range 的中位数，然后运行：

```bash
python -m test.calibrate_distance_scale 1.00:读数 1.30:读数 1.60:读数 2.00:读数
```

将工具输出的 `PNP_MODEL_SCALE` 写回 `core/config.py`。如果修正后的 RMSE
仍超过约 3 cm，应检查 RGB 内参、灯条有效长度、中心距和轮廓端点完整性。

---

## ⚠️ 注意事项

1. **不要修改灯带尺寸**:
   ```python
   LIGHT_LENGTH = 0.26  # 必须是实际测量值
   LIGHT_WIDTH = 0.011  # 不要随意修改
   ```

2. **相机内参自动读取**: 不需要手动设置fx/fy

3. **PnP失败不一定是参数问题**: 可能是检测本身不准确

4. **重投影误差大**: 说明角点位置不准，应该优化检测而不是放宽阈值

---

快速保存本表，调参时随时查阅！
