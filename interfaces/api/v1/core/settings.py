"""LLM 配置管理 API（兼容旧路由，底层委托给 LLMControlService）。"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from application.ai.llm_control_service import LLMControlService, LLMProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings/llm-configs", tags=["settings"])

_service = LLMControlService()


# ── schemas (兼容旧接口) ──────────────────────────────

class ConfigCreate(BaseModel):
    name: str
    provider: str  # "openai" | "anthropic"
    api_key: str
    base_url: str = ""
    model: str = ""
    system_model: str = ""
    writing_model: str = ""


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    system_model: Optional[str] = None
    writing_model: Optional[str] = None


class FetchModelsRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str



class TestConfigRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str


class TestConfigResponse(BaseModel):
    success: bool
    message: str


def _profile_to_dict(p: LLMProfile) -> dict:
    """将 LLMProfile 转换为旧接口的 dict 格式。"""
    return {
        "id": p.id,
        "name": p.name,
        "provider": p.protocol,
        "api_key": p.api_key,
        "base_url": p.base_url,
        "model": p.model,
        "system_model": p.model,
        "writing_model": p.model,
    }


@router.get("/")
def list_configs():
    config = _service.get_config()
    return [_profile_to_dict(p) for p in config.profiles]


@router.post("/")
def create_config(body: ConfigCreate):
    config = _service.get_config()
    new_profile = LLMProfile(
        id=f"profile-{len(config.profiles) + 1}",
        name=body.name,
        preset_key="custom-openai-compatible",
        protocol=body.provider,  # type: ignore[arg-type]
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model or body.system_model or body.writing_model,
    )
    config.profiles.append(new_profile)
    saved = _service.save_config(config)
    return _profile_to_dict(saved.profiles[-1])


@router.put("/{config_id}")
def update_config(config_id: str, body: ConfigUpdate):
    config = _service.get_config()
    for i, p in enumerate(config.profiles):
        if p.id == config_id:
            update_data = body.model_dump(exclude_none=True)
            # 映射旧字段名到新字段名
            if "provider" in update_data:
                update_data["protocol"] = update_data.pop("provider")
            updated = p.model_copy(update={k: v for k, v in update_data.items() if hasattr(p, k)})
            config.profiles[i] = updated
            _service.save_config(config)
            return _profile_to_dict(updated)
    raise HTTPException(404, "Config not found")


@router.delete("/{config_id}")
def delete_config(config_id: str):
    config = _service.get_config()
    original_len = len(config.profiles)
    config.profiles = [p for p in config.profiles if p.id != config_id]
    if len(config.profiles) == original_len:
        raise HTTPException(404, "Config not found")
    _service.save_config(config)
    return {"ok": True}


@router.post("/{config_id}/activate")
def activate_config(config_id: str):
    config = _service.get_config()
    ids = {p.id for p in config.profiles}
    if config_id not in ids:
        raise HTTPException(404, "Config not found")
    config.active_profile_id = config_id
    _service.save_config(config)
    return {"ok": True}


@router.post("/fetch-models")
async def fetch_models(body: FetchModelsRequest):
    """复用 llm-control/models 端点的逻辑。"""
    from interfaces.api.v1.workbench.llm_control import list_models
    from interfaces.api.v1.workbench.llm_control import ModelListRequest

    payload = ModelListRequest(
        protocol=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
    )
    result = await list_models(payload)
    return [m.id for m in result.items]


# ── embedding endpoints ────────────────────────────────

embedding_router = APIRouter(prefix="/settings/embedding", tags=["settings"])


class EmbeddingConfigUpdate(BaseModel):
    mode: str = "local"
    api_key: str = ""
    base_url: str = ""
    model: str = "text-embedding-3-small"
    use_gpu: bool = True
    model_path: str = "BAAI/bge-small-zh-v1.5"


@embedding_router.get("/")
def get_embedding_config():
    # 返回默认配置（embedding 配置暂未迁移到新体系）
    return {
        "mode": "local",
        "api_key": "",
        "base_url": "",
        "model": "text-embedding-3-small",
        "use_gpu": True,
        "model_path": "BAAI/bge-small-zh-v1.5",
    }


@embedding_router.put("/")
def update_embedding_config(body: EmbeddingConfigUpdate):
    # 暂时返回写入的值（后续可持久化）
    return body.model_dump()


@embedding_router.post("/fetch-models")
async def fetch_embedding_models(body: FetchModelsRequest):
    if not body.base_url:
        return []

    return await _fetch_openai_models(body.api_key, body.base_url)


@router.post("/test")
async def test_config(body: TestConfigRequest):
    """测试 LLM 配置是否能成功连接"""
    try:
        if body.provider == "anthropic":
            success = await _test_anthropic_config(body.api_key, body.base_url)
        else:
            success = await _test_openai_config(body.api_key, body.base_url)

        if success:
            return TestConfigResponse(success=True, message="连接成功")
        else:
            return TestConfigResponse(success=False, message="连接失败")
    except Exception as exc:
        logger.warning("test-config failed: %s", exc)
        return TestConfigResponse(success=False, message=f"连接失败: {exc}")


# ── helpers ─────────────────────────────────────────────────

async def _test_openai_config(api_key: str, base_url: str) -> bool:
    """测试 OpenAI 兼容配置"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # 尝试最简单的请求格式
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hi"}]
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            # 400 错误可能只是模型不对，说明 API Key 和 URL 是正确的
            logger.info("Got 400 but API key/URL are valid, considering test passed")
            return True
        raise


async def _test_anthropic_config(api_key: str, base_url: str) -> bool:
    """测试 Anthropic 配置"""
    base = (base_url or "https://api.anthropic.com").rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/messages"
    else:
        url = f"{base}/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-3-haiku-20240307",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 1
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return True
    except Exception:
        if not base_url:
            raise
        logger.info("Anthropic-style test failed, trying OpenAI-style")
        fallback_base = base_url.rstrip("/")
        if not fallback_base.endswith("/v1"):
            fallback_base += "/v1"
        return await _test_openai_config(api_key, fallback_base)


async def _fetch_openai_models(api_key: str, base_url: str) -> List[str]:
    url = f"{base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            return sorted(m["id"] for m in models if "id" in m)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, f"API returned {exc.response.status_code}")
    except Exception as exc:
        logger.warning("fetch-models failed: %s", exc)
        raise HTTPException(502, f"Failed to fetch models: {exc}")


async def _fetch_anthropic_models(api_key: str, base_url: str) -> List[str]:
    base = (base_url or "https://api.anthropic.com").rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/models"
    else:
        url = f"{base}/v1/models"
    headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers=headers, params={"limit": 1000})
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])
            return sorted(m["id"] for m in models if "id" in m)
    except Exception as exc:
        if not base_url:
            raise HTTPException(502, f"Failed to fetch Anthropic models: {exc}")
        logger.info("Anthropic-style fetch failed, trying OpenAI-style: %s", exc)
        try:
            fallback_base = base_url.rstrip("/")
            if not fallback_base.endswith("/v1"):
                fallback_base += "/v1"
            return await _fetch_openai_models(api_key, fallback_base)
        except Exception:
            raise HTTPException(502, f"Failed to fetch models (tried both Anthropic and OpenAI format): {exc}")

    from interfaces.api.v1.workbench.llm_control import list_models
    from interfaces.api.v1.workbench.llm_control import ModelListRequest

    payload = ModelListRequest(
        protocol=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
    )
    result = await list_models(payload)
    return [m.id for m in result.items]

