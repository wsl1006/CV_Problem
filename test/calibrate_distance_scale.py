"""根据多组真实距离与 PnP 读数估计统一模型尺度。"""

import argparse
import math

from core.config import Config


def estimate_scale(samples, current_scale):
    """最小化 sum((reported * factor - actual)^2)，返回新尺度与结果统计。"""
    denominator = sum(reported * reported for actual, reported in samples)
    if denominator <= 0:
        raise ValueError("程序读数必须大于 0")
    factor = sum(actual * reported for actual, reported in samples) / denominator
    new_scale = current_scale * factor
    corrected = [reported * factor for actual, reported in samples]
    errors = [value - actual for (actual, _), value in zip(samples, corrected)]
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    return new_scale, factor, corrected, errors, rmse


def parse_sample(text):
    try:
        actual_text, reported_text = text.split(":", 1)
        actual = float(actual_text)
        reported = float(reported_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "样本格式应为 真实距离:程序Range，例如 1.30:1.42"
        ) from exc
    if actual <= 0 or reported <= 0:
        raise argparse.ArgumentTypeError("距离必须大于 0")
    return actual, reported


def main():
    parser = argparse.ArgumentParser(
        description="使用多距离样本计算 core/config.py 中的 PNP_MODEL_SCALE"
    )
    parser.add_argument(
        "samples", nargs="+", type=parse_sample,
        help="真实距离:程序Range，例如 1.00:1.09 1.30:1.42 1.60:1.73"
    )
    args = parser.parse_args()

    if len(args.samples) < 3:
        print("提示：建议至少使用 3 个不同距离的样本。")

    new_scale, factor, corrected, errors, rmse = estimate_scale(
        args.samples, Config.PNP_MODEL_SCALE
    )

    print(f"当前 PNP_MODEL_SCALE = {Config.PNP_MODEL_SCALE:.6f}")
    print(f"统一修正倍率          = {factor:.6f}")
    print(f"建议 PNP_MODEL_SCALE = {new_scale:.6f}\n")
    print("真实值(m)  原读数(m)  修正后(m)  残差(m)")
    for (actual, reported), value, error in zip(
            args.samples, corrected, errors):
        print(f"{actual:9.3f}  {reported:9.3f}  {value:9.3f}  {error:+8.3f}")
    print(f"\nRMSE = {rmse:.4f} m")
    print("\n复制到 core/config.py：")
    print(f"PNP_MODEL_SCALE = {new_scale:.6f}")
    if rmse > 0.03:
        print("\n警告：不同距离的残差超过 3 cm，建议检查 RGB 内参、灯条尺寸和端点完整性。")


if __name__ == "__main__":
    main()
