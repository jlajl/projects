"""宠物医院 MCP Server

把 pethospital REST 服务包装成 11 个 MCP tool，供 AI agent 调用。
通过环境变量 PET_HOSPITAL_URL 指定 REST 地址（默认 http://127.0.0.1:8080）。

运行：python mcp/server.py  （stdio transport，需先启动 pethospital REST 服务）
"""
from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from client import PetHospitalClient, PetHospitalError

BASE_URL = os.environ.get("PET_HOSPITAL_URL", "http://127.0.0.1:8080").rstrip("/")
client = PetHospitalClient(BASE_URL)

mcp = FastMCP("宠物医院")


# ---------------------------------------------------------------------------
# 系统 / 统计
# ---------------------------------------------------------------------------


@mcp.tool()
def get_stats(top: int = 5) -> Any:
    """获取医院经营统计：档案数、病历数、收费笔数、总收入、客单价、
    按种类/状态/医生分布、医生收入排行、消费前 N 的宠物。
    REST: GET /api/v1/stats?top=
    """
    return client.stats(top=top)


# ---------------------------------------------------------------------------
# 宠物档案 CRUD
# ---------------------------------------------------------------------------


@mcp.tool()
def list_pets(
    q: str = "",
    name: str = "",
    ownerName: str = "",
    ownerPhone: str = "",
    species: str = "",
    doctor: str = "",
    disease: str = "",
    status: str = "",
    min: float | None = None,
    max: float | None = None,
    sortBy: str = "",
    order: str = "asc",
    page: int = 1,
    pageSize: int = 20,
) -> Any:
    """查询宠物档案列表，支持多维度过滤+排序+分页。
    species 取值：犬/猫/兔/鸟/仓鼠/爬宠/其他；
    status 取值：待就诊/就诊中/住院中/已康复/慢性病随访；
    sortBy 取值：id/name/ownerName/species/doctor/disease/status/totalCost/visitCount/createdAt/updatedAt；
    order 取值：asc/desc。返回 {items,total,page,pageSize,totalPages,totalCost}。
    REST: GET /api/v1/pets
    """
    params: dict[str, Any] = {
        "q": q, "name": name, "ownerName": ownerName, "ownerPhone": ownerPhone,
        "species": species, "doctor": doctor, "disease": disease, "status": status,
        "sortBy": sortBy, "order": order, "page": page, "pageSize": pageSize,
    }
    if min is not None:
        params["min"] = min
    if max is not None:
        params["max"] = max
    return client.list_pets(**params)


@mcp.tool()
def get_pet(id: str) -> Any:
    """按档案 ID 查询单个宠物的完整信息（含历史病历与消费明细）。
    id 格式：PET-000001。REST: GET /api/v1/pets/{id}
    """
    return client.get_pet(id)


@mcp.tool()
def create_pet(
    name: str,
    species: str,
    ownerName: str,
    ownerPhone: str,
    doctor: str,
    disease: str = "",
    breed: str = "",
    gender: str = "",
    ageMonths: int = 0,
    color: str = "",
    chipNo: str = "",
    ownerAddr: str = "",
    status: str = "",
    allergy: str = "",
    note: str = "",
) -> Any:
    """新增宠物档案，id 自动生成（PET-000001 递增）。
    必填：name, ownerName, ownerPhone(7-15位数字), doctor, disease；
    species 必须是 犬/猫/兔/鸟/仓鼠/爬宠/其他 之一（空则默认"其他"）；
    status 空则默认"待就诊"。REST: POST /api/v1/pets
    """
    pet: dict[str, Any] = {
        "name": name, "species": species, "ownerName": ownerName,
        "ownerPhone": ownerPhone, "doctor": doctor, "disease": disease,
        "breed": breed, "gender": gender, "ageMonths": ageMonths,
        "color": color, "chipNo": chipNo, "ownerAddr": ownerAddr,
        "status": status, "allergy": allergy, "note": note,
    }
    # 去掉空字符串字段，避免覆盖服务端默认值
    return client.create_pet({k: v for k, v in pet.items() if v not in ("", 0) or k in ("ageMonths",)})


@mcp.tool()
def update_pet(id: str, fields: dict[str, Any]) -> Any:
    """局部更新宠物档案（PATCH 语义，只改传入字段）。
    fields 为字段名到值的 dict，如 {"status":"住院中","doctor":"王医生"}；
    不要传 totalCost/visitCount（只读，由服务端汇总）。REST: PATCH /api/v1/pets/{id}
    """
    return client.update_pet(id, fields)


@mcp.tool()
def delete_pet(id: str) -> Any:
    """删除宠物档案（含其病历与消费明细）。
    REST: DELETE /api/v1/pets/{id}
    """
    return client.delete_pet(id)


@mcp.tool()
def search_pets(q: str) -> Any:
    """全文检索宠物：按空白分词 AND 命中，覆盖主档字段+病历全文+收费项目。
    如 search_pets("肠胃炎 李医生")。返回 Result{items,total,page,pageSize,totalPages,totalCost}。
    REST: GET /api/v1/pets/search?q=
    """
    return client.search_pets(q)


# ---------------------------------------------------------------------------
# 病历 / 收费
# ---------------------------------------------------------------------------


@mcp.tool()
def add_medical_record(
    id: str,
    doctor: str,
    diagnosis: str,
    symptoms: str = "",
    treatment: str = "",
    prescription: list[str] | None = None,
    weightKg: float = 0,
    temperature: float = 0,
    charge: float = 0,
    followUp: str = "",
) -> Any:
    """为宠物追加一条历史病历，同时可带本次费用 charge。
    必填：doctor, diagnosis；charge 不可为负。返回更新后的宠物。
    REST: POST /api/v1/pets/{id}/records
    """
    record: dict[str, Any] = {
        "doctor": doctor, "diagnosis": diagnosis, "symptoms": symptoms,
        "treatment": treatment, "charge": charge, "followUp": followUp,
    }
    if prescription:
        record["prescription"] = prescription
    if weightKg:
        record["weightKg"] = weightKg
    if temperature:
        record["temperature"] = temperature
    return client.add_medical_record(id, record)


@mcp.tool()
def add_charge(
    id: str,
    item: str,
    category: str,
    amount: float,
    doctor: str = "",
    date: str = "",
) -> Any:
    """为宠物追加一笔收费明细，amount 自动累计到宠物总花费。
    必填：item, amount(不可为负)；category 取值：检查/药品/手术/住院/疫苗/护理/其他。
    date 空则用当天，格式 YYYY-MM-DD。REST: POST /api/v1/pets/{id}/charges
    """
    charge: dict[str, Any] = {"item": item, "category": category, "amount": amount}
    if doctor:
        charge["doctor"] = doctor
    if date:
        charge["date"] = date
    return client.add_charge(id, charge)


@mcp.tool()
def get_pet_summary(id: str) -> Any:
    """查询单只宠物的费用与就诊汇总（总花费、就诊次数、病历/收费明细）。
    REST: GET /api/v1/pets/{id}/summary
    """
    return client.get_summary(id)


# ---------------------------------------------------------------------------
# 管理
# ---------------------------------------------------------------------------


@mcp.tool()
def seed_data(count: int = 1000, force: bool = False) -> Any:
    """写入模拟数据用于演示/测试。count 为本次追加条数，force=true 时强制追加
    （即使库非空）。遵循真实兽医规律：疾病与物种匹配、医生按专长分配、
    费用分层、重症患者有多次随访。REST: POST /api/v1/admin/seed?force=&count=
    """
    return client.seed_data(count=count, force=force)


if __name__ == "__main__":
    mcp.run()
