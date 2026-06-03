import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import sys
import threading
import datetime

# 添加项目根目录到路径，以导入 backend 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.core.algorithm import process_image as algo_process_image, detect_petri_dish_circle


class ColonyCounter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微生物菌落计数器")
        self.root.geometry("1280x800")

        # 变量
        self.image_path = None
        self.original_image = None
        self.processed_image = None
        self.binary_image = None
        self.colony_count = 0

        # 参数变量
        self.blur_ksize = tk.IntVar(value=7)
        self.thresh_method = tk.StringVar(value="自适应阈值")
        self.thresh_val = tk.IntVar(value=100)
        self.adaptive_block_size = tk.IntVar(value=11)
        self.adaptive_c = tk.IntVar(value=2)
        self.min_area = tk.IntVar(value=50)
        self.max_area = tk.IntVar(value=5000)
        self.min_distance_from_edge = tk.IntVar(value=20)
        self.detect_petri_dish = tk.BooleanVar(value=False)
        self.use_watershed = tk.BooleanVar(value=False)
        self.min_circularity = tk.IntVar(value=0)  # 0-90, 对应 0.0-0.9

        # 处理结果详情
        self.colony_details = []
        self.is_processing = False

        # 手动选择区域变量
        self.manual_roi = None
        self.roi_shape = "rectangle"
        self.selecting_roi = False
        self.dragging_roi = False
        self.roi_start = None
        self.roi_end = None
        self.drag_start = None

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 主框架 - 垂直布局：顶部工具栏 -> 图片区域 -> 底部结果栏
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ============================================
        # 顶部工具栏
        # ============================================
        toolbar = tk.Frame(main_frame, bg='#f5f5f5', relief=tk.RAISED, borderwidth=1)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        # 工具栏内部布局
        toolbar_inner = tk.Frame(toolbar, bg='#f5f5f5')
        toolbar_inner.pack(fill=tk.X, padx=10, pady=8)

        # 左侧：操作按钮
        btn_frame = tk.Frame(toolbar_inner, bg='#f5f5f5')
        btn_frame.pack(side=tk.LEFT)

        self.select_button = tk.Button(
            btn_frame, text="📂 打开图片", command=self.select_image,
            font=("Microsoft YaHei", 10), bg='#4CAF50', fg='white',
            relief=tk.FLAT, cursor='hand2', padx=12, pady=4
        )
        self.select_button.pack(side=tk.LEFT, padx=(0, 5))

        self.roi_button = tk.Button(
            btn_frame, text="✂️ 选择区域", command=self.start_roi_selection,
            state=tk.DISABLED, font=("Microsoft YaHei", 10),
            relief=tk.FLAT, padx=12, pady=4
        )
        self.roi_button.pack(side=tk.LEFT, padx=5)

        self.process_button = tk.Button(
            btn_frame, text="▶️ 处理", command=self.process_image,
            state=tk.DISABLED, font=("Microsoft YaHei", 10, "bold"),
            bg='#2196F3', fg='white', relief=tk.FLAT, padx=15, pady=4
        )
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(
            btn_frame, text="💾 保存", command=self.save_results,
            state=tk.DISABLED, font=("Microsoft YaHei", 10),
            relief=tk.FLAT, padx=12, pady=4
        )
        self.save_button.pack(side=tk.LEFT, padx=5)

        # 分隔线
        ttk.Separator(toolbar_inner, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=15, pady=2)

        # 中间：常用参数（紧凑布局）
        param_frame = tk.Frame(toolbar_inner, bg='#f5f5f5')
        param_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 模糊
        tk.Label(param_frame, text="模糊:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        blur_spin = tk.Spinbox(
            param_frame, from_=3, to=15, increment=2,
            textvariable=self.blur_ksize, width=3, font=("Microsoft YaHei", 9)
        )
        blur_spin.pack(side=tk.LEFT, padx=(2, 10))

        # 阈值方法
        tk.Label(param_frame, text="阈值:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        thresh_combo = ttk.Combobox(
            param_frame, textvariable=self.thresh_method,
            values=["自适应阈值", "手动阈值"], state="readonly", width=10
        )
        thresh_combo.pack(side=tk.LEFT, padx=(2, 10))
        thresh_combo.bind("<<ComboboxSelected>>", self.on_thresh_method_change)

        # 阈值参数（根据方法动态显示）
        self.thresh_param_frame = tk.Frame(param_frame, bg='#f5f5f5')
        self.thresh_param_frame.pack(side=tk.LEFT)

        # 自适应阈值参数
        self.adaptive_param_frame = tk.Frame(self.thresh_param_frame, bg='#f5f5f5')
        tk.Label(self.adaptive_param_frame, text="块:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            self.adaptive_param_frame, from_=3, to=31, increment=2,
            textvariable=self.adaptive_block_size, width=3, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(self.adaptive_param_frame, text="C:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            self.adaptive_param_frame, from_=-5, to=5,
            textvariable=self.adaptive_c, width=3, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)

        # 手动阈值参数
        self.manual_param_frame = tk.Frame(self.thresh_param_frame, bg='#f5f5f5')
        tk.Label(self.manual_param_frame, text="值:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            self.manual_param_frame, from_=0, to=255,
            textvariable=self.thresh_val, width=4, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)

        # 面积范围
        ttk.Separator(param_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=2)
        tk.Label(param_frame, text="面积:", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            param_frame, from_=10, to=10000, increment=50,
            textvariable=self.min_area, width=5, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)
        tk.Label(param_frame, text="~", bg='#f5f5f5', font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        tk.Spinbox(
            param_frame, from_=1000, to=100000, increment=500,
            textvariable=self.max_area, width=6, font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=2)

        # 右侧：高级选项按钮 + 培养皿检测
        right_frame = tk.Frame(toolbar_inner, bg='#f5f5f5')
        right_frame.pack(side=tk.RIGHT)

        tk.Checkbutton(
            right_frame, text="培养皿检测", variable=self.detect_petri_dish,
            bg='#f5f5f5', font=("Microsoft YaHei", 9)
        ).pack(side=tk.LEFT, padx=5)

        self.advanced_btn = tk.Button(
            right_frame, text="⚙️ 高级选项", command=self.show_advanced_dialog,
            font=("Microsoft YaHei", 9), relief=tk.FLAT, padx=10, pady=4
        )
        self.advanced_btn.pack(side=tk.LEFT, padx=5)

        # 初始化阈值方法显示
        self.on_thresh_method_change()

        # ============================================
        # 中间图片显示区域（最大化，固定布局）
        # ============================================
        image_container = tk.Frame(main_frame, bg='white')
        image_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 防止容器根据子控件调整大小
        image_container.grid_propagate(False)

        # 图片区域使用网格布局，三张图等宽
        image_container.grid_columnconfigure(0, weight=1, uniform='img_col')
        image_container.grid_columnconfigure(1, weight=1, uniform='img_col')
        image_container.grid_columnconfigure(2, weight=1, uniform='img_col')
        image_container.grid_rowconfigure(0, weight=0)  # 标题行
        image_container.grid_rowconfigure(1, weight=1)  # 图片行

        # 原始图片
        tk.Label(image_container, text="📷 原始图片", font=("Microsoft YaHei", 10, "bold"),
                 bg='white').grid(row=0, column=0, pady=(5, 2))
        orig_frame = tk.Frame(image_container, bg='#e0e0e0')
        orig_frame.grid(row=1, column=0, sticky='nsew', padx=(0, 3), pady=(0, 5))
        orig_frame.grid_propagate(False)
        self.original_canvas = tk.Canvas(orig_frame, bg='#e0e0e0', highlightthickness=0)
        self.original_canvas.pack(fill=tk.BOTH, expand=True)

        # 二值化图像
        tk.Label(image_container, text="🔲 二值化", font=("Microsoft YaHei", 10, "bold"),
                 bg='white').grid(row=0, column=1, pady=(5, 2))
        bin_frame = tk.Frame(image_container, bg='#e0e0e0')
        bin_frame.grid(row=1, column=1, sticky='nsew', padx=3, pady=(0, 5))
        bin_frame.grid_propagate(False)
        self.binary_canvas = tk.Canvas(bin_frame, bg='#e0e0e0', highlightthickness=0)
        self.binary_canvas.pack(fill=tk.BOTH, expand=True)

        # 计数结果
        tk.Label(image_container, text="✅ 计数结果", font=("Microsoft YaHei", 10, "bold"),
                 bg='white').grid(row=0, column=2, pady=(5, 2))
        proc_frame = tk.Frame(image_container, bg='#e0e0e0')
        proc_frame.grid(row=1, column=2, sticky='nsew', padx=(3, 0), pady=(0, 5))
        proc_frame.grid_propagate(False)
        self.processed_canvas = tk.Canvas(proc_frame, bg='#e0e0e0', highlightthickness=0)
        self.processed_canvas.pack(fill=tk.BOTH, expand=True)

        # ============================================
        # 底部结果栏
        # ============================================
        bottom_bar = tk.Frame(main_frame, bg='#f8f8f8', relief=tk.RAISED, borderwidth=1, height=50)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)

        bottom_inner = tk.Frame(bottom_bar, bg='#f8f8f8')
        bottom_inner.pack(fill=tk.X, padx=15, pady=8)

        # 左侧：计数结果（醒目显示）
        self.count_label = tk.Label(
            bottom_inner, text="菌落总数: 0 个",
            font=("Microsoft YaHei", 14, "bold"), bg='#f8f8f8', fg='#1976D2'
        )
        self.count_label.pack(side=tk.LEFT)

        # 中间：参数摘要
        self.param_summary = tk.Label(
            bottom_inner, text="", font=("Microsoft YaHei", 9),
            bg='#f8f8f8', fg='#666666'
        )
        self.param_summary.pack(side=tk.LEFT, padx=30)

        # 右侧：状态信息
        self.status_label = tk.Label(
            bottom_inner, text="就绪", font=("Microsoft YaHei", 9),
            bg='#f8f8f8', fg='#999999'
        )
        self.status_label.pack(side=tk.RIGHT)

        # 绑定窗口大小改变事件
        self.root.bind('<Configure>', self.on_window_resize)

    def on_thresh_method_change(self, event=None):
        """阈值方法改变时更新显示"""
        # 隐藏所有阈值参数
        self.adaptive_param_frame.pack_forget()
        self.manual_param_frame.pack_forget()

        # 根据选择显示对应参数
        if self.thresh_method.get() == "自适应阈值":
            self.adaptive_param_frame.pack(side=tk.LEFT)
        else:
            self.manual_param_frame.pack(side=tk.LEFT)

    def show_advanced_dialog(self):
        """显示高级选项对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("高级选项")
        dialog.geometry("450x480")
        dialog.resizable(True, True)  # 允许调整大小
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 450) // 2
        y = (dialog.winfo_screenheight() - 480) // 2
        dialog.geometry(f"+{x}+{y}")

        # 使用 Canvas + Scrollbar 支持滚动
        canvas = tk.Canvas(dialog, highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, padx=20, pady=15)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        main_frame = scrollable_frame

        # 分水岭算法
        tk.Label(main_frame, text="菌落分离", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W, pady=(0, 10))

        tk.Checkbutton(
            main_frame, text="启用分水岭算法分离粘连菌落",
            variable=self.use_watershed, font=("Microsoft YaHei", 10)
        ).pack(anchor=tk.W, pady=(0, 5))

        tk.Label(
            main_frame, text="⚠️ 分水岭可能导致过分割，使计数偏低",
            font=("Microsoft YaHei", 9), fg='#888888'
        ).pack(anchor=tk.W, pady=(0, 15))

        # 圆度过滤
        tk.Label(main_frame, text="形状过滤", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W, pady=(10, 10))

        circ_frame = tk.Frame(main_frame)
        circ_frame.pack(fill=tk.X)

        tk.Label(circ_frame, text="最小圆度 (0=不过滤, 90=只保留圆形):",
                 font=("Microsoft YaHei", 10)).pack(anchor=tk.W)

        circ_scale = tk.Scale(
            circ_frame, from_=0, to=90, orient=tk.HORIZONTAL,
            variable=self.min_circularity, resolution=5, length=300
        )
        circ_scale.pack(fill=tk.X, pady=5)

        self.circ_value_label = tk.Label(
            circ_frame, text=f"当前: {self.min_circularity.get() / 100:.2f}",
            font=("Microsoft YaHei", 9), fg='#666666'
        )
        self.circ_value_label.pack(anchor=tk.W)

        def update_circ_label(event=None):
            self.circ_value_label.config(text=f"当前: {self.min_circularity.get() / 100:.2f}")

        circ_scale.bind("<B1-Motion>", update_circ_label)

        # 边缘距离
        tk.Label(main_frame, text="边缘过滤", font=("Microsoft YaHei", 11, "bold")).pack(anchor=tk.W, pady=(15, 10))

        edge_frame = tk.Frame(main_frame)
        edge_frame.pack(fill=tk.X)

        tk.Label(edge_frame, text="最小边缘距离 (像素):", font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        tk.Spinbox(
            edge_frame, from_=0, to=200,
            textvariable=self.min_distance_from_edge, width=6, font=("Microsoft YaHei", 10)
        ).pack(anchor=tk.W, pady=5)

        # 关闭按钮
        tk.Button(
            main_frame, text="确定", command=dialog.destroy,
            font=("Microsoft YaHei", 10), bg='#2196F3', fg='white',
            relief=tk.FLAT, padx=20, pady=5
        ).pack(pady=(20, 0))

    def select_image(self):
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if file_path:
            self.image_path = file_path
            self.load_image()
            self.process_button.config(state=tk.NORMAL)
            self.status_label.config(text=f"已加载: {os.path.basename(file_path)}")

    def load_image(self):
        try:
            self.original_image = cv2.imread(self.image_path)
            if self.original_image is None:
                raise ValueError("无法读取图片")

            # 重置ROI
            self.manual_roi = None
            self.roi_button.config(state=tk.NORMAL)

            # 显示原图
            self.display_image_on_canvas_widget(self.original_image, self.original_canvas)

            # 清除之前的结果
            self.binary_canvas.delete("all")
            self.processed_canvas.delete("all")
            self.count_label.config(text="菌落总数: 0 个")

        except Exception as e:
            messagebox.showerror("错误", f"加载图片失败: {str(e)}")

    def start_roi_selection(self):
        """开始手动选择区域"""
        if self.original_image is None:
            return

        self.roi_window = tk.Toplevel(self.root)
        self.roi_window.title("选择统计区域")
        self.roi_window.geometry("800x600")

        shape_frame = tk.Frame(self.roi_window)
        shape_frame.pack(fill=tk.X, pady=5)

        tk.Label(shape_frame, text="选择形状:").pack(side=tk.LEFT, padx=10)
        self.shape_var = tk.StringVar(value="circle")
        tk.Radiobutton(shape_frame, text="圆形", variable=self.shape_var,
                      value="circle", command=self.on_shape_change).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(shape_frame, text="矩形", variable=self.shape_var,
                      value="rectangle", command=self.on_shape_change).pack(side=tk.LEFT, padx=5)

        self.roi_canvas = tk.Canvas(self.roi_window, bg='gray')
        self.roi_canvas.pack(fill=tk.BOTH, expand=True)

        self.display_image_on_canvas(self.original_image, self.roi_canvas)

        self.roi_canvas.bind("<ButtonPress-1>", self.on_roi_mouse_down)
        self.roi_canvas.bind("<B1-Motion>", self.on_roi_mouse_drag)
        self.roi_canvas.bind("<ButtonRelease-1>", self.on_roi_mouse_up)

        button_frame = tk.Frame(self.roi_window)
        button_frame.pack(fill=tk.X, pady=10)

        tk.Button(button_frame, text="确认选择", command=self.confirm_roi).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="取消", command=self.cancel_roi).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="清除选择", command=self.clear_roi).pack(side=tk.LEFT, padx=10)

        self.roi_status_label = tk.Label(button_frame, text="请拖拽鼠标选择矩形区域")
        self.roi_status_label.pack(side=tk.RIGHT, padx=10)

        self.on_shape_change()

    def on_shape_change(self):
        self.roi_shape = self.shape_var.get()
        if self.roi_shape == "rectangle":
            self.roi_status_label.config(text="请拖拽鼠标选择矩形区域")
        else:
            self.roi_status_label.config(text="请拖拽鼠标选择圆形区域")

    def display_image_on_canvas(self, cv_image, canvas):
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        canvas_width = 780
        canvas_height = 500
        pil_image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)

        self.canvas_photo = ImageTk.PhotoImage(pil_image)
        canvas.create_image(canvas_width//2, canvas_height//2, image=self.canvas_photo, anchor=tk.CENTER)

        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.image_width, self.image_height = pil_image.size

    def on_roi_mouse_down(self, event):
        if self.roi_start and self.roi_end:
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end
            margin = 10
            if self.roi_shape == "rectangle":
                if (min(x1, x2) - margin <= event.x <= max(x1, x2) + margin and
                    min(y1, y2) - margin <= event.y <= max(y1, y2) + margin):
                    self.dragging_roi = True
                    self.drag_start = (event.x, event.y)
                    return
            else:
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius = min(abs(x2 - x1), abs(y2 - y1)) // 2
                if (abs(event.x - center_x) <= radius + margin and
                    abs(event.y - center_y) <= radius + margin):
                    self.dragging_roi = True
                    self.drag_start = (event.x, event.y)
                    return

        self.selecting_roi = True
        self.dragging_roi = False
        self.roi_start = (event.x, event.y)
        self.roi_end = (event.x, event.y)
        self.drag_start = None
        self.roi_canvas.delete("roi_shape")

    def on_roi_mouse_drag(self, event):
        if self.dragging_roi and self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end
            self.roi_start = (x1 + dx, y1 + dy)
            self.roi_end = (x2 + dx, y2 + dy)
            self.drag_start = (event.x, event.y)
            self.draw_roi_shape()
        elif self.selecting_roi:
            self.roi_end = (event.x, event.y)
            self.draw_roi_shape()

    def on_roi_mouse_up(self, event):
        if self.selecting_roi:
            self.roi_end = (event.x, event.y)
            self.selecting_roi = False
            self.draw_roi_shape()

    def draw_roi_shape(self):
        if self.roi_start and self.roi_end:
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end
            self.roi_canvas.delete("roi_shape")

            if self.roi_shape == "rectangle":
                self.roi_canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=2, tags="roi_shape")
            else:
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius = min(abs(x2 - x1), abs(y2 - y1)) // 2
                self.roi_canvas.create_oval(
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius,
                    outline='red', width=2, tags="roi_shape"
                )

    def confirm_roi(self):
        if self.roi_start and self.roi_end:
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end

            offset_x = (self.canvas_width - self.image_width) // 2
            offset_y = (self.canvas_height - self.image_height) // 2

            img_x1 = max(0, (x1 - offset_x) * self.original_image.shape[1] // self.image_width)
            img_y1 = max(0, (y1 - offset_y) * self.original_image.shape[0] // self.image_height)
            img_x2 = min(self.original_image.shape[1], (x2 - offset_x) * self.original_image.shape[1] // self.image_width)
            img_y2 = min(self.original_image.shape[0], (y2 - offset_y) * self.original_image.shape[0] // self.image_height)

            if img_x1 > img_x2:
                img_x1, img_x2 = img_x2, img_x1
            if img_y1 > img_y2:
                img_y1, img_y2 = img_y2, img_y1

            if self.roi_shape == "rectangle":
                self.manual_roi = (img_x1, img_y1, img_x2 - img_x1, img_y2 - img_y1)
                messagebox.showinfo("成功", f"已选择矩形区域")
            else:
                center_x = (img_x1 + img_x2) // 2
                center_y = (img_y1 + img_y2) // 2
                radius = min(img_x2 - img_x1, img_y2 - img_y1) // 2
                self.manual_roi = (center_x, center_y, radius)
                messagebox.showinfo("成功", f"已选择圆形区域")

            self.roi_window.destroy()

    def cancel_roi(self):
        self.manual_roi = None
        self.roi_window.destroy()

    def clear_roi(self):
        self.roi_start = None
        self.roi_end = None
        self.roi_canvas.delete("roi_shape")
        if self.roi_shape == "rectangle":
            self.roi_status_label.config(text="请拖拽鼠标选择矩形区域")
        else:
            self.roi_status_label.config(text="请拖拽鼠标选择圆形区域")

    def process_image(self):
        if self.original_image is None or self.is_processing:
            return

        self.is_processing = True
        self.process_button.config(state=tk.DISABLED, text="处理中...")
        self.status_label.config(text="正在处理...")
        self.root.config(cursor="wait")
        threading.Thread(target=self._process_image_thread, daemon=True).start()

    def _process_image_thread(self):
        try:
            thresh_method_map = {"手动阈值": "manual", "自适应阈值": "adaptive"}
            thresh_method = thresh_method_map.get(self.thresh_method.get(), "adaptive")

            result = algo_process_image(
                image=self.original_image,
                blur_ksize=self.blur_ksize.get(),
                thresh_method=thresh_method,
                thresh_val=self.thresh_val.get(),
                adaptive_block_size=self.adaptive_block_size.get(),
                adaptive_c=self.adaptive_c.get(),
                min_area=self.min_area.get(),
                max_area=self.max_area.get(),
                min_distance_from_edge=self.min_distance_from_edge.get(),
                detect_petri_dish=self.detect_petri_dish.get(),
                manual_roi=self.manual_roi,
                use_watershed=self.use_watershed.get(),
                min_circularity=self.min_circularity.get() / 100.0
            )

            if result["error"]:
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理图片失败: {result['error']}"))
                return

            self.binary_image = result["binary_image"]
            self.processed_image = result["processed_image"]
            self.colony_count = result["count"]
            self.colony_details = result.get("colony_details", [])

            self.root.after(0, self._update_process_result)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("错误", f"处理图片失败: {str(e)}"))
        finally:
            self.is_processing = False
            self.root.after(0, self._reset_process_button)

    def _update_process_result(self):
        if self.binary_image is not None:
            self.display_image_on_canvas_widget(self.binary_image, self.binary_canvas)

        if self.processed_image is not None:
            self.display_image_on_canvas_widget(self.processed_image, self.processed_canvas)

        self.count_label.config(text=f"菌落总数: {self.colony_count} 个")

        # 更新参数摘要
        summary = f"blur={self.blur_ksize.get()}, area=[{self.min_area.get()},{self.max_area.get()}]"
        if self.use_watershed.get():
            summary += ", 分水岭"
        if self.min_circularity.get() > 0:
            summary += f", 圆度≥{self.min_circularity.get()/100:.1f}"
        self.param_summary.config(text=summary)

        self.save_button.config(state=tk.NORMAL)
        self.status_label.config(text="处理完成")

    def _reset_process_button(self):
        self.process_button.config(state=tk.NORMAL, text="▶️ 处理")
        self.root.config(cursor="")

    def display_image_on_canvas_widget(self, cv_image, canvas):
        """在 Canvas 控件上显示 OpenCV 图像（固定布局，不调整窗口）"""
        try:
            # 获取 Canvas 当前尺寸
            canvas.update_idletasks()
            canvas_width = canvas.winfo_width()
            canvas_height = canvas.winfo_height()

            # 如果尺寸为 0，使用默认值
            if canvas_width <= 1:
                canvas_width = 400
            if canvas_height <= 1:
                canvas_height = 300

            # 转换为 RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_image)

            # 缩放图像以适应 Canvas（保持宽高比）
            pil_image.thumbnail((canvas_width - 10, canvas_height - 10), Image.Resampling.LANCZOS)

            # 转换为 PhotoImage
            photo = ImageTk.PhotoImage(pil_image)

            # 清除旧图像并显示新图像
            canvas.delete("all")
            canvas.create_image(canvas_width // 2, canvas_height // 2, image=photo, anchor=tk.CENTER)

            # 保持引用防止被垃圾回收
            canvas.image = photo
        except Exception as e:
            print(f"显示图像失败: {e}")

    def save_results(self):
        if self.original_image is None or self.processed_image is None or self.binary_image is None:
            messagebox.showerror("错误", "没有可保存的处理结果")
            return

        try:
            height, width = self.original_image.shape[:2]

            info_bar_height = 80
            canvas_width = width * 2
            canvas_height = height * 2 + 100 + info_bar_height

            result_image = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255

            target_width = width
            target_height = height

            original_resized = cv2.resize(self.original_image, (target_width, target_height))
            binary_3ch = cv2.cvtColor(self.binary_image, cv2.COLOR_GRAY2BGR)
            binary_resized = cv2.resize(binary_3ch, (target_width, target_height))
            processed_resized = cv2.resize(self.processed_image, (canvas_width, target_height))

            result_image[50:50+target_height, 0:target_width] = original_resized
            result_image[50:50+target_height, target_width:canvas_width] = binary_resized
            result_image[50+target_height:50+target_height*2, 0:canvas_width] = processed_resized

            font = cv2.FONT_HERSHEY_SIMPLEX
            title = "微生物菌落计数结果"
            text_size = cv2.getTextSize(title, font, 1.5, 2)[0]
            text_x = (canvas_width - text_size[0]) // 2
            cv2.putText(result_image, title, (text_x, 30), font, 1.5, (0, 0, 0), 2)

            cv2.putText(result_image, "原始图片", (10, 45), font, 0.8, (0, 0, 0), 2)
            cv2.putText(result_image, "二值化图像", (target_width + 10, 45), font, 0.8, (0, 0, 0), 2)
            cv2.putText(result_image, "计数结果", (10, 45 + target_height), font, 0.8, (0, 0, 0), 2)

            info_y = 50 + target_height * 2 + 15
            count_text = f"菌落总数: {self.colony_count} 个"
            cv2.putText(result_image, count_text, (20, info_y), font, 0.9, (0, 0, 255), 2)

            thresh_name = self.thresh_method.get()
            param_text = f"Parameters: blur={self.blur_ksize.get()}, thresh={thresh_name}, area=[{self.min_area.get()},{self.max_area.get()}]"
            if self.use_watershed.get():
                param_text += ", watershed=ON"
            if self.min_circularity.get() > 0:
                param_text += f", circularity>={self.min_circularity.get() / 100.0:.2f}"
            cv2.putText(result_image, param_text, (20, info_y + 30), font, 0.55, (100, 100, 100), 1)

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(result_image, timestamp, (canvas_width - 350, info_y + 30), font, 0.55, (100, 100, 100), 1)

            file_path = filedialog.asksaveasfilename(
                title="保存统计结果",
                defaultextension=".png",
                filetypes=[("PNG文件", "*.png"), ("JPEG文件", "*.jpg"), ("BMP文件", "*.bmp")]
            )

            if file_path:
                cv2.imwrite(file_path, result_image)
                messagebox.showinfo("成功", f"统计结果已保存到: {file_path}")

        except Exception as e:
            messagebox.showerror("错误", f"保存结果失败: {str(e)}")

    def on_window_resize(self, event=None):
        """窗口大小改变时重新绘制图片"""
        if hasattr(self, 'original_image') and self.original_image is not None:
            try:
                self.display_image_on_canvas_widget(self.original_image, self.original_canvas)
                if hasattr(self, 'binary_image') and self.binary_image is not None:
                    self.display_image_on_canvas_widget(self.binary_image, self.binary_canvas)
                if hasattr(self, 'processed_image') and self.processed_image is not None:
                    self.display_image_on_canvas_widget(self.processed_image, self.processed_canvas)
            except:
                pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ColonyCounter()
    app.run()
