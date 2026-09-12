"""
相机标定辅助脚本
使用棋盘格标定板进行相机标定，获取相机内参和畸变系数

使用方法：
1. 打印一个棋盘格标定板（例如9x6的棋盘格）
2. 运行此脚本
3. 按空格键拍摄不同角度的标定板图像（至少10张）
4. 按ESC键结束拍摄，自动进行标定
5. 标定结果会保存到 calibration_result.txt
"""
import cv2
import numpy as np
import os

# 棋盘格参数
CHESSBOARD_SIZE = (9, 6)  # 内角点数量 (列, 行)
SQUARE_SIZE = 0.025  # 棋盘格每个方格的边长（米），例如2.5cm

# 准备标定板的3D点
def prepare_object_points():
    """准备棋盘格的3D坐标"""
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE
    return objp

def calibrate_camera():
    """相机标定主函数"""
    # 初始化相机
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("无法打开相机")
        return

    print("\n" + "="*60)
    print("相机标定程序")
    print("="*60)
    print(f"棋盘格尺寸: {CHESSBOARD_SIZE[0]}x{CHESSBOARD_SIZE[1]} 内角点")
    print(f"方格大小: {SQUARE_SIZE*100}cm")
    print("\n操作说明：")
    print("  - 按空格键: 捕获当前图像")
    print("  - 按ESC键: 结束捕获，开始标定")
    print("  - 至少需要捕获10张不同角度的图像")
    print("="*60 + "\n")

    # 存储所有图像的角点
    obj_points = []  # 3D点
    img_points = []  # 2D点

    objp = prepare_object_points()

    captured_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        display_frame = frame.copy()

        # 查找棋盘格角点
        ret_corners, corners = cv2.findChessboardCorners(
            gray, CHESSBOARD_SIZE,
            cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )

        # 如果找到角点
        if ret_corners:
            # 亚像素精度优化
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

            # 绘制角点
            cv2.drawChessboardCorners(display_frame, CHESSBOARD_SIZE, corners_refined, ret_corners)

            cv2.putText(display_frame, "Press SPACE to capture", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, "Chessboard not detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        cv2.putText(display_frame, f"Captured: {captured_count}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        cv2.imshow('Camera Calibration', display_frame)

        key = cv2.waitKey(1) & 0xFF

        # 按空格键捕获
        if key == ord(' ') and ret_corners:
            obj_points.append(objp)
            img_points.append(corners_refined)
            captured_count += 1
            print(f"✓ 已捕获第 {captured_count} 张图像")

        # 按ESC键退出
        elif key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    # 开始标定
    if captured_count < 10:
        print(f"\n✗ 捕获的图像数量不足（需要至少10张，当前{captured_count}张）")
        return

    print(f"\n开始标定，使用 {captured_count} 张图像...")

    # 执行标定
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, gray.shape[::-1], None, None
    )

    if ret:
        print("\n" + "="*60)
        print("✓ 标定成功！")
        print("="*60)
        print("\n相机内参矩阵:")
        print(camera_matrix)
        print("\n畸变系数:")
        print(dist_coeffs)

        # 计算重投影误差
        mean_error = 0
        for i in range(len(obj_points)):
            img_points_reproj, _ = cv2.projectPoints(
                obj_points[i], rvecs[i], tvecs[i], camera_matrix, dist_coeffs
            )
            error = cv2.norm(img_points[i], img_points_reproj, cv2.NORM_L2) / len(img_points_reproj)
            mean_error += error

        mean_error /= len(obj_points)
        print(f"\n重投影误差: {mean_error:.4f} 像素")

        # 保存结果
        save_calibration_result(camera_matrix, dist_coeffs, mean_error)

    else:
        print("\n✗ 标定失败")

def save_calibration_result(camera_matrix, dist_coeffs, error):
    """保存标定结果"""
    with open('calibration_result.txt', 'w') as f:
        f.write("="*60 + "\n")
        f.write("相机标定结果\n")
        f.write("="*60 + "\n\n")

        f.write("相机内参矩阵 (CAMERA_MATRIX):\n")
        f.write("np.array([\n")
        f.write(f"    [{camera_matrix[0, 0]:.6f}, {camera_matrix[0, 1]:.6f}, {camera_matrix[0, 2]:.6f}],\n")
        f.write(f"    [{camera_matrix[1, 0]:.6f}, {camera_matrix[1, 1]:.6f}, {camera_matrix[1, 2]:.6f}],\n")
        f.write(f"    [{camera_matrix[2, 0]:.6f}, {camera_matrix[2, 1]:.6f}, {camera_matrix[2, 2]:.6f}]\n")
        f.write("], dtype=np.float32)\n\n")

        f.write("畸变系数 (DIST_COEFFS):\n")
        f.write(f"np.array([{dist_coeffs[0, 0]:.6f}, {dist_coeffs[0, 1]:.6f}, {dist_coeffs[0, 2]:.6f}, {dist_coeffs[0, 3]:.6f}, {dist_coeffs[0, 4]:.6f}], dtype=np.float32)\n\n")

        f.write(f"重投影误差: {error:.4f} 像素\n")

        f.write("\n" + "="*60 + "\n")
        f.write("请将以上参数复制到 config.py 文件中\n")
        f.write("="*60 + "\n")

    print(f"\n✓ 标定结果已保存到 calibration_result.txt")

if __name__ == "__main__":
    calibrate_camera()
