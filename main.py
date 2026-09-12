"""
主程序 - 基于D435i RGB的灯带识别与目标位移解算

流程：
D435i RGB → 灯带检测 → 角点提取 → PnP位姿估计 → 位移计算 → 显示
"""
import cv2
import numpy as np
import os
from datetime import datetime

from camera_realsense import RealSenseCamera
from detector import LightDetector
from geometry import GeometryProcessor
from pose import PoseEstimator
from config import Config


class LightTrackingSystem:
    """灯带跟踪系统主类（D435i RGB版本）"""

    def __init__(self):
        """初始化系统"""
        # 初始化相机
        self.camera = RealSenseCamera()

        # 初始化检测器和几何处理器
        self.detector = LightDetector()
        self.geometry = GeometryProcessor()

        # 位姿估计器（稍后用真实内参初始化）
        self.pose_estimator = None

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
        # 打开D435i相机
        if not self.camera.open():
            print("\n程序退出")
            return

        # 获取D435i RGB真实内参
        try:
            camera_matrix, dist_coeffs = self.camera.get_camera_params()
            self.pose_estimator = PoseEstimator(camera_matrix, dist_coeffs)
        except Exception as e:
            print(f"\n❌ 无法获取相机内参: {e}")
            self.camera.release()
            return

        print("\n" + "="*60)
        print("  D435i RGB 灯带跟踪系统已启动")
        print("="*60)
        print("\n操作说明：")
        print("  按 'q' - 退出程序")
        print("  按 's' - 保存当前帧到 results/ 目录")
        print("  按 'r' - 重置初始位置")
        print("="*60 + "\n")

        frame_count = 0

        try:
            while True:
                # 读取RGB图像
                ret, color_frame = self.camera.read()
                if not ret:
                    print("❌ 无法读取RGB图像")
                    break

                frame_count += 1

                # 处理图像
                result_frame = self.process_frame(color_frame)

                # 显示结果
                cv2.imshow("Light Tracking (D435i RGB Only)", result_frame)

                # 键盘控制
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n退出程序")
                    break
                elif key == ord('s'):
                    self.save_frame(result_frame, frame_count)
                elif key == ord('r'):
                    self.reset_initial_pose()
                    print("✅ 已重置初始位置")

        finally:
            # 清理资源
            self.camera.release()
            cv2.destroyAllWindows()

    def process_frame(self, frame):
        """
        处理单帧图像

        Args:
            frame: 输入彩色图像帧

        Returns:
            result_frame: 处理后的图像（带标注）
        """
        # 1. 灯带检测（分离红蓝）
        light_objects, debug_info = self.detector.detect(frame)

        # 创建结果图像
        result_frame = frame.copy()

        # 如果没有检测到灯带
        if len(light_objects) == 0:
            cv2.putText(result_frame, "No light detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(result_frame, "Tip: Adjust HSV in config.py", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)
            return result_frame

        if Config.DEBUG:
            print(f"\n[帧 {id(frame)}] 检测到 {len(light_objects)} 个灯带")

        # 2. 提取灯带角点
        for idx, light_obj in enumerate(light_objects):
            contour = light_obj["contour"]
            color_label = light_obj["color"]

            if Config.DEBUG:
                area = cv2.contourArea(contour)
                print(f"\n灯带 {idx+1} ({color_label}):")
                print(f"  面积: {area:.1f}")

            # 矩形拟合
            rect, box = self.geometry.fit_rectangle(contour)

            if Config.DEBUG:
                width, height = rect[1]
                aspect_ratio = max(width, height) / (min(width, height) + 1e-6)
                print(f"  外接矩形: {width:.1f} × {height:.1f}")
                print(f"  长宽比: {aspect_ratio:.2f}")

            # 角点排序（严格按 TL, TR, BR, BL）
            corners = self.geometry.sort_corners(box)

            # 绘制旋转矩形框
            box_draw = np.intp(box)
            cv2.drawContours(result_frame, [box_draw], 0, (0, 255, 0), 2)

            # 绘制角点（明确标注 P1-P4）
            corner_labels = ["P1(TL)", "P2(TR)", "P3(BR)", "P4(BL)"]
            for i, (corner, label) in enumerate(zip(corners, corner_labels)):
                pt = tuple(corner.astype(int))
                cv2.circle(result_frame, pt, 6, (0, 0, 255), -1)
                cv2.putText(result_frame, label, (pt[0] + 10, pt[1] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

            # 3. 姿态估计（单灯带PnP）
            success, rvec, tvec = self.pose_estimator.estimate_pose_single_light(corners)

            if success:
                # 保存当前位姿
                self.current_rvec = rvec
                self.current_tvec = tvec

                # 如果是第一次检测，设置初始位姿
                if self.initial_tvec is None:
                    self.initial_tvec = tvec.copy()
                    self.initial_rvec = rvec.copy()
                    print("\n✅ 已设置初始位置")

                # 4. 计算位移
                dx, dy, dz, distance = self.pose_estimator.calculate_displacement(
                    self.initial_tvec, self.current_tvec
                )

                # 5. 计算欧拉角
                roll, pitch, yaw = self.pose_estimator.rotation_vector_to_euler(rvec)

                if Config.DEBUG:
                    print(f"\n[姿态]")
                    print(f"  Roll  = {roll:.2f}°")
                    print(f"  Pitch = {pitch:.2f}°")
                    print(f"  Yaw   = {yaw:.2f}°")
                    print(f"\n[位移]")
                    print(f"  dX = {dx:.3f} m")
                    print(f"  dY = {dy:.3f} m")
                    print(f"  dZ = {dz:.3f} m")
                    print(f"  Distance = {distance:.3f} m")

                # 6. 绘制坐标轴
                result_frame = self.pose_estimator.draw_axis(result_frame, rvec, tvec, length=0.1)

                # 7. 显示信息
                self.display_info(result_frame, tvec, dx, dy, dz, distance,
                                 roll, pitch, yaw, len(light_objects))

                # 只处理第一个检测到的灯带
                break

        return result_frame

    def display_info(self, frame, tvec, dx, dy, dz, distance, roll, pitch, yaw, num_lights):
        """
        在图像上显示位姿信息

        Args:
            frame: 图像
            tvec: 平移向量
            dx, dy, dz: 位移
            distance: 总位移距离
            roll, pitch, yaw: 欧拉角
            num_lights: 检测到的灯带数量
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 255, 255)
        thickness = 1
        line_height = 20
        x_offset = 10
        y_offset = 25

        # 显示检测到的灯带数量
        cv2.putText(frame, f"Detected Lights: {num_lights}", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        # 显示当前位置
        cv2.putText(frame, f"Position:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  X = {tvec[0, 0]:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Y = {tvec[1, 0]:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Z = {tvec[2, 0]:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height + 5

        # 显示位移
        cv2.putText(frame, f"Displacement:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dX = {dx:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dY = {dy:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  dZ = {dz:+.3f} m", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Distance = {distance:.3f} m", (x_offset, y_offset),
                   font, font_scale, (0, 255, 0), thickness)
        y_offset += line_height + 5

        # 显示姿态角度
        cv2.putText(frame, f"Orientation:", (x_offset, y_offset),
                   font, font_scale, (255, 255, 255), thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Roll  = {roll:+.2f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Pitch = {pitch:+.2f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)
        y_offset += line_height

        cv2.putText(frame, f"  Yaw   = {yaw:+.2f} deg", (x_offset, y_offset),
                   font, font_scale, color, thickness)

    def save_frame(self, frame, frame_count):
        """
        保存当前帧

        Args:
            frame: 要保存的图像
            frame_count: 帧编号
        """
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
    print("  Intel RealSense D435i 灯带识别与目标位移解算系统")
    print("  Light Detection and Pose Estimation with D435i RGB")
    print("="*60)
    print("\n说明：")
    print("  - 使用 D435i RGB 彩色相机")
    print("  - 不使用深度信息")
    print("  - 通过 PnP 算法估计位姿")
    print("  - 距离由 灯带尺寸 + RGB图像 + 相机内参 计算")
    print("="*60)

    # 创建系统实例
    system = LightTrackingSystem()

    # 运行系统
    system.run()

    print("\n程序已正常退出")


if __name__ == "__main__":
    main()
