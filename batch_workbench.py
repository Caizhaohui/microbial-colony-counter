"""
电脑端批次标定工作台。
策略1: 部分点选 + 总数 N
策略2: 全量点选
策略3: 图片 + 菌落数
不修改原有自动计数流程，由 main.py 工具栏打开。
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageTk

from backend.core.batch import batch_count_paths, results_to_csv_rows
from backend.core.calibrator import (
    STRATEGY_COUNT_ONLY,
    STRATEGY_FULL_POINTS,
    STRATEGY_PARTIAL_POINTS,
    calibrate,
    params_to_process_kwargs,
)
from backend.core.pointset import (
    draw_points_on_image,
    find_nearest_point,
    make_point,
    renumber_points,
)


class BatchWorkbench(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("批次标定工作台")
        self.geometry("1100x720")
        self.minsize(900, 600)

        # 状态
        self.ref_path: Optional[str] = None
        self.ref_image: Optional[np.ndarray] = None  # BGR
        self.points: List[Dict[str, Any]] = []
        self.undo_stack: List[List[Dict[str, Any]]] = []
        self.calibrated_params: Optional[Dict[str, Any]] = None
        self.calib_meta: Optional[Dict[str, Any]] = None
        self.batch_paths: List[str] = []
        self.batch_results: List[Dict[str, Any]] = []
        self.is_busy = False

        # 显示缩放
        self._photo = None
        self._disp_scale = 1.0
        self._offset = (0.0, 0.0)
        self._img_size = (1, 1)

        self.strategy_var = tk.StringVar(value=STRATEGY_COUNT_ONLY)
        self.total_n_var = tk.StringVar(value="")
        self.batch_name_var = tk.StringVar(value="批次1")
        self.status_var = tk.StringVar(value="请加载参考盘图片")
        self.point_count_var = tk.StringVar(value="点选: 0")
        self.result_summary_var = tk.StringVar(value="")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(top, text="批次名:", bg="#f0f0f0").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self.batch_name_var, width=12).pack(side=tk.LEFT, padx=4)

        tk.Button(top, text="📂 加载参考盘", command=self.load_reference,
                  bg="#4CAF50", fg="white", relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=6)

        tk.Label(top, text="策略:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(12, 2))
        strategies = [
            (STRATEGY_PARTIAL_POINTS, "1.部分点选+总数"),
            (STRATEGY_FULL_POINTS, "2.全量点选"),
            (STRATEGY_COUNT_ONLY, "3.图片+菌落数"),
        ]
        for val, label in strategies:
            tk.Radiobutton(
                top, text=label, variable=self.strategy_var, value=val,
                bg="#f0f0f0", command=self._on_strategy_change
            ).pack(side=tk.LEFT, padx=2)

        mid = tk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左侧：图像 + 点选
        left = tk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tip = tk.Label(
            left,
            text="点选：左键加点 · 右键删最近点 · Ctrl+Z 撤销 · 滚轮缩放提示见状态栏",
            fg="#666", anchor="w"
        )
        tip.pack(fill=tk.X)

        canvas_frame = tk.Frame(left, bg="#333")
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="#2b2b2b", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Control-z>", self._on_undo)
        self.bind("<Control-Z>", self._on_undo)
        self.canvas.bind("<Control-z>", self._on_undo)
        self.canvas.bind("<Control-Z>", self._on_undo)

        tool_bar = tk.Frame(left)
        tool_bar.pack(fill=tk.X, pady=4)
        tk.Label(tool_bar, textvariable=self.point_count_var, font=("", 11, "bold"),
                 fg="#c62828").pack(side=tk.LEFT)
        tk.Button(tool_bar, text="清空点", command=self.clear_points).pack(side=tk.LEFT, padx=6)
        tk.Button(tool_bar, text="撤销", command=lambda: self._on_undo(None)).pack(side=tk.LEFT)
        tk.Button(tool_bar, text="导出点JSON", command=self.export_points).pack(side=tk.LEFT, padx=6)
        tk.Button(tool_bar, text="保存标注图", command=self.save_annotated).pack(side=tk.LEFT)

        # 右侧：参数与结果
        right = tk.Frame(mid, width=320)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)

        n_frame = tk.LabelFrame(right, text="真值总数 N", padx=8, pady=8)
        n_frame.pack(fill=tk.X, pady=4)
        self.n_entry = tk.Entry(n_frame, textvariable=self.total_n_var, font=("", 14), width=10)
        self.n_entry.pack(side=tk.LEFT)
        self.n_hint = tk.Label(n_frame, text="策略3必填；策略1必填；策略2=点数", fg="#888", wraplength=280)
        self.n_hint.pack(side=tk.LEFT, padx=6)

        tk.Button(
            right, text="▶ 开始学习 / 标定", command=self.start_calibrate,
            bg="#1976D2", fg="white", font=("", 11, "bold"), relief=tk.FLAT, pady=8
        ).pack(fill=tk.X, pady=8)

        self.calib_info = tk.Text(right, height=10, wrap=tk.WORD, font=("Consolas", 9))
        self.calib_info.pack(fill=tk.X, pady=4)
        self.calib_info.insert("1.0", "标定结果将显示在这里。\n")
        self.calib_info.config(state=tk.DISABLED)

        batch_frame = tk.LabelFrame(right, text="批量计数（其余平板）", padx=8, pady=8)
        batch_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        tk.Button(batch_frame, text="添加图片…", command=self.add_batch_images).pack(fill=tk.X)
        tk.Button(batch_frame, text="清空列表", command=self.clear_batch).pack(fill=tk.X, pady=4)
        self.batch_list = tk.Listbox(batch_frame, height=8)
        self.batch_list.pack(fill=tk.BOTH, expand=True, pady=4)
        tk.Button(
            batch_frame, text="批量计数", command=self.start_batch,
            bg="#00897B", fg="white", relief=tk.FLAT, pady=6
        ).pack(fill=tk.X)
        tk.Button(batch_frame, text="导出 CSV", command=self.export_csv).pack(fill=tk.X, pady=4)
        tk.Button(batch_frame, text="保存参数 JSON", command=self.save_params_json).pack(fill=tk.X)
        tk.Button(batch_frame, text="应用到主窗口参数", command=self.apply_to_main).pack(fill=tk.X, pady=4)

        tk.Label(right, textvariable=self.result_summary_var, fg="#333", wraplength=300,
                 justify=tk.LEFT).pack(fill=tk.X, pady=4)

        status = tk.Label(self, textvariable=self.status_var, anchor="w", bg="#eeeeee", padx=8)
        status.pack(fill=tk.X, side=tk.BOTTOM)

        self._on_strategy_change()

    def _on_close(self):
        self.destroy()

    def _on_strategy_change(self):
        s = self.strategy_var.get()
        if s == STRATEGY_FULL_POINTS:
            self.n_hint.config(text="全量点选：N 自动等于点数，无需填写")
            self.n_entry.config(state=tk.DISABLED)
        elif s == STRATEGY_PARTIAL_POINTS:
            self.n_entry.config(state=tk.NORMAL)
            self.n_hint.config(text="部分点选：至少点 5 个样本，并填写整盘真值 N")
        else:
            self.n_entry.config(state=tk.NORMAL)
            self.n_hint.config(text="仅填总数：不点选也可标定（无位置约束）")
        self._update_point_label()

    def _set_busy(self, busy: bool, msg: str = ""):
        self.is_busy = busy
        if msg:
            self.status_var.set(msg)

    def _set_info(self, text: str):
        self.calib_info.config(state=tk.NORMAL)
        self.calib_info.delete("1.0", tk.END)
        self.calib_info.insert("1.0", text)
        self.calib_info.config(state=tk.DISABLED)

    # ── 参考图与点选 ──────────────────────────────
    def load_reference(self):
        path = filedialog.askopenfilename(
            title="选择参考盘图片",
            filetypes=[("图片", "*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff"), ("所有", "*.*")]
        )
        if not path:
            return
        img = cv2.imread(path)
        if img is None:
            messagebox.showerror("错误", "无法读取图片", parent=self)
            return
        self.ref_path = path
        self.ref_image = img
        self.points = []
        self.undo_stack = []
        self.calibrated_params = None
        self.calib_meta = None
        self.status_var.set(f"参考盘: {os.path.basename(path)}  ({img.shape[1]}x{img.shape[0]})")
        self._update_point_label()
        self._redraw()

    def _push_undo(self):
        self.undo_stack.append([dict(p) for p in self.points])
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def _on_undo(self, event=None):
        if self.is_busy or not self.undo_stack:
            return
        self.points = self.undo_stack.pop()
        self._update_point_label()
        self._redraw()

    def clear_points(self):
        if self.is_busy:
            return
        self._push_undo()
        self.points = []
        self._update_point_label()
        self._redraw()

    def _update_point_label(self):
        self.point_count_var.set(f"点选: {len(self.points)}")
        if self.strategy_var.get() == STRATEGY_FULL_POINTS:
            self.total_n_var.set(str(len(self.points)))

    def _canvas_to_image(self, cx: float, cy: float) -> Optional[Tuple[float, float]]:
        if self.ref_image is None:
            return None
        ox, oy = self._offset
        if self._disp_scale <= 0:
            return None
        ix = (cx - ox) / self._disp_scale
        iy = (cy - oy) / self._disp_scale
        h, w = self.ref_image.shape[:2]
        if ix < 0 or iy < 0 or ix >= w or iy >= h:
            return None
        return ix, iy

    def _on_left_click(self, event):
        if self.is_busy or self.ref_image is None:
            return
        s = self.strategy_var.get()
        if s == STRATEGY_COUNT_ONLY:
            self.status_var.set("当前为「图片+菌落数」策略，无需点选；可切换策略 1/2 进行点选")
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords is None:
            return
        self._push_undo()
        ix, iy = coords
        self.points.append(make_point(ix, iy, point_id=len(self.points) + 1))
        self.points = renumber_points(self.points)
        self._update_point_label()
        self._redraw()

    def _on_right_click(self, event):
        if self.is_busy or self.ref_image is None or not self.points:
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords is None:
            return
        ix, iy = coords
        # 容差随缩放
        tol = max(12.0, 18.0 / max(self._disp_scale, 0.01))
        idx = find_nearest_point(self.points, ix, iy, max_dist=tol)
        if idx is None:
            return
        self._push_undo()
        self.points.pop(idx)
        self.points = renumber_points(self.points)
        self._update_point_label()
        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        if self.ref_image is None:
            return
        img = self.ref_image
        if self.points:
            img = draw_points_on_image(img, self.points, radius=max(4, int(6)), with_index=True)

        cw = max(self.canvas.winfo_width(), 10)
        ch = max(self.canvas.winfo_height(), 10)
        h, w = img.shape[:2]
        self._img_size = (w, h)
        scale = min(cw / w, ch / h)
        self._disp_scale = scale
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        ox = (cw - nw) / 2.0
        oy = (ch - nh) / 2.0
        self._offset = (ox, oy)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb).resize((nw, nh), Image.Resampling.BILINEAR)
        self._photo = ImageTk.PhotoImage(pil)
        self.canvas.create_image(ox, oy, image=self._photo, anchor=tk.NW)

    def export_points(self):
        if not self.points:
            messagebox.showinfo("提示", "当前没有点", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="导出点集", defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.points, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"已导出点集: {path}")

    def save_annotated(self):
        if self.ref_image is None:
            return
        img = draw_points_on_image(self.ref_image, self.points) if self.points else self.ref_image
        path = filedialog.asksaveasfilename(
            title="保存标注图", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
        )
        if path:
            cv2.imwrite(path, img)
            self.status_var.set(f"已保存: {path}")

    # ── 标定 ──────────────────────────────────────
    def start_calibrate(self):
        if self.is_busy:
            return
        if self.ref_image is None:
            messagebox.showwarning("提示", "请先加载参考盘图片", parent=self)
            return

        strategy = self.strategy_var.get()
        total_gt = None
        pts = None

        if strategy == STRATEGY_COUNT_ONLY:
            try:
                total_gt = int(self.total_n_var.get().strip())
            except Exception:
                messagebox.showerror("错误", "请输入有效的真值总数 N", parent=self)
                return
            if total_gt < 1:
                messagebox.showerror("错误", "N 必须 ≥ 1", parent=self)
                return
        elif strategy == STRATEGY_PARTIAL_POINTS:
            try:
                total_gt = int(self.total_n_var.get().strip())
            except Exception:
                messagebox.showerror("错误", "部分点选必须填写整盘真值 N", parent=self)
                return
            if len(self.points) < 5:
                messagebox.showerror("错误", f"部分点选至少需要 5 个点（当前 {len(self.points)}）", parent=self)
                return
            pts = self.points
        else:  # full
            if len(self.points) < 1:
                messagebox.showerror("错误", "请先在图上点选菌落", parent=self)
                return
            pts = self.points
            total_gt = len(self.points)

        self._set_busy(True, "正在标定学习，请稍候…")
        self._set_info("标定中…\n")

        def worker():
            try:
                def prog(i, n, pred, gt):
                    self.after(0, lambda: self.status_var.set(
                        f"标定中 {i}/{n}  当前最优预测≈{pred} / 真值{gt}"
                    ))

                result = calibrate(
                    image=self.ref_image,
                    strategy=strategy,
                    total_gt=total_gt,
                    points=pts,
                    max_evals=40,
                    time_limit_sec=28.0,
                    progress_callback=prog,
                )
                self.after(0, lambda: self._on_calib_done(result))
            except Exception as e:
                self.after(0, lambda: self._on_calib_done({
                    "success": False, "message": str(e)
                }))

        threading.Thread(target=worker, daemon=True).start()

    def _on_calib_done(self, result: Dict[str, Any]):
        self._set_busy(False)
        if not result.get("success"):
            self.status_var.set("标定失败")
            self._set_info(result.get("message", "未知错误"))
            messagebox.showerror("标定失败", result.get("message", "未知错误"), parent=self)
            return

        self.calibrated_params = result["params"]
        self.calib_meta = result
        lines = [
            result.get("message", "完成"),
            f"策略: {result.get('strategy')}",
            f"真值 N: {result.get('ref_count_gt')}  预测: {result.get('predicted_count')}",
            f"相对误差: {result.get('fit_error', 0):.2%}",
            f"匹配分: {result.get('match_score')}",
            f"评估次数: {result.get('evals')}  耗时: {result.get('elapsed_ms', 0):.0f} ms",
            "",
            "参数 θ*:",
        ]
        for k, v in result["params"].items():
            lines.append(f"  {k} = {v}")
        warns = result.get("warnings") or []
        if warns:
            lines.append("")
            lines.append("提示:")
            for w in warns:
                lines.append(f"  · {w}")
        self._set_info("\n".join(lines))
        self.status_var.set("标定完成，可进行批量计数或应用到主窗口")
        self.result_summary_var.set(
            f"参考盘: 预测 {result.get('predicted_count')} / 真值 {result.get('ref_count_gt')}"
        )

        # 显示标定预览到画布（叠加自动结果若有）
        proc = (result.get("result") or {}).get("processed_image")
        if proc is not None:
            # 临时展示：不替换 ref_image，另开简单刷新用标注点图即可
            pass

    # ── 批量 ──────────────────────────────────────
    def add_batch_images(self):
        paths = filedialog.askopenfilenames(
            title="选择其余平板图片",
            filetypes=[("图片", "*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff"), ("所有", "*.*")]
        )
        if not paths:
            return
        for p in paths:
            if p not in self.batch_paths:
                self.batch_paths.append(p)
                self.batch_list.insert(tk.END, os.path.basename(p))
        self.status_var.set(f"批量列表: {len(self.batch_paths)} 张")

    def clear_batch(self):
        self.batch_paths = []
        self.batch_results = []
        self.batch_list.delete(0, tk.END)
        self.result_summary_var.set("")

    def start_batch(self):
        if self.is_busy:
            return
        if not self.calibrated_params:
            messagebox.showwarning("提示", "请先完成标定学习", parent=self)
            return
        if not self.batch_paths:
            messagebox.showwarning("提示", "请先添加批量图片", parent=self)
            return

        self._set_busy(True, "批量计数中…")
        params = dict(self.calibrated_params)
        paths = list(self.batch_paths)

        def worker():
            def prog(i, n, name, count):
                self.after(0, lambda: self.status_var.set(
                    f"批量 {i}/{n}: {name} → {count}"
                ))

            try:
                results = batch_count_paths(paths, params, progress_callback=prog)
                self.after(0, lambda: self._on_batch_done(results))
            except Exception as e:
                self.after(0, lambda: self._on_batch_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_batch_fail(self, msg: str):
        self._set_busy(False)
        messagebox.showerror("批量失败", msg, parent=self)
        self.status_var.set("批量失败")

    def _on_batch_done(self, results: List[Dict[str, Any]]):
        self.is_busy = False
        self.batch_results = results
        # 刷新列表显示计数
        self.batch_list.delete(0, tk.END)
        total = 0
        ok = 0
        for r in results:
            err = r.get("error")
            if err:
                self.batch_list.insert(tk.END, f"{r['name']}: 错误 {err}")
            else:
                self.batch_list.insert(tk.END, f"{r['name']}: {r['count']}")
                total += r["count"]
                ok += 1
        self.result_summary_var.set(f"批量完成: {ok}/{len(results)} 成功, 菌落合计 {total}")
        self.status_var.set("批量计数完成，可导出 CSV")
        messagebox.showinfo("完成", f"已处理 {len(results)} 张图片", parent=self)

    def export_csv(self):
        if not self.batch_results:
            messagebox.showinfo("提示", "没有批量结果", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="导出 CSV", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        text = results_to_csv_rows(self.batch_results, self.calibrated_params)
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(text)
        self.status_var.set(f"已导出: {path}")

    def save_params_json(self):
        if not self.calibrated_params:
            messagebox.showinfo("提示", "没有标定参数", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="保存参数", defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        payload = {
            "batch_name": self.batch_name_var.get(),
            "params": self.calibrated_params,
            "meta": {
                "strategy": (self.calib_meta or {}).get("strategy"),
                "ref_count_gt": (self.calib_meta or {}).get("ref_count_gt"),
                "predicted_count": (self.calib_meta or {}).get("predicted_count"),
                "fit_error": (self.calib_meta or {}).get("fit_error"),
                "match_score": (self.calib_meta or {}).get("match_score"),
                "ref_path": self.ref_path,
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"参数已保存: {path}")

    def apply_to_main(self):
        """将标定参数写回主窗口控件（若存在）。"""
        if not self.calibrated_params:
            messagebox.showinfo("提示", "没有标定参数", parent=self)
            return
        master = self.master
        p = params_to_process_kwargs(self.calibrated_params)
        try:
            if hasattr(master, "blur_ksize"):
                master.blur_ksize.set(p["blur_ksize"])
            if hasattr(master, "thresh_method"):
                master.thresh_method.set("手动阈值" if p["thresh_method"] == "manual" else "自适应阈值")
                if hasattr(master, "on_thresh_method_change"):
                    master.on_thresh_method_change()
            if hasattr(master, "thresh_val"):
                master.thresh_val.set(p["thresh_val"])
            if hasattr(master, "adaptive_block_size"):
                master.adaptive_block_size.set(p["adaptive_block_size"])
            if hasattr(master, "adaptive_c"):
                master.adaptive_c.set(p["adaptive_c"])
            if hasattr(master, "min_area"):
                master.min_area.set(p["min_area"])
            if hasattr(master, "max_area"):
                master.max_area.set(p["max_area"])
            if hasattr(master, "min_distance_from_edge"):
                master.min_distance_from_edge.set(p["min_distance_from_edge"])
            if hasattr(master, "detect_petri_dish"):
                master.detect_petri_dish.set(p["detect_petri_dish"])
            if hasattr(master, "use_watershed"):
                master.use_watershed.set(p["use_watershed"])
            if hasattr(master, "min_circularity"):
                master.min_circularity.set(int(round(p["min_circularity"] * 100)))
            messagebox.showinfo("成功", "已将标定参数应用到主窗口", parent=self)
            self.status_var.set("参数已应用到主窗口")
        except Exception as e:
            messagebox.showerror("错误", f"应用失败: {e}", parent=self)


def open_batch_workbench(master):
    """打开工作台（避免重复多开可简单允许多实例）。"""
    win = BatchWorkbench(master)
    win.transient(master)
    win.focus_set()
    return win
