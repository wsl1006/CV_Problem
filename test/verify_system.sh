#!/bin/bash
#
# D435i RGB 灯带检测系统 - 快速验证脚本
#

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT" || exit 1

echo "=========================================="
echo "  D435i RGB 灯带检测系统 - 验证"
echo "=========================================="
echo ""

# 1. 检查Python依赖
echo "1️⃣  检查Python依赖..."
python3 -c "import cv2; import numpy; import pyrealsense2; print('✅ 所有依赖已安装')" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ 缺少依赖，正在安装..."
    pip install opencv-python numpy pyrealsense2
fi
echo ""

# 2. 检查D435i连接
echo "2️⃣  检查RealSense D435i连接..."
lsusb | grep -i intel
if [ $? -eq 0 ]; then
    echo "✅ D435i 已连接"
else
    echo "❌ 未检测到D435i，请检查USB连接"
    exit 1
fi
echo ""

# 3. 检查文件完整性
echo "3️⃣  检查文件完整性..."
FILES=("core/config.py" "core/camera_realsense.py" "core/detector.py" "core/geometry.py" "core/pose.py" "main_rgb.py")
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file 缺失"
        exit 1
    fi
done
echo ""

# 4. 提示下一步
echo "=========================================="
echo "✅ 验证通过！"
echo "=========================================="
echo ""
echo "📋 下一步操作："
echo ""
echo "第1步：标定HSV参数（必须！）"
echo "  python -m test.hsv_tuner_realsense"
echo ""
echo "第2步：更新 core/config.py 中的HSV值"
echo ""
echo "第3步：运行主程序"
echo "  python main_rgb.py"
echo ""
echo "详细说明请查看："
echo "  cat docs/debug/REALSENSE_REFACTORED.md"
echo ""
echo "=========================================="
