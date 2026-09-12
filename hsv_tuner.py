"""
HSV颜色调试工具 - 用于找到最佳的HSV阈值
这是测试中最重要的工具！
"""
import cv2
import numpy as np

# 全局变量存储HSV阈值
h_min = 0
h_max = 180
s_min = 0
s_max = 255
v_min = 0
v_max = 255

def nothing(x):
    """滑动条回调函数"""
    pass

def create_trackbars():
    """创建HSV调整滑动条"""
    cv2.namedWindow('HSV Tuner')

    # 创建6个滑动条
    cv2.createTrackbar('H Min', 'HSV Tuner', 0, 180, nothing)
    cv2.createTrackbar('H Max', 'HSV Tuner', 180, 180, nothing)
    cv2.createTrackbar('S Min', 'HSV Tuner', 0, 255, nothing)
    cv2.createTrackbar('S Max', 'HSV Tuner', 255, 255, nothing)
    cv2.createTrackbar('V Min', 'HSV Tuner', 0, 255, nothing)
    cv2.createTrackbar('V Max', 'HSV Tuner', 255, 255, nothing)

    # 预设值（根据常见灯带颜色）
    # 红色灯带的初始值
    cv2.setTrackbarPos('H Min', 'HSV Tuner', 0)
    cv2.setTrackbarPos('H Max', 'HSV Tuner', 10)
    cv2.setTrackbarPos('S Min', 'HSV Tuner', 100)
    cv2.setTrackbarPos('S Max', 'HSV Tuner', 255)
    cv2.setTrackbarPos('V Min', 'HSV Tuner', 100)
    cv2.setTrackbarPos('V Max', 'HSV Tuner', 255)

def main():
    """主函数"""
    print("\n" + "="*70)
    print("           HSV 颜色调试工具")
    print("="*70)
    print("\n这个工具帮助你找到灯带的最佳HSV颜色阈值\n")
    print("操作说明：")
    print("  1. 把灯带放在相机前")
    print("  2. 调整6个滑动条，直到'Mask'窗口中只显示灯带（白色区域）")
    print("  3. 记录下最终的HSV值")
    print("  4. 把这些值填入 config.py")
    print("\n提示：")
    print("  - 红色灯带：H在0-10或160-180")
    print("  - 蓝色灯带：H在100-130")
    print("  - 绿色灯带：H在40-80")
    print("  - S和V通常在100-255之间")
    print("\n按 'q' 退出\n")
    print("="*70 + "\n")

    # 打开相机
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ 无法打开相机")
        return

    print("✅ 相机已打开\n")

    # 创建滑动条窗口
    create_trackbars()

    while True:
        # 读取图像
        ret, frame = cap.read()
        if not ret:
            break

        # 转换到HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # 获取当前滑动条的值
        h_min = cv2.getTrackbarPos('H Min', 'HSV Tuner')
        h_max = cv2.getTrackbarPos('H Max', 'HSV Tuner')
        s_min = cv2.getTrackbarPos('S Min', 'HSV Tuner')
        s_max = cv2.getTrackbarPos('S Max', 'HSV Tuner')
        v_min = cv2.getTrackbarPos('V Min', 'HSV Tuner')
        v_max = cv2.getTrackbarPos('V Max', 'HSV Tuner')

        # 创建HSV阈值
        lower = np.array([h_min, s_min, v_min])
        upper = np.array([h_max, s_max, v_max])

        # 应用阈值
        mask = cv2.inRange(hsv, lower, upper)

        # 形态学操作（可选，减少噪声）
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 应用mask到原图
        result = cv2.bitwise_and(frame, frame, mask=mask)

        # 在原图上显示HSV值
        text = f"H:[{h_min}-{h_max}] S:[{s_min}-{s_max}] V:[{v_min}-{v_max}]"
        cv2.putText(frame, text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, "Original", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        cv2.putText(mask, "Mask (White = Detected)", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.putText(result, "Result", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # 显示图像
        cv2.imshow('Original', frame)
        cv2.imshow('Mask', mask)
        cv2.imshow('Result', result)

        # 按q退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 输出最终结果
    print("\n" + "="*70)
    print("           最终HSV阈值")
    print("="*70)
    print(f"\nH_min = {h_min}")
    print(f"H_max = {h_max}")
    print(f"S_min = {s_min}")
    print(f"S_max = {s_max}")
    print(f"V_min = {v_min}")
    print(f"V_max = {v_max}")
    print("\n复制到 config.py：")
    print("-"*70)
    print(f"HSV_LOWER = np.array([{h_min}, {s_min}, {v_min}])")
    print(f"HSV_UPPER = np.array([{h_max}, {s_max}, {v_max}])")
    print("="*70 + "\n")

    # 清理
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
