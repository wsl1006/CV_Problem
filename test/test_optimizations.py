"""不依赖相机的检测稳定性、PnP 与尺度标定测试。"""

import unittest
from types import SimpleNamespace

import cv2
import numpy as np

from core.detector import LightBarCandidate, LightBarPair, LightDetector
from core.geometry import GeometryProcessor
from core.pose import PoseEstimator
from test.calibrate_distance_scale import estimate_scale


def make_vertical_bar(center_x, top=100, bottom=200, width=8):
    half = width / 2
    contour = np.array([
        [center_x - half, top], [center_x + half, top],
        [center_x + half, bottom], [center_x - half, bottom],
    ], dtype=np.float32).reshape(-1, 1, 2)
    return LightBarCandidate(contour, "red")


class OptimizationTests(unittest.TestCase):
    def test_endpoint_percentiles_ignore_isolated_outliers(self):
        # 主体是 y=100..200 的灯条，上下各有一条很窄的 10px 光晕尖刺。
        points = np.array([
            [96, 100], [99, 100], [99, 90], [101, 90], [101, 100], [104, 100],
            [104, 200], [101, 200], [101, 210], [99, 210], [99, 200], [96, 200],
        ], dtype=np.float32).reshape(-1, 1, 2)
        bar = LightBarCandidate(points, "red")
        self.assertGreater(bar.top[1], 90)
        self.assertLess(bar.bottom[1], 210)

    def test_expected_pair_spacing_scores_higher(self):
        detector = LightDetector()
        left = make_vertical_bar(100)
        expected = make_vertical_bar(155)
        far = make_vertical_bar(300)
        expected_score = detector._score_pair(LightBarPair(left, expected))
        far_score = detector._score_pair(LightBarPair(left, far))
        self.assertGreater(expected_score, far_score)

    def test_ippe_recovers_synthetic_pose(self):
        camera_matrix = np.array([
            [600.0, 0.0, 320.0],
            [0.0, 600.0, 240.0],
            [0.0, 0.0, 1.0],
        ])
        dist_coeffs = np.zeros(5)
        object_points = GeometryProcessor().build_light_bar_center_endpoints_3d_model()
        expected_rvec = np.array([[0.08], [-0.18], [0.04]])
        expected_tvec = np.array([[0.06], [0.03], [1.50]])
        image_points, _ = cv2.projectPoints(
            object_points, expected_rvec, expected_tvec,
            camera_matrix, dist_coeffs
        )
        image_points = image_points.reshape(-1, 2)
        left = SimpleNamespace(top=image_points[0], bottom=image_points[1])
        right = SimpleNamespace(bottom=image_points[2], top=image_points[3])

        result = PoseEstimator(camera_matrix, dist_coeffs).estimate_pose_two_bars(
            left, right
        )
        self.assertTrue(result.valid, result.reason)
        self.assertAlmostEqual(result.z, 1.50, places=3)
        self.assertLess(result.reprojection_error, 0.01)

    def test_multi_distance_scale_fit(self):
        samples = [(1.0, 1.1), (1.5, 1.65), (2.0, 2.2)]
        new_scale, factor, corrected, _, rmse = estimate_scale(samples, 1.045)
        self.assertAlmostEqual(factor, 1.0 / 1.1, places=6)
        self.assertAlmostEqual(new_scale, 1.045 / 1.1, places=6)
        self.assertTrue(np.allclose(corrected, [1.0, 1.5, 2.0]))
        self.assertLess(rmse, 1e-9)


if __name__ == "__main__":
    unittest.main()
