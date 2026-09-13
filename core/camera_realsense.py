"""
RealSense D435i 相机模块 - 重构版
核心改进：
1. 真实RGB内参自动读取
2. 详细的相机信息打印
3. 只使用RGB流（不使用深度）
"""
import pyrealsense2 as rs
import numpy as np


class RealSenseCamera:
    """Intel RealSense D435i 相机类 - 仅RGB模式"""

    def __init__(self):
        """初始化RealSense相机"""
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # 相机内参（从D435i RGB读取）
        self.camera_matrix = None
        self.dist_coeffs = None

        # 相机信息
        self.width = 0
        self.height = 0
        self.fps = 0

        self.is_opened = False

    def open(self):
        """
        打开RealSense D435i，启动RGB彩色流

        Returns:
            bool: 是否成功打开
        """
        try:
            print("\n" + "="*60)
            print("正在初始化 Intel RealSense D435i (RGB Only)...")
            print("="*60)

            # 只启用RGB彩色流（640x480 @ 30fps）
            self.config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

            # 启动管道
            profile = self.pipeline.start(self.config)

            # 获取RGB彩色流的profile
            color_stream = profile.get_stream(rs.stream.color)
            color_profile = color_stream.as_video_stream_profile()
            intrinsics = color_profile.get_intrinsics()

            # 保存分辨率和帧率
            self.width = intrinsics.width
            self.height = intrinsics.height
            self.fps = color_profile.fps()

            # 从D435i RGB相机读取真实内参
            fx = intrinsics.fx
            fy = intrinsics.fy
            cx = intrinsics.ppx
            cy = intrinsics.ppy

            # 转换为OpenCV格式的相机内参矩阵
            self.camera_matrix = np.array([
                [fx,  0,  cx],
                [0,   fy, cy],
                [0,   0,   1]
            ], dtype=np.float32)

            # 读取真实畸变参数
            # RealSense使用Brown-Conrady模型: [k1, k2, p1, p2, k3]
            self.dist_coeffs = np.array(intrinsics.coeffs[:5], dtype=np.float32)

            self.is_opened = True

            # 打印相机参数
            print("\n" + "="*60)
            print("✅ Intel RealSense D435i 已成功启动")
            print("="*60)
            print("\n📷 D435i RGB Camera Intrinsics:")
            print("-"*60)
            print(f"分辨率: {self.width} × {self.height}")
            print(f"帧率: {self.fps} FPS")
            print()
            print("内参矩阵 (Camera Matrix):")
            print(f"  fx = {fx:.2f}")
            print(f"  fy = {fy:.2f}")
            print(f"  cx = {cx:.2f}")
            print(f"  cy = {cy:.2f}")
            print()
            print("畸变系数 (Distortion Coefficients):")
            print(f"  k1 = {intrinsics.coeffs[0]:.6f}")
            print(f"  k2 = {intrinsics.coeffs[1]:.6f}")
            print(f"  p1 = {intrinsics.coeffs[2]:.6f}")
            print(f"  p2 = {intrinsics.coeffs[3]:.6f}")
            print(f"  k3 = {intrinsics.coeffs[4]:.6f}")
            print("="*60 + "\n")

            return True

        except RuntimeError as e:
            print("\n" + "="*60)
            print("❌ 无法启动 RealSense D435i")
            print("="*60)
            print(f"错误信息: {e}")
            print()
            print("可能的原因：")
            print("  1. RealSense D435i 未连接")
            print("  2. USB连接不稳定（建议使用USB 3.0蓝色接口）")
            print("  3. 其他程序正在使用相机")
            print("  4. 需要更新RealSense驱动")
            print()
            print("排查方法：")
            print("  1. 运行: lsusb | grep Intel")
            print("  2. 运行: realsense-viewer（测试相机）")
            print("  3. 重新插拔USB线")
            print("="*60 + "\n")
            return False

        except Exception as e:
            print(f"\n❌ 启动相机时发生未知错误: {e}")
            return False

    def read(self):
        """
        读取一帧RGB图像

        Returns:
            ret (bool): 是否成功读取
            color_frame (np.ndarray): RGB图像
        """
        if not self.is_opened:
            return False, None

        try:
            # 等待新的帧
            frames = self.pipeline.wait_for_frames()

            # 获取彩色帧
            color_frame = frames.get_color_frame()

            if not color_frame:
                return False, None

            # 转换为numpy数组
            color_image = np.asanyarray(color_frame.get_data())

            return True, color_image

        except Exception as e:
            print(f"❌ 读取RGB图像失败: {e}")
            return False, None

    def release(self):
        """释放相机资源"""
        if self.pipeline:
            self.pipeline.stop()
            self.is_opened = False
            print("✅ RealSense D435i 已释放")

    def get_camera_params(self):
        """
        获取D435i RGB真实相机参数

        Returns:
            camera_matrix (np.ndarray): 相机内参矩阵
            dist_coeffs (np.ndarray): 畸变系数
        """
        if self.camera_matrix is None or self.dist_coeffs is None:
            raise RuntimeError("相机内参未初始化，请先调用 open() 方法")

        return self.camera_matrix, self.dist_coeffs

    def get_resolution(self):
        """
        获取相机分辨率

        Returns:
            width (int): 宽度
            height (int): 高度
        """
        return self.width, self.height
