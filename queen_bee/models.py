"""Pydantic 模型定义"""
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel): message: str
class ChatResponse(BaseModel): reply: str; timestamp: float
class StatusResponse(BaseModel): cpu_percent: float; memory_percent: float; memory_used_mb: float; memory_total_mb: float; agent_ready: bool; model: str; version: str
class SwitchModelRequest(BaseModel): provider: str; name: str
class CreateReportRequest(BaseModel): task_name: str; items: list[str]; version: str = "0.0.0"
class FeedbackRequest(BaseModel): item_index: int; status: str; feedback: str = ""
class SubmitRequest(BaseModel): overall_notes: str = ""
class ModelConfigRequest(BaseModel): provider: str; name: str; api_key: str = ""; base_url: str = ""
class DeleteModelRequest(BaseModel): provider: str; name: str
class SpawnAgentRequest(BaseModel): name: str; role: str = "通用助手"; provider: str = ""; model: str = ""; api_key: str = ""
class DelegateRequest(BaseModel): agent_name: str; task: str
