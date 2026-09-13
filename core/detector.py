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

        # 最小二乘拟合灯条中心线，再与轮廓外接框的上下边界相交得到端点。
        # 这样不会把 minAreaRect 的短边抖动和光晕宽度带入 PnP。
        vx, vy, x0, y0 = cv2.fitLine(
            contour, cv2.DIST_L2, 0, 0.01, 0.01
        ).reshape(4)
        x, y, _, h = cv2.boundingRect(contour)
        top_y = float(y)
        bottom_y = float(y + h - 1)
        if abs(vy) > 1e-6:
            top_x = x0 + (top_y - y0) * vx / vy
            bottom_x = x0 + (bottom_y - y0) * vx / vy
            self.top = np.array([top_x, top_y], dtype=np.float32)
            self.bottom = np.array([bottom_x, bottom_y], dtype=np.float32)
        else:
            # 水平轮廓会在后续角度筛选中被拒绝；这里仍保证端点有效。
            self.top = np.array([x0, top_y], dtype=np.float32)
            self.bottom = np.array([x0, bottom_y], dtype=np.float32)
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
        self.config = Config()
        self._color_rejection_counts = {}

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
        mask_red, mask_blue = self._preprocess(frame)

        # 2. 提取灯条候选
        candidates = self._find_light_bar_candidates(frame, mask_red, mask_blue)

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
        else:
            if Config.DEBUG:
                print("\n[Detector] ❌ 无法找到有效的灯条配对")

        debug_info = {
            'mask_red': mask_red,
            'mask_blue': mask_blue,
            'all_candidates': candidates,
            'valid_candidates': valid_candidates,
            'best_pair': best_pair
        }

        return left_bar, right_bar, valid_candidates, debug_info

    def _preprocess(self, frame):
        """
        预处理：通道差分 + HSV + 亮度联合检测

        Returns:
            mask_red: 红灯mask
            mask_blue: 蓝灯mask
        """
        # 分离通道
        B = frame[:, :, 0].astype(np.float32)
        G = frame[:, :, 1].astype(np.float32)
        R = frame[:, :, 2].astype(np.float32)

        # HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 使用 HSV 的 V 通道作亮度门限。相比灰度图，它不会低估纯红灯条的亮度。
        value_channel = hsv[:, :, 2]
        _, mask_bright = cv2.threshold(
            value_channel, Config.HSV_MIN_VALUE, 255, cv2.THRESH_BINARY
        )

        # 方法1：通道差分
        red_diff = R - G
        red_diff = np.clip(red_diff, 0, 255).astype(np.uint8)
        _, mask_red_diff = cv2.threshold(red_diff, Config.RED_CHANNEL_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

        # 方法2：HSV 辅助检测。红色跨越 Hue=0/179，两个区间均需保留。
        mask_red_hsv1 = cv2.inRange(hsv, Config.HSV_LOWER_RED1, Config.HSV_UPPER_RED1)
        mask_red_hsv2 = cv2.inRange(hsv, Config.HSV_LOWER_RED2, Config.HSV_UPPER_RED2)
        mask_red_hsv = cv2.bitwise_or(mask_red_hsv1, mask_red_hsv2)

        # 参考 rm_vision 的灰度二值化：先提取过曝的白色灯芯，颜色在轮廓
        # 提取后由其邻域 R/B 响应判断。近距离自动曝光时再补充高饱和红色区域，
        # 以免白色灯芯灰度下降后整条灯带消失。
        if Config.RED_USE_GRAYSCALE_CORE_MASK:
            _, mask_red = cv2.threshold(
                gray, Config.GRAYSCALE_CORE_THRESHOLD, 255, cv2.THRESH_BINARY
            )
            # 用户标定的灯芯低饱和但 Hue 稳定；直接并入 HSV 结果，避免它在
            # 灰度略低于阈值时从候选掩膜中消失。
            mask_red = cv2.bitwise_or(mask_red, mask_red_hsv)
            if Config.RED_USE_CHROMA_MASK:
                chroma_margin = Config.RED_COLOR_DOMINANCE_MARGIN
                red_chroma = (
                    (R > G + chroma_margin) &
                    (R > B + chroma_margin) &
                    (R >= Config.RED_CHROMA_MIN_VALUE)
                )
                mask_red = cv2.bitwise_or(mask_red, red_chroma.astype(np.uint8) * 255)
        # 光晕较强时不直接并入整片 R-G 响应。斜视造成白色灯芯 Hue 漂移时，
        # 只恢复红色响应邻域内的高亮核心。
        elif Config.RED_USE_CHANNEL_DIFF:
            mask_red_combined = cv2.bitwise_or(mask_red_diff, mask_red_hsv)
            mask_red = cv2.bitwise_and(mask_red_combined, mask_bright)
        else:
            mask_red_combined = mask_red_hsv
            if Config.RED_RECOVER_BRIGHT_CORE:
                support_size = Config.RED_SUPPORT_DILATE_SIZE
                support_kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (support_size, support_size)
                )
                red_support = cv2.dilate(mask_red_diff, support_kernel)
                _, mask_core = cv2.threshold(
                    value_channel, Config.RED_CORE_MIN_VALUE, 255, cv2.THRESH_BINARY
                )
                mask_core = cv2.bitwise_and(mask_core, red_support)
                mask_red_combined = cv2.bitwise_or(mask_red_combined, mask_core)
            mask_red = cv2.bitwise_and(mask_red_combined, mask_bright)

        # 蓝灯检测：B-R 通道差分 + HSV 辅助检测
        blue_diff = B - R
        blue_diff = np.clip(blue_diff, 0, 255).astype(np.uint8)
        _, mask_blue_diff = cv2.threshold(blue_diff, Config.BLUE_CHANNEL_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
        mask_blue_hsv = cv2.inRange(hsv, Config.HSV_LOWER_BLUE, Config.HSV_UPPER_BLUE)
        mask_blue_combined = cv2.bitwise_or(mask_blue_diff, mask_blue_hsv)
        mask_blue = cv2.bitwise_and(mask_blue_combined, mask_bright)

        # 小核保留偏航时只有数个像素宽的灯条，同时连接轻微断点。
        kernel_size = Config.MORPH_KERNEL_SIZE
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_CLOSE, kernel)
        mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel)

        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_CLOSE, kernel)
        mask_blue = cv2.morphologyEx(mask_blue, cv2.MORPH_OPEN, kernel, iterations=1)

        return mask_red, mask_blue

    def _find_light_bar_candidates(self, frame, mask_red, mask_blue):
        """提取灯条候选"""
        candidates = []
        self._color_rejection_counts = {}

        # 灰度灯芯候选通过邻域颜色确定归属，避免白色过曝核心被误判为蓝色。
        contours_red, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours_red:
            if cv2.contourArea(contour) >= Config.MIN_LIGHT_BAR_AREA:
                color, response, fraction = self._classify_contour_color(frame, contour)
                if color == Config.TARGET_LIGHT_COLOR:
                    bar = LightBarCandidate(contour, color)
                    bar.color_response = response
                    bar.color_fraction = fraction
                    candidates.append(bar)
                else:
                    self._color_rejection_counts[color] = (
                        self._color_rejection_counts.get(color, 0) + 1
                    )

        # 仅在需要蓝色目标时才处理蓝色候选，避免高亮背景形成 blue 候选后干扰配对。
        if Config.TARGET_LIGHT_COLOR == 'blue':
            contours_blue, _ = cv2.findContours(mask_blue, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours_blue:
                if cv2.contourArea(contour) >= Config.MIN_LIGHT_BAR_AREA:
                    color, response, fraction = self._classify_contour_color(frame, contour)
                    if color == 'blue':
                        bar = LightBarCandidate(contour, color)
                        bar.color_response = response
                        bar.color_fraction = fraction
                        candidates.append(bar)

        # 使用 HSV 的 V 通道计算候选内部亮度，与预处理阶段的亮度定义保持一致。
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
        size = Config.COLOR_CLASSIFICATION_DILATE_SIZE
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        support = cv2.dilate(mask, kernel)
        b, g, r = cv2.split(frame)
        pixels = support > 0
        b_values = b[pixels].astype(np.int16)
        g_values = g[pixels].astype(np.int16)
        r_values = r[pixels].astype(np.int16)
        response = float(np.mean(r_values - b_values))
        margin = Config.RED_COLOR_DOMINANCE_MARGIN
        red_fraction = float(np.mean(
            (r_values > g_values + margin) & (r_values > b_values + margin)
        ))
        blue_fraction = float(np.mean(
            (b_values > g_values + margin) & (b_values > r_values + margin)
        ))

        # 低饱和的过曝灯芯不满足 R-G > 45，但已落在用户现场标定的 HSV
        # 范围内。用轮廓邻域的 HSV 命中比例作为第二条红色确认通路。
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_red = cv2.bitwise_or(
            cv2.inRange(hsv, Config.HSV_LOWER_RED1, Config.HSV_UPPER_RED1),
            cv2.inRange(hsv, Config.HSV_LOWER_RED2, Config.HSV_UPPER_RED2)
        )
        hsv_hits = hsv_red[pixels] > 0
        hsv_fraction = float(np.mean(hsv_hits))
        # 色差只在 HSV 命中像素上计算，不能让膨胀邻域中的黑背景稀释结果。
        if np.any(hsv_hits):
            hsv_response = float(np.mean((r_values - b_values)[hsv_hits]))
        else:
            hsv_response = 0.0
        strong_red = (
            response >= Config.MIN_RED_COLOR_RESPONSE and
            red_fraction >= Config.MIN_RED_COLOR_FRACTION
        )
        calibrated_hsv_red = (
            hsv_fraction >= Config.MIN_RED_HSV_FRACTION and
            Config.MIN_RED_HSV_RESPONSE <= hsv_response <= Config.MAX_RED_HSV_RESPONSE
        )
        if strong_red or calibrated_hsv_red:
            return 'red', response, max(red_fraction, hsv_fraction)
        if (response <= -Config.MIN_RED_COLOR_RESPONSE and
                blue_fraction >= Config.MIN_RED_COLOR_FRACTION):
            return 'blue', response, blue_fraction
        return 'unknown', response, max(red_fraction, blue_fraction)

    def _filter_light_bars(self, candidates, frame):
        """筛选灯条候选"""
        valid = []
        rejected_counts = {}
        frame_area = frame.shape[0] * frame.shape[1]
        max_area = max(
            Config.MAX_LIGHT_BAR_AREA,
            Config.MAX_LIGHT_BAR_AREA_RATIO * frame_area
        )

        def reject(bar, reason):
            bar.rejection_reason = reason
            rejected_counts[reason] = rejected_counts.get(reason, 0) + 1

        for bar in candidates:
            # 面积筛选
            if bar.area < Config.MIN_LIGHT_BAR_AREA or bar.area > max_area:
                reject(bar, 'area')
                continue

            # 长宽比筛选
            if bar.aspect_ratio < Config.MIN_LIGHT_BAR_ASPECT_RATIO:
                reject(bar, 'aspect_ratio_low')
                continue
            if bar.aspect_ratio > Config.MAX_LIGHT_BAR_ASPECT_RATIO:
                reject(bar, 'aspect_ratio_high')
                continue

            # 矩形度筛选
            if bar.rectangularity < Config.MIN_LIGHT_BAR_RECTANGULARITY:
                reject(bar, 'rectangularity')
                continue

            # 方向筛选
            angle_diff = abs(bar.angle - Config.EXPECTED_LIGHT_BAR_ANGLE)
            if angle_diff > 90:
                angle_diff = 180 - angle_diff
            if angle_diff > Config.LIGHT_BAR_ANGLE_TOLERANCE:
                reject(bar, 'angle')
                continue

            # 亮度筛选
            if bar.brightness < Config.MIN_LIGHT_BAR_BRIGHTNESS:
                reject(bar, 'brightness')
                continue

            bar.rejection_reason = None
            valid.append(bar)

        if Config.DEBUG and rejected_counts:
            summary = ', '.join(f'{name}={count}' for name, count in rejected_counts.items())
            print(f"[Detector] 候选淘汰统计: {summary}")
            if Config.DEBUG_SHOW_FILTERED:
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
        best_score = Config.MIN_PAIR_SCORE

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

                if Config.DEBUG and Config.DEBUG_SHOW_PAIRS:
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
        if Config.REQUIRE_SAME_COLOR_PAIR and bar1.color != bar2.color:
            pair.rejection_reason = 'color_mismatch'
            return 0.0

        area_ratio = max(bar1.area, bar2.area) / (min(bar1.area, bar2.area) + 1e-6)
        width_diff = abs(bar1.width - bar2.width) / (pair.avg_width + 1e-6)
        angle_diff = abs(bar1.angle - bar2.angle)
        if angle_diff > 90:
            angle_diff = 180 - angle_diff
        if area_ratio > Config.MAX_AREA_RATIO:
            pair.rejection_reason = f'area_ratio={area_ratio:.2f}'
            return 0.0
        if width_diff > Config.MAX_WIDTH_DIFF_RATIO:
            pair.rejection_reason = f'width_diff={width_diff:.2f}'
            return 0.0
        if angle_diff > Config.MAX_ANGLE_DIFF:
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
        if overlap_ratio < Config.MIN_VERTICAL_OVERLAP_RATIO:
            pair.rejection_reason = f'vertical_overlap={overlap_ratio:.2f}'
            return 0.0
        if horizontal_overlap > Config.MAX_HORIZONTAL_OVERLAP_RATIO * pair.avg_width:
            pair.rejection_reason = f'horizontal_overlap={horizontal_overlap:.1f}px'
            return 0.0

        # 长度、宽度和角度相似度。
        length_diff = abs(bar1.length - bar2.length) / pair.avg_length
        length_score = max(0, 1.0 - length_diff / Config.MAX_LENGTH_DIFF_RATIO)
        width_score = max(0, 1.0 - width_diff / Config.MAX_WIDTH_DIFF_RATIO)
        angle_score = max(0, 1.0 - angle_diff / Config.MAX_ANGLE_DIFF)

        # 使用水平中心距，避免一根灯条轻微上下偏移破坏间距判断。
        distance_ratio = pair.horizontal_distance / pair.avg_length
        if not Config.MIN_PAIR_DISTANCE_RATIO <= distance_ratio <= Config.MAX_PAIR_DISTANCE_RATIO:
            pair.rejection_reason = f'distance_ratio={distance_ratio:.2f}'
            return 0.0
        distance_score = 1.0

        vertical_offset = abs(bar1.center[1] - bar2.center[1])
        vertical_ratio = vertical_offset / pair.avg_length
        alignment_score = max(0, 1.0 - vertical_ratio / Config.MAX_VERTICAL_OFFSET_RATIO)

        score = (
            Config.WEIGHT_LENGTH_SIMILARITY * length_score +
            Config.WEIGHT_WIDTH_SIMILARITY * width_score +
            Config.WEIGHT_ANGLE_SIMILARITY * angle_score +
            Config.WEIGHT_DISTANCE * distance_score +
            Config.WEIGHT_ALIGNMENT * alignment_score +
            Config.WEIGHT_VERTICAL_OVERLAP * overlap_ratio
        )
        if score <= Config.MIN_PAIR_SCORE:
            pair.rejection_reason = f'score_below_threshold={score:.3f}'
        return score

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
