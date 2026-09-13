#!/usr/bin/env python3
"""
快速验证脚本 - 测试重构后的系统
"""
import cv2
import numpy as np
import sys

print("="*70)
print("  验证重构后的灯条检测+配对+PnP系统")
print("="*70)

# 1. 检查依赖
print("\n1️⃣  检查Python依赖...")
try:
    import pyrealsense2 as rs
    import numpy as np
    import cv2
    print("✅ 所有依赖已安装")
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    sys.exit(1)

# 2. 检查文件
print("\n2️⃣  检查文件完整性...")
import os
files = ['core/config.py', 'core/detector.py', 'core/geometry.py', 'core/pose.py',
         'core/camera_realsense.py', 'core/main_rgb.py', 'main_rgb.py']
for f in files:
    if os.path.exists(f):
        print(f"  ✅ {f}")
    else:
        print(f"  ❌ {f} 缺失")
        sys.exit(1)

# 3. 测试导入
print("\n3️⃣  测试模块导入...")
try:
    from core.config import Config
    from core.detector import LightDetector, LightBarCandidate
    from core.geometry import GeometryProcessor
    from core.pose import PoseEstimator, PoseResult
    from core.camera_realsense import RealSenseCamera
    print("✅ 所有模块导入成功")
except Exception as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

# 4. 验证Config
print("\n4️⃣  验证配置参数...")
print(f"  灯带尺寸: {Config.LIGHT_LENGTH*1000:.1f}mm × {Config.LIGHT_WIDTH*1000:.1f}mm")
print(f"  通道差分阈值: {Config.RED_CHANNEL_DIFF_THRESHOLD}")
print(f"  最小长宽比: {Config.MIN_LIGHT_BAR_ASPECT_RATIO}")
print(f"  最小配对得分: {Config.MIN_PAIR_SCORE}")
print(f"  最大重投影误差: {Config.MAX_REPROJECTION_ERROR} px")
print("✅ 配置参数正常")

# 5. 测试几何模块
print("\n5️⃣  测试几何模块...")
geom = GeometryProcessor()
obj_points = geom.build_target_3d_model()
print(f"  3D模型点数: {len(obj_points)}")
print(f"  P1(TL): {obj_points[0]}")
print(f"  P4(BL): {obj_points[3]}")
print("✅ 几何模块正常")

print("\n" + "="*70)
print("  ✅ 系统验证通过！")
print("="*70)
print("\n📋 下一步:")
print("  运行主程序: python main_rgb.py")
print("\n  操作说明:")
print("    按 'q' - 退出")
print("    按 's' - 保存帧")
print("    按 'r' - 重置位置")
print("    按 'd' - 切换调试显示")
print("\n  详细说明: cat README_REFACTORED.md")
print("="*70)
