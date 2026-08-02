"""
批次批量计数：将标定参数应用到多张图片。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence

import cv2
import numpy as np

from backend.core.algorithm import process_image
from backend.core.calibrator import params_to_process_kwargs, _normalize_params


def process_one(image: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
    kwargs = params_to_process_kwargs(params)
    return process_image(image=image, manual_roi=None, **kwargs)


def batch_count_images(
    images: Sequence[np.ndarray],
    params: Dict[str, Any],
    names: Optional[Sequence[str]] = None,
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """
    对多张图应用同一套参数。
    返回每项: {name, count, error, colony_details, processing ok flags}
    """
    results = []
    n = len(images)
    for i, image in enumerate(images):
        name = names[i] if names and i < len(names) else f"image_{i+1}"
        try:
            r = process_one(image, params)
            item = {
                "name": name,
                "count": int(r.get("count", 0)),
                "error": r.get("error"),
                "colony_details": r.get("colony_details") or [],
                "processed_image": r.get("processed_image"),
                "binary_image": r.get("binary_image"),
                "petri_circle": r.get("petri_circle"),
            }
        except Exception as e:
            item = {
                "name": name,
                "count": 0,
                "error": str(e),
                "colony_details": [],
                "processed_image": None,
                "binary_image": None,
                "petri_circle": None,
            }
        results.append(item)
        if progress_callback:
            progress_callback(i + 1, n, name, item.get("count"))
    return results


def batch_count_paths(
    paths: Sequence[str],
    params: Dict[str, Any],
    progress_callback=None,
) -> List[Dict[str, Any]]:
    images = []
    names = []
    valid_paths = []
    for p in paths:
        img = cv2.imread(p)
        if img is None:
            results_err = {
                "name": os.path.basename(p),
                "path": p,
                "count": 0,
                "error": "无法读取图片",
                "colony_details": [],
                "processed_image": None,
                "binary_image": None,
            }
            # 占位，后面统一处理更简单：先收集
            images.append(None)
            names.append(os.path.basename(p))
            valid_paths.append(p)
        else:
            images.append(img)
            names.append(os.path.basename(p))
            valid_paths.append(p)

    out = []
    n = len(images)
    for i, (img, name, path) in enumerate(zip(images, names, valid_paths)):
        if img is None:
            item = {
                "name": name,
                "path": path,
                "count": 0,
                "error": "无法读取图片",
                "colony_details": [],
                "processed_image": None,
                "binary_image": None,
                "petri_circle": None,
            }
        else:
            try:
                r = process_one(img, params)
                item = {
                    "name": name,
                    "path": path,
                    "count": int(r.get("count", 0)),
                    "error": r.get("error"),
                    "colony_details": r.get("colony_details") or [],
                    "processed_image": r.get("processed_image"),
                    "binary_image": r.get("binary_image"),
                    "petri_circle": r.get("petri_circle"),
                }
            except Exception as e:
                item = {
                    "name": name,
                    "path": path,
                    "count": 0,
                    "error": str(e),
                    "colony_details": [],
                    "processed_image": None,
                    "binary_image": None,
                    "petri_circle": None,
                }
        out.append(item)
        if progress_callback:
            progress_callback(i + 1, n, name, item.get("count"))
    return out


def results_to_csv_rows(items: Sequence[Dict[str, Any]], params: Optional[Dict[str, Any]] = None) -> str:
    """生成简单 CSV 文本。"""
    lines = ["filename,count,error"]
    for it in items:
        err = (it.get("error") or "").replace(",", ";")
        lines.append(f"{it.get('name','')},{it.get('count',0)},{err}")
    if params:
        p = _normalize_params(params)
        lines.append("")
        lines.append("# calibrated params")
        for k, v in p.items():
            lines.append(f"# {k}={v}")
    return "\n".join(lines) + "\n"
