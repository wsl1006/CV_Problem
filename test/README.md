# 工具与测试

从项目根目录运行：

```bash
python -m test.hsv_tuner_realsense       # 现场调整红灯 HSV
python -m test.calibrate_distance_scale 1.00:1.09 1.30:1.42 1.60:1.73
python -m test.test_realsense           # 检查相机彩色与深度流
python -m unittest test.test_optimizations
```

正常使用运行 `python main_rgb.py`。D435i 的 RGB 内参由程序自动读取，不需要手工棋盘格标定。
