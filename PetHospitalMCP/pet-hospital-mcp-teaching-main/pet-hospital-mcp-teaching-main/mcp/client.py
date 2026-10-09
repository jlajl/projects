"""宠物医院 REST 客户端：用标准库 urllib 封装，零额外依赖。

把 11 个业务操作映射到 pethospital REST 服务的 HTTP 调用。
所有方法在 REST 非 200 或网络异常时抛 PetHospitalError，
由上层 MCP server 原样回传给 LLM，LLM 可据此重试或改参数。
"""
from __future__ import annotations

import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class PetHospitalError(RuntimeError):
    """REST 调用失败的统一异常，message 会回传给 LLM。"""


class PetHospitalClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: Any | None = None,
    ) -> Any:
        url = self.base_url + path
        if params:
            clean = {k: v for k, v in params.items() if v not in (None, "", [])}
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean, doseq=True)}"

        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = _json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raise PetHospitalError(
                f"HTTP {e.code} {e.reason} {e.url}: {e.read().decode('utf-8', 'ignore')[:500]}"
            ) from None
        except urllib.error.URLError as e:
            raise PetHospitalError(
                f"无法连接宠物医院 REST 服务 {self.base_url}（先启动 pethospital 再调 tool）: {e.reason}"
            ) from None

        try:
            payload = _json.loads(raw)
        except _json.JSONDecodeError as e:
            raise PetHospitalError(f"响应不是合法 JSON: {raw[:500]}") from e

        code = payload.get("code", 0)
        # 200 OK / 201 Created 均为成功；其他 code 视为失败，message 回传给 LLM
        if code not in (200, 201):
            raise PetHospitalError(f"{code}: {payload.get('message', 'REST 调用失败')}")
        return payload.get("data")

    # ---------- 系统 ----------
    def health(self) -> Any:
        return self._request("GET", "/health")

    def stats(self, top: int = 5) -> Any:
        return self._request("GET", "/api/v1/stats", params={"top": top})

    # ---------- 宠物 CRUD ----------
    def list_pets(self, **filters: Any) -> Any:
        return self._request("GET", "/api/v1/pets", params=filters)

    def get_pet(self, pet_id: str) -> Any:
        return self._request("GET", f"/api/v1/pets/{pet_id}")

    def create_pet(self, pet: dict[str, Any]) -> Any:
        return self._request("POST", "/api/v1/pets", body=pet)

    def update_pet(self, pet_id: str, fields: dict[str, Any]) -> Any:
        return self._request("PATCH", f"/api/v1/pets/{pet_id}", body=fields)

    def delete_pet(self, pet_id: str) -> Any:
        return self._request("DELETE", f"/api/v1/pets/{pet_id}")

    def search_pets(self, q: str) -> Any:
        return self._request("GET", "/api/v1/pets/search", params={"q": q})

    # ---------- 病历 / 收费 ----------
    def add_medical_record(self, pet_id: str, record: dict[str, Any]) -> Any:
        return self._request("POST", f"/api/v1/pets/{pet_id}/records", body=record)

    def add_charge(self, pet_id: str, charge: dict[str, Any]) -> Any:
        return self._request("POST", f"/api/v1/pets/{pet_id}/charges", body=charge)

    def get_summary(self, pet_id: str) -> Any:
        return self._request("GET", f"/api/v1/pets/{pet_id}/summary")

    # ---------- 管理 ----------
    def seed_data(self, count: int = 1000, force: bool = False) -> Any:
        return self._request(
            "POST",
            "/api/v1/admin/seed",
            params={"force": "true" if force else "false", "count": count},
        )
