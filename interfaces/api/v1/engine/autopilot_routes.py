"""自动驾驶控制 API（v2：含审阅确认 + SSE 生成流）"""
import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from domain.novel.entities.novel import AutopilotStatus, NovelStage
from domain.novel.value_objects.novel_id import NovelId
from interfaces.api.dependencies import get_novel_repository, get_chapter_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/autopilot", tags=["autopilot"])


class StartRequest(BaseModel):
    max_auto_chapters: Optional[int] = 50  # 本次托管最大章节数


@router.post("/{novel_id}/start")
async def start_autopilot(novel_id: str, body: StartRequest = StartRequest()):
    """启动自动驾驶"""
    repo = get_novel_repository()
    novel = repo.get_by_id(NovelId(novel_id))
    if not novel:
        raise HTTPException(404, "小说不存在")

    novel.autopilot_status = AutopilotStatus.RUNNING
    novel.max_auto_chapters = body.max_auto_chapters
    novel.current_auto_chapters = novel.current_auto_chapters or 0
    novel.consecutive_error_count = 0

    # 如果是全新小说，从宏观规划开始
    fresh_stages = {NovelStage.PLANNING, NovelStage.MACRO_PLANNING}
    if novel.current_stage in fresh_stages:
        novel.current_stage = NovelStage.MACRO_PLANNING

    # 如果之前处于审阅等待，恢复为写作
    if novel.current_stage == NovelStage.PAUSED_FOR_REVIEW:
        novel.current_stage = NovelStage.ACT_PLANNING

    repo.save(novel)
    return {
        "success": True,
        "message": f"自动驾驶已启动，目标 {body.max_auto_chapters} 章",
        "autopilot_status": novel.autopilot_status.value,
        "current_stage": novel.current_stage.value,
    }


@router.post("/{novel_id}/stop")
async def stop_autopilot(novel_id: str):
    """停止自动驾驶"""
    repo = get_novel_repository()
    novel = repo.get_by_id(NovelId(novel_id))
    if not novel:
        raise HTTPException(404, "小说不存在")
    novel.autopilot_status = AutopilotStatus.STOPPED
    repo.save(novel)
    return {"success": True, "message": "自动驾驶已停止"}


@router.post("/{novel_id}/resume")
async def resume_from_review(novel_id: str):
    """从人工审阅点恢复（PAUSED_FOR_REVIEW → RUNNING）"""
    repo = get_novel_repository()
    novel = repo.get_by_id(NovelId(novel_id))
    if not novel:
        raise HTTPException(404, "小说不存在")
    if novel.current_stage != NovelStage.PAUSED_FOR_REVIEW:
        raise HTTPException(400, f"当前不在审阅等待状态（当前：{novel.current_stage.value}）")

    novel.autopilot_status = AutopilotStatus.RUNNING
    novel.current_stage = NovelStage.ACT_PLANNING
    repo.save(novel)
    return {"success": True, "message": "已恢复，开始规划下一幕章节"}


@router.get("/{novel_id}/status")
async def get_autopilot_status(novel_id: str):
    """获取完整运行状态"""
    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    novel = novel_repo.get_by_id(NovelId(novel_id))
    if not novel:
        raise HTTPException(404, "小说不存在")

    chapters = chapter_repo.list_by_novel(NovelId(novel_id))
    total_words = sum(
        c.word_count.value if hasattr(c.word_count, 'value') else c.word_count
        for c in chapters if c.word_count
    )
    _status = lambda c: c.status.value if hasattr(c.status, 'value') else c.status
    completed = [c for c in chapters if _status(c) == "completed"]

    return {
        "autopilot_status": novel.autopilot_status.value,
        "current_stage": novel.current_stage.value,
        "current_act": novel.current_act,
        "current_chapter_in_act": novel.current_chapter_in_act,
        "current_beat_index": getattr(novel, "current_beat_index", 0),
        "current_auto_chapters": getattr(novel, "current_auto_chapters", 0),
        "max_auto_chapters": getattr(novel, "max_auto_chapters", 50),
        "last_chapter_tension": getattr(novel, "last_chapter_tension", 0),
        "consecutive_error_count": getattr(novel, "consecutive_error_count", 0),
        "total_words": total_words,
        "completed_chapters": len(completed),
        "target_chapters": novel.target_chapters,
        "progress_pct": round(len(completed) / novel.target_chapters * 100, 1) if novel.target_chapters else 0,
        "needs_review": novel.current_stage.value == "paused_for_review",
    }


@router.get("/{novel_id}/events")
async def autopilot_events(novel_id: str):
    """SSE 实时状态推送（每 3 秒）"""
    novel_repo = get_novel_repository()
    chapter_repo = get_chapter_repository()

    async def event_generator():
        while True:
            try:
                novel = novel_repo.get_by_id(NovelId(novel_id))
                if not novel:
                    break
                chapters = chapter_repo.list_by_novel(NovelId(novel_id))
                total_words = sum(
                    c.word_count.value if hasattr(c.word_count, 'value') else c.word_count
                    for c in chapters if c.word_count
                )
                _st = lambda c: c.status.value if hasattr(c.status, 'value') else c.status
                completed = [c for c in chapters if _st(c) == "completed"]

                data = {
                    "autopilot_status": novel.autopilot_status.value,
                    "current_stage": novel.current_stage.value,
                    "current_act": novel.current_act,
                    "current_beat_index": getattr(novel, "current_beat_index", 0),
                    "completed_chapters": len(completed),
                    "total_words": total_words,
                    "target_chapters": novel.target_chapters,
                    "needs_review": novel.current_stage.value == "paused_for_review",
                    "consecutive_error_count": getattr(novel, "consecutive_error_count", 0),
                }
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

                terminal_states = {"stopped", "error", "completed"}
                if novel.autopilot_status.value in terminal_states and \
                   novel.current_stage.value != "paused_for_review":
                    break

                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"SSE error: {e}")
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
