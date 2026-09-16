"""
姿态估计模块 - 重构版
核心改进：
1. 使用真实D435i RGB内参
2. PnP重投影误差验证
3. 结果合理性检查
"""
import cv2
import numpy as np
from .geometry import GeometryProcessor
from .config import Config


class PoseResult:
    """PnP结果类"""

    def __init__(self):
        self.success = False
        self.valid = False
        self.rvec = None
        self.tvec = None
        self.reprojection_error = None
        self.x = None
        self.y = None
        self.z = None
        self.roll = None
        self.pitch = None
        self.yaw = None
        self.reason = ""  # 失败原因


class PoseEstimator:
    """姿态估计器 - 重构版"""

    def __init__(self, camera_matrix, dist_coeffs):
        """
        初始化

        Args:
            camera_matrix: D435i RGB真实相机内参矩阵
            dist_coeffs: D435i RGB真实畸变系数
        """
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.geometry = GeometryProcessor()
        self._previous_solution_rvec = None
        self._previous_solution_tvec = None
        self._filtered_rvec = None
        self._filtered_tvec = None

        if Config.DEBUG:
            print("\n[PoseEstimator] 初始化")
            print(f"  相机内参:")
            print(f"    fx = {camera_matrix[0, 0]:.2f}")
            print(f"    fy = {camera_matrix[1, 1]:.2f}")
            print(f"    cx = {camera_matrix[0, 2]:.2f}")
            print(f"    cy = {camera_matrix[1, 2]:.2f}")
            print(f"  畸变系数: {dist_coeffs.flatten()}")

    def estimate_pose_two_bars(self, left_bar, right_bar):
        """
        基于两条灯带估计位姿

        使用两根灯条中心线的上、下端点，共 4 个稳定的平面点。
        该建模方式避免细灯条短边角点抖动造成的 PnP 不稳定。

        Args:
            left_bar: 左灯条 LightBarCandidate
            right_bar: 右灯条 LightBarCandidate

        Returns:
            PoseResult对象
        """
        result = PoseResult()

        # 严格对应：左上、左下、右下、右上。
        image_points = np.array([
            left_bar.top,
            left_bar.bottom,
            right_bar.bottom,
            right_bar.top,
        ], dtype=np.float32)
        object_points = self.geometry.build_light_bar_center_endpoints_3d_model()

        left_length = float(np.linalg.norm(left_bar.bottom - left_bar.top))
        right_length = float(np.linalg.norm(right_bar.bottom - right_bar.top))
        endpoint_length_diff = abs(left_length - right_length) / (
            0.5 * (left_length + right_length) + 1e-6
        )
        if endpoint_length_diff > Config.PNP_MAX_ENDPOINT_LENGTH_DIFF_RATIO:
            result.reason = (
                f"灯条端点长度差异过大: {endpoint_length_diff:.2f} > "
                f"{Config.PNP_MAX_ENDPOINT_LENGTH_DIFF_RATIO}"
            )
            return result

        if Config.DEBUG:
            print("\n[PnP] 输入:")
            print("  灯条中心线端点 [L_TOP, L_BOTTOM, R_BOTTOM, R_TOP]:")
            for label, pt in zip(['L_TOP', 'L_BOTTOM', 'R_BOTTOM', 'R_TOP'], image_points):
                print(f"    {label}: ({pt[0]:.1f}, {pt[1]:.1f})")

        # IPPE 对平面目标通常返回两个候选解。综合重投影误差和上一帧连续性选解，
        # 再用 LM 做一次局部优化；OpenCV 不支持该接口时退回通用迭代法。
        success, rvec, tvec = self._solve_pose(object_points, image_points)

        result.success = success

        if not success:
            result.reason = "solvePnP failed"
            if Config.DEBUG:
                print(f"[PnP] ❌ 失败: {result.reason}")
            return result

        raw_rvec = rvec.copy()
        raw_tvec = tvec.copy()

        if Config.DEBUG:
            print(f"\n[PnP] 初步结果:")
            print(f"  rvec: {rvec.flatten()}")
            print(f"  tvec: {tvec.flatten()}")
            print(f"  X = {raw_tvec[0, 0]:.3f} m")
            print(f"  Y = {raw_tvec[1, 0]:.3f} m")
            print(f"  Z = {raw_tvec[2, 0]:.3f} m")

        # 验证1：重投影误差
        reprojection_error = self._compute_reprojection_error(
            object_points, image_points, rvec, tvec
        )
        result.reprojection_error = reprojection_error

        if Config.DEBUG:
            print(f"  重投影误差: {reprojection_error:.2f} px")

        if reprojection_error > Config.MAX_REPROJECTION_ERROR:
            result.reason = f"重投影误差过大: {reprojection_error:.2f} > {Config.MAX_REPROJECTION_ERROR}"
            if Config.DEBUG:
                print(f"[PnP] ❌ 无效: {result.reason}")
            return result

        # 验证2：距离合理性
        if not self._validate_distance(raw_tvec[2, 0]):
            result.reason = f"距离不合理: Z={raw_tvec[2, 0]:.3f}m"
            if Config.DEBUG:
                print(f"[PnP] ❌ 无效: {result.reason}")
            return result

        # 验证3：数值有效性
        if not self._validate_values(tvec):
            result.reason = "tvec包含无效值(nan/inf)"
            if Config.DEBUG:
                print(f"[PnP] ❌ 无效: {result.reason}")
            return result

        self._previous_solution_rvec = raw_rvec
        self._previous_solution_tvec = raw_tvec
        rvec, tvec = self._apply_temporal_filter(raw_rvec, raw_tvec)
        result.rvec = rvec
        result.tvec = tvec
        result.x = float(tvec[0, 0])
        result.y = float(tvec[1, 0])
        result.z = float(tvec[2, 0])

        # 计算欧拉角
        roll, pitch, yaw = self.rotation_vector_to_euler(rvec)
        result.roll = roll
        result.pitch = pitch
        result.yaw = yaw

        if Config.DEBUG:
            print(f"  Roll  = {roll:.2f}°")
            print(f"  Pitch = {pitch:.2f}°")
            print(f"  Yaw   = {yaw:.2f}°")

        # 所有验证通过
        result.valid = True

        if Config.DEBUG:
            print("[PnP] ✅ 有效")

        return result

    def _solve_pose(self, object_points, image_points):
        """求解平面 PnP，并在 IPPE 双解中选择稳定且重投影误差较小的解。"""
        candidates = []
        if Config.PNP_USE_IPPE and hasattr(cv2, 'solvePnPGeneric'):
            try:
                output = cv2.solvePnPGeneric(
                    object_points, image_points, self.camera_matrix,
                    self.dist_coeffs, flags=cv2.SOLVEPNP_IPPE
                )
                success, rvecs, tvecs = output[:3]
                if success:
                    for rvec, tvec in zip(rvecs, tvecs):
                        rvec = np.asarray(rvec, dtype=np.float64).reshape(3, 1)
                        tvec = np.asarray(tvec, dtype=np.float64).reshape(3, 1)
                        if self._validate_values(tvec) and tvec[2, 0] > 0:
                            candidates.append((rvec, tvec))
            except cv2.error:
                candidates = []

        if candidates:
            rvec, tvec = min(
                candidates,
                key=lambda pose: self._pose_candidate_cost(
                    object_points, image_points, pose[0], pose[1]
                )
            )
        else:
            try:
                success, rvec, tvec = cv2.solvePnP(
                    object_points, image_points, self.camera_matrix,
                    self.dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
                )
            except cv2.error:
                return False, None, None
            if not success:
                return False, None, None

        if hasattr(cv2, 'solvePnPRefineLM'):
            try:
                rvec, tvec = cv2.solvePnPRefineLM(
                    object_points, image_points, self.camera_matrix,
                    self.dist_coeffs, rvec, tvec
                )
            except cv2.error:
                pass
        return True, rvec, tvec

    def _pose_candidate_cost(self, object_points, image_points, rvec, tvec):
        cost = float(self._compute_reprojection_error(
            object_points, image_points, rvec, tvec
        ))
        if self._previous_solution_tvec is None:
            return cost

        previous_range = float(np.linalg.norm(self._previous_solution_tvec)) + 1e-6
        relative_position_change = float(
            np.linalg.norm(tvec - self._previous_solution_tvec) / previous_range
        )
        rotation_change = self._rotation_difference_degrees(
            self._previous_solution_rvec, rvec
        )
        return (
            cost +
            Config.PNP_TEMPORAL_POSITION_WEIGHT * relative_position_change +
            Config.PNP_TEMPORAL_ROTATION_WEIGHT * rotation_change
        )

    @staticmethod
    def _rotation_difference_degrees(rvec_a, rvec_b):
        rmat_a, _ = cv2.Rodrigues(rvec_a)
        rmat_b, _ = cv2.Rodrigues(rvec_b)
        delta = rmat_a.T @ rmat_b
        cosine = np.clip((np.trace(delta) - 1.0) / 2.0, -1.0, 1.0)
        return float(np.degrees(np.arccos(cosine)))

    def _apply_temporal_filter(self, rvec, tvec):
        """对有效姿态做低延迟 EMA，并把旋转矩阵投影回合法旋转。"""
        if self._filtered_tvec is None:
            self._filtered_rvec = rvec.copy()
            self._filtered_tvec = tvec.copy()
            return rvec.copy(), tvec.copy()

        alpha = float(np.clip(Config.POSE_EMA_ALPHA, 0.0, 1.0))
        filtered_tvec = alpha * tvec + (1.0 - alpha) * self._filtered_tvec

        previous_rotation, _ = cv2.Rodrigues(self._filtered_rvec)
        current_rotation, _ = cv2.Rodrigues(rvec)
        blended_rotation = (
            (1.0 - alpha) * previous_rotation + alpha * current_rotation
        )
        u, _, vt = np.linalg.svd(blended_rotation)
        filtered_rotation = u @ vt
        if np.linalg.det(filtered_rotation) < 0:
            u[:, -1] *= -1
            filtered_rotation = u @ vt
        filtered_rvec, _ = cv2.Rodrigues(filtered_rotation)

        self._filtered_rvec = filtered_rvec
        self._filtered_tvec = filtered_tvec
        return filtered_rvec.copy(), filtered_tvec.copy()

    def reset_tracking(self):
        """清除 PnP 的多解选择和滤波状态。"""
        self._previous_solution_rvec = None
        self._previous_solution_tvec = None
        self._filtered_rvec = None
        self._filtered_tvec = None

    def _compute_reprojection_error(self, object_points, image_points, rvec, tvec):
        """
        计算重投影误差

        Returns:
            平均重投影误差（像素）
        """
        # 将3D点重新投影到2D
        projected_points, _ = cv2.projectPoints(
            object_points,
            rvec,
            tvec,
            self.camera_matrix,
            self.dist_coeffs
        )

        projected_points = projected_points.reshape(-1, 2)

        # 计算每个点的误差
        errors = np.linalg.norm(image_points - projected_points, axis=1)

        if Config.DEBUG:
            print("  重投影误差详情:")
            labels = ['L_TOP', 'L_BOTTOM', 'R_BOTTOM', 'R_TOP']
            for i, err in enumerate(errors):
                if i < len(labels):
                    print(f"    {labels[i]}: {err:.2f} px")
                else:
                    print(f"    P{i+1}: {err:.2f} px")

        # 返回平均误差
        return np.mean(errors)

    def _validate_distance(self, z):
        """验证距离合理性"""
        if z < Config.MIN_DISTANCE or z > Config.MAX_DISTANCE:
            return False
        return True

    def _validate_values(self, tvec):
        """验证数值有效性"""
        return np.all(np.isfinite(tvec))

    def rotation_vector_to_euler(self, rvec):
        """
        旋转向量 → 欧拉角

        OpenCV相机坐标系：
        X → 右
        Y → 下
        Z → 前

        Returns:
            roll, pitch, yaw (度)
        """
        # 旋转向量 → 旋转矩阵
        rmat, _ = cv2.Rodrigues(rvec)

        # 旋转矩阵 → 欧拉角 (ZYX顺序)
        sy = np.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)

        singular = sy < 1e-6

        if not singular:
            roll = np.arctan2(rmat[2, 1], rmat[2, 2])
            pitch = np.arctan2(-rmat[2, 0], sy)
            yaw = np.arctan2(rmat[1, 0], rmat[0, 0])
        else:
            roll = np.arctan2(-rmat[1, 2], rmat[1, 1])
            pitch = np.arctan2(-rmat[2, 0], sy)
            yaw = 0

        # 转换为度
        roll = np.degrees(roll)
        pitch = np.degrees(pitch)
        yaw = np.degrees(yaw)

        return roll, pitch, yaw

    def calculate_displacement(self, tvec_prev, tvec_curr):
        """
        计算位移

        Args:
            tvec_prev: 初始位置
            tvec_curr: 当前位置

        Returns:
            dx, dy, dz, distance
        """
        if tvec_prev is None or tvec_curr is None:
            return 0, 0, 0, 0

        dx = tvec_curr[0, 0] - tvec_prev[0, 0]
        dy = tvec_curr[1, 0] - tvec_prev[1, 0]
        dz = tvec_curr[2, 0] - tvec_prev[2, 0]

        distance = np.sqrt(dx**2 + dy**2 + dz**2)

        return dx, dy, dz, distance

    def draw_axis(self, frame, rvec, tvec, length=0.1):
        """
        绘制3D坐标轴

        坐标系：
        X轴 → 红色
        Y轴 → 绿色
        Z轴 → 蓝色

        Args:
            frame: 图像
            rvec: 旋转向量
            tvec: 平移向量
            length: 坐标轴长度(米)

        Returns:
            绘制后的图像
        """
        # 定义坐标轴3D点
        axis_points = np.array([
            [0, 0, 0],          # 原点
            [length, 0, 0],     # X轴
            [0, length, 0],     # Y轴
            [0, 0, length]      # Z轴
        ], dtype=np.float32)

        # 投影到图像
        image_points, _ = cv2.projectPoints(
            axis_points,
            rvec,
            tvec,
            self.camera_matrix,
            self.dist_coeffs
        )

        image_points = image_points.reshape(-1, 2).astype(int)

        result = frame.copy()
        origin = tuple(image_points[0])

        # X轴 - 红色
        cv2.line(result, origin, tuple(image_points[1]), (0, 0, 255), 3)
        cv2.putText(result, "X", tuple(image_points[1]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Y轴 - 绿色
        cv2.line(result, origin, tuple(image_points[2]), (0, 255, 0), 3)
        cv2.putText(result, "Y", tuple(image_points[2]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Z轴 - 蓝色
        cv2.line(result, origin, tuple(image_points[3]), (255, 0, 0), 3)
        cv2.putText(result, "Z", tuple(image_points[3]),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        return result
