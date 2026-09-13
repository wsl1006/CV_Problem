"""
测试相机是否正常工作
"""
import cv2

print("正在打开相机...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ 无法打开相机")
    print("提示：如果有多个摄像头，尝试使用 VideoCapture(1) 或 VideoCapture(2)")
    exit()

print("✅ 相机已打开")
print("\n操作说明：")
print("  - 按 's' 保存当前图像")
print("  - 按 'q' 退出")

frame_count = 0

while True:
    ret, frame = cap.read()

    if not ret:
        print("无法读取图像")
        break

    # 显示图像尺寸
    h, w = frame.shape[:2]
    cv2.putText(frame, f"Resolution: {w}x{h}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, "Press 'q' to quit, 's' to save", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.imshow('Camera Test', frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('s'):
        filename = f"test_image_{frame_count}.jpg"
        cv2.imwrite(filename, frame)
        print(f"✅ 已保存: {filename}")
        frame_count += 1

cap.release()
cv2.destroyAllWindows()
print("\n✅ 测试完成")
