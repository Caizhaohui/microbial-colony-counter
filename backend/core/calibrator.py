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


# ── 多参考盘联合标定 ─────────────────────────────────

MIN_REF_PLATES = 1
MAX_REF_PLATES = 5


def _normalize_ref_item(item: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    规范化单条参考盘记录。
    必填: image (ndarray), total_gt (int, 或 points 可推导)
    可选: name, points, strategy (默认 count_only；有足够点时可 partial/full)
    """
    if item is None or item.get("image") is None:
        raise ValueError(f"参考盘#{index + 1} 缺少 image")

    name = item.get("name") or f"ref_{index + 1}"
    points_list = renumber_points(item["points"]) if item.get("points") else []
    strategy = (item.get("strategy") or STRATEGY_COUNT_ONLY).strip()

    total_gt = item.get("total_gt")
    if strategy == STRATEGY_FULL_POINTS:
        if len(points_list) < 1:
            raise ValueError(f"{name}: 全量点选需要至少一个点")
        total_gt = len(points_list)
    elif strategy == STRATEGY_PARTIAL_POINTS:
        if total_gt is None or int(total_gt) < 1:
            raise ValueError(f"{name}: 部分点选必须提供总数 N")
        if len(points_list) < 5:
            raise ValueError(f"{name}: 部分点选至少 5 个样本点（当前 {len(points_list)}）")
        total_gt = int(total_gt)
    else:
        strategy = STRATEGY_COUNT_ONLY
        # 增强：仅有点数且未填 N 时，可用点数作为 N（等同全量但弱匹配可选）
        if (total_gt is None or int(total_gt) < 1) and len(points_list) >= 1:
            total_gt = len(points_list)
            strategy = STRATEGY_FULL_POINTS
        elif total_gt is None or int(total_gt) < 1:
            raise ValueError(f"{name}: 必须提供真值总数 N（图+N 为主）")
        else:
            total_gt = int(total_gt)
            # 有点则作为增强（弱匹配），策略记为 partial 若点数>=5 否则仍 count_only + 可选弱匹配
            if len(points_list) >= 5:
                strategy = STRATEGY_PARTIAL_POINTS

    return {
        "name": name,
        "image": item["image"],
        "total_gt": int(total_gt),
        "points": points_list,
        "strategy": strategy,
        "path": item.get("path"),
    }


def _score_one_ref(
    image: np.ndarray,
    params: Dict[str, Any],
    total_gt: int,
    points_list: List[Dict[str, Any]],
    strategy: str,
) -> Dict[str, Any]:
    result = _run(image, params)
    if result.get("error"):
        return {
            "loss": 1e9,
            "fit_error": 1.0,
            "match_score": None,
            "predicted_count": 0,
            "result": result,
        }

    use_match = strategy == STRATEGY_FULL_POINTS and len(points_list) > 0
    # 部分点选 / 图+N 附带点选 → 弱匹配增强
    weak_match = (
        strategy in (STRATEGY_PARTIAL_POINTS, STRATEGY_COUNT_ONLY)
        and len(points_list) > 0
    )
    scale = float(result.get("scale_ratio") or 1.0)
    gt_scaled = scale_points(points_list, scale) if points_list else None

    loss, fit_error, m_score = _score_candidate(
        result, total_gt, gt_scaled,
        use_match=use_match or weak_match,
    )
    if weak_match and not use_match and m_score is not None:
        # 点选增强权重低于全量匹配
        w = 0.25 if strategy == STRATEGY_COUNT_ONLY else 0.2
        loss = _count_cost(int(result.get("count", 0)), total_gt) + (1.0 - m_score) * w

    return {
        "loss": loss,
        "fit_error": float(fit_error),
        "match_score": m_score,
        "predicted_count": int(result.get("count", 0)),
        "result": result,
    }


def calibrate_multi(
    references: Sequence[Dict[str, Any]],
    max_evals: int = 40,
    time_limit_sec: float = 60.0,
    base_params: Optional[Dict[str, Any]] = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    多参考盘联合标定（建议 2～5 盘，最多 MAX_REF_PLATES）。

    每条 reference:
      - image: np.ndarray (必填)
      - total_gt: int (图+N 主路径必填；全量点选可省略)
      - points: 可选，点选增强
      - name / path: 可选
      - strategy: 可选 count_only | partial_points | full_points
        默认 count_only；若提供 ≥5 点且有 N → 自动按 partial 增强

    目标: 最小化各盘 loss 的平均值（等权）。

    返回:
      success, params, fit_error (平均相对误差), plate_results[],
      evals, elapsed_ms, warnings, message, n_refs, version
    """
    t0 = time.time()

    if not references:
        return {"success": False, "message": "请至少提供 1 块参考盘"}

    if len(references) > MAX_REF_PLATES:
        return {
            "success": False,
            "message": f"参考盘最多支持 {MAX_REF_PLATES} 块（当前 {len(references)}）",
        }

    try:
        refs = [_normalize_ref_item(item, i) for i, item in enumerate(references)]
    except ValueError as e:
        return {"success": False, "message": str(e)}

    n_refs = len(refs)

    # 搜索空间：合并各盘点集先验（用第一张图尺寸 + 所有点）
    all_points: List[Dict[str, Any]] = []
    for r in refs:
        all_points.extend(r["points"])
    # 策略：有任一点增强则用 partial 空间，否则 count_only
    space_strategy = STRATEGY_PARTIAL_POINTS if len(all_points) >= 2 else STRATEGY_COUNT_ONLY
    space = _build_search_space(space_strategy, refs[0]["image"], all_points or None, base_params)

    # 多盘每轮更贵，适当限制评估次数
    effective_max = max(12, max_evals // max(1, n_refs // 2 + 1)) if n_refs >= 3 else max_evals
    effective_max = min(effective_max, max_evals)
    if len(space) > effective_max:
        rest = space[1:]
        random.Random(7).shuffle(rest)
        space = [space[0]] + rest[: effective_max - 1]

    # 时间预算随盘数略增
    time_budget = max(time_limit_sec, 25.0 * n_refs)

    best_params = None
    best_loss = 1e18
    best_plate_meta: List[Dict[str, Any]] = []
    evals = 0

    for idx, params in enumerate(space):
        if time.time() - t0 > time_budget:
            break

        plate_metas = []
        losses = []
        for r in refs:
            meta = _score_one_ref(
                r["image"], params, r["total_gt"], r["points"], r["strategy"]
            )
            plate_metas.append({
                "name": r["name"],
                "path": r.get("path"),
                "total_gt": r["total_gt"],
                "strategy": r["strategy"],
                "n_points": len(r["points"]),
                "predicted_count": meta["predicted_count"],
                "fit_error": meta["fit_error"],
                "match_score": meta["match_score"],
                "loss": meta["loss"],
                # 多盘时不保留完整大图，减内存；仅最优时再跑一遍可取图
            })
            losses.append(meta["loss"])

        mean_loss = float(np.mean(losses)) if losses else 1e9
        evals += 1

        if mean_loss < best_loss:
            best_loss = mean_loss
            best_params = params
            best_plate_meta = plate_metas

        if progress_callback:
            avg_fit = float(np.mean([m["fit_error"] for m in plate_metas])) if plate_metas else 1.0
            progress_callback(idx + 1, len(space), n_refs, avg_fit)

        # 各盘都足够好则提前停
        if plate_metas and all(m["fit_error"] <= 0.03 for m in plate_metas):
            break

    elapsed_ms = (time.time() - t0) * 1000.0

    if best_params is None:
        return {
            "success": False,
            "message": "联合标定失败：无有效候选",
            "evals": evals,
            "elapsed_ms": elapsed_ms,
            "n_refs": n_refs,
        }

    params_out = _normalize_params(best_params)

    # 用最优参数再跑一遍，带上预览结果（processed_image）
    plate_results = []
    for r in refs:
        meta = _score_one_ref(
            r["image"], params_out, r["total_gt"], r["points"], r["strategy"]
        )
        plate_results.append({
            "name": r["name"],
            "path": r.get("path"),
            "total_gt": r["total_gt"],
            "strategy": r["strategy"],
            "n_points": len(r["points"]),
            "predicted_count": meta["predicted_count"],
            "fit_error": meta["fit_error"],
            "match_score": meta["match_score"],
            "result": meta["result"],
        })

    fit_errors = [p["fit_error"] for p in plate_results]
    mean_fit = float(np.mean(fit_errors))
    max_fit = float(np.max(fit_errors))

    warnings = []
    if mean_fit > 0.15:
        warnings.append("平均拟合误差较大，建议增加参考盘、检查真值 N，或对难盘补充点选")
    if max_fit > 0.25:
        worst = max(plate_results, key=lambda x: x["fit_error"])
        warnings.append(
            f"参考盘「{worst['name']}」误差偏大 ({worst['fit_error']:.1%})，可单独检查该盘拍照或真值"
        )
    if n_refs == 1:
        warnings.append("当前仅 1 块参考盘；建议 2～5 块联合标定以提高泛化")
    if all(p["n_points"] == 0 for p in plate_results):
        warnings.append("均未使用点选增强（纯图+N）；同批次拍照条件请尽量一致")

    lines = [f"联合标定完成：{n_refs} 块参考盘，平均相对误差 {mean_fit:.1%}（最大 {max_fit:.1%}）"]
    for p in plate_results:
        lines.append(
            f"  · {p['name']}: 预测 {p['predicted_count']} / 真值 {p['total_gt']} "
            f"(误差 {p['fit_error']:.1%}, 点 {p['n_points']})"
        )

    return {
        "success": True,
        "strategy": "multi_ref",
        "params": params_out,
        "n_refs": n_refs,
        "fit_error": mean_fit,
        "max_fit_error": max_fit,
        "plate_results": plate_results,
        "ref_count_gt": [p["total_gt"] for p in plate_results],
        "predicted_count": [p["predicted_count"] for p in plate_results],
        "evals": evals,
        "elapsed_ms": elapsed_ms,
        "warnings": warnings,
        "message": "\n".join(lines),
        "version": "1.1",
        # 兼容单盘字段（取第一盘）
        "result": plate_results[0].get("result") if plate_results else None,
        "match_score": plate_results[0].get("match_score") if plate_results else None,
    }


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
    单参考盘标定（兼容旧接口）。内部委托 calibrate_multi。
    """
    def _prog(i, n, n_refs, avg_fit):
        if progress_callback:
            # 旧回调签名: (i, n, pred, gt) — 多盘时 pred/gt 用占位
            progress_callback(i, n, None, total_gt)

    result = calibrate_multi(
        references=[{
            "image": image,
            "total_gt": total_gt,
            "points": points,
            "strategy": strategy,
            "name": "ref",
        }],
        max_evals=max_evals,
        time_limit_sec=time_limit_sec,
        base_params=base_params,
        progress_callback=_prog if progress_callback else None,
    )

    if not result.get("success"):
        return result

    # 展开为单盘风格字段
    pr = (result.get("plate_results") or [{}])[0]
    result["strategy"] = pr.get("strategy", strategy)
    result["ref_count_gt"] = pr.get("total_gt", total_gt)
    result["predicted_count"] = pr.get("predicted_count")
    result["fit_error"] = pr.get("fit_error", result.get("fit_error"))
    result["match_score"] = pr.get("match_score")
    result["result"] = pr.get("result")
    result["message"] = (
        f"标定完成：预测 {result['predicted_count']} / 真值 {result['ref_count_gt']}，"
        f"相对误差 {result.get('fit_error', 0):.1%}"
    )
    return result

