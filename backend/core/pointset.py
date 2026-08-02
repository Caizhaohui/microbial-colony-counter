"""
菌落点集工具：坐标变换、序列化、标注图绘制。
坐标约定：一律使用原图像素坐标 (x, y)。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
import json
import cv2
import numpy as np


PointDict = Dict[str, Any]


def make_point(x: float, y: float, point_id: int = 0, source: str = "manual") -> PointDict:
    return {
        "id": int(point_id),
        "x": float(x),
        "y": float(y),
        "source": source,
    }


def renumber_points(points: Sequence[PointDict]) -> List[PointDict]:
    out = []
    for i, p in enumerate(points, start=1):
        out.append(make_point(p["x"], p["y"], point_id=i, source=p.get("source", "manual")))
    return out


def points_to_json(points: Sequence[PointDict]) -> str:
    return json.dumps(list(points), ensure_ascii=False)


def points_from_json(text: str) -> List[PointDict]:
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("points JSON must be a list")
    result = []
    for i, item in enumerate(data, start=1):
        result.append(make_point(item["x"], item["y"], point_id=item.get("id", i),
                                 source=item.get("source", "manual")))
    return renumber_points(result)


def scale_points(points: Sequence[PointDict], scale_ratio: float) -> List[PointDict]:
    """将原图坐标映射到缩放后图像坐标。"""
    if scale_ratio == 1.0:
        return renumber_points(points)
    out = []
    for p in points:
        out.append(make_point(p["x"] * scale_ratio, p["y"] * scale_ratio,
                              point_id=p.get("id", 0), source=p.get("source", "manual")))
    return renumber_points(out)


def display_to_image_coords(
    dx: float, dy: float,
    display_size: Tuple[int, int],
    image_size: Tuple[int, int],
    offset: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    """
    将显示/画布坐标转换为原图像素坐标。
    假设图像按等比缩放后居中显示在 display_size 内。
    image_size: (width, height)
    display_size: (width, height)
    offset: 图像左上角在画布上的偏移
    """
    img_w, img_h = image_size
    disp_w, disp_h = display_size
    if img_w <= 0 or img_h <= 0 or disp_w <= 0 or disp_h <= 0:
        return dx, dy

    scale = min(disp_w / img_w, disp_h / img_h)
    drawn_w = img_w * scale
    drawn_h = img_h * scale
    ox = offset[0] if offset[0] else (disp_w - drawn_w) / 2.0
    oy = offset[1] if offset[1] else (disp_h - drawn_h) / 2.0

    ix = (dx - ox) / scale
    iy = (dy - oy) / scale
    return ix, iy


def image_to_display_coords(
    ix: float, iy: float,
    display_size: Tuple[int, int],
    image_size: Tuple[int, int],
    offset: Tuple[float, float] = (0.0, 0.0),
) -> Tuple[float, float]:
    img_w, img_h = image_size
    disp_w, disp_h = display_size
    if img_w <= 0 or img_h <= 0:
        return ix, iy
    scale = min(disp_w / img_w, disp_h / img_h)
    drawn_w = img_w * scale
    drawn_h = img_h * scale
    ox = offset[0] if offset[0] else (disp_w - drawn_w) / 2.0
    oy = offset[1] if offset[1] else (disp_h - drawn_h) / 2.0
    return ox + ix * scale, oy + iy * scale


def find_nearest_point(
    points: Sequence[PointDict],
    x: float, y: float,
    max_dist: float = 20.0,
) -> Optional[int]:
    """返回最近点的列表下标，超过 max_dist 则 None。"""
    best_i = None
    best_d2 = max_dist * max_dist
    for i, p in enumerate(points):
        d2 = (p["x"] - x) ** 2 + (p["y"] - y) ** 2
        if d2 <= best_d2:
            best_d2 = d2
            best_i = i
    return best_i


def draw_points_on_image(
    image: np.ndarray,
    points: Sequence[PointDict],
    color: Tuple[int, int, int] = (0, 0, 255),
    radius: int = 6,
    with_index: bool = True,
    thickness: int = 2,
) -> np.ndarray:
    """在 BGR 图像上绘制点标记，返回拷贝。"""
    out = image.copy()
    for p in points:
        cx, cy = int(round(p["x"])), int(round(p["y"]))
        cv2.circle(out, (cx, cy), radius, color, thickness)
        cv2.circle(out, (cx, cy), 2, color, -1)
        if with_index:
            label = str(p.get("id", ""))
            cv2.putText(
                out, label, (cx + radius + 2, cy - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA
            )
    # 左上角计数
    count_text = f"Manual: {len(points)}"
    cv2.putText(out, count_text, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    return out


def estimate_area_prior_from_points(
    points: Sequence[PointDict],
    image_shape: Tuple[int, ...],
) -> Tuple[int, int]:
    """
    根据点间距粗估典型菌落面积范围 (min_area, max_area)。
    使用最近邻距离中位数作为直径代理。
    """
    n = len(points)
    if n < 2:
        # 回退默认
        return 30, 8000

    coords = np.array([[p["x"], p["y"]] for p in points], dtype=np.float64)
    # 每个点到最近邻的距离
    nn_dists = []
    for i in range(n):
        d = np.sqrt(np.sum((coords - coords[i]) ** 2, axis=1))
        d[i] = np.inf
        nn_dists.append(float(np.min(d)))
    med = float(np.median(nn_dists))
    if med < 3:
        med = 8.0
    # 直径约 0.5~1.2 * 最近邻距（避免重叠点）
    diam = max(4.0, med * 0.55)
    area_typ = np.pi * (diam / 2.0) ** 2
    min_area = max(5, int(area_typ * 0.25))
    max_area = max(min_area + 50, int(area_typ * 6.0))
    # 相对图像尺寸限制
    h, w = image_shape[:2]
    max_area = min(max_area, int(h * w * 0.05))
    return min_area, max_area
