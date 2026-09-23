"""
检测器模块 - 基于灯条检测+配对的完整算法
核心改进：
1. 通道差分检测（R-G, B-R）处理过曝
2. 灯条候选提取与筛选
3. 灯条配对算法
4. 从灯条对生成目标四角点
"""
import cv2
import numpy as np
from .config import Config

# 固定算法默认值；日常只需调整 core/config.py。
COLOR_CLASSIFICATION_DILATE_SIZE = 13
MIN_RED_COLOR_RESPONSE = 8.0
RED_COLOR_DOMINANCE_MARGIN = 45
MIN_RED_COLOR_FRACTION = 0.03
MIN_RED_HSV_FRACTION = 0.20
MIN_RED_HSV_RESPONSE = 0.0
MAX_RED_HSV_RESPONSE = 70.0
MORPH_KERNEL_SIZE = 3
LIGHT_ENDPOINT_LOW_PERCENTILE = 2.0
LIGHT_ENDPOINT_HIGH_PERCENTILE = 98.0
MIN_LIGHT_BAR_AREA = 50
MAX_LIGHT_BAR_AREA = 50000
MAX_LIGHT_BAR_AREA_RATIO = 0.20
MIN_LIGHT_BAR_ASPECT_RATIO = 1.1
MAX_LIGHT_BAR_ASPECT_RATIO = 50.0
MIN_LIGHT_BAR_RECTANGULARITY = 0.50
EXPECTED_LIGHT_BAR_ANGLE = 90.0
LIGHT_BAR_ANGLE_TOLERANCE = 50.0
MIN_LIGHT_BAR_BRIGHTNESS = 70
MAX_LENGTH_DIFF_RATIO = 0.5
MAX_WIDTH_DIFF_RATIO = 1.2
MAX_AREA_RATIO = 3.0
MIN_VERTICAL_OVERLAP_RATIO = 0.5
MAX_HORIZONTAL_OVERLAP_RATIO = 0.2
MAX_ANGLE_DIFF = 15.0
MIN_PAIR_DISTANCE_RATIO = 0.30
MAX_PAIR_DISTANCE_RATIO = 4.0
MAX_VERTICAL_OFFSET_RATIO = 1.0
EXPECTED_PAIR_DISTANCE_RATIO = Config.LIGHT_SPACING / Config.LIGHT_LENGTH
PAIR_DISTANCE_SCORE_SIGMA = 0.65
WEIGHT_LENGTH_SIMILARITY = 0.17
WEIGHT_WIDTH_SIMILARITY = 0.08
WEIGHT_ANGLE_SIMILARITY = 0.16
WEIGHT_DISTANCE = 0.18
WEIGHT_ALIGNMENT = 0.13
WEIGHT_VERTICAL_OVERLAP = 0.13
WEIGHT_TEMPORAL_CONTINUITY = 0.15
TRACK_ASSOCIATION_SIGMA = 0.75
TRACK_MAX_MISSED_FRAMES = 3
MIN_PAIR_SCORE = 0.5
DEBUG_SHOW_FILTERED = False
DEBUG_SHOW_PAIRS = False


class LightBarCandidate:
    """灯条候选类"""

    def __init__(self, contour, color):
        self.contour = contour
        self.color = color  # 'red' or 'blue'

        # 基础几何特征
        self.area = cv2.contourArea(contour)
        self.rect = cv2.minAreaRect(contour)  # ((cx, cy), (w, h), angle)
        self.box = cv2.boxPoints(self.rect)

        # 提取尺寸
        (cx, cy), (w, h), angle = self.rect
        self.center = np.array([cx, cy])
        self.width = min(w, h)   # 短边
        self.length = max(w, h)  # 长边
        self.angle = angle

        # 调整角度：让angle表示长边方向
        if w < h:
            self.angle = (angle + 90) % 180

        # 长宽比
        self.aspect_ratio = self.length / (self.width + 1e-6)

        # 矩形度
        rect_area = w * h
        self.rectangularity = self.area / (rect_area + 1e-6)

        # 最小二乘拟合灯条中心线，并用轮廓点在线方向上的稳健分位数确定端点。
        # 相比 boundingRect 的极值，分位数不会被顶端/底端的少量光晕噪点拉长。
        x, y, roi_width, roi_height = cv2.boundingRect(contour)
        local_mask = np.zeros((roi_height, roi_width), dtype=np.uint8)
        local_contour = contour.astype(np.int32) - np.array([[[x, y]]], dtype=np.int32)
        cv2.drawContours(local_mask, [local_contour], -1, 255, cv2.FILLED)
        pixel_y, pixel_x = np.nonzero(local_mask)
        contour_points = np.column_stack([
            pixel_x.astype(np.float32) + x,
            pixel_y.astype(np.float32) + y,
        ])
        vx, vy, x0, y0 = cv2.fitLine(
            contour_points, cv2.DIST_L2, 0, 0.01, 0.01
        ).reshape(4)
        direction = np.array([vx, vy], dtype=np.float32)
        direction /= np.linalg.norm(direction) + 1e-6
        if direction[1] < 0:
            direction = -direction
        origin = np.array([x0, y0], dtype=np.float32)
        projections = (contour_points - origin) @ direction
        low, high = np.percentile(
            projections,
            [LIGHT_ENDPOINT_LOW_PERCENTILE,
             LIGHT_ENDPOINT_HIGH_PERCENTILE]
        )
        self.top = (origin + float(low) * direction).astype(np.float32)
        self.bottom = (origin + float(high) * direction).astype(np.float32)
        if self.top[1] > self.bottom[1]:
            self.top, self.bottom = self.bottom, self.top
        self.line_length = float(max(high - low, 1e-6))
        self.center = (self.top + self.bottom) / 2

        # 亮度和颜色响应（稍后计算）
        self.brightness = 0.0
        self.color_response = 0.0
        self.color_fraction = 0.0
        self.rejection_reason = None


class LightBarPair:
    """灯条配对类"""

    def __init__(self, bar1, bar2):
        self.bar1 = bar1
        self.bar2 = bar2
        self.score = 0.0
        self.rejection_reason = None

        # 配对几何特征
        self.center_distance = np.linalg.norm(bar1.center - bar2.center)
        self.horizontal_distance = abs(bar1.center[0] - bar2.center[0])
        self.avg_length = (bar1.length + bar2.length) / 2
        self.avg_width = (bar1.width + bar2.width) / 2

        # 确定左右顺序
        if bar1.center[0] < bar2.center[0]:
            self.left_bar = bar1
            self.right_bar = bar2
        else:
            self.left_bar = bar2
            self.right_bar = bar1


class LightDetector:
    """灯带检测器 - 完整重构版"""

    def __init__(self):
        self._color_rejection_counts = {}
        self._previous_pair_centers = None
        self._missed_frames = 0

    def detect(self, frame):
        """
        完整检测流程

        Returns:
            left_bar: 左灯条 LightBarCandidate 或 None
            right_bar: 右灯条 LightBarCandidate 或 None
            valid_candidates: 所有有效灯条候选
            debug_info: 调试信息
        """
        # 1. 预处理和二值化
        mask_red = self._preprocess(frame)

        # 2. 提取灯条候选
        candidates = self._find_light_bar_candidates(frame, mask_red)

        if Config.DEBUG:
            print(f"\n[Detector] 检测到 {len(candidates)} 个灯条候选")
            if self._color_rejection_counts:
                summary = ', '.join(
                    f'{name}={count}' for name, count in self._color_rejection_counts.items()
                )
                print(f"[Detector] 颜色确认淘汰: {summary}")

        # 3. 筛选灯条候选
        valid_candidates = self._filter_light_bars(candidates, frame)

        if Config.DEBUG:
            print(f"[Detector] 筛选后剩余 {len(valid_candidates)} 个有效灯条")
            for i, bar in enumerate(valid_candidates):
                print(f"  灯条 #{i+1}:")
                print(f"    颜色: {bar.color}")
                print(f"    长度: {bar.length:.1f} px")
                print(f"    宽度: {bar.width:.1f} px")
                print(f"    长宽比: {bar.aspect_ratio:.2f}")
                print(f"    角度: {bar.angle:.1f}°")
                print(f"    矩形度: {bar.rectangularity:.2f}")
                print(f"    亮度: {bar.brightness:.1f}")
                print(f"    红色响应: {bar.color_response:.1f}")
                print(f"    明显红色占比: {bar.color_fraction:.2f}")

        # 4. 灯条配对
        best_pair = self._match_light_bars(valid_candidates)

        left_bar = None
        right_bar = None

        if best_pair is not None:
            if Config.DEBUG:
                print(f"\n[Detector] ✅ 配对成功，得分: {best_pair.score:.3f}")
                print(f"  左灯条中心: {best_pair.left_bar.center}")
                print(f"  右灯条中心: {best_pair.right_bar.center}")
                print(f"  中心距离: {best_pair.center_distance:.1f} px")

            left_bar = best_pair.left_bar
            right_bar = best_pair.right_bar
            self._previous_pair_centers = np.vstack([
                left_bar.center.copy(), right_bar.center.copy()
            ])
            self._missed_frames = 0
        else:
            self._missed_frames += 1
            if self._missed_frames > TRACK_MAX_MISSED_FRAMES:
                self._previous_pair_centers = None
            if Config.DEBUG:
                print("\n[Detector] ❌ 无法找到有效的灯条配对")

        debug_info = {
            'mask_red': mask_red,
            'all_candidates': candidates,
            'valid_candidates': valid_candidates,
            'best_pair': best_pair
        }

        return left_bar, right_bar, valid_candidates, debug_info

    def _preprocess(self, frame):
        """使用现场标定的 HSV 范围提取红色灯芯。"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, Config.HSV_LOWER_RED1, Config.HSV_UPPER_RED1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL_SIZE,) * 2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    def _find_light_bar_candidates(self, frame, mask_red):
        """从红色掩膜中提取灯条候选并确认颜色。"""
        candidates = []
        self._color_rejection_counts = {}
        contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if cv2.contourArea(contour) < MIN_LIGHT_BAR_AREA:
                continue
            color, response, fraction = self._classify_contour_color(frame, contour)
            if color != 'red':
                self._color_rejection_counts[color] = self._color_rejection_counts.get(color, 0) + 1
                continue
            bar = LightBarCandidate(contour, color)
            bar.color_response = response
            bar.color_fraction = fraction
            candidates.append(bar)

        value_channel = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 2]
        for bar in candidates:
            bar.brightness = self._compute_brightness(bar, value_channel)
        return candidates

    def _classify_contour_color(self, frame, contour):
        """以轮廓及其相邻光晕的平均 R-B 响应分类颜色。

        灯芯过曝后近似白色，直接读取灯芯会丢失颜色；膨胀少量像素后可采到
        紧邻灯芯的红/蓝发光区域。frame 为 OpenCV BGR 图像。
        """
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
        size = COLOR_CLASSIFICATION_DILATE_SIZE
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        support = cv2.dilate(mask, kernel)
        b, g, r = cv2.split(frame)
        pixels = support > 0
        b_values = b[pixels].astype(np.int16)
        g_values = g[pixels].astype(np.int16)
        r_values = r[pixels].astype(np.int16)
        response = float(np.mean(r_values - b_values))
        margin = RED_COLOR_DOMINANCE_MARGIN
        red_fraction = float(np.mean(
            (r_values > g_values + margin) & (r_values > b_values + margin)
        ))
        blue_fraction = float(np.mean(
            (b_values > g_values + margin) & (b_values > r_values + margin)
        ))

        # 低饱和的过曝灯芯不满足 R-G > 45，但已落在用户现场标定的 HSV
        # 范围内。用轮廓邻域的 HSV 命中比例作为第二条红色确认通路。
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_red = cv2.inRange(hsv, Config.HSV_LOWER_RED1, Config.HSV_UPPER_RED1)
        hsv_hits = hsv_red[pixels] > 0
        hsv_fraction = float(np.mean(hsv_hits))
        # 色差只在 HSV 命中像素上计算，不能让膨胀邻域中的黑背景稀释结果。
        if np.any(hsv_hits):
            hsv_response = float(np.mean((r_values - b_values)[hsv_hits]))
        else:
            hsv_response = 0.0
        strong_red = (
            response >= MIN_RED_COLOR_RESPONSE and
            red_fraction >= MIN_RED_COLOR_FRACTION
        )
        calibrated_hsv_red = (
            hsv_fraction >= MIN_RED_HSV_FRACTION and
            MIN_RED_HSV_RESPONSE <= hsv_response <= MAX_RED_HSV_RESPONSE
        )
        if strong_red or calibrated_hsv_red:
            return 'red', response, max(red_fraction, hsv_fraction)
        return 'unknown', response, max(red_fraction, blue_fraction)

    def _filter_light_bars(self, candidates, frame):
        """筛选灯条候选"""
        valid = []
        rejected_counts = {}
        frame_area = frame.shape[0] * frame.shape[1]
        max_area = max(
            MAX_LIGHT_BAR_AREA,
            MAX_LIGHT_BAR_AREA_RATIO * frame_area
        )

        def reject(bar, reason):
            bar.rejection_reason = reason
            rejected_counts[reason] = rejected_counts.get(reason, 0) + 1

        for bar in candidates:
            # 面积筛选
            if bar.area < MIN_LIGHT_BAR_AREA or bar.area > max_area:
                reject(bar, 'area')
                continue

            # 长宽比筛选
            if bar.aspect_ratio < MIN_LIGHT_BAR_ASPECT_RATIO:
                reject(bar, 'aspect_ratio_low')
                continue
            if bar.aspect_ratio > MAX_LIGHT_BAR_ASPECT_RATIO:
                reject(bar, 'aspect_ratio_high')
                continue

            # 矩形度筛选
            if bar.rectangularity < MIN_LIGHT_BAR_RECTANGULARITY:
                reject(bar, 'rectangularity')
                continue

            # 方向筛选
            angle_diff = abs(bar.angle - EXPECTED_LIGHT_BAR_ANGLE)
            if angle_diff > 90:
                angle_diff = 180 - angle_diff
            if angle_diff > LIGHT_BAR_ANGLE_TOLERANCE:
                reject(bar, 'angle')
                continue

            # 亮度筛选
            if bar.brightness < MIN_LIGHT_BAR_BRIGHTNESS:
                reject(bar, 'brightness')
                continue

            bar.rejection_reason = None
            valid.append(bar)

        if Config.DEBUG and rejected_counts:
            summary = ', '.join(f'{name}={count}' for name, count in rejected_counts.items())
            print(f"[Detector] 候选淘汰统计: {summary}")
            if DEBUG_SHOW_FILTERED:
                for i, bar in enumerate(candidates):
                    if bar.rejection_reason is not None:
                        print(
                            f"  淘汰 #{i + 1}: {bar.rejection_reason}, "
                            f"size={bar.length:.1f}x{bar.width:.1f}px, "
                            f"ratio={bar.aspect_ratio:.2f}, angle={bar.angle:.1f}°, "
                            f"fill={bar.rectangularity:.2f}, brightness={bar.brightness:.1f}"
                        )

        return valid

    def _match_light_bars(self, candidates):
        """
        灯条配对算法

        Returns:
            best_pair: LightBarPair 或 None
        """
        if len(candidates) < 2:
            return None

        best_pair = None
        best_score = MIN_PAIR_SCORE

        # 遍历所有配对
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                bar1 = candidates[i]
                bar2 = candidates[j]

                # 创建配对
                pair = LightBarPair(bar1, bar2)

                # 评分
                score = self._score_pair(pair)
                pair.score = score

                if Config.DEBUG and DEBUG_SHOW_PAIRS:
                    print(f"\n  配对尝试: 灯条{i+1} + 灯条{j+1}")
                    print(f"    得分: {score:.3f}")
                    if pair.rejection_reason:
                        print(f"    拒绝原因: {pair.rejection_reason}")

                if score > best_score:
                    best_score = score
                    best_pair = pair

        return best_pair

    def _score_pair(self, pair):
        """RoboMaster 风格的灯条配对评分与硬几何约束。"""
        bar1, bar2 = pair.bar1, pair.bar2

        # 同一装甲板的两根灯条颜色一致；外观明显不同的候选直接拒绝。
        if bar1.color != bar2.color:
            pair.rejection_reason = 'color_mismatch'
            return 0.0

        area_ratio = max(bar1.area, bar2.area) / (min(bar1.area, bar2.area) + 1e-6)
        width_diff = abs(bar1.width - bar2.width) / (pair.avg_width + 1e-6)
        angle_diff = abs(bar1.angle - bar2.angle)
        if angle_diff > 90:
            angle_diff = 180 - angle_diff
        if area_ratio > MAX_AREA_RATIO:
            pair.rejection_reason = f'area_ratio={area_ratio:.2f}'
            return 0.0
        if width_diff > MAX_WIDTH_DIFF_RATIO:
            pair.rejection_reason = f'width_diff={width_diff:.2f}'
            return 0.0
        if angle_diff > MAX_ANGLE_DIFF:
            pair.rejection_reason = f'light_angle_diff={angle_diff:.1f}deg'
            return 0.0

        # 两根灯条应有足够上下重叠，且不应横向明显交叠。
        top_y = max(bar1.top[1], bar2.top[1])
        bottom_y = min(bar1.bottom[1], bar2.bottom[1])
        overlap = max(0.0, bottom_y - top_y)
        vertical_span = min(abs(bar1.bottom[1] - bar1.top[1]),
                            abs(bar2.bottom[1] - bar2.top[1]))
        overlap_ratio = overlap / (vertical_span + 1e-6)

        left_rightmost = max(pair.left_bar.box[:, 0])
        right_leftmost = min(pair.right_bar.box[:, 0])
        horizontal_overlap = max(0.0, left_rightmost - right_leftmost)
        if overlap_ratio < MIN_VERTICAL_OVERLAP_RATIO:
            pair.rejection_reason = f'vertical_overlap={overlap_ratio:.2f}'
            return 0.0
        if horizontal_overlap > MAX_HORIZONTAL_OVERLAP_RATIO * pair.avg_width:
            pair.rejection_reason = f'horizontal_overlap={horizontal_overlap:.1f}px'
            return 0.0

        # 长度、宽度和角度相似度。
        length_diff = abs(bar1.length - bar2.length) / pair.avg_length
        length_score = max(0, 1.0 - length_diff / MAX_LENGTH_DIFF_RATIO)
        width_score = max(0, 1.0 - width_diff / MAX_WIDTH_DIFF_RATIO)
        angle_score = max(0, 1.0 - angle_diff / MAX_ANGLE_DIFF)

        # 使用水平中心距，避免一根灯条轻微上下偏移破坏间距判断。
        distance_ratio = pair.horizontal_distance / pair.avg_length
        if not MIN_PAIR_DISTANCE_RATIO <= distance_ratio <= MAX_PAIR_DISTANCE_RATIO:
            pair.rejection_reason = f'distance_ratio={distance_ratio:.2f}'
            return 0.0
        expected_ratio = EXPECTED_PAIR_DISTANCE_RATIO
        relative_distance_error = abs(distance_ratio - expected_ratio) / (expected_ratio + 1e-6)
        distance_score = float(np.exp(
            -0.5 * (relative_distance_error / PAIR_DISTANCE_SCORE_SIGMA) ** 2
        ))

        vertical_offset = abs(bar1.center[1] - bar2.center[1])
        vertical_ratio = vertical_offset / pair.avg_length
        alignment_score = max(0, 1.0 - vertical_ratio / MAX_VERTICAL_OFFSET_RATIO)

        temporal_score = self._temporal_pair_score(pair)

        score = (
            WEIGHT_LENGTH_SIMILARITY * length_score +
            WEIGHT_WIDTH_SIMILARITY * width_score +
            WEIGHT_ANGLE_SIMILARITY * angle_score +
            WEIGHT_DISTANCE * distance_score +
            WEIGHT_ALIGNMENT * alignment_score +
            WEIGHT_VERTICAL_OVERLAP * overlap_ratio +
            WEIGHT_TEMPORAL_CONTINUITY * temporal_score
        )
        if score <= MIN_PAIR_SCORE:
            pair.rejection_reason = f'score_below_threshold={score:.3f}'
        return score

    def _temporal_pair_score(self, pair):
        """根据左右灯条相对上一帧的位移计算连续性得分。"""
        if self._previous_pair_centers is None:
            return 1.0
        current = np.vstack([pair.left_bar.center, pair.right_bar.center])
        mean_shift = float(np.mean(np.linalg.norm(
            current - self._previous_pair_centers, axis=1
        )))
        normalized_shift = mean_shift / (pair.avg_length + 1e-6)
        return float(np.exp(
            -0.5 * (normalized_shift / TRACK_ASSOCIATION_SIGMA) ** 2
        ))

    def reset_tracking(self):
        """清除候选配对的帧间关联状态。"""
        self._previous_pair_centers = None
        self._missed_frames = 0

    def _build_target_corners(self, pair):
        """
        从灯条对生成目标四角点

        严格顺序：[TL, TR, BR, BL]

        Returns:
            corners: np.array shape (4, 2)
        """
        left_bar = pair.left_bar
        right_bar = pair.right_bar

        # 使用中心线端点。细灯条的短边角点只有数个像素，噪声远大于中心线方向。
        left_top, left_bottom = left_bar.top, left_bar.bottom
        right_top, right_bottom = right_bar.top, right_bar.bottom

        # 组成目标四角点：TL, TR, BR, BL
        corners = np.array([
            left_top,      # P1: Top-Left
            right_top,     # P2: Top-Right
            right_bottom,  # P3: Bottom-Right
            left_bottom    # P4: Bottom-Left
        ], dtype=np.float32)

        if Config.DEBUG:
            print("\n[Detector] 目标四角点:")
            print(f"  P1(TL): {corners[0]}")
            print(f"  P2(TR): {corners[1]}")
            print(f"  P3(BR): {corners[2]}")
            print(f"  P4(BL): {corners[3]}")

        return corners

    def _compute_brightness(self, bar, value_channel):
        """计算灯条内部平均 HSV-V 亮度"""
        mask = np.zeros(value_channel.shape, dtype=np.uint8)
        cv2.drawContours(mask, [bar.contour], 0, 255, -1)
        mean_val = cv2.mean(value_channel, mask=mask)[0]
        return mean_val
