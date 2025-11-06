import cv2
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os

class ColonyCounter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微生物菌落计数器")
        self.root.geometry("1400x900")

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

        # 手动选择区域变量
        self.manual_roi = None  # 矩形: (x, y, w, h), 圆形: (center_x, center_y, radius)
        self.roi_shape = "rectangle"  # "rectangle" 或 "circle"
        self.selecting_roi = False
        self.dragging_roi = False
        self.roi_start = None
        self.roi_end = None
        self.drag_start = None

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        # 创建主框架
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 配置主框架的网格布局
        main_frame.grid_columnconfigure(0, weight=2)  # 左侧面板：40%
        main_frame.grid_columnconfigure(1, weight=3)  # 右侧内容区域：60%
        main_frame.grid_rowconfigure(0, weight=7)     # 参数调整区域：70%
        main_frame.grid_rowconfigure(1, weight=3)     # 统计结果区域：30%

        # 参数调整区域 - 占左侧面板的70%高度
        sidebar = tk.Frame(main_frame, bg='#f0f0f0')
        sidebar.grid(row=0, column=0, sticky='nsew', padx=5, pady=(5,2))

        # 参数标题
        tk.Label(sidebar, text="⚙️ 参数调整", font=("Arial", 12, "bold"), bg='#f0f0f0').pack(pady=10)

        # 1. 图像预处理参数
        preprocess_frame = tk.LabelFrame(sidebar, text="1. 图像预处理", padx=10, pady=5)
        preprocess_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(preprocess_frame, text="高斯模糊核大小 (奇数):").pack(anchor=tk.W)
        blur_scale = tk.Scale(preprocess_frame, from_=3, to=15, orient=tk.HORIZONTAL,
                             variable=self.blur_ksize, resolution=2)
        blur_scale.pack(fill=tk.X)

        tk.Label(preprocess_frame, text="二值化方法:").pack(anchor=tk.W, pady=(10,0))
        thresh_methods = ["手动阈值", "自适应阈值"]
        thresh_combo = ttk.Combobox(preprocess_frame, textvariable=self.thresh_method,
                                   values=thresh_methods, state="readonly")
        thresh_combo.pack(fill=tk.X, pady=(0,5))
        thresh_combo.bind("<<ComboboxSelected>>", self.on_thresh_method_change)

        # 手动阈值控件
        self.manual_thresh_frame = tk.Frame(preprocess_frame)
        tk.Label(self.manual_thresh_frame, text="手动阈值:").pack(anchor=tk.W)
        manual_scale = tk.Scale(self.manual_thresh_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                               variable=self.thresh_val)
        manual_scale.pack(fill=tk.X)

        # 自适应阈值控件
        self.adaptive_thresh_frame = tk.Frame(preprocess_frame)
        tk.Label(self.adaptive_thresh_frame, text="自适应阈值块大小 (奇数):").pack(anchor=tk.W)
        adaptive_block_scale = tk.Scale(self.adaptive_thresh_frame, from_=3, to=31, orient=tk.HORIZONTAL,
                                       variable=self.adaptive_block_size, resolution=2)
        adaptive_block_scale.pack(fill=tk.X)

        tk.Label(self.adaptive_thresh_frame, text="自适应阈值常数C:").pack(anchor=tk.W)
        adaptive_c_scale = tk.Scale(self.adaptive_thresh_frame, from_=-5, to=5, orient=tk.HORIZONTAL,
                                   variable=self.adaptive_c)
        adaptive_c_scale.pack(fill=tk.X)

        # 2. 培养皿检测
        petri_frame = tk.LabelFrame(sidebar, text="2. 培养皿检测", padx=10, pady=5)
        petri_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Checkbutton(petri_frame, text="自动检测培养皿圆形区域",
                      variable=self.detect_petri_dish).pack(anchor=tk.W)

        # 3. 菌落过滤参数
        filter_frame = tk.LabelFrame(sidebar, text="3. 菌落过滤", padx=10, pady=5)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(filter_frame, text="菌落最小面积 (像素):").pack(anchor=tk.W)
        min_area_scale = tk.Scale(filter_frame, from_=10, to=1000, orient=tk.HORIZONTAL,
                                 variable=self.min_area)
        min_area_scale.pack(fill=tk.X)

        tk.Label(filter_frame, text="菌落最大面积 (像素):").pack(anchor=tk.W)
        max_area_scale = tk.Scale(filter_frame, from_=1000, to=50000, orient=tk.HORIZONTAL,
                                 variable=self.max_area)
        max_area_scale.pack(fill=tk.X)

        tk.Label(filter_frame, text="最小边缘距离 (像素):").pack(anchor=tk.W)
        edge_distance_scale = tk.Scale(filter_frame, from_=0, to=200, orient=tk.HORIZONTAL,
                                      variable=self.min_distance_from_edge)
        edge_distance_scale.pack(fill=tk.X)

        # 统计结果区域 - 占GUI的15%高度，15%宽度
        stats_frame = tk.Frame(main_frame, bg='white', relief=tk.RIDGE, borderwidth=2)
        stats_frame.grid(row=1, column=0, sticky='nw', padx=5, pady=(2,5))
        stats_frame.config(width=200, height=100)  # 固定尺寸
        stats_frame.pack_propagate(False)

        tk.Label(stats_frame, text="📊 统计结果", font=("Arial", 12, "bold"), bg='white').pack(pady=(5,2))
        self.count_label = tk.Label(stats_frame, text="检测到的菌落总数: 0 个",
                                  font=("Arial", 12), fg='black', bg='white')
        self.count_label.pack(pady=(0,5))

        # 主内容区域 - 占右侧60%宽度，跨越两行
        content_frame = tk.Frame(main_frame)
        content_frame.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=5, pady=5)

        # 配置内容区域的内部布局
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=0)  # 按钮区域
        content_frame.grid_rowconfigure(1, weight=1)  # 图片区域

        # 顶部按钮
        button_frame = tk.Frame(content_frame)
        button_frame.grid(row=0, column=0, pady=10)

        self.select_button = tk.Button(button_frame, text="选择图片", command=self.select_image,
                                     font=("Arial", 10, "bold"))
        self.select_button.pack(side=tk.LEFT, padx=5)

        self.roi_button = tk.Button(button_frame, text="选择区域", command=self.start_roi_selection,
                                  state=tk.DISABLED, font=("Arial", 10, "bold"))
        self.roi_button.pack(side=tk.LEFT, padx=5)

        self.process_button = tk.Button(button_frame, text="处理图片", command=self.process_image,
                                      state=tk.DISABLED, font=("Arial", 10, "bold"))
        self.process_button.pack(side=tk.LEFT, padx=5)

        self.save_button = tk.Button(button_frame, text="保存结果", command=self.save_results,
                                   state=tk.DISABLED, font=("Arial", 10, "bold"))
        self.save_button.pack(side=tk.LEFT, padx=5)

        # 图片显示区域 - 三张图片并排，大小一致
        image_frame = tk.Frame(content_frame)
        image_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)

        # 原始图片
        original_frame = tk.Frame(image_frame)
        original_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0,5))

        tk.Label(original_frame, text="原始图片", font=("Arial", 10, "bold")).pack(pady=(0,5))
        self.original_label = tk.Label(original_frame, bg='gray')
        self.original_label.pack(expand=True, fill=tk.BOTH)

        # 二值化图片
        binary_frame = tk.Frame(image_frame)
        binary_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)

        tk.Label(binary_frame, text="二值化图像", font=("Arial", 10, "bold")).pack(pady=(0,5))
        self.binary_label = tk.Label(binary_frame, bg='gray')
        self.binary_label.pack(expand=True, fill=tk.BOTH)

        # 计数结果图片
        processed_frame = tk.Frame(image_frame)
        processed_frame.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(5,0))

        tk.Label(processed_frame, text="计数结果", font=("Arial", 10, "bold")).pack(pady=(0,5))
        self.processed_label = tk.Label(processed_frame, bg='gray')
        self.processed_label.pack(expand=True, fill=tk.BOTH)

        # 初始化阈值方法显示
        self.on_thresh_method_change()

        # 绑定窗口大小改变事件
        self.root.bind('<Configure>', self.on_window_resize)

    def on_thresh_method_change(self, event=None):
        # 隐藏所有阈值控件
        self.manual_thresh_frame.pack_forget()
        self.adaptive_thresh_frame.pack_forget()

        # 根据选择的阈值方法显示相应控件
        method = self.thresh_method.get()
        if method == "手动阈值":
            self.manual_thresh_frame.pack(fill=tk.X, pady=(5,0))
        elif method == "自适应阈值":
            self.adaptive_thresh_frame.pack(fill=tk.X, pady=(5,0))

    def select_image(self):
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if file_path:
            self.image_path = file_path
            self.load_image()
            self.process_button.config(state=tk.NORMAL)

    def load_image(self):
        try:
            self.original_image = cv2.imread(self.image_path)
            if self.original_image is None:
                raise ValueError("无法读取图片")

            # 重置ROI
            self.manual_roi = None
            self.roi_button.config(state=tk.NORMAL)

            # 显示原图
            self.display_image(self.original_image, self.original_label)

        except Exception as e:
            messagebox.showerror("错误", f"加载图片失败: {str(e)}")

    def start_roi_selection(self):
        """开始手动选择区域"""
        if self.original_image is None:
            return

        # 创建一个新的窗口用于选择区域
        self.roi_window = tk.Toplevel(self.root)
        self.roi_window.title("选择统计区域")
        self.roi_window.geometry("800x600")

        # 形状选择
        shape_frame = tk.Frame(self.roi_window)
        shape_frame.pack(fill=tk.X, pady=5)

        tk.Label(shape_frame, text="选择形状:").pack(side=tk.LEFT, padx=10)
        self.shape_var = tk.StringVar(value="circle")
        tk.Radiobutton(shape_frame, text="圆形", variable=self.shape_var,
                      value="circle", command=self.on_shape_change).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(shape_frame, text="矩形", variable=self.shape_var,
                      value="rectangle", command=self.on_shape_change).pack(side=tk.LEFT, padx=5)

        # 创建画布
        self.roi_canvas = tk.Canvas(self.roi_window, bg='gray')
        self.roi_canvas.pack(fill=tk.BOTH, expand=True)

        # 显示图片
        self.display_image_on_canvas(self.original_image, self.roi_canvas)

        # 绑定鼠标事件
        self.roi_canvas.bind("<ButtonPress-1>", self.on_roi_mouse_down)
        self.roi_canvas.bind("<B1-Motion>", self.on_roi_mouse_drag)
        self.roi_canvas.bind("<ButtonRelease-1>", self.on_roi_mouse_up)

        # 按钮
        button_frame = tk.Frame(self.roi_window)
        button_frame.pack(fill=tk.X, pady=10)

        tk.Button(button_frame, text="确认选择", command=self.confirm_roi).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="取消", command=self.cancel_roi).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="清除选择", command=self.clear_roi).pack(side=tk.LEFT, padx=10)

        # 状态标签
        self.roi_status_label = tk.Label(button_frame, text="请拖拽鼠标选择矩形区域")
        self.roi_status_label.pack(side=tk.RIGHT, padx=10)

        # 初始化形状
        self.on_shape_change()

    def on_shape_change(self):
        """形状改变时的处理"""
        self.roi_shape = self.shape_var.get()
        if self.roi_shape == "rectangle":
            self.roi_status_label.config(text="请拖拽鼠标选择矩形区域")
        else:  # circle
            self.roi_status_label.config(text="请拖拽鼠标选择圆形区域")

    def display_image_on_canvas(self, cv_image, canvas):
        """在画布上显示图像"""
        # 转换为RGB
        rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

        # 转换为PIL Image
        pil_image = Image.fromarray(rgb_image)

        # 调整大小适应画布
        canvas_width = 780
        canvas_height = 500
        pil_image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)

        # 转换为PhotoImage
        self.canvas_photo = ImageTk.PhotoImage(pil_image)

        # 在画布中心显示
        canvas.create_image(canvas_width//2, canvas_height//2, image=self.canvas_photo, anchor=tk.CENTER)

        # 保存画布尺寸用于坐标转换
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.image_width, self.image_height = pil_image.size

    def on_roi_mouse_down(self, event):
        """鼠标按下事件"""
        # 检查是否点击在已有的选择框内（用于拖拽）
        if self.roi_start and self.roi_end:
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end

            # 扩大点击区域以便更容易拖拽
            margin = 10
            if self.roi_shape == "rectangle":
                if (min(x1, x2) - margin <= event.x <= max(x1, x2) + margin and
                    min(y1, y2) - margin <= event.y <= max(y1, y2) + margin):
                    self.dragging_roi = True
                    self.drag_start = (event.x, event.y)
                    return
            else:  # circle
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius = min(abs(x2 - x1), abs(y2 - y1)) // 2
                # 检查是否在圆形区域内（包括边界）
                if (abs(event.x - center_x) <= radius + margin and
                    abs(event.y - center_y) <= radius + margin):
                    self.dragging_roi = True
                    self.drag_start = (event.x, event.y)
                    return

        # 开始新的选择
        self.selecting_roi = True
        self.dragging_roi = False
        self.roi_start = (event.x, event.y)
        self.roi_end = (event.x, event.y)
        self.drag_start = None

        # 清除之前的图形
        self.roi_canvas.delete("roi_shape")

    def on_roi_mouse_drag(self, event):
        """鼠标拖拽事件"""
        if self.dragging_roi and self.drag_start:
            # 计算移动距离
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]

            # 更新选择框位置
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end

            self.roi_start = (x1 + dx, y1 + dy)
            self.roi_end = (x2 + dx, y2 + dy)
            self.drag_start = (event.x, event.y)

            self.draw_roi_rectangle()
        elif self.selecting_roi:
            self.roi_end = (event.x, event.y)
            self.draw_roi_rectangle()

    def on_roi_mouse_up(self, event):
        """鼠标释放事件"""
        if self.selecting_roi:
            self.roi_end = (event.x, event.y)
            self.selecting_roi = False
            self.draw_roi_rectangle()

    def draw_roi_rectangle(self):
        """绘制选择区域（矩形或圆形）"""
        if self.roi_start and self.roi_end:
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end

            # 清除之前的图形
            self.roi_canvas.delete("roi_shape")

            if self.roi_shape == "rectangle":
                # 绘制矩形
                self.roi_canvas.create_rectangle(x1, y1, x2, y2, outline='red', width=2, tags="roi_shape")
            else:  # circle
                # 计算圆心和半径
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                radius = min(abs(x2 - x1), abs(y2 - y1)) // 2

                # 绘制圆形
                x0 = center_x - radius
                y0 = center_y - radius
                x1_circle = center_x + radius
                y1_circle = center_y + radius
                self.roi_canvas.create_oval(x0, y0, x1_circle, y1_circle, outline='red', width=2, tags="roi_shape")

    def confirm_roi(self):
        """确认选择的区域"""
        if self.roi_start and self.roi_end:
            # 转换画布坐标到图像坐标
            x1, y1 = self.roi_start
            x2, y2 = self.roi_end

            # 计算图像在画布上的偏移
            offset_x = (self.canvas_width - self.image_width) // 2
            offset_y = (self.canvas_height - self.image_height) // 2

            # 转换到图像坐标
            img_x1 = max(0, (x1 - offset_x) * self.original_image.shape[1] // self.image_width)
            img_y1 = max(0, (y1 - offset_y) * self.original_image.shape[0] // self.image_height)
            img_x2 = min(self.original_image.shape[1], (x2 - offset_x) * self.original_image.shape[1] // self.image_width)
            img_y2 = min(self.original_image.shape[0], (y2 - offset_y) * self.original_image.shape[0] // self.image_height)

            # 确保x1 < x2, y1 < y2
            if img_x1 > img_x2:
                img_x1, img_x2 = img_x2, img_x1
            if img_y1 > img_y2:
                img_y1, img_y2 = img_y2, img_y1

            if self.roi_shape == "rectangle":
                # 保存矩形ROI
                self.manual_roi = (img_x1, img_y1, img_x2 - img_x1, img_y2 - img_y1)
                messagebox.showinfo("成功", f"已选择矩形区域: x={img_x1}, y={img_y1}, 宽={img_x2 - img_x1}, 高={img_y2 - img_y1}")
            else:  # circle
                # 计算圆心和半径
                center_x = (img_x1 + img_x2) // 2
                center_y = (img_y1 + img_y2) // 2
                radius = min(img_x2 - img_x1, img_y2 - img_y1) // 2

                # 保存圆形ROI
                self.manual_roi = (center_x, center_y, radius)
                messagebox.showinfo("成功", f"已选择圆形区域: 圆心=({center_x}, {center_y}), 半径={radius}")

            # 关闭窗口
            self.roi_window.destroy()

    def cancel_roi(self):
        """取消选择"""
        self.manual_roi = None
        self.roi_window.destroy()

    def clear_roi(self):
        """清除选择"""
        self.roi_start = None
        self.roi_end = None
        self.roi_canvas.delete("roi_shape")
        if self.roi_shape == "rectangle":
            self.roi_status_label.config(text="请拖拽鼠标选择矩形区域")
        else:
            self.roi_status_label.config(text="请拖拽鼠标选择圆形区域")

    def process_image(self):
        if self.original_image is None:
            return

        try:
            height, width = self.original_image.shape[:2]
            output_image = self.original_image.copy()

            # 如果启用培养皿检测，先检测圆形区域
            petri_mask = None
            if self.detect_petri_dish.get():
                petri_mask = self.detect_petri_dish_circle()
                if petri_mask is not None:
                    # 在输出图像上绘制检测到的培养皿圆形
                    cv2.circle(output_image, (int(petri_mask[0]), int(petri_mask[1])),
                             int(petri_mask[2]), (255, 0, 0), 3)  # 蓝色圆圈标记培养皿

            # 1. 转换为灰度图
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)

            # 如果有手动选择的ROI，创建一个掩码
            roi_mask = None
            if self.manual_roi is not None:
                if len(self.manual_roi) == 3:  # 圆形ROI (center_x, center_y, radius)
                    center_x, center_y, radius = self.manual_roi
                    roi_mask = np.zeros_like(gray)
                    cv2.circle(roi_mask, (int(center_x), int(center_y)), int(radius), 255, -1)
                    # 在输出图像上绘制选择的ROI圆形
                    cv2.circle(output_image, (int(center_x), int(center_y)), int(radius), (0, 255, 255), 3)  # 黄色圆圈
                else:  # 矩形ROI (x, y, w, h)
                    x, y, w, h = self.manual_roi
                    roi_mask = np.zeros_like(gray)
                    cv2.rectangle(roi_mask, (x, y), (x + w, y + h), 255, -1)
                    # 在输出图像上绘制选择的ROI矩形
                    cv2.rectangle(output_image, (x, y), (x + w, y + h), (0, 255, 255), 3)  # 黄色矩形

            # 如果有培养皿掩码，只处理圆形区域内的图像
            if petri_mask is not None:
                center_x, center_y, radius = petri_mask
                # 创建圆形掩码
                mask = np.zeros_like(gray)
                cv2.circle(mask, (int(center_x), int(center_y)), int(radius), 255, -1)
                gray = cv2.bitwise_and(gray, gray, mask=mask)
            elif roi_mask is not None:
                # 如果有手动ROI，使用矩形掩码
                gray = cv2.bitwise_and(gray, roi_mask)

            # 2. 高斯模糊去噪
            ksize = self.blur_ksize.get()
            blurred = cv2.GaussianBlur(gray, (ksize, ksize), 0)

            # 3. 二值化
            thresh_method = self.thresh_method.get()
            if thresh_method == "手动阈值":
                thresh_val = self.thresh_val.get()
                _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
            else:  # 自适应阈值
                block_size = self.adaptive_block_size.get()
                c = self.adaptive_c.get()
                thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                             cv2.THRESH_BINARY_INV, block_size, c)

            # 应用掩码到二值化结果
            if petri_mask is not None:
                center_x, center_y, radius = petri_mask
                mask = np.zeros_like(thresh)
                cv2.circle(mask, (int(center_x), int(center_y)), int(radius), 255, -1)
                thresh = cv2.bitwise_and(thresh, mask)
            elif roi_mask is not None:
                # 如果有手动ROI，应用矩形掩码
                thresh = cv2.bitwise_and(thresh, roi_mask)

            # 保存二值化图像用于显示
            self.binary_image = thresh.copy()

            # 显示二值化图像
            self.display_image(self.binary_image, self.binary_label)

            # 4. 轮廓检测 (只检测最外层的轮廓，适合分离的菌落)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 5. 过滤和计数
            min_area = self.min_area.get()
            max_area = self.max_area.get()
            min_edge_distance = self.min_distance_from_edge.get()
            colony_count = 0

            for cnt in contours:
                area = cv2.contourArea(cnt)

                # 获取轮廓的边界框
                x, y, w, h = cv2.boundingRect(cnt)

                # 检查是否距离边缘足够远
                if petri_mask is not None:
                    # 如果有培养皿掩码，检查是否在圆形区域内
                    center_x, center_y, radius = petri_mask
                    # 计算轮廓中心点
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        # 检查是否在圆内
                        cX_int = int(cX)
                        cY_int = int(cY)
                        center_x_int = int(center_x)
                        center_y_int = int(center_y)
                        dx = float(cX_int - center_x_int)
                        dy = float(cY_int - center_y_int)
                        distance_from_center = np.sqrt(dx*dx + dy*dy)
                        in_petri = distance_from_center <= radius * 0.9  # 稍微缩小一点，避免边缘
                    else:
                        in_petri = False
                else:
                    # 传统边缘距离检查
                    distance_from_edge = min(x, y, width - (x + w), height - (y + h))
                    in_petri = distance_from_edge >= min_edge_distance

                # 根据面积和位置过滤
                if min_area < area < max_area and in_petri:
                    colony_count += 1

                    # 在 output_image 上绘制轮廓 (绿色轮廓)
                    cv2.drawContours(output_image, [cnt], -1, (0, 255, 0), 2)

                    # (可选) 绘制中心点和编号
                    M = cv2.moments(cnt)
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        cv2.putText(output_image, str(colony_count), (cX - 10, cY + 5),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)  # 红色编号

            self.processed_image = output_image
            self.colony_count = colony_count

            # 显示计数结果
            self.display_image(self.processed_image, self.processed_label)

            # 更新计数显示
            self.count_label.config(text=f"检测到的菌落总数: {self.colony_count} 个")

            # 启用保存按钮
            self.save_button.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("错误", f"处理图片失败: {str(e)}")

    def detect_petri_dish_circle(self):
        """检测培养皿的圆形区域"""
        try:
            # 转换为灰度
            gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)

            # 高斯模糊减少噪声
            blurred = cv2.GaussianBlur(gray, (9, 9), 2)

            # Hough圆检测
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=100,
                param1=50,
                param2=30,
                minRadius=int(min(self.original_image.shape[:2]) * 0.2),
                maxRadius=int(min(self.original_image.shape[:2]) * 0.45)
            )

            if circles is not None:
                # 取第一个检测到的圆（通常是最大的）
                circles = np.uint16(np.around(circles))
                x, y, r = circles[0][0]
                return (x, y, r)
            else:
                # 如果没有检测到圆，返回None
                return None

        except Exception as e:
            print(f"培养皿检测失败: {e}")
            return None

    def display_image(self, cv_image, label, fixed_size=True):
        """显示OpenCV图像到Tkinter标签"""
        try:
            # 使用固定尺寸显示所有图片，确保大小统一
            if fixed_size:
                # 固定尺寸：400x300 (4:3比例)
                target_width = 400
                target_height = 300
            else:
                # 获取标签的实际尺寸（自适应模式）
                label.update_idletasks()  # 确保布局已更新
                target_width = label.winfo_width()
                target_height = label.winfo_height()

                # 如果尺寸无效，使用默认值
                if target_width <= 1:
                    target_width = 400
                if target_height <= 1:
                    target_height = 300

            # 转换为RGB
            rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)

            # 转换为PIL Image
            pil_image = Image.fromarray(rgb_image)

            # 调整大小，保持宽高比
            pil_image.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

            # 转换为PhotoImage
            photo = ImageTk.PhotoImage(pil_image)

            # 显示
            label.config(image=photo)
            label.image = photo  # 保持引用
        except Exception as e:
            print(f"显示图像失败: {e}")

    def save_results(self):
        """保存统计结果，将三张图片合并成一张"""
        if self.original_image is None or self.processed_image is None or self.binary_image is None:
            messagebox.showerror("错误", "没有可保存的处理结果")
            return

        try:
            # 获取图片尺寸
            height, width = self.original_image.shape[:2]

            # 创建一个大的画布来容纳三张图片
            # 布局：上方两张图片（原图和二值化），下方计数结果
            canvas_width = width * 2
            canvas_height = height * 2 + 100  # 多出100像素用于标题

            # 创建白色背景的画布
            result_image = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255

            # 调整图片大小以适应布局
            target_width = width
            target_height = height

            # 调整原图大小
            original_resized = cv2.resize(self.original_image, (target_width, target_height))
            # 调整二值化图片大小（转换为3通道以便显示）
            binary_3ch = cv2.cvtColor(self.binary_image, cv2.COLOR_GRAY2BGR)
            binary_resized = cv2.resize(binary_3ch, (target_width, target_height))
            # 调整计数结果图片大小
            processed_resized = cv2.resize(self.processed_image, (canvas_width, target_height))

            # 放置图片
            # 左上：原图
            result_image[50:50+target_height, 0:target_width] = original_resized
            # 右上：二值化
            result_image[50:50+target_height, target_width:canvas_width] = binary_resized
            # 下方：计数结果
            result_image[50+target_height:50+target_height*2, 0:canvas_width] = processed_resized

            # 添加标题和信息
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 1.5
            font_thickness = 2
            color = (0, 0, 0)  # 黑色

            # 主标题
            title = "微生物菌落计数结果"
            text_size = cv2.getTextSize(title, font, font_scale, font_thickness)[0]
            text_x = (canvas_width - text_size[0]) // 2
            cv2.putText(result_image, title, (text_x, 30), font, font_scale, color, font_thickness)

            # 菌落数量信息
            count_text = f"检测到的菌落总数: {self.colony_count} 个"
            count_size = cv2.getTextSize(count_text, font, 1.0, 2)[0]
            count_x = (canvas_width - count_size[0]) // 2
            cv2.putText(result_image, count_text, (count_x, canvas_height - 20), font, 1.0, (0, 0, 255), 2)

            # 添加图片标签
            label_font_scale = 0.8
            label_thickness = 2

            # 原图标签
            cv2.putText(result_image, "原始图片", (10, 45), font, label_font_scale, color, label_thickness)
            # 二值化标签
            cv2.putText(result_image, "二值化图像", (target_width + 10, 45), font, label_font_scale, color, label_thickness)
            # 计数结果标签
            cv2.putText(result_image, "计数结果", (10, 45 + target_height), font, label_font_scale, color, label_thickness)

            # 保存文件对话框
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
        """窗口大小改变时重新调整图片显示"""
        # 只在有图片时才重新显示，避免不必要的操作
        if hasattr(self, 'original_image') and self.original_image is not None:
            try:
                # 重新显示所有图片
                self.display_image(self.original_image, self.original_label)
                if hasattr(self, 'binary_image') and self.binary_image is not None:
                    self.display_image(self.binary_image, self.binary_label)
                if hasattr(self, 'processed_image') and self.processed_image is not None:
                    self.display_image(self.processed_image, self.processed_label)
            except:
                pass  # 忽略重新显示过程中的错误

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ColonyCounter()
    app.run()
