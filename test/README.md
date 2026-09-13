# 调试与测试脚本

从项目根目录以模块方式运行，确保能够导入 `core`：

```bash
python -m test.hsv_tuner_realsense
python -m test.test_realsense
python -m test.calibrate_camera
python -m test.test_system
```

正式运行灯条检测程序仍使用：

```bash
python main_rgb.py
```
