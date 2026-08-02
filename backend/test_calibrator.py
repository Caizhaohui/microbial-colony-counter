"""标定器与点集冒烟测试（从项目根目录运行）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from backend.core.pointset import make_point, renumber_points, estimate_area_prior_from_points
from backend.core.calibrator import (
    calibrate,
    STRATEGY_COUNT_ONLY,
    STRATEGY_FULL_POINTS,
    STRATEGY_PARTIAL_POINTS,
)
from backend.core.batch import batch_count_paths
from backend.core.algorithm import process_image


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img_path = os.path.join(base, "test1.jpg")
    if not os.path.exists(img_path):
        print("test1.jpg not found")
        return

    image = cv2.imread(img_path)
    print(f"image: {img_path} shape={image.shape}")

    # baseline count
    base_r = process_image(image, detect_petri_dish=True)
    print(f"baseline count (petri): {base_r['count']}")

    # count_only calibrate toward baseline count (should find near-zero error quickly)
    target = max(1, base_r["count"])
    print(f"\n=== count_only target N={target} ===")
    r = calibrate(
        image, strategy=STRATEGY_COUNT_ONLY, total_gt=target,
        max_evals=25, time_limit_sec=20,
    )
    print(r.get("message"), "success=", r.get("success"))
    print("pred", r.get("predicted_count"), "fit", r.get("fit_error"), "evals", r.get("evals"))

    # fake partial points from colony details
    details = base_r.get("colony_details") or []
    pts = [make_point(d["x"], d["y"], i + 1) for i, d in enumerate(details[:15])]
    # details are on scaled image; process_image returns scale_ratio
    scale = float(base_r.get("scale_ratio") or 1.0)
    if scale != 1.0:
        pts = [make_point(p["x"] / scale, p["y"] / scale, p["id"]) for p in pts]
    pts = renumber_points(pts)
    print(f"\n=== partial_points n_pts={len(pts)} N={target} ===")
    if len(pts) >= 5:
        r2 = calibrate(
            image, strategy=STRATEGY_PARTIAL_POINTS, total_gt=target, points=pts,
            max_evals=20, time_limit_sec=18,
        )
        print(r2.get("message"), "success=", r2.get("success"), "fit", r2.get("fit_error"))
    else:
        print("skip partial (not enough points)")

    print(f"\n=== full_points n={len(pts)} ===")
    if pts:
        r3 = calibrate(
            image, strategy=STRATEGY_FULL_POINTS, points=pts,
            max_evals=20, time_limit_sec=18,
        )
        print(r3.get("message"), "success=", r3.get("success"),
              "pred", r3.get("predicted_count"), "match", r3.get("match_score"))

    # batch on same image twice
    if r.get("success"):
        print("\n=== batch ===")
        items = batch_count_paths([img_path, img_path], r["params"])
        for it in items:
            print(it["name"], it["count"], it.get("error"))

    print("\narea prior", estimate_area_prior_from_points(pts, image.shape) if pts else None)
    print("OK")


if __name__ == "__main__":
    main()
