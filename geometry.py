"""
几何处理模块 - 重构版
主要用于3D模型构建和工具函数
"""
import cv2
import numpy as np
from config import Config


class GeometryProcessor:
    """几何处理器"""

    def __init__(self):
        pass

    def build_two_light_bars_3d_model(self):
        """
        构建两条灯带的完整3D模型

        题目要求：根据两条灯带的实际长度、宽度和安装位置建立3D模型

        坐标系定义：
        - 原点在两灯带中心
        - X轴向右（两灯带连线方向）
        - Y轴向上（灯带长度方向）
        - Z=0平面

        返回：8个3D点，对应两条灯带的8个角点
        顺序：左灯带4个点 + 右灯带4个点
        [L_TL, L_TR, L_BR, L_BL, R_TL, R_TR, R_BR, R_BL]
        """
        scale = Config.PNP_MODEL_SCALE
        L = Config.LIGHT_LENGTH * scale    # 标定后的灯带长度
        W = Config.LIGHT_WIDTH * scale     # 标定后的灯带宽度（含光晕）
        S = Config.LIGHT_SPACING * scale   # 标定后的两灯带中心距离

        # 左灯带中心在 X=-S/2
        # 右灯带中心在 X=+S/2

        # 左灯带4个3D点
        #   L_TL ---- L_TR
        #     |        |
        #     |        |
        #   L_BL ---- L_BR

        left_bar_3d = np.array([
            [-S/2 - W/2,  L/2, 0],   # L_TL: 左灯带左上
            [-S/2 + W/2,  L/2, 0],   # L_TR: 左灯带右上
            [-S/2 + W/2, -L/2, 0],   # L_BR: 左灯带右下
            [-S/2 - W/2, -L/2, 0]    # L_BL: 左灯带左下
        ], dtype=np.float32)

        # 右灯带4个3D点
        #   R_TL ---- R_TR
        #     |        |
        #     |        |
        #   R_BL ---- R_BR

        right_bar_3d = np.array([
            [S/2 - W/2,  L/2, 0],    # R_TL: 右灯带左上
            [S/2 + W/2,  L/2, 0],    # R_TR: 右灯带右上
            [S/2 + W/2, -L/2, 0],    # R_BR: 右灯带右下
            [S/2 - W/2, -L/2, 0]     # R_BL: 右灯带左下
        ], dtype=np.float32)

        # 合并：8个点
        object_points = np.vstack([left_bar_3d, right_bar_3d])

        if Config.DEBUG:
            print("\n[Geometry] 两条灯带3D模型:")
            print(f"  PnP尺度系数: {scale:.3f}")
            print(f"  标定模型尺寸: {L*1000:.1f}mm(长) × {W*1000:.1f}mm(宽)")
            print(f"  标定模型间距: {S*1000:.1f}mm")
            print(f"  左灯带:")
            print(f"    L_TL: {left_bar_3d[0]}")
            print(f"    L_TR: {left_bar_3d[1]}")
            print(f"    L_BR: {left_bar_3d[2]}")
            print(f"    L_BL: {left_bar_3d[3]}")
            print(f"  右灯带:")
            print(f"    R_TL: {right_bar_3d[0]}")
            print(f"    R_TR: {right_bar_3d[1]}")
            print(f"    R_BR: {right_bar_3d[2]}")
            print(f"    R_BL: {right_bar_3d[3]}")

        return object_points

    def build_light_bar_center_endpoints_3d_model(self):
        """构造两根灯条中心线端点的 4 点平面模型。

        顺序与图像点严格一致：左上、左下、右下、右上。相比灯条的 8 个
        矩形角点，这个模型不依赖难以稳定测量的 10 mm 灯条宽度。
        """
        scale = Config.PNP_MODEL_SCALE
        L = Config.LIGHT_LENGTH * scale
        S = Config.LIGHT_SPACING * scale
        return np.array([
            [-S / 2,  L / 2, 0],
            [-S / 2, -L / 2, 0],
            [ S / 2, -L / 2, 0],
            [ S / 2,  L / 2, 0],
        ], dtype=np.float32)

    def extract_bar_corners(self, bar):
        """
        从灯条的minAreaRect提取4个角点

        严格顺序：[TL, TR, BR, BL]

        Args:
            bar: LightBarCandidate对象

        Returns:
            corners: np.array shape (4, 2) - [TL, TR, BR, BL]
        """
        # 获取旋转矩形的4个点
        box = bar.box  # shape (4, 2)

        if Config.DEBUG:
            print(f"\n[Geometry] 提取灯条角点:")
            print(f"  原始box:\n{box}")
            print(f"  灯条中心: {bar.center}")
            print(f"  灯条长度: {bar.length:.1f} px")
            print(f"  灯条宽度: {bar.width:.1f} px")

        # minAreaRect返回的box顺序不固定，需要排序
        # 找到最上面和最下面的点
        sorted_by_y = box[box[:, 1].argsort()]

        # 上面两个点
        top_two = sorted_by_y[:2]
        # 下面两个点
        bottom_two = sorted_by_y[2:]

        # 按x坐标排序，确定左右
        if top_two[0, 0] < top_two[1, 0]:
            TL = top_two[0]
            TR = top_two[1]
        else:
            TL = top_two[1]
            TR = top_two[0]

        if bottom_two[0, 0] < bottom_two[1, 0]:
            BL = bottom_two[0]
            BR = bottom_two[1]
        else:
            BL = bottom_two[1]
            BR = bottom_two[0]

        corners = np.array([TL, TR, BR, BL], dtype=np.float32)

        if Config.DEBUG:
            print(f"  排序后角点:")
            print(f"    TL: {TL}")
            print(f"    TR: {TR}")
            print(f"    BR: {BR}")
            print(f"    BL: {BL}")

        return corners
