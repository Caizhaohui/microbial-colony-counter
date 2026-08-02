"""
批次参数标定器：根据参考图真值搜索最优 process_image 参数。

策略：
  - count_only:      仅总数 N
  - full_points:     全量点选，N = 点数，带点匹配分
  - partial_points:  部分点选 + 总数 N，用点收窄面积搜索
"""

from __future__ import annotations

import time
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from backend.core.algorithm import process_image
from backend.core.pointset import (
    estimate_area_prior_from_points,
    renumber_points,
    scale_points,
)


STRATEGY_COUNT_ONLY = "count_only"
STRATEGY_FULL_POINTS = "full_points"
STRATEGY_PARTIAL_POINTS = "partial_points"

DEFAULT_PARAMS: Dict[str, Any] = {
    "blur_ksize": 7,
    "thresh_method": "adaptive",
    "thresh_val": 100,
    "adaptive_block_size": 11,
    "adaptive_c": 2,
    "min_area": 50,
    "max_area": 5000,
    "min_distance_from_edge": 20,
    "detect_petri_dish": False,
    "use_watershed": False,
    "min_circularity": 0.0,
}


def _odd(v: int) -> int:
    v = int(v)
    return v if v % 2 == 1 else v + 1


def _normalize_params(p: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(DEFAULT_PARAMS)
    out.update(p)
    out["blur_ksize"] = max(3, min(15, _odd(out["blur_ksize"])))
    out["adaptive_block_size"] = max(3, min(51, _odd(out["adaptive_block_size"])))
    out["thresh_val"] = int(max(0, min(255, out["thresh_val"])))
    out["adaptive_c"] = int(max(-10, min(20, out["adaptive_c"])))
    out["min_area"] = int(max(1, out["min_area"]))
    out["max_area"] = int(max(out["min_area"] + 1, out["max_area"]))
    out["min_distance_from_edge"] = int(max(0, out["min_distance_from_edge"]))
    out["detect_petri_dish"] = bool(out["detect_petri_dish"])
    out["use_watershed"] = bool(out["use_watershed"])
    out["min_circularity"] = float(max(0.0, min(0.9, out["min_circularity"])))
    out["thresh_method"] = "manual" if out["thresh_method"] == "manual" else "adaptive"
    return out


def _run(image: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
    p = _normalize_params(params)
    return process_image(
        image=image,
        blur_ksize=p["blur_ksize"],
        thresh_method=p["thresh_method"],
        thresh_val=p["thresh_val"],
        adaptive_block_size=p["adaptive_block_size"],
        adaptive_c=p["adaptive_c"],
        min_area=p["min_area"],
        max_area=p["max_area"],
        min_distance_from_edge=p["min_distance_from_edge"],
        detect_petri_dish=p["detect_petri_dish"],
        manual_roi=None,
        use_watershed=p["use_watershed"],
        min_circularity=p["min_circularity"],
    )


def match_score(
    detected: Sequence[Dict[str, Any]],
    gt_points: Sequence[Dict[str, Any]],
    max_dist: float = 25.0,
) -> float:
    """
    双向贪心匹配比例，返回 0~1。
    detected: colony_details with x,y
    gt_points: manual points in same coordinate space
    """
    if not gt_points:
        return 0.0
    if not detected:
        return 0.0

    det = [(float(d["x"]), float(d["y"])) for d in detected]
    gt = [(float(p["x"]), float(p["y"])) for p in gt_points]
    max_d2 = max_dist * max_dist

    used_det = set()
    matched = 0
    # 对每个 GT 找最近未用检测点
    for gx, gy in gt:
        best_j = None
        best_d2 = max_d2
        for j, (dx, dy) in enumerate(det):
            if j in used_det:
                continue
            d2 = (dx - gx) ** 2 + (dy - gy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_j = j
        if best_j is not None:
            used_det.add(best_j)
            matched += 1

    recall = matched / len(gt)
    precision = matched / len(det) if det else 0.0
    if recall + precision <= 0:
        return 0.0
    return float(2 * recall * precision / (recall + precision))  # F1


def _count_cost(pred: int, gt: int) -> float:
    if gt <= 0:
        return float(abs(pred - gt))
    rel = abs(pred - gt) / float(gt)
    # 绝对误差也惩罚，避免大 N 时相对误差掩盖
    abs_pen = abs(pred - gt) * 0.02
    return rel + abs_pen


def _score_candidate(
    result: Dict[str, Any],
    total_gt: int,
    gt_points_scaled: Optional[List[Dict[str, Any]]],
    use_match: bool,
) -> Tuple[float, float, Optional[float]]:
    """
    返回 (loss越小越好, fit_error相对, match_f1)。
    """
    if result.get("error"):
        return 1e9, 1.0, None
    pred = int(result.get("count", 0))
    fit_error = abs(pred - total_gt) / float(total_gt) if total_gt > 0 else float(abs(pred - total_gt))
    count_loss = _count_cost(pred, total_gt)

    m_score = None
    if use_match and gt_points_scaled:
        details = result.get("colony_details") or []
        # 匹配距离随图像尺度略调
        m_score = match_score(details, gt_points_scaled, max_dist=28.0)
        # 匹配差则加大惩罚
        loss = count_loss + (1.0 - m_score) * 0.5
    else:
        loss = count_loss

    return loss, fit_error, m_score


def _build_search_space(
    strategy: str,
    image: np.ndarray,
    points: Optional[Sequence[Dict[str, Any]]],
    base: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """生成候选参数列表（有限网格 + 随机扰动）。"""
    base = _normalize_params(base or DEFAULT_PARAMS)
    h, w = image.shape[:2]
    area_img = h * w

    if strategy == STRATEGY_PARTIAL_POINTS and points and len(points) >= 2:
        amin, amax = estimate_area_prior_from_points(points, image.shape)
        min_area_choices = sorted(set([
            max(5, int(amin * 0.5)), max(5, amin), max(5, int(amin * 1.5)),
            20, 50, 80, 100,
        ]))
        max_area_choices = sorted(set([
            amax, int(amax * 1.5), int(amax * 2.5), 3000, 5000, 8000, 12000,
        ]))
    else:
        min_area_choices = [20, 30, 50, 80, 100, 150, 200, 300]
        max_area_choices = [2000, 3000, 5000, 8000, 12000, 20000, min(area_img // 10, 50000)]

    blur_choices = [3, 5, 7, 9, 11]
    block_choices = [7, 11, 15, 21, 31]
    c_choices = [1, 2, 3, 5, 8]
    circ_choices = [0.0, 0.2, 0.3, 0.4, 0.5]
    edge_choices = [5, 10, 20, 30]
    watershed_choices = [False, True]
    petri_choices = [False, True]
    thresh_methods = ["adaptive"]
    manual_thresh = [80, 100, 120, 140, 160]

    candidates: List[Dict[str, Any]] = []

    # 默认基线
    candidates.append(dict(base))

    # 结构化网格（采样）
    rng = random.Random(42)
    for _ in range(80):
        p = dict(base)
        p["blur_ksize"] = rng.choice(blur_choices)
        p["thresh_method"] = rng.choice(thresh_methods + ["manual"] if rng.random() < 0.25 else thresh_methods)
        if p["thresh_method"] == "manual":
            p["thresh_val"] = rng.choice(manual_thresh)
        else:
            p["adaptive_block_size"] = rng.choice(block_choices)
            p["adaptive_c"] = rng.choice(c_choices)
        p["min_area"] = rng.choice(min_area_choices)
        p["max_area"] = rng.choice(max_area_choices)
        if p["max_area"] <= p["min_area"]:
            p["max_area"] = p["min_area"] + 500
        p["min_circularity"] = rng.choice(circ_choices)
        p["min_distance_from_edge"] = rng.choice(edge_choices)
        p["use_watershed"] = rng.choice(watershed_choices)
        p["detect_petri_dish"] = rng.choice(petri_choices)
        candidates.append(p)

    # 常见实用组合
    for wa in (False, True):
        for petri in (False, True):
            for ma in (30, 50, 100):
                for xa in (3000, 5000, 10000):
                    p = dict(base)
                    p["use_watershed"] = wa
                    p["detect_petri_dish"] = petri
                    p["min_area"] = ma
                    p["max_area"] = xa
                    candidates.append(p)

    # 去重
    seen = set()
    unique = []
    for p in candidates:
        p = _normalize_params(p)
        key = tuple(sorted((k, str(v)) for k, v in p.items()))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def calibrate(
    image: np.ndarray,
    strategy: str = STRATEGY_COUNT_ONLY,
    total_gt: Optional[int] = None,
    points: Optional[Sequence[Dict[str, Any]]] = None,
    max_evals: int = 45,
    time_limit_sec: float = 30.0,
    base_params: Optional[Dict[str, Any]] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    对参考图执行参数标定。

    返回:
      {
        success, strategy, params, ref_count_gt, predicted_count,
        fit_error, match_score, evals, elapsed_ms,
        result (process_image 最优结果), message
      }
    """
    t0 = time.time()
    strategy = (strategy or STRATEGY_COUNT_ONLY).strip()
    points_list = renumber_points(points) if points else []

    if strategy == STRATEGY_FULL_POINTS:
        if len(points_list) < 1:
            return {
                "success": False,
                "message": "全量点选策略需要至少一个点",
                "strategy": strategy,
            }
        total_gt = len(points_list)
    elif strategy == STRATEGY_PARTIAL_POINTS:
        if total_gt is None or int(total_gt) < 1:
            return {
                "success": False,
                "message": "部分点选策略必须提供整盘真值总数 N",
                "strategy": strategy,
            }
        if len(points_list) < 5:
            return {
                "success": False,
                "message": f"部分点选至少需要 5 个样本点（当前 {len(points_list)}）",
                "strategy": strategy,
            }
        total_gt = int(total_gt)
    elif strategy == STRATEGY_COUNT_ONLY:
        if total_gt is None or int(total_gt) < 1:
            return {
                "success": False,
                "message": "图片+菌落数策略必须提供真值总数 N",
                "strategy": strategy,
            }
        total_gt = int(total_gt)
    else:
        return {
            "success": False,
            "message": f"未知策略: {strategy}",
            "strategy": strategy,
        }

    use_match = strategy == STRATEGY_FULL_POINTS and len(points_list) > 0
    # 部分点选也可用弱匹配（仅对已标注点）
    weak_match = strategy == STRATEGY_PARTIAL_POINTS and len(points_list) > 0

    space = _build_search_space(strategy, image, points_list, base_params)
    # 限制评估次数
    if len(space) > max_evals:
        # 保留第一个（基线）+ 随机采样
        rest = space[1:]
        random.Random(7).shuffle(rest)
        space = [space[0]] + rest[: max_evals - 1]

    best = None
    best_loss = 1e18
    best_meta = {}
    evals = 0

    for idx, params in enumerate(space):
        if time.time() - t0 > time_limit_sec:
            break
        result = _run(image, params)
        evals += 1

        scale = float(result.get("scale_ratio") or 1.0)
        gt_scaled = scale_points(points_list, scale) if points_list else None

        loss, fit_error, m_score = _score_candidate(
            result, total_gt, gt_scaled,
            use_match=use_match or weak_match,
        )
        # 部分点匹配权重更低（已在 match 内），再略减
        if weak_match and not use_match and m_score is not None:
            loss = _count_cost(int(result.get("count", 0)), total_gt) + (1.0 - m_score) * 0.2

        if loss < best_loss:
            best_loss = loss
            best = params
            best_meta = {
                "result": result,
                "fit_error": fit_error,
                "match_score": m_score,
                "predicted_count": int(result.get("count", 0)),
            }

        if progress_callback:
            progress_callback(idx + 1, len(space), best_meta.get("predicted_count"), total_gt)

        # 足够好则提前停
        if fit_error <= 0.02 and (not use_match or (m_score is not None and m_score >= 0.85)):
            break

    elapsed_ms = (time.time() - t0) * 1000.0

    if best is None:
        return {
            "success": False,
            "message": "标定失败：无有效候选",
            "strategy": strategy,
            "evals": evals,
            "elapsed_ms": elapsed_ms,
        }

    params_out = _normalize_params(best)
    pred = best_meta["predicted_count"]
    fit_error = best_meta["fit_error"]

    # 置信提示
    warnings = []
    if fit_error > 0.15:
        warnings.append("参考盘拟合误差较大，建议改用全量/部分点选或检查真值")
    if use_match and best_meta.get("match_score") is not None and best_meta["match_score"] < 0.5:
        warnings.append("点匹配分较低，自动圈出的位置可能与手点不一致")
    if strategy == STRATEGY_COUNT_ONLY:
        warnings.append("仅使用总数标定，无位置约束；同批次拍照条件请尽量一致")

    return {
        "success": True,
        "strategy": strategy,
        "params": params_out,
        "ref_count_gt": total_gt,
        "predicted_count": pred,
        "fit_error": float(fit_error),
        "match_score": best_meta.get("match_score"),
        "evals": evals,
        "elapsed_ms": elapsed_ms,
        "result": best_meta["result"],
        "warnings": warnings,
        "message": f"标定完成：预测 {pred} / 真值 {total_gt}，相对误差 {fit_error:.1%}",
        "version": "1.0",
    }


def params_to_process_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    """提取可直接传给 process_image 的关键字参数。"""
    p = _normalize_params(params)
    return {
        "blur_ksize": p["blur_ksize"],
        "thresh_method": p["thresh_method"],
        "thresh_val": p["thresh_val"],
        "adaptive_block_size": p["adaptive_block_size"],
        "adaptive_c": p["adaptive_c"],
        "min_area": p["min_area"],
        "max_area": p["max_area"],
        "min_distance_from_edge": p["min_distance_from_edge"],
        "detect_petri_dish": p["detect_petri_dish"],
        "use_watershed": p["use_watershed"],
        "min_circularity": p["min_circularity"],
    }
