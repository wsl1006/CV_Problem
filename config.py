"""
配置文件 - RealSense D435i 灯带检测系统
基于灯条检测+配对的完整算法
"""
import numpy as np


class Config:
    """系统配置类"""

    # ==================== 灯带物理尺寸 (单位：米) ====================
    # 真实测量值（宽度包含可见光晕）
    LIGHT_LENGTH = 0.3  # 260mm
    LIGHT_WIDTH = 0.014   # 14mm（1.4cm，包含光晕）

    # 两条灯带之间的距离（中心距离，单位：米）
    # 这是两条灯带实际安装位置，用于建立3D模型
    LIGHT_SPACING = 0.165  # 16.5cm

    # PnP 尺度标定：手测相机至目标中心为 1.300m 时，当前输出约 1.500m。
    # 新系数 = 旧系数 1.206 × (1.300 / 1.500) = 1.045。
    # 后续重标定时：新系数 = 当前系数 × (真实距离 / 当前 Range)。
    PNP_MODEL_SCALE = 1.045

    # ==================== 通道差分检测参数 ====================
    # 红灯通道差分 - 实际标定值
    RED_CHANNEL_DIFF_WEIGHT_R = 1.0
    RED_CHANNEL_DIFF_WEIGHT_G = 1.0
    RED_CHANNEL_DIFF_THRESHOLD = 15  # R-G阈值
    # True 会把整片 R-G 差分区域并入红色掩膜；光晕较强时保持 False。
    RED_USE_CHANNEL_DIFF = False
    # 斜视时灯条变窄且白色核心的 Hue 不稳定：用附近的红色响应证明其属于红灯，
    # 但只把高亮核心并入轮廓，避免重新引入整片光晕。
    RED_RECOVER_BRIGHT_CORE = False
    RED_CORE_MIN_VALUE = 245
    RED_SUPPORT_DILATE_SIZE = 9
    # 参考 rm_vision：先用灰度高亮区域提取灯芯，再由轮廓邻域颜色确认红灯。
    # 过曝灯芯趋近白色时，HSV 的色相和饱和度不再可靠。
    # 当前现场 HSV 标定已经能干净分离两条灯芯，直接使用 HSV 主掩膜；
    # 不再把整幅高亮灰度区域并入，避免窗户和反光形成大轮廓。
    RED_USE_GRAYSCALE_CORE_MASK = False
    GRAYSCALE_CORE_THRESHOLD = 200
    # 近距离自动曝光会压低白色灯芯的灰度；此掩膜保留仍然呈明显红色的灯带部分。
    RED_USE_CHROMA_MASK = True
    RED_CHROMA_MIN_VALUE = 70
    COLOR_CLASSIFICATION_DILATE_SIZE = 13
    # 单灯芯常有较大白色过曝区域，颜色确认保持适度门槛；窗光主要由后续双灯条配对排除。
    MIN_RED_COLOR_RESPONSE = 8.0
    # 防止暖白窗光仅凭轻微 R-B 偏差被误判为红灯：要求邻域内存在明显红色像素。
    RED_COLOR_DOMINANCE_MARGIN = 45
    MIN_RED_COLOR_FRACTION = 0.03
    # 标定的灯芯是低饱和、高亮的暖红色，无法满足 R-G > 45。
    # HSV 命中足够多且 R-B 色差处于该灯芯范围时，也确认其为红灯。
    MIN_RED_HSV_FRACTION = 0.20
    MIN_RED_HSV_RESPONSE = 0.0
    MAX_RED_HSV_RESPONSE = 45.0

    # 蓝灯通道差分
    BLUE_CHANNEL_DIFF_WEIGHT_B = 1.0
    BLUE_CHANNEL_DIFF_WEIGHT_R = 1.0
    BLUE_CHANNEL_DIFF_THRESHOLD = 30  # B-R阈值

    # HSV 辅助识别与亮度门限（按现场灯带标定）。
    # V 通道直接描述像素亮度，避免环境中较暗的红色物体进入候选。
    HSV_MIN_VALUE = 234
    HSV_LOWER_RED1 = np.array([0, 0, HSV_MIN_VALUE])
    HSV_UPPER_RED1 = np.array([16, 10, 255])
    # 当前灯带的色相不跨越 OpenCV Hue 的 0/179 边界，第二段复用标定范围，
    # 以免旧的 170--179 范围引入背景候选。
    HSV_LOWER_RED2 = HSV_LOWER_RED1.copy()
    HSV_UPPER_RED2 = HSV_UPPER_RED1.copy()
    HSV_LOWER_BLUE = np.array([100, 70, HSV_MIN_VALUE])
    HSV_UPPER_BLUE = np.array([130, 255, 255])

    # 本项目当前目标为亮红色灯条，不将蓝色候选送入配对。
    TARGET_LIGHT_COLOR = 'red'

    # 显示时只保留已确认目标灯条附近的红色发光区域；检测与 PnP 始终使用原始帧。
    DISPLAY_RED_ONLY = True
    DISPLAY_TARGET_DILATE_SIZE = 25
    DISPLAY_RED_MARGIN = 12
    # 配对尚未成功时仅显示通过几何筛选的红色候选，避免大片背景候选染红整幅图。
    # 该选项仅影响显示，PnP 仍必须使用一对通过全部约束的灯条。
    DISPLAY_UNPAIRED_RED_CANDIDATES = False
    # 纯红色处理图默认不绘制候选框、角点、坐标轴和文字；识别结果仍输出到终端。
    DISPLAY_ANNOTATIONS = False
    SHOW_MEASUREMENT_WINDOW = True

    # 斜视后灯条短边可能仅剩 3--5px，5x5 开运算会将其完全腐蚀。
    MORPH_KERNEL_SIZE = 3

    # ==================== 灯条候选筛选参数 ====================
    # 基础筛选
    MIN_LIGHT_BAR_AREA = 50       # 最小面积(px²)
    # 靠近相机时灯条面积会快速增大。固定 10000px² 会在约 1.5m 内误删真灯条。
    MAX_LIGHT_BAR_AREA = 50000    # 最大面积的低分辨率保底值(px²)
    MAX_LIGHT_BAR_AREA_RATIO = 0.20  # 最大面积占整帧比例，分辨率变化时自动放宽

    # 亮红色灯带应为细长且接近矩形的高亮轮廓；这两项排除窗户反光等不规则亮斑。
    # 近距离、快速移动或斜视时，膨胀光晕会使单根灯条的表观长宽比降低。
    # 误检由后面的双灯条同色、平行、重叠和间距约束排除。
    MIN_LIGHT_BAR_ASPECT_RATIO = 1.1
    MAX_LIGHT_BAR_ASPECT_RATIO = 50.0   # 最大长宽比

    MIN_LIGHT_BAR_RECTANGULARITY = 0.50

    # 方向约束（度）
    EXPECTED_LIGHT_BAR_ANGLE = 90.0     # 期望方向（竖直）
    LIGHT_BAR_ANGLE_TOLERANCE = 50.0    # 单灯条相对竖直方向的容差，兼容移动与大偏航

    # 亮度要求 - 降低要求，包含更多区域
    MIN_LIGHT_BAR_BRIGHTNESS = 70       # 自动曝光降低时仍保留明显红色灯带

    # ==================== 灯条配对参数 ====================
    # 长度相似度
    MAX_LENGTH_DIFF_RATIO = 0.5    # 长度差异比例

    # 宽度相似度：灯带光晕会随曝光和背景反射而显著变化。
    MAX_WIDTH_DIFF_RATIO = 1.2

    # RoboMaster 风格装甲板配对约束：两根灯条应同色、近似平行且上下有明显重叠。
    REQUIRE_SAME_COLOR_PAIR = True
    # 两条真实灯带的光晕面积可能不同，保留方向、重叠和间距约束来排除误配。
    MAX_AREA_RATIO = 3.0
    MIN_VERTICAL_OVERLAP_RATIO = 0.5
    MAX_HORIZONTAL_OVERLAP_RATIO = 0.2

    # 角度相似度
    MAX_ANGLE_DIFF = 15.0          # 角度差（度）

    # 距离约束
    # 当前目标中两灯带中心距约为灯带长度的 0.36 倍；留出姿态与轮廓误差余量。
    MIN_PAIR_DISTANCE_RATIO = 0.30  # 水平中心距/平均灯条长度
    MAX_PAIR_DISTANCE_RATIO = 4.0

    # 垂直对齐
    MAX_VERTICAL_OFFSET_RATIO = 1.0  # 垂直偏移/平均长度

    # 配对评分权重
    WEIGHT_LENGTH_SIMILARITY = 0.20
    WEIGHT_WIDTH_SIMILARITY = 0.10
    WEIGHT_ANGLE_SIMILARITY = 0.20
    WEIGHT_DISTANCE = 0.20
    WEIGHT_ALIGNMENT = 0.15
    WEIGHT_VERTICAL_OVERLAP = 0.15

    # 最小配对得分
    MIN_PAIR_SCORE = 0.5

    # 平面灯条对 PnP：优先使用 IPPE；不支持时自动退回迭代法。
    PNP_USE_IPPE = True

    # ==================== PnP参数 ====================
    # 重投影误差阈值（像素）- 暂时放宽
    MAX_REPROJECTION_ERROR = 15.0  # 从8.0提高到15.0，等检测改善后再降低

    # 距离合理性范围（米）
    MIN_DISTANCE = 0.05
    MAX_DISTANCE = 10.0

    # ==================== 显示参数 ====================
    # 窗口尺寸
    WINDOW_WIDTH = 1280
    WINDOW_HEIGHT = 720

    # 结果保存
    SAVE_RESULTS = True
    RESULTS_PATH = "results/"

    # ==================== 调试模式 ====================
    DEBUG = True                    # 详细调试信息
    DEBUG_SHOW_ALL_CANDIDATES = False  # 默认仅显示最终配对；按 d 可临时查看候选
    DEBUG_SHOW_FILTERED = False        # 显示被过滤的候选
    DEBUG_SHOW_PAIRS = True            # 显示所有配对尝试
    DEBUG_SHOW_MASKS = False           # 显示中间mask
