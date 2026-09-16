# 调试与测试脚本

从项目根目录以模块方式运行，确保能够导入 `core`：

```bash
python -m test.hsv_tuner_realsense
python -m test.test_realsense
python -m test.calibrate_camera
python -m test.test_system
```

多距离尺度标定（格式为“真实距离:程序 Range”）：

```bash
python -m test.calibrate_distance_scale 1.00:1.09 1.30:1.42 1.60:1.73 2.00:2.16
```

工具会给出建议的 `PNP_MODEL_SCALE` 和各测距点的残差。建议目标正对相机，
每个距离稳定后记录 20 帧左右的 Range 中位数，再作为程序读数输入。

正式运行灯条检测程序仍使用：

```bash
python main_rgb.py
```
