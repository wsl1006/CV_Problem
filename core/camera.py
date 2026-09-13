"""
相机模块 - 处理相机初始化和图像获取
"""
import cv2 # pyright: ignore[reportMissingImports]
import numpy as np # pyright: ignore[reportMissingImports]
from .config import Config


class Camera:
    """相机类，负责图像采集和相机参数管理"""

    def __init__(self, source=0):
        """
        初始化相机

        Args:
            source: 相机源，0表示默认摄像头，或者视频文件路径
        """
        self.source = source
        self.cap = None
        self.camera_matrix = Config.CAMERA_MATRIX
        self.dist_coeffs = Config.DIST_COEFFS
        self.is_opened = False

    def open(self):
        """打开相机"""
        try:
            if Config.USE_VIDEO_FILE and Config.VIDEO_PATH:
                self.cap = cv2.VideoCapture(Config.VIDEO_PATH)
            else:
                self.cap = cv2.VideoCapture(self.source)

            if self.cap.isOpened():
                self.is_opened = True
                print("相机已打开")
                return True
            else:
                print("无法打开相机")
                return False
        except Exception as e:
            print(f"打开相机时出错: {e}")
            return False

    def read(self):
        """
        读取一帧图像

        Returns:
            ret: 是否成功读取
            frame: 读取的图像帧
        """
        if not self.is_opened:
            return False, None

        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        """释放相机资源"""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False
            print("相机已释放")

    def get_camera_params(self):
        """
        获取相机参数

        Returns:
            camera_matrix: 相机内参矩阵
            dist_coeffs: 畸变系数
        """
        return self.camera_matrix, self.dist_coeffs

    def undistort_image(self, image):
        """
        对图像进行畸变校正

        Args:
            image: 输入图像

        Returns:
            校正后的图像
        """
        h, w = image.shape[:2]
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
            self.camera_matrix, self.dist_coeffs, (w, h), 1, (w, h)
        )

        # 执行畸变校正
        undistorted = cv2.undistort(
            image, self.camera_matrix, self.dist_coeffs,
            None, new_camera_matrix
        )

        return undistorted
