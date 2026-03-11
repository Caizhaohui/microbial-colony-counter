
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, Any, List

def detect_petri_dish_circle(image: np.ndarray) -> Optional[Tuple[int, int, int]]:
    """
    检测培养皿的圆形区域
    :param image: 输入图像 (BGR)
    :return: (x, y, r) 或 None
    """
    try:
        # 转换为灰度
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 高斯模糊减少噪声
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        # Hough圆检测
        # 参数根据原 main.py 调整
        min_dim = min(image.shape[:2])
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=100,
            param1=50,
            param2=30,
            minRadius=int(min_dim * 0.2),
            maxRadius=int(min_dim * 0.45)
        )

        if circles is not None:
            # 取第一个检测到的圆（通常是最大的）
            circles = np.uint16(np.around(circles))
            x, y, r = circles[0][0]
            return (int(x), int(y), int(r))
        else:
            return None

    except Exception as e:
        print(f"培养皿检测失败: {e}")
        return None

def process_image(
    image: np.ndarray,
    blur_ksize: int = 7,
    thresh_method: str = "adaptive", # "manual" or "adaptive"
    thresh_val: int = 100,
    adaptive_block_size: int = 11,
    adaptive_c: int = 2,
    min_area: int = 50,
    max_area: int = 5000,
    min_distance_from_edge: int = 20,
    detect_petri_dish: bool = False,
    manual_roi: Optional[Tuple] = None # (x, y, w, h) for rect or (cx, cy, r) for circle
) -> Dict[str, Any]:
    """
    核心图像处理函数
    """
    try:
        # 大图自动缩放优化
        original_height, original_width = image.shape[:2]
        scale_ratio = 1.0
        max_dimension = 2000 # 限制最大边长

        if max(original_height, original_width) > max_dimension:
            scale_ratio = max_dimension / max(original_height, original_width)
            new_width = int(original_width * scale_ratio)
            new_height = int(original_height * scale_ratio)
            image = cv2.resize(image, (new_width, new_height))
        
        height, width = image.shape[:2]
        output_image = image.copy()
        
        # 结果字典
        result = {
            "count": 0,
            "binary_image": None,
            "processed_image": None,
            "petri_circle": None,
            "error": None
        }

        # 调整参数以适应缩放
        # 注意：这里我们主要调整面积参数，其他参数如 blur_ksize, block_size 相对不敏感或难以线性调整
        if scale_ratio != 1.0:
            min_area = int(min_area * (scale_ratio * scale_ratio))
            max_area = int(max_area * (scale_ratio * scale_ratio))
            min_distance_from_edge = int(min_distance_from_edge * scale_ratio)
            if manual_roi is not None:
                # 检查 manual_roi 长度，以防万一
                if len(manual_roi) >= 3:
                    manual_roi = tuple(int(v * scale_ratio) for v in manual_roi)

        # 如果启用培养皿检测，先检测圆形区域
        petri_mask = None
        if detect_petri_dish:
            petri_mask = detect_petri_dish_circle(image)
            if petri_mask is not None:
                result["petri_circle"] = petri_mask
                # 在输出图像上绘制检测到的培养皿圆形
                cv2.circle(output_image, (int(petri_mask[0]), int(petri_mask[1])),
                         int(petri_mask[2]), (255, 0, 0), 3)  # 蓝色圆圈标记培养皿

        # 1. 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 如果有手动选择的ROI，创建一个掩码
        roi_mask = None
        if manual_roi is not None:
            if len(manual_roi) == 3:  # 圆形ROI (center_x, center_y, radius)
                center_x, center_y, radius = manual_roi
                roi_mask = np.zeros_like(gray)
                cv2.circle(roi_mask, (int(center_x), int(center_y)), int(radius), 255, -1)
                # 在输出图像上绘制选择的ROI圆形
                cv2.circle(output_image, (int(center_x), int(center_y)), int(radius), (0, 255, 255), 3)  # 黄色圆圈
            elif len(manual_roi) == 4:  # 矩形ROI (x, y, w, h)
                x, y, w, h = manual_roi
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
        # 确保ksize是奇数
        if blur_ksize % 2 == 0:
            blur_ksize += 1
        blurred = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)

        # 3. 二值化
        if thresh_method == "manual":
            _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
        else:  # adaptive
            # 确保block_size是奇数
            if adaptive_block_size % 2 == 0:
                adaptive_block_size += 1
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY_INV, adaptive_block_size, adaptive_c)

        # 应用掩码到二值化结果
        if petri_mask is not None:
            center_x, center_y, radius = petri_mask
            mask = np.zeros_like(thresh)
            cv2.circle(mask, (int(center_x), int(center_y)), int(radius), 255, -1)
            thresh = cv2.bitwise_and(thresh, mask)
        elif roi_mask is not None:
            # 如果有手动ROI，应用矩形掩码
            thresh = cv2.bitwise_and(thresh, roi_mask)

        result["binary_image"] = thresh.copy()

        # 4. 轮廓检测 (只检测最外层的轮廓，适合分离的菌落)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 5. 过滤和计数
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
                    dx = float(cX - center_x)
                    dy = float(cY - center_y)
                    distance_from_center = np.sqrt(dx*dx + dy*dy)
                    in_petri = distance_from_center <= radius * 0.9  # 稍微缩小一点，避免边缘
                else:
                    in_petri = False
            else:
                # 传统边缘距离检查
                distance_from_edge = min(x, y, width - (x + w), height - (y + h))
                in_petri = distance_from_edge >= min_distance_from_edge

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

        result["processed_image"] = output_image
        result["count"] = colony_count
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        result["error"] = str(e)
        return result
