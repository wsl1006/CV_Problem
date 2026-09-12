"""
RealSense相机测试程序
测试RealSense相机的彩色和深度功能
"""
import pyrealsense2 as rs
import numpy as np
import cv2

def main():
    print("\n" + "="*70)
    print("           RealSense 相机测试程序")
    print("="*70)
    print("\n正在初始化RealSense相机...\n")

    # 创建管道
    pipeline = rs.pipeline()
    config = rs.config()

    # 配置流
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)

    try:
        # 启动管道
        profile = pipeline.start(config)

        # 获取相机内参
        color_stream = profile.get_stream(rs.stream.color)
        intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

        print("✅ RealSense相机已成功打开！\n")
        print("相机信息：")
        print(f"  - 分辨率: {intrinsics.width} x {intrinsics.height}")
        print(f"  - 焦距 fx: {intrinsics.fx:.2f}")
        print(f"  - 焦距 fy: {intrinsics.fy:.2f}")
        print(f"  - 主点 cx: {intrinsics.ppx:.2f}")
        print(f"  - 主点 cy: {intrinsics.ppy:.2f}")
        print(f"  - 畸变模型: {intrinsics.model}")
        print(f"  - 畸变系数: {intrinsics.coeffs}")

        print("\n内参矩阵：")
        print(f"  [[{intrinsics.fx:.2f},    0.00, {intrinsics.ppx:.2f}],")
        print(f"   [   0.00, {intrinsics.fy:.2f}, {intrinsics.ppy:.2f}],")
        print(f"   [   0.00,    0.00,    1.00]]")

        print("\n" + "="*70)
        print("操作说明：")
        print("  - 移动鼠标查看像素点的深度值")
        print("  - 按 's' 保存当前图像")
        print("  - 按 'd' 切换深度显示模式")
        print("  - 按 'q' 退出")
        print("="*70 + "\n")

        # 创建对齐对象
        align_to = rs.stream.color
        align = rs.align(align_to)

        # 鼠标回调函数
        depth_image = None
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_MOUSEMOVE and depth_image is not None:
                h, w = depth_image.shape
                if 0 <= x < w and 0 <= y < h:
                    depth = depth_image[y, x] / 1000.0  # 转换为米
                    print(f"\r像素 ({x:3d}, {y:3d}) 深度: {depth:.3f} m    ", end='', flush=True)

        cv2.namedWindow('RealSense - Color')
        cv2.setMouseCallback('RealSense - Color', mouse_callback)

        show_depth = True
        frame_count = 0

        while True:
            # 等待新的帧
            frames = pipeline.wait_for_frames()

            # 对齐深度帧到彩色帧
            aligned_frames = align.process(frames)

            # 获取对齐后的帧
            color_frame = aligned_frames.get_color_frame()
            depth_frame = aligned_frames.get_depth_frame()

            if not color_frame or not depth_frame:
                continue

            # 转换为numpy数组
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(depth_frame.get_data())

            # 应用颜色映射到深度图像
            depth_colormap = cv2.applyColorMap(
                cv2.convertScaleAbs(depth_image, alpha=0.03),
                cv2.COLORMAP_JET
            )

            # 在彩色图像上显示信息
            cv2.putText(color_image, "RealSense D435/D455", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(color_image, f"Frame: {frame_count}", (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # 显示图像
            cv2.imshow('RealSense - Color', color_image)

            if show_depth:
                cv2.imshow('RealSense - Depth', depth_colormap)

            # 键盘控制
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                print("\n\n退出程序")
                break
            elif key == ord('s'):
                cv2.imwrite(f'realsense_color_{frame_count}.jpg', color_image)
                cv2.imwrite(f'realsense_depth_{frame_count}.png', depth_image)
                print(f"\n✅ 已保存图像: realsense_color_{frame_count}.jpg")
                frame_count += 1
            elif key == ord('d'):
                show_depth = not show_depth
                if not show_depth:
                    cv2.destroyWindow('RealSense - Depth')
                print(f"\n深度显示: {'开启' if show_depth else '关闭'}")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("\n可能的原因：")
        print("  1. RealSense相机未连接")
        print("  2. USB连接不稳定（建议使用USB 3.0蓝色接口）")
        print("  3. 相机正被其他程序使用")
        print("  4. 需要更新RealSense驱动")

    finally:
        # 清理
        pipeline.stop()
        cv2.destroyAllWindows()
        print("\n✅ 相机已关闭")

if __name__ == "__main__":
    main()
