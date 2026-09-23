"""现场配置：只修改目标尺寸、颜色范围和 PnP 参数。"""

import numpy as np


class Config:
    # 双灯条的实测尺寸，单位：米。
    LIGHT_LENGTH = 0.3
    LIGHT_WIDTH = 0.014
    LIGHT_SPACING = 0.165
    PNP_MODEL_SCALE = 1.028057  # 多距离标定所得；未标定时设为 1.0

    # OpenCV HSV 范围。先运行 python -m test.hsv_tuner_realsense 标定。
    HSV_LOWER_RED1 = np.array([3, 0, 212])
    HSV_UPPER_RED1 = np.array([42, 73, 255])

    # PnP 允许的最大重投影误差，单位：像素。
    MAX_REPROJECTION_ERROR = 15.0

    DEBUG = False
