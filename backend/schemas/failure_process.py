# ============================================================
# Failure Process Schema — 失败记录标注的请求/响应数据模型
# ============================================================

from typing import List, Optional  # List 列表类型，Optional 可选类型

from pydantic import BaseModel, field_validator, model_validator  # 字段校验器、模型校验器


class CaseFailedTypeItem(BaseModel):
    """失败类型选项项，来自 case_failed_type 表"""

    id: int  # 主键
    failed_reason_type: str  # 失败原因分类，如 bug、环境问题
    owner: Optional[str] = None  # 该类型的默认跟踪人工号，可为空


class OwnerItem(BaseModel):
    """跟踪人选项项，来自 ums_email 表"""

    employee_id: str  # 工号，提交时用此值
    name: str  # 姓名，下拉展示用


class ModuleItem(BaseModel):
    """模块选项项，来自 ums_module_owner 表"""

    module: str  # 模块名
    owner: str  # 负责人工号，选 bug 时用于默认跟踪人


class FailureProcessOptions(BaseModel):
    """标注弹窗选项响应模型，GET /failure-process-options 返回"""

    case_failed_types: List[CaseFailedTypeItem] = []  # 失败类型下拉选项
    owners: List[OwnerItem] = []  # 跟踪人下拉选项
    modules: List[ModuleItem] = []  # 模块下拉选项（仅 bug 时显示）


class FailureProcessRequest(BaseModel):
    """失败标注提交请求模型，POST /failure-process 请求体"""

    history_ids: List[int]  # 选中的 pipeline_history.id 列表
    failed_type: str  # 失败类型，来自 case_failed_type.failed_reason_type
    owner: str  # 跟踪人工号，对应 ums_email.employee_id
    reason: str  # 详细失败原因
    module: Optional[str] = None  # 模块，仅 failed_type=bug 时必填

    @field_validator("history_ids")
    @classmethod
    def history_ids_not_empty(cls, v: List[int]) -> List[int]:
        """校验 history_ids 非空"""
        if not v:
            raise ValueError("history_ids 不能为空")
        return v

    @field_validator("failed_type", "owner", "reason")
    @classmethod
    def not_empty_string(cls, v: str) -> str:
        """校验字符串非空且去除首尾空格"""
        if not v or not str(v).strip():
            raise ValueError("字段不能为空")
        return str(v).strip()

    @model_validator(mode="after")
    def module_required_when_bug(self) -> "FailureProcessRequest":
        """当 failed_type 为 bug 时，module 必填（忽略首尾空格、大小写）"""
        if self.failed_type and str(self.failed_type).strip().lower() == "bug":
            if not self.module or not str(self.module).strip():
                raise ValueError("失败类型为 bug 时，模块为必填项")
        return self
