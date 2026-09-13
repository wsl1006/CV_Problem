"""
模块测试脚本 - 验证所有模块是否正常工作
"""
import sys
print("正在测试各个模块...\n")

try:
    print("1. 测试 core.config...")
    from core.config import Config
    print("   ✓ Config 模块导入成功")
    print(f"   - 相机内参矩阵: {Config.CAMERA_MATRIX.shape}")
    print(f"   - 灯带长度: {Config.LIGHT_LENGTH}m")

    print("\n2. 测试 core.camera...")
    from core.camera import Camera
    print("   ✓ Camera 模块导入成功")
    camera = Camera()
    print(f"   - Camera 对象创建成功")

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
    pose_estimator = PoseEstimator(Config.CAMERA_MATRIX, Config.DIST_COEFFS)
    print(f"   - PoseEstimator 对象创建成功")

    print("\n6. 测试 main.py...")
    from main import LightTrackingSystem
    print("   ✓ LightTrackingSystem 模块导入成功")

    print("\n" + "="*50)
    print("✓ 所有模块测试通过！")
    print("="*50)
    print("\n可以运行 'python main.py' 启动系统")

except Exception as e:
    print(f"\n✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
