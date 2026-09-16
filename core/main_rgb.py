"""
主程序 - RealSense D435i RGB 灯带检测系统
完全重构版：基于灯条检测+配对的完整算法
"""
import cv2
import numpy as np
import os
from datetime import datetime

from .camera_realsense import RealSenseCamera
from .detector import LightDetector
from .geometry import GeometryProcessor
from .pose import PoseEstimator
from .config import Config


class LightTrackingSystem:
    """灯带跟踪系统 - 完全重构版"""

    def __init__(self):
        """初始化系统"""
        self.camera = RealSenseCamera()
        self.detector = LightDetector()
        self.geometry = GeometryProcessor()
        self.pose_estimator = None
        self.measurement_panel = None
        self.processed_light_frame = None
        self.last_valid_pose_result = None
        self.last_displacement = None
        self.pose_missed_frames = 0

        # 初始位姿
        self.initial_tvec = None
        self.initial_rvec = None

        # 创建结果保存目录
        if Config.SAVE_RESULTS:
            os.makedirs(Config.RESULTS_PATH, exist_ok=True)

    def run(self):
        """运行主循环"""
        # 打开相机
        if not self.camera.open():
            print("❌ 无法打开相机，程序退出")
            return

        # 初始化位姿估计器（使用真实内参）
        camera_matrix, dist_coeffs = self.camera.get_camera_params()
        self.pose_estimator = PoseEstimator(camera_matrix, dist_coeffs)

        print("\n" + "="*70)
        print("  🚀 D435i RGB 灯条检测+配对+PnP 系统已启动")
        print("="*70)
        print("\n操作说明：")
        print("  按 'q' - 退出程序")
        print("  按 's' - 保存当前帧")
        print("  按 'r' - 重置初始位置")
        print("  按 'd' - 切换调试显示")
        print("="*70 + "\n")

        frame_count = 0
        show_debug = Config.DEBUG_SHOW_ALL_CANDIDATES

        try:
            while True:
                # 读取RGB图像
                ret, color_frame = self.camera.read()
                if not ret:
                    print("❌ 无法读取图像")
                    break

                frame_count += 1

                # 处理图像
                result_frame = self.process_frame(color_frame, show_debug)

                # 显示结果
                cv2.imshow("Light Bar Detection + Matching + PnP", result_frame)
                if self.processed_light_frame is not None:
                    cv2.imshow("Processed Light Bars", self.processed_light_frame)
                if Config.SHOW_MEASUREMENT_WINDOW and self.measurement_panel is not None:
                    cv2.imshow("Pose Measurement", self.measurement_panel)

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
                elif key == ord('d'):
                    show_debug = not show_debug
                    print(f"调试显示: {'开' if show_debug else '关'}")

        finally:
            self.camera.release()
            cv2.destroyAllWindows()

    def process_frame(self, frame, show_debug=True):
        """
        处理单帧图像

        Args:
            frame: 输入图像
            show_debug: 是否显示调试信息

        Returns:
            result_frame: 处理后的图像
        """
        # 1. 完整检测流程
        left_bar, right_bar, valid_candidates, debug_info = self.detector.detect(frame)

        # 显示使用红色目标图，检测和 PnP 仍使用上面的原始 frame，避免显示掩膜影响测量。
        if left_bar is not None and right_bar is not None:
            display_bars = [left_bar, right_bar]
        elif Config.DISPLAY_UNPAIRED_RED_CANDIDATES:
            display_bars = debug_info['all_candidates']
        else:
            display_bars = valid_candidates

        # 独立输出处理结果：仅保留已确认灯条，其他像素置黑。
        self.processed_light_frame = self._render_red_only_frame(
            frame, display_bars, debug_info['mask_red']
        )

        if Config.DISPLAY_RED_ONLY:
            result_frame = self.processed_light_frame.copy()
        else:
            result_frame = frame.copy()

        # 2. 可视化所有灯条候选
        if show_debug and Config.DISPLAY_ANNOTATIONS:
            self._draw_all_candidates(result_frame, valid_candidates)

        # 3. 如果没有配对成功
        if left_bar is None or right_bar is None:
            held = self._hold_last_pose(result_frame, "NO VALID LIGHT PAIR")
            if not held:
                self._update_measurement_panel(None, "NO VALID LIGHT PAIR")
            if Config.DISPLAY_ANNOTATIONS:
                message = "Target temporarily lost - holding pose" if held else \
                    "No valid light bar pair found"
                color = (0, 255, 255) if held else (0, 0, 255)
                cv2.putText(result_frame, message, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(result_frame, f"Candidates: {len(valid_candidates)}", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return result_frame

        if Config.DISPLAY_ANNOTATIONS:
            # 调试标注使用红色，保证不会改变纯红显示模式的颜色语义。
            self._draw_single_bar(result_frame, left_bar, "LEFT", (0, 0, 255))
            self._draw_single_bar(result_frame, right_bar, "RIGHT", (0, 0, 255))
            left_center = tuple(left_bar.center.astype(int))
            right_center = tuple(right_bar.center.astype(int))
            cv2.line(result_frame, left_center, right_center, (0, 0, 255), 2)

        # 6. PnP姿态估计（使用两条灯带中心线的4个端点）
        pose_result = self.pose_estimator.estimate_pose_two_bars(left_bar, right_bar)

        if pose_result.valid:
            self.pose_missed_frames = 0
            # 保存初始位姿
            if self.initial_tvec is None:
                self.initial_tvec = pose_result.tvec.copy()
                self.initial_rvec = pose_result.rvec.copy()
                print("\n✅ 已设置初始位置")

            # 计算位移
            dx, dy, dz, distance = self.pose_estimator.calculate_displacement(
                self.initial_tvec, pose_result.tvec
            )

            if Config.DISPLAY_ANNOTATIONS:
                # 仅在调试标注开启时绘制坐标轴和数值信息。
                result_frame = self.pose_estimator.draw_axis(
                    result_frame, pose_result.rvec, pose_result.tvec, length=0.1
                )
                self._display_pose_info(result_frame, pose_result, dx, dy, dz, distance)
            self._update_measurement_panel(
                pose_result, displacement=(dx, dy, dz, distance)
            )
            self.last_valid_pose_result = pose_result
            self.last_displacement = (dx, dy, dz, distance)
        else:
            held = self._hold_last_pose(
                result_frame, f"PnP INVALID: {pose_result.reason}"
            )
            if not held:
                self._update_measurement_panel(None, f"PnP INVALID: {pose_result.reason}")
            if Config.DISPLAY_ANNOTATIONS:
                status_text = "PnP: HOLD" if held else "PnP: INVALID"
                status_color = (0, 255, 255) if held else (0, 0, 255)
                cv2.putText(result_frame, status_text, (10, frame.shape[0] - 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                cv2.putText(result_frame, pose_result.reason, (10, frame.shape[0] - 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

        return result_frame

    def _hold_last_pose(self, frame, reason):
        """检测短暂丢失时保留最近一次有效数值，超过限度后清除跟踪状态。"""
        self.pose_missed_frames += 1
        can_hold = (
            self.last_valid_pose_result is not None and
            self.last_displacement is not None and
            self.pose_missed_frames <= Config.POSE_HOLD_FRAMES
        )
        if not can_hold:
            if self.pose_missed_frames == Config.POSE_HOLD_FRAMES + 1:
                self.last_valid_pose_result = None
                self.last_displacement = None
                if self.pose_estimator is not None:
                    self.pose_estimator.reset_tracking()
            return False

        hold_status = (
            f"HOLD {self.pose_missed_frames}/{Config.POSE_HOLD_FRAMES}: {reason}"
        )
        self._update_measurement_panel(
            self.last_valid_pose_result,
            status=hold_status,
            displacement=self.last_displacement
        )
        if Config.DISPLAY_ANNOTATIONS:
            dx, dy, dz, distance = self.last_displacement
            self._display_pose_info(
                frame, self.last_valid_pose_result, dx, dy, dz, distance
            )
        return True

    def _update_measurement_panel(self, pose_result, status=None, displacement=None):
        """更新独立的目标位置、位移与姿态数值窗口。"""
        panel = np.zeros((530, 500, 3), dtype=np.uint8)
        red = (0, 0, 255)
        font = cv2.FONT_HERSHEY_SIMPLEX

        cv2.putText(panel, "POSE MEASUREMENT", (24, 38), font, 0.85, red, 2)

        if status and pose_result is not None and pose_result.valid:
            cv2.putText(panel, status[:48], (24, 60), font, 0.38,
                       (0, 255, 255), 1)

        if pose_result is None or not pose_result.valid:
            message = status or "WAITING FOR TARGET"
            cv2.putText(panel, message[:34], (24, 92), font, 0.55, red, 1)
            self.measurement_panel = panel
            return

        if displacement is None:
            displacement = (0.0, 0.0, 0.0, 0.0)
        dx, dy, dz, distance = displacement
        range_m = float(np.sqrt(
            pose_result.x ** 2 + pose_result.y ** 2 + pose_result.z ** 2
        ))
        lines = [
            "Position:",
            f"X = {pose_result.x:.3f} m",
            f"Y = {pose_result.y:.3f} m",
            f"Z = {pose_result.z:.3f} m",
            "Displacement:",
            f"dX = {dx:.3f} m",
            f"dY = {dy:.3f} m",
            f"dZ = {dz:.3f} m",
            f"Distance = {distance:.3f} m",
            f"Range = {range_m:.3f} m",
            "Orientation:",
            f"Roll = {pose_result.roll:.2f} deg",
            f"Pitch = {pose_result.pitch:.2f} deg",
            f"Yaw = {pose_result.yaw:.2f} deg",
        ]
        y = 76
        for line in lines:
            is_heading = line.endswith(":")
            cv2.putText(
                panel, line, (28, y), font,
                0.62 if is_heading else 0.56, red, 2 if is_heading else 1
            )
            y += 32
        self.measurement_panel = panel

    def _render_red_only_frame(self, frame, bars, core_mask):
        """生成仅保留已确认红色灯条的显示图像。

        轮廓区域扩大后作为目标区域，只保留其中红色占优像素和高亮灯芯；
        灯芯虽然过曝为白色，显示时也映射为红色，因此背景不会残留白光干扰。
        """
        target_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        for bar in bars:
            cv2.drawContours(target_mask, [bar.contour], -1, 255, thickness=cv2.FILLED)

        if not bars:
            return np.zeros_like(frame)

        size = Config.DISPLAY_TARGET_DILATE_SIZE
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        target_mask = cv2.dilate(target_mask, kernel)

        b, g, r = cv2.split(frame)
        margin = Config.DISPLAY_RED_MARGIN
        red_pixels = ((r.astype(np.int16) > g.astype(np.int16) + margin) &
                      (r.astype(np.int16) > b.astype(np.int16) + margin))
        target_pixels = target_mask > 0
        # core_mask 只在目标区域内使用，排除窗户等其他白色高亮物。
        keep = (red_pixels | (core_mask > 0)) & target_pixels

        output = np.zeros_like(frame)
        # 使用原始最大亮度作为红色强度，使白色过曝灯芯也显示为亮红色。
        output[:, :, 2] = np.where(keep, np.maximum.reduce([b, g, r]), 0)
        return output

    def _draw_all_candidates(self, frame, candidates):
        """绘制所有灯条候选"""
        for i, bar in enumerate(candidates):
            # 绘制轮廓（黄色）
            cv2.drawContours(frame, [bar.contour], 0, (0, 255, 255), 1)

            # 绘制中心点
            center = tuple(bar.center.astype(int))
            cv2.circle(frame, center, 3, (0, 255, 255), -1)

            # 显示ID
            cv2.putText(frame, f"#{i+1}", (center[0] + 5, center[1] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    def _draw_single_bar(self, frame, bar, label, color):
        """
        绘制单条灯带的旋转矩形和4个角点

        题目要求：对每条灯带进行旋转矩形拟合，显示矩形框和4个角点

        Args:
            frame: 图像
            bar: LightBarCandidate
            label: 标签（"LEFT"或"RIGHT"）
            color: 颜色
        """
        # 1. 绘制旋转矩形（题目要求）- 使用更粗的线条
        box = np.intp(bar.box)
        cv2.drawContours(frame, [box], 0, color, 5)  # 线宽从3增加到5

        if Config.DEBUG:
            print(f"\n[Draw] {label}灯条矩形框:")
            print(f"  box坐标: {box}")

        # 2. 提取并绘制4个角点（题目要求）
        from .geometry import GeometryProcessor
        geom = GeometryProcessor()
        corners = geom.extract_bar_corners(bar)  # [TL, TR, BR, BL]

        corner_labels = ["TL", "TR", "BR", "BL"]
        corner_colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]

        for i, (corner, clabel, ccolor) in enumerate(zip(corners, corner_labels, corner_colors)):
            pt = tuple(corner.astype(int))
            cv2.circle(frame, pt, 8, ccolor, -1)  # 从6增加到8
            cv2.circle(frame, pt, 10, (255, 255, 255), 2)  # 从8增加到10
            cv2.putText(frame, f"{label[0]}_{clabel}", (pt[0] + 12, pt[1] - 12),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, ccolor, 2)  # 字体加大

        # RoboMaster 风格 PnP 实际使用的稳定特征：灯条中心线及其上下端点。
        top = tuple(bar.top.astype(int))
        bottom = tuple(bar.bottom.astype(int))
        cv2.line(frame, top, bottom, color, 2)
        for point, endpoint_label in ((top, "TOP"), (bottom, "BOTTOM")):
            cv2.circle(frame, point, 5, (255, 255, 255), -1)
            cv2.putText(frame, f"{label[0]}_{endpoint_label}",
                       (point[0] + 8, point[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # 3. 绘制灯条标签
        center = tuple(bar.center.astype(int))
        cv2.circle(frame, center, 8, color, -1)  # 中心点也加大
        cv2.putText(frame, label, (center[0] - 40, center[1] - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)  # 字体加大

    def _display_pose_info(self, frame, pose_result, dx, dy, dz, distance):
        """显示姿态信息"""
        h, w = frame.shape[:2]
        info_x = w - 300
        info_y = 30
        line_h = 22

        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 255, 0)
        thickness = 1

        # PnP状态
        cv2.putText(frame, "PnP: VALID", (info_x, info_y),
                   font, 0.7, (0, 255, 0), 2)
        info_y += line_h

        cv2.putText(frame, f"Reproj Err: {pose_result.reprojection_error:.2f} px",
                   (info_x, info_y), font, font_scale, color, thickness)
        info_y += line_h + 5

        # 位置（题目要求：X, Y, Z）
        cv2.putText(frame, "Position:", (info_x, info_y),
                   font, 0.6, (255, 255, 255), 2)
        info_y += line_h

        cv2.putText(frame, f"  X = {pose_result.x:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  Y = {pose_result.y:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  Z = {pose_result.z:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h + 5

        # 位移（题目要求：dX, dY, dZ, Distance）
        cv2.putText(frame, "Displacement:", (info_x, info_y),
                   font, 0.6, (255, 255, 255), 2)
        info_y += line_h

        cv2.putText(frame, f"  dX = {dx:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  dY = {dy:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  dZ = {dz:.3f} m", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  Dist = {distance:.3f} m", (info_x, info_y),
                   font, font_scale, (0, 255, 255), thickness)
        info_y += line_h + 5

        # 姿态
        cv2.putText(frame, "Orientation:", (info_x, info_y),
                   font, 0.6, (255, 255, 255), 2)
        info_y += line_h

        cv2.putText(frame, f"  Roll  = {pose_result.roll:.2f} deg", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  Pitch = {pose_result.pitch:.2f} deg", (info_x, info_y),
                   font, font_scale, color, thickness)
        info_y += line_h

        cv2.putText(frame, f"  Yaw   = {pose_result.yaw:.2f} deg", (info_x, info_y),
                   font, font_scale, color, thickness)

    def save_frame(self, frame, frame_count):
        """保存当前帧"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"frame_{timestamp}_{frame_count}.jpg"
        filepath = os.path.join(Config.RESULTS_PATH, filename)
        cv2.imwrite(filepath, frame)
        print(f"✅ 已保存: {filepath}")

    def reset_initial_pose(self):
        """重置初始位姿"""
        self.initial_tvec = None
        self.initial_rvec = None


def main():
    """主函数"""
    print("\n" + "="*70)
    print("  D435i RGB 灯条检测+配对+PnP 系统 (完全重构版)")
    print("="*70)

    system = LightTrackingSystem()
    system.run()

    print("\n程序已正常退出")


if __name__ == "__main__":
    main()
