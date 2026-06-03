
from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Any, Dict

class ColonyDetail(BaseModel):
    id: int = Field(..., description="菌落编号")
    x: int = Field(..., description="中心X坐标")
    y: int = Field(..., description="中心Y坐标")
    area: int = Field(..., description="面积(像素)")
    circularity: Optional[float] = Field(None, description="圆度(0-1)")

class CountResponse(BaseModel):
    count: int = Field(..., description="检测到的菌落总数")
    quality_score: Optional[float] = Field(None, description="图像质量评分 (0-100)")
    warnings: List[str] = Field(default=[], description="处理过程中的警告信息")
    binary_image_base64: Optional[str] = Field(None, description="二值化图像的Base64编码")
    processed_image_base64: Optional[str] = Field(None, description="处理后（带标注）图像的Base64编码")
    petri_circle: Optional[Tuple[int, int, int]] = Field(None, description="检测到的培养皿圆形 (x, y, r)")
    processing_ms: Optional[float] = Field(None, description="处理耗时(ms)")
    colony_details: List[ColonyDetail] = Field(default=[], description="各菌落详情列表")
