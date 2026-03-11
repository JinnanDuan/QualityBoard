from typing import List, Optional

from pydantic import BaseModel


class LatestBatchItem(BaseModel):
    """最新批次聚合数据"""

    batch: str
    total_case_num: int
    passed_num: int
    failed_num: int
    pass_rate: float
    batch_start: Optional[str] = None
    batch_end: Optional[str] = None
    result: str

    model_config = {"from_attributes": True}


class BatchTrendItem(BaseModel):
    """趋势数据单条"""

    batch: str
    total_case_num: int
    passed_num: int
    failed_num: int
    pass_rate: float
    batch_start: Optional[str] = None

    model_config = {"from_attributes": True}


class BatchTrendResponse(BaseModel):
    """批次趋势接口响应"""

    items: List[BatchTrendItem]
