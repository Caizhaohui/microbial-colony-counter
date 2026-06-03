
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import Optional
import cv2
import numpy as np
import base64
import time
import io
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

# Import core algorithm and schemas
from backend.core.algorithm import process_image
from backend.schemas import CountResponse

# 线程池用于CPU密集型任务，避免阻塞事件循环
_executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(
    title="Microbial Colony Counter API",
    description="Backend API for Colony Counter Mobile App",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

def image_to_base64(image: np.ndarray, quality: int = 55) -> str:
    """Convert OpenCV image to compressed base64 string"""
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode('.jpg', image, encode_params)
    return base64.b64encode(buffer).decode('utf-8')

def make_thumbnail(image: np.ndarray, max_dim: int = 800) -> np.ndarray:
    """生成缩略图用于前端显示，减小传输体积"""
    h, w = image.shape[:2]
    if max(h, w) <= max_dim:
        return image
    ratio = max_dim / max(h, w)
    new_w, new_h = int(w * ratio), int(h * ratio)
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

def decode_image(file_bytes: bytes) -> np.ndarray:
    """Decode image bytes to OpenCV format"""
    nparr = np.frombuffer(file_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image")
    return image

@app.post("/api/v1/count", response_model=CountResponse)
async def count_colonies(
    image: UploadFile = File(...),
    thresh_method: str = Form("adaptive", description="二值化方法: 'manual' 或 'adaptive'"),
    thresh_val: int = Form(100, description="手动阈值 (0-255)"),
    adaptive_block_size: int = Form(11, description="自适应阈值块大小 (奇数)"),
    adaptive_c: int = Form(2, description="自适应阈值常数C"),
    blur_ksize: int = Form(7, description="高斯模糊核大小 (奇数)"),
    min_area: int = Form(50, description="最小菌落面积"),
    max_area: int = Form(5000, description="最大菌落面积"),
    min_distance_from_edge: int = Form(20, description="最小边缘距离"),
    detect_petri_dish: bool = Form(False, description="是否自动检测培养皿"),
    use_watershed: bool = Form(False, description="是否使用分水岭算法分离粘连菌落"),
    min_circularity: float = Form(0.0, description="最小圆度 (0-1, 0=不过滤)"),
    roi_type: Optional[str] = Form(None, description="ROI类型: 'circle' 或 'rectangle'"),
    roi_data: Optional[str] = Form(None, description="ROI数据 (逗号分隔): x,y,w,h 或 cx,cy,r")
):
    start_time = time.time()
    
    # 1. Read and decode image
    try:
        contents = await image.read()
        cv_image = decode_image(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {str(e)}")

    # 2. Parse ROI
    manual_roi = None
    if roi_type and roi_data and roi_type != "none":
        try:
            parts = [int(float(x.strip())) for x in roi_data.split(',')]
            if roi_type == "circle" and len(parts) == 3:
                manual_roi = tuple(parts)
            elif roi_type == "rectangle" and len(parts) == 4:
                manual_roi = tuple(parts)
        except Exception as e:
            print(f"ROI parsing error: {e}")
            pass

    # 3. 在线程池中执行CPU密集型算法，避免阻塞事件循环
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor,
        lambda: process_image(
            image=cv_image,
            blur_ksize=blur_ksize,
            thresh_method=thresh_method,
            thresh_val=thresh_val,
            adaptive_block_size=adaptive_block_size,
            adaptive_c=adaptive_c,
            min_area=min_area,
            max_area=max_area,
            min_distance_from_edge=min_distance_from_edge,
            detect_petri_dish=detect_petri_dish,
            manual_roi=manual_roi,
            use_watershed=use_watershed,
            min_circularity=min_circularity
        )
    )

    if result["error"]:
        raise HTTPException(status_code=500, detail=f"Algorithm error: {result['error']}")

    # 4. Prepare response
    end_time = time.time()
    processing_ms = (end_time - start_time) * 1000

    response = CountResponse(
        count=result["count"],
        quality_score=None,
        warnings=[],
        petri_circle=result.get("petri_circle"),
        processing_ms=processing_ms,
        colony_details=result.get("colony_details", [])
    )

    # 5. 生成缩略图 + 压缩JPEG，大幅减小响应体积
    if result["binary_image"] is not None:
        thumb = make_thumbnail(result["binary_image"], max_dim=800)
        response.binary_image_base64 = image_to_base64(thumb, quality=50)
    
    if result["processed_image"] is not None:
        thumb = make_thumbnail(result["processed_image"], max_dim=800)
        response.processed_image_base64 = image_to_base64(thumb, quality=55)

    return response

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("backend/static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(
            content=f.read(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Microbial Colony Counter API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
