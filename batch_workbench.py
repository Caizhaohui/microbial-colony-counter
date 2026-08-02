"""
电脑端批次标定工作台。

- 多参考盘联合标定（1～5 块，建议 2～5）
- 主路径：图 + 菌落数 N
- 增强：对当前盘可选点选（左键加点 / 右键删点）
- 标定后批量计数其余平板

不修改原有自动计数流程，由 main.py 工具栏打开。
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageTk

from backend.core.batch import batch_count_paths, results_to_csv_rows
from backend.core.calibrator import (
    MAX_REF_PLATES,
    STRATEGY_COUNT_ONLY,
    STRATEGY_FULL_POINTS,
    STRATEGY_PARTIAL_POINTS,
    calibrate_multi,
    params_to_process_kwargs,
)
from backend.core.pointset import (
    draw_points_on_image,
    find_nearest_point,
    make_point,
    renumber_points,
)


class RefPlate:
    """一块参考盘的内存状态。"""

    def __init__(self, path: str, image: np.ndarray, total_gt: Optional[int] = None):
        self.path = path
        self.name = os.path.basename(path)
        self.image = image
        self.total_gt: Optional[int] = total_gt
        self.points: List[Dict[str, Any]] = []
        self.undo_stack: List[List[Dict[str, Any]]] = []

    def display_label(self) -> str:
        n = self.total_gt if self.total_gt is not None else "?"
        pts = len(self.points)
        extra = f", 点{pts}" if pts else ""
        return f"{self.name}  N={n}{extra}"

    def to_ref_dict(self) -> Dict[str, Any]:
        """转为 calibrate_multi 输入。点选为增强：有点且有 N → partial；仅点无 N → full。"""
        d: Dict[str, Any] = {
            "name": self.name,
            "path": self.path,
            "image": self.image,
            "total_gt": self.total_gt,
            "points": list(self.points),
        }
        if self.points and self.total_gt is not None and int(self.total_gt) >= 1:
            if len(self.points) >= 5:
                d["strategy"] = STRATEGY_PARTIAL_POINTS
            else:
                d["strategy"] = STRATEGY_COUNT_ONLY  # 少量点仍可作弱增强（normalize 内）
        elif self.points and (self.total_gt is None or int(self.total_gt) < 1):
            d["strategy"] = STRATEGY_FULL_POINTS
            d["total_gt"] = len(self.points)
        else:
            d["strategy"] = STRATEGY_COUNT_ONLY
        return d


class BatchWorkbench(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("批次标定工作台 · 多参考盘联合标定")
        self.geometry("1180x760")
        self.minsize(960, 640)

        self.refs: List[RefPlate] = []
        self.current_idx: int = -1

        self.calibrated_params: Optional[Dict[str, Any]] = None
        self.calib_meta: Optional[Dict[str, Any]] = None
        self.batch_paths: List[str] = []
        self.batch_results: List[Dict[str, Any]] = []
        self.is_busy = False

        self._photo = None
        self._disp_scale = 1.0
        self._offset = (0.0, 0.0)

        self.batch_name_var = tk.StringVar(value="批次1")
        self.total_n_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(
            value=f"请添加参考盘（建议 2～{MAX_REF_PLATES} 块，主路径：图 + 菌落数 N）"
        )
        self.point_count_var = tk.StringVar(value="当前盘点选: 0")
        self.result_summary_var = tk.StringVar(value="")
        self.ref_count_var = tk.StringVar(value="参考盘: 0 / 最多 5")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ──────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self, bg="#f0f0f0")
        top.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(top, text="批次名:", bg="#f0f0f0").pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self.batch_name_var, width=12).pack(side=tk.LEFT, padx=4)

        tk.Button(
            top, text="➕ 添加参考盘…", command=self.add_references,
            bg="#4CAF50", fg="white", relief=tk.FLAT, padx=10
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(top, text="移除当前", command=self.remove_current_ref).pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="清空参考", command=self.clear_refs).pack(side=tk.LEFT, padx=2)

        tk.Label(top, textvariable=self.ref_count_var, bg="#f0f0f0", fg="#1565C0",
                 font=("", 10, "bold")).pack(side=tk.LEFT, padx=12)

        mid = tk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左侧：参考列表 + 画布
        left = tk.Frame(mid)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        list_frame = tk.LabelFrame(left, text="参考盘列表（点击切换；主路径填 N，点选可选）", padx=4, pady=4)
        list_frame.pack(fill=tk.X)
        self.ref_listbox = tk.Listbox(list_frame, height=5, exportselection=False)
        self.ref_listbox.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.ref_listbox.bind("<<ListboxSelect>>", self._on_ref_select)
        sb = tk.Scrollbar(list_frame, command=self.ref_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.ref_listbox.config(yscrollcommand=sb.set)

        tip = tk.Label(
            left,
            text="当前盘：左键加点（增强）· 右键删点 · Ctrl+Z 撤销 · 下方填写本盘真值 N 后点「保存 N」",
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
        tk.Button(tool_bar, text="导出当前点JSON", command=self.export_points).pack(side=tk.LEFT, padx=6)
        tk.Button(tool_bar, text="保存标注图", command=self.save_annotated).pack(side=tk.LEFT)

        # 右侧
        right = tk.Frame(mid, width=340)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        right.pack_propagate(False)

        n_frame = tk.LabelFrame(right, text="当前盘真值总数 N（图+N 主路径）", padx=8, pady=8)
        n_frame.pack(fill=tk.X, pady=4)
        self.n_entry = tk.Entry(n_frame, textvariable=self.total_n_var, font=("", 14), width=10)
        self.n_entry.pack(side=tk.LEFT)
        tk.Button(n_frame, text="保存 N 到当前盘", command=self.save_n_to_current,
                  bg="#FF9800", fg="white", relief=tk.FLAT).pack(side=tk.LEFT, padx=8)

        help_lbl = tk.Label(
            right,
            text=(
                f"• 建议添加 2～{MAX_REF_PLATES} 块参考盘，每块填写人工计数 N\n"
                "• 点选为增强：可选，有助于面积约束与位置一致性\n"
                "• 联合标定：一套参数同时拟合所有参考盘\n"
                "• 标定后再批量处理其余未标真值的平板"
            ),
            justify=tk.LEFT, fg="#555", wraplength=320
        )
        help_lbl.pack(fill=tk.X, pady=4)

        tk.Button(
            right, text="▶ 联合学习 / 标定", command=self.start_calibrate,
            bg="#1976D2", fg="white", font=("", 11, "bold"), relief=tk.FLAT, pady=8
        ).pack(fill=tk.X, pady=8)

        self.calib_info = tk.Text(right, height=12, wrap=tk.WORD, font=("Consolas", 9))
        self.calib_info.pack(fill=tk.X, pady=4)
        self.calib_info.insert(
            "1.0",
            "标定结果将显示在这里。\n\n"
            "流程：添加 2～5 块参考盘 → 每块填 N → 联合标定 → 批量计数。\n"
        )
        self.calib_info.config(state=tk.DISABLED)

        batch_frame = tk.LabelFrame(right, text="批量计数（其余平板）", padx=8, pady=8)
        batch_frame.pack(fill=tk.BOTH, expand=True, pady=6)
        tk.Button(batch_frame, text="添加图片…", command=self.add_batch_images).pack(fill=tk.X)
        tk.Button(batch_frame, text="清空列表", command=self.clear_batch).pack(fill=tk.X, pady=4)
        self.batch_list = tk.Listbox(batch_frame, height=6)
        self.batch_list.pack(fill=tk.BOTH, expand=True, pady=4)
        tk.Button(
            batch_frame, text="批量计数", command=self.start_batch,
            bg="#00897B", fg="white", relief=tk.FLAT, pady=6
        ).pack(fill=tk.X)
        tk.Button(batch_frame, text="导出 CSV", command=self.export_csv).pack(fill=tk.X, pady=4)
        tk.Button(batch_frame, text="保存参数 JSON", command=self.save_params_json).pack(fill=tk.X)
        tk.Button(batch_frame, text="应用到主窗口参数", command=self.apply_to_main).pack(fill=tk.X, pady=4)

        tk.Label(right, textvariable=self.result_summary_var, fg="#333", wraplength=320,
                 justify=tk.LEFT).pack(fill=tk.X, pady=4)

        status = tk.Label(self, textvariable=self.status_var, anchor="w", bg="#eeeeee", padx=8)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _on_close(self):
        self.destroy()

    def _set_busy(self, busy: bool, msg: str = ""):
        self.is_busy = busy
        if msg:
            self.status_var.set(msg)

    def _set_info(self, text: str):
        self.calib_info.config(state=tk.NORMAL)
        self.calib_info.delete("1.0", tk.END)
        self.calib_info.insert("1.0", text)
        self.calib_info.config(state=tk.DISABLED)

    def _current(self) -> Optional[RefPlate]:
        if 0 <= self.current_idx < len(self.refs):
            return self.refs[self.current_idx]
        return None

    def _refresh_ref_list(self, select: Optional[int] = None):
        self.ref_listbox.delete(0, tk.END)
        for r in self.refs:
            self.ref_listbox.insert(tk.END, r.display_label())
        self.ref_count_var.set(f"参考盘: {len(self.refs)} / 最多 {MAX_REF_PLATES}")
        if select is not None and 0 <= select < len(self.refs):
            self.ref_listbox.selection_clear(0, tk.END)
            self.ref_listbox.selection_set(select)
            self.ref_listbox.activate(select)
            self.current_idx = select
        self._sync_n_entry()
        self._update_point_label()
        self._redraw()

    def _sync_n_entry(self):
        cur = self._current()
        if cur and cur.total_gt is not None:
            self.total_n_var.set(str(cur.total_gt))
        else:
            self.total_n_var.set("")

    def _on_ref_select(self, event=None):
        sel = self.ref_listbox.curselection()
        if not sel:
            return
        # 切换前可自动尝试保存 N 输入框（不打断）
        self._try_autosave_n()
        self.current_idx = int(sel[0])
        self._sync_n_entry()
        self._update_point_label()
        self._redraw()
        cur = self._current()
        if cur:
            self.status_var.set(f"当前参考盘: {cur.name}")

    def _try_autosave_n(self):
        cur = self._current()
        if not cur:
            return
        text = self.total_n_var.get().strip()
        if not text:
            return
        try:
            cur.total_gt = int(text)
            self._refresh_ref_list(select=self.current_idx)
        except ValueError:
            pass

    # ── 参考盘管理 ────────────────────────────────
    def add_references(self):
        if self.is_busy:
            return
        remain = MAX_REF_PLATES - len(self.refs)
        if remain <= 0:
            messagebox.showwarning(
                "已达上限",
                f"参考盘最多 {MAX_REF_PLATES} 块。请先移除部分再添加。",
                parent=self,
            )
            return
        paths = filedialog.askopenfilenames(
            title=f"选择参考盘图片（还可添加 {remain} 块）",
            filetypes=[("图片", "*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff"), ("所有", "*.*")]
        )
        if not paths:
            return

        added = 0
        for path in paths:
            if len(self.refs) >= MAX_REF_PLATES:
                messagebox.showinfo("提示", f"已达上限 {MAX_REF_PLATES} 块，后续文件已忽略。", parent=self)
                break
            if any(r.path == path for r in self.refs):
                continue
            img = cv2.imread(path)
            if img is None:
                messagebox.showwarning("跳过", f"无法读取: {path}", parent=self)
                continue

            # 弹窗询问 N（主路径）
            n = simpledialog.askinteger(
                "参考盘真值 N",
                f"请输入「{os.path.basename(path)}」的人工菌落总数 N：\n"
                "（可稍后在右侧修改；点选为可选项）",
                parent=self,
                minvalue=1,
                maxvalue=100000,
            )
            self.refs.append(RefPlate(path, img, total_gt=n))
            added += 1

        if added:
            self._refresh_ref_list(select=len(self.refs) - 1)
            self.status_var.set(f"已添加 {added} 块参考盘，共 {len(self.refs)} 块")
            if len(self.refs) == 1:
                messagebox.showinfo(
                    "提示",
                    "已添加 1 块参考盘。\n建议再添加 1～4 块有真值的盘做联合标定，泛化通常更好。",
                    parent=self,
                )

    def remove_current_ref(self):
        if self.is_busy or not self.refs:
            return
        cur = self._current()
        if cur is None:
            messagebox.showinfo("提示", "请先选中要移除的参考盘", parent=self)
            return
        idx = self.current_idx
        self.refs.pop(idx)
        new_idx = min(idx, len(self.refs) - 1)
        self.current_idx = new_idx
        self._refresh_ref_list(select=new_idx if new_idx >= 0 else None)
        self.status_var.set(f"已移除，剩余 {len(self.refs)} 块参考盘")

    def clear_refs(self):
        if self.is_busy:
            return
        if self.refs and not messagebox.askyesno("确认", "清空全部参考盘？", parent=self):
            return
        self.refs = []
        self.current_idx = -1
        self.calibrated_params = None
        self.calib_meta = None
        self._refresh_ref_list()
        self.status_var.set("参考盘已清空")

    def save_n_to_current(self):
        cur = self._current()
        if cur is None:
            messagebox.showwarning("提示", "请先添加并选中参考盘", parent=self)
            return
        try:
            n = int(self.total_n_var.get().strip())
            if n < 1:
                raise ValueError
        except Exception:
            messagebox.showerror("错误", "请输入有效的正整数 N", parent=self)
            return
        cur.total_gt = n
        self._refresh_ref_list(select=self.current_idx)
        self.status_var.set(f"{cur.name} 真值 N = {n}")

    # ── 点选 ──────────────────────────────────────
    def _push_undo(self):
        cur = self._current()
        if not cur:
            return
        cur.undo_stack.append([dict(p) for p in cur.points])
        if len(cur.undo_stack) > 50:
            cur.undo_stack.pop(0)

    def _on_undo(self, event=None):
        if self.is_busy:
            return
        cur = self._current()
        if not cur or not cur.undo_stack:
            return
        cur.points = cur.undo_stack.pop()
        self._update_point_label()
        self._refresh_ref_list(select=self.current_idx)
        self._redraw()

    def clear_points(self):
        if self.is_busy:
            return
        cur = self._current()
        if not cur:
            return
        self._push_undo()
        cur.points = []
        self._update_point_label()
        self._refresh_ref_list(select=self.current_idx)
        self._redraw()

    def _update_point_label(self):
        cur = self._current()
        n = len(cur.points) if cur else 0
        self.point_count_var.set(f"当前盘点选: {n}")

    def _canvas_to_image(self, cx: float, cy: float) -> Optional[Tuple[float, float]]:
        cur = self._current()
        if cur is None:
            return None
        ox, oy = self._offset
        if self._disp_scale <= 0:
            return None
        ix = (cx - ox) / self._disp_scale
        iy = (cy - oy) / self._disp_scale
        h, w = cur.image.shape[:2]
        if ix < 0 or iy < 0 or ix >= w or iy >= h:
            return None
        return ix, iy

    def _on_left_click(self, event):
        if self.is_busy:
            return
        cur = self._current()
        if cur is None:
            self.status_var.set("请先添加参考盘")
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords is None:
            return
        self._push_undo()
        ix, iy = coords
        cur.points.append(make_point(ix, iy, point_id=len(cur.points) + 1))
        cur.points = renumber_points(cur.points)
        self._update_point_label()
        self._refresh_ref_list(select=self.current_idx)
        self._redraw()

    def _on_right_click(self, event):
        if self.is_busy:
            return
        cur = self._current()
        if cur is None or not cur.points:
            return
        coords = self._canvas_to_image(event.x, event.y)
        if coords is None:
            return
        ix, iy = coords
        tol = max(12.0, 18.0 / max(self._disp_scale, 0.01))
        idx = find_nearest_point(cur.points, ix, iy, max_dist=tol)
        if idx is None:
            return
        self._push_undo()
        cur.points.pop(idx)
        cur.points = renumber_points(cur.points)
        self._update_point_label()
        self._refresh_ref_list(select=self.current_idx)
        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        cur = self._current()
        if cur is None:
            return
        img = cur.image
        if cur.points:
            img = draw_points_on_image(img, cur.points, radius=6, with_index=True)

        cw = max(self.canvas.winfo_width(), 10)
        ch = max(self.canvas.winfo_height(), 10)
        h, w = img.shape[:2]
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

        # 叠加 N 文字
        n_txt = f"N={cur.total_gt}" if cur.total_gt is not None else "N=未设置"
        self.canvas.create_text(
            12, 12, anchor=tk.NW, text=f"{cur.name}  {n_txt}",
            fill="#fff", font=("Microsoft YaHei", 11, "bold")
        )

    def export_points(self):
        cur = self._current()
        if not cur or not cur.points:
            messagebox.showinfo("提示", "当前盘没有点", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="导出点集", defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cur.points, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"已导出点集: {path}")

    def save_annotated(self):
        cur = self._current()
        if cur is None:
            return
        img = draw_points_on_image(cur.image, cur.points) if cur.points else cur.image
        path = filedialog.asksaveasfilename(
            title="保存标注图", defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")]
        )
        if path:
            cv2.imwrite(path, img)
            self.status_var.set(f"已保存: {path}")

    # ── 联合标定 ──────────────────────────────────
    def start_calibrate(self):
        if self.is_busy:
            return
        self._try_autosave_n()

        if not self.refs:
            messagebox.showwarning("提示", "请先添加至少 1 块参考盘", parent=self)
            return

        missing = [r.name for r in self.refs if r.total_gt is None and not r.points]
        if missing:
            messagebox.showerror(
                "缺少真值",
                "以下参考盘未设置 N，且无点选：\n" + "\n".join(missing) +
                "\n\n请选中后填写 N 并点「保存 N 到当前盘」。",
                parent=self,
            )
            return

        # 无 N 但有全量点选的盘允许
        for r in self.refs:
            if r.total_gt is None and r.points:
                r.total_gt = len(r.points)

        if any(r.total_gt is None or r.total_gt < 1 for r in self.refs):
            messagebox.showerror("错误", "每块参考盘都需要有效的真值 N", parent=self)
            return

        n_refs = len(self.refs)
        if n_refs == 1:
            if not messagebox.askyesno(
                "仅 1 块参考盘",
                "当前只有 1 块参考盘。\n建议 2～5 块联合标定效果更好。\n是否仍用单盘继续？",
                parent=self,
            ):
                return

        refs_payload = [r.to_ref_dict() for r in self.refs]
        self._set_busy(True, f"联合标定中（{n_refs} 盘）…")
        self._set_info(f"联合标定中，共 {n_refs} 块参考盘…\n")

        def worker():
            try:
                def prog(i, n, nref, avg_fit):
                    self.after(0, lambda: self.status_var.set(
                        f"联合标定 {i}/{n}  盘数={nref}  当前平均误差≈{avg_fit:.1%}"
                    ))

                # 盘数多时放宽时间
                tlim = 35.0 + 20.0 * n_refs
                result = calibrate_multi(
                    references=refs_payload,
                    max_evals=36 if n_refs <= 2 else 28,
                    time_limit_sec=tlim,
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
            "",
            f"评估次数: {result.get('evals')}  耗时: {result.get('elapsed_ms', 0):.0f} ms",
            f"平均误差: {result.get('fit_error', 0):.2%}  最大误差: {result.get('max_fit_error', 0):.2%}",
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
        self.status_var.set("联合标定完成，可进行批量计数或应用到主窗口")
        self.result_summary_var.set(
            f"{result.get('n_refs')} 盘联合 · 平均误差 {result.get('fit_error', 0):.1%}"
        )

    # ── 批量 ──────────────────────────────────────
    def add_batch_images(self):
        paths = filedialog.askopenfilenames(
            title="选择其余平板图片",
            filetypes=[("图片", "*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff"), ("所有", "*.*")]
        )
        if not paths:
            return
        ref_paths = {r.path for r in self.refs}
        for p in paths:
            if p in ref_paths:
                # 允许但提示
                pass
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
            messagebox.showwarning("提示", "请先完成联合标定", parent=self)
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
        meta = self.calib_meta or {}
        plate_summary = []
        for p in meta.get("plate_results") or []:
            plate_summary.append({
                "name": p.get("name"),
                "path": p.get("path"),
                "total_gt": p.get("total_gt"),
                "predicted_count": p.get("predicted_count"),
                "fit_error": p.get("fit_error"),
                "n_points": p.get("n_points"),
                "strategy": p.get("strategy"),
            })
        payload = {
            "batch_name": self.batch_name_var.get(),
            "params": self.calibrated_params,
            "n_refs": meta.get("n_refs"),
            "fit_error": meta.get("fit_error"),
            "max_fit_error": meta.get("max_fit_error"),
            "plate_results": plate_summary,
            "version": meta.get("version", "1.1"),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.status_var.set(f"参数已保存: {path}")

    def apply_to_main(self):
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
    win = BatchWorkbench(master)
    win.transient(master)
    win.focus_set()
    return win
