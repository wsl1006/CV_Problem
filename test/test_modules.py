"""
模块测试脚本 - 验证所有模块是否正常工作
"""
import sys
import numpy as np
print("正在测试各个模块...\n")

try:
    print("1. 测试 core.config...")
    from core.config import Config
    print("   ✓ Config 模块导入成功")
    print(f"   - 灯带长度: {Config.LIGHT_LENGTH}m")
    print(f"   - 灯带中心距: {Config.LIGHT_SPACING}m")

    print("\n2. 测试 core.camera_realsense...")
    from core.camera_realsense import RealSenseCamera
    print("   ✓ RealSenseCamera 模块导入成功")

    print("\n3. 测试 core.detector...")
    from core.detector import LightDetector
    print("   ✓ LightDetector 模块导入成功")
    detector = LightDetector()
    print(f"   - LightDetector 对象创建成功")

    print("\n4. 测试 core.geometry...")
    from core.geometry import GeometryProcessor
    print("   ✓ GeometryProcessor 模块导入成功")
    geometry = GeometryProcessor()
    print(f"   - GeometryProcessor 对象创建成功")

    print("\n5. 测试 core.pose...")
    from core.pose import PoseEstimator
    print("   ✓ PoseEstimator 模块导入成功")
    camera_matrix = np.array([[600.0, 0.0, 320.0], [0.0, 600.0, 240.0], [0.0, 0.0, 1.0]])
    pose_estimator = PoseEstimator(camera_matrix, np.zeros(5))
    print(f"   - PoseEstimator 对象创建成功")

    print("\n6. 测试 core.main_rgb...")
    from core.main_rgb import LightTrackingSystem
    print("   ✓ LightTrackingSystem 模块导入成功")

    print("\n" + "="*50)
    print("✓ 所有模块测试通过！")
    print("="*50)
    print("\n可以运行 'python main_rgb.py' 启动系统")

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
