"""
主程序（RealSense版本） - 基于RealSense的灯带识别与目标位移解算
"""
import cv2
import numpy as np
import os
from datetime import datetime

from core.camera_realsense import RealSenseCamera
from core.detector import LightDetector
from core.geometry import GeometryProcessor
from core.pose import PoseEstimator
from core.config import Config


class LightTrackingSystemRealSense:
    """灯带跟踪系统主类（RealSense版本）"""

    def __init__(self):
        """初始化系统"""
        # 初始化各模块
        self.camera = RealSenseCamera()
        self.detector = LightDetector()
        self.geometry = GeometryProcessor()

        # 获取相机参数
        camera_matrix, dist_coeffs = self.camera.get_camera_params()
        self.pose_estimator = PoseEstimator(camera_matrix, dist_coeffs)

        # 初始位姿（用于计算位移）
        self.initial_tvec = None
        self.initial_rvec = None

        # 当前位姿
        self.current_tvec = None
        self.current_rvec = None

        # 创建结果保存目录
        if Config.SAVE_RESULTS:
            os.makedirs(Config.RESULTS_PATH, exist_ok=True)

    def run(self):
        """运行主循环"""
        # 打开相机
        if not self.camera.open():
            print("无法打开RealSense相机，程序退出")
            return

        # 更新相机参数（RealSense会自动提供准确的内参）
        camera_matrix, dist_coeffs = self.camera.get_camera_params()
        self.pose_estimator = PoseEstimator(camera_matrix, dist_coeffs)

        print("\n=== RealSense 灯带跟踪系统已启动 ===")
        print("按 'q' 退出")
        print("按 's' 保存当前帧")
        print("按 'r' 重置初始位置")
        print("按 'd' 显示深度图")
        print("=" * 40 + "\n")

        frame_count = 0
        show_depth = False

        try:
            while True:
                # 读取图像（彩色 + 深度）
                ret, color_frame, depth_frame = self.camera.read()
                if not ret:
                    print("无法读取图像")
                    break

                frame_count += 1

                # 处理图像
                result_frame = self.process_frame(color_frame, depth_frame)

                # 显示结果
                cv2.imshow("RealSense Light Tracking", result_frame)

                # 显示深度图（可选）
                if show_depth and depth_frame is not None:
                    depth_colormap = cv2.applyColorMap(
                        cv2.convertScaleAbs(depth_frame, alpha=0.03),
                        cv2.COLORMAP_JET
                    )
                    cv2.imshow("Depth", depth_colormap)

                # 键盘控制
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("退出程序")
                    break
                elif key == ord('s'):
                    self.save_frame(result_frame, frame_count)
                elif key == ord('r'):
                    self.reset_initial_pose()
                    print("已重置初始位置")
                elif key == ord('d'):
                    show_depth = not show_depth
                    if not show_depth:
                        cv2.destroyWindow("Depth")

        finally:
            # 清理资源
            self.camera.release()
            cv2.destroyAllWindows()

    def process_frame(self, frame, depth_frame=None):
        """
        处理单帧图像

        Args:
            frame: 输入彩色图像帧
            depth_frame: 深度图像帧（可选）

        Returns:
            result_frame: 处理后的图像（带标注）
        """
        # 1. 灯带检测
        contours, mask = self.detector.detect(frame)

        # 创建结果图像
        result_frame = frame.copy()

        # 如果没有检测到灯带
        if len(contours) == 0:
            cv2.putText(result_frame, "No light detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(result_frame, "Adjust HSV values in config.py", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
            return result_frame

        # 2. 提取灯带角点
        all_corners = []
        for contour in contours:
            rect, box = self.geometry.fit_rectangle(contour)
            corners = self.geometry.sort_corners(box)
            all_corners.append(corners)

            # 绘制旋转矩形框
            cv2.drawContours(result_frame, [box], 0, (0, 255, 0), 2)

            # 绘制角点
            for i, corner in enumerate(corners):
                cv2.circle(result_frame, tuple(corner.astype(int)), 5, (0, 0, 255), -1)
                cv2.putText(result_frame, f"P{i+1}", tuple(corner.astype(int) + 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

                # 如果有深度信息，显示深度值
                if depth_frame is not None:
                    x, y = corner.astype(int)
                    depth = self.camera.get_depth_at_point(depth_frame, x, y)
                    if depth is not None and depth > 0:
                        cv2.putText(result_frame, f"{depth:.2f}m",
                                   tuple(corner.astype(int) + np.array([10, 25])),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # 3. 姿态估计
        if len(all_corners) > 0:
            # 使用第一条检测到的灯带进行姿态估计
            success, rvec, tvec = self.pose_estimator.estimate_pose_single_light(all_corners[0])

            if success:
                # 保存当前位姿
                self.current_rvec = rvec
                self.current_tvec = tvec

                # 如果是第一次检测，设置初始位姿
                if self.initial_tvec is None:
                    self.initial_tvec = tvec.copy()
                    self.initial_rvec = rvec.copy()

                # 4. 计算位移
                dx, dy, dz, distance = self.pose_estimator.calculate_displacement(
                    self.initial_tvec, self.current_tvec
                )

                # 5. 计算欧拉角
                roll, pitch, yaw = self.pose_estimator.rotation_vector_to_euler(rvec)

                # 6. 绘制坐标轴
                result_frame = self.pose_estimator.draw_axis(result_frame, rvec, tvec)

                # 7. 显示信息
                self.display_info(result_frame, tvec, dx, dy, dz, distance, roll, pitch, yaw, len(contours))

        return result_frame

    def display_info(self, frame, tvec, dx, dy, dz, distance, roll, pitch, yaw, num_lights):
        """在图像上显示位姿信息"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        color = (0, 255, 255)
        thickness = 2
        line_height = 25
        x_offset = 10
        y_offset = 30

        # 显示检测到的灯带数量
        cv2.putText(frame, f"Lights: {num_lights}", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        # 显示当前位置
        cv2.putText(frame, f"Position:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  X = {tvec[0, 0]:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Y = {tvec[1, 0]:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Z = {tvec[2, 0]:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height + 10

        # 显示位移
        cv2.putText(frame, f"Displacement:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dX = {dx:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dY = {dy:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dZ = {dz:.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Dist = {distance:.3f} m", (x_offset, y_offset),
                   font, font_scale, (0, 255, 0), thickness)
        y_offset += line_height + 10

        # 显示姿态角度
        cv2.putText(frame, f"Orientation:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Roll  = {roll:.1f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Pitch = {pitch:.1f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Yaw   = {yaw:.1f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)

    def save_frame(self, frame, frame_count):
        """保存当前帧"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}_{frame_count}.jpg"
        filepath = os.path.join(Config.RESULTS_PATH, filename)
        cv2.imwrite(filepath, frame)
        print(f"✅ 已保存图像: {filepath}")

    def reset_initial_pose(self):
        """重置初始位姿"""
        self.initial_tvec = self.current_tvec.copy() if self.current_tvec is not None else None
        self.initial_rvec = self.current_rvec.copy() if self.current_rvec is not None else None


def main():
    """主函数"""
    print("\n" + "="*60)
    print("  RealSense 灯带识别与目标位移解算系统")
    print("  Light Detection with Intel RealSense")
    print("="*60 + "\n")

    # 创建系统实例
    system = LightTrackingSystemRealSense()

    # 运行系统
    system.run()

    print("\n程序已正常退出")


if __name__ == "__main__":
    main()
