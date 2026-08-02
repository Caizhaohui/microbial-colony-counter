"""标定器与多参考盘联合标定冒烟测试（从项目根目录运行）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from backend.core.pointset import make_point, renumber_points
from backend.core.calibrator import (
    calibrate,
    calibrate_multi,
    STRATEGY_COUNT_ONLY,
    MAX_REF_PLATES,
)
from backend.core.batch import batch_count_paths
from backend.core.algorithm import process_image


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    img1 = os.path.join(base, "test1.jpg")
    img2 = os.path.join(base, "test2.jpg")
    if not os.path.exists(img1):
        print("test1.jpg not found")
        return

    image1 = cv2.imread(img1)
    print(f"image1: {img1} shape={image1.shape}")
    print(f"MAX_REF_PLATES={MAX_REF_PLATES}")

    base_r = process_image(image1, detect_petri_dish=True)
    print(f"baseline count (petri): {base_r['count']}")
    target1 = max(1, base_r["count"])

    print(f"\n=== single count_only N={target1} ===")
    r = calibrate(
        image1, strategy=STRATEGY_COUNT_ONLY, total_gt=target1,
        max_evals=20, time_limit_sec=18,
    )
    print(r.get("message"), "success=", r.get("success"), "fit=", r.get("fit_error"))

    # multi: use same image twice with same N (smoke), or test1+test2 if available
    refs = [
        {"image": image1, "total_gt": target1, "name": "test1.jpg", "path": img1},
    ]
    if os.path.exists(img2):
        image2 = cv2.imread(img2)
        base2 = process_image(image2, detect_petri_dish=True)
        target2 = max(1, base2["count"])
        print(f"image2 baseline: {target2}")
        refs.append({
            "image": image2, "total_gt": target2, "name": "test2.jpg", "path": img2,
        })
    else:
        # 模拟第二盘：同一图略不同目标，仅作接口验证
        refs.append({
            "image": image1, "total_gt": target1, "name": "test1_dup.jpg",
        })

    print(f"\n=== multi-ref joint calibrate n={len(refs)} ===")
    rm = calibrate_multi(refs, max_evals=18, time_limit_sec=40)
    print(rm.get("message"))
    print("success=", rm.get("success"), "mean_fit=", rm.get("fit_error"),
          "max_fit=", rm.get("max_fit_error"), "evals=", rm.get("evals"))
    for p in rm.get("plate_results") or []:
        print(f"  {p['name']}: pred={p['predicted_count']} gt={p['total_gt']} err={p['fit_error']:.2%}")

    if rm.get("success"):
        print("\n=== batch with multi params ===")
        paths = [img1] + ([img2] if os.path.exists(img2) else [])
        items = batch_count_paths(paths, rm["params"])
        for it in items:
            print(it["name"], it["count"], it.get("error"))

    # 上限校验
    print("\n=== max plates check ===")
    too_many = [{"image": image1, "total_gt": 10, "name": f"p{i}"} for i in range(MAX_REF_PLATES + 1)]
    bad = calibrate_multi(too_many, max_evals=2, time_limit_sec=5)
    print("expect fail:", bad.get("success"), bad.get("message"))

    print("\nOK")


if __name__ == "__main__":
    main()
