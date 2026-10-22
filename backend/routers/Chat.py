"""
API Chat: Chatbot เรียก Gemini API โดยตรงผ่าน Google GenAI SDK (native) รองรับข้อความและรูปภาพ
- โหลดรายการหินจาก MySQL (ตาราง granite_products) เป็น context ให้ LLM แนะนำหินให้ลูกค้า
  (เดิมอ่านจาก CSV ตรงๆ — เปลี่ยนมาอ่านจาก DB แล้ว เพราะตอนนี้ Catalog Service มี MySQL จริง)
- POST /chat/completions: คืนคำตอบแบบเต็ม (ไม่ stream)
- POST /chat/completions/stream: คืนคำตอบแบบ streaming (SSE) พร้อมแนบรูปหินที่ AI พูดถึง

การตั้งค่า (.env หรือ environment variables):
    GEMINI_API_KEY=xxxxxxxx        (จำเป็น — ขอได้ฟรีที่ https://aistudio.google.com/apikey)
    GEMINI_CHAT_MODEL=gemini-3.6-flash   (ไม่ใส่ก็ได้ มีค่า default ให้)

หมายเหตุสำคัญ — ทำไมใช้ SDK นี้แทน OpenAI-compatible endpoint:
    Google กำลังเปลี่ยน API key ที่ออกใหม่จาก Google AI Studio จากฟอร์แมตเดิม `AIza...`
    ไปเป็นฟอร์แมตใหม่ `AQ....` คีย์แบบใหม่ใช้กับ endpoint ที่เข้ากันได้กับ OpenAI ไม่ได้
    ต้องใช้ไลบรารี `google-genai` (native Google SDK) เรียก Gemini โดยตรงแทนถึงจะใช้ได้กับ
    คีย์ทั้งสองแบบ อ้างอิง: https://ai.google.dev/gemini-api/docs/api-key
"""
import base64
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Union

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from database import SessionLocal, get_db
from models import GraniteProduct, ChatMessage as ChatMessageRow, User
from auth_utils import decode_access_token
from routers.Auth import get_current_user, oauth2_scheme
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

# ---------------------------------------------------------------------------
# Gemini config — อ่านจาก environment variable เท่านั้น (ห้าม hardcode คีย์ในโค้ด!)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# โมเดล Gemini ที่แนะนำสำหรับแชทบอทแบบนี้ (เร็ว ราคาถูก รองรับรูปภาพ):
#   gemini-3.6-flash       -> ค่า default (gemini-2.5-flash ถูกปิดสำหรับผู้ใช้ใหม่แล้ว)
#   gemini-2.5-flash-lite  -> ถูกและเร็วที่สุด เหมาะกับงานตอบคำถามสั้นๆ (ถ้ายังใช้ได้กับบัญชี)
#   gemini-3.6-pro         -> ฉลาดที่สุด แต่ช้ากว่าและแพงกว่า
# ตรวจสอบรายชื่อ/ราคาโมเดลล่าสุดได้ที่ https://ai.google.dev/gemini-api/docs/models ก่อนใช้งานจริง
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "8192"))

# ลองเรียก Gemini ซ้ำอัตโนมัติเมื่อเจอ error ชั่วคราว (503 server โหลดหนัก / 429 โดน rate limit)
# โดยรอนานขึ้นเรื่อยๆ ระหว่างครั้ง (1.5s, 3s, ...) — ตั้งค่าได้ใน .env
GEMINI_MAX_RETRIES = max(1, int(os.environ.get("GEMINI_MAX_RETRIES", "3")))
GEMINI_RETRY_BASE_DELAY = float(os.environ.get("GEMINI_RETRY_BASE_DELAY", "1.5"))
_TRANSIENT_CODES = {429, 500, 502, 503, 504}
_TRANSIENT_WORDS = ("503", "UNAVAILABLE", "OVERLOADED", "RESOURCE_EXHAUSTED", "429", "DEADLINE_EXCEEDED")
BUSY_MESSAGE = "ตอนนี้ AI (Gemini) กำลังมีผู้ใช้งานหนาแน่น ลองส่งข้อความใหม่อีกครั้งในอีกสักครู่นะครับ"

_genai_client: Optional[genai.Client] = None


def _is_transient_error(e: Exception) -> bool:
    """error ที่ลองใหม่แล้วมีโอกาสสำเร็จ (ไม่ใช่ความผิดของ request เช่น key ผิด/คำขอไม่ถูกต้อง)"""
    code = getattr(e, "code", None)
    if isinstance(code, int) and code in _TRANSIENT_CODES:
        return True
    msg = str(e).upper()
    return any(w in msg for w in _TRANSIENT_WORDS)


def _friendly_error(e: Exception) -> str:
    return BUSY_MESSAGE if _is_transient_error(e) else str(e)


def _retry_wait(attempt: int, e: Exception) -> None:
    delay = GEMINI_RETRY_BASE_DELAY * (2 ** (attempt - 1))
    logger.warning("Gemini error ชั่วคราว (ครั้งที่ %d/%d) จะลองใหม่ใน %.1fs: %s",
                   attempt, GEMINI_MAX_RETRIES, delay, e)
    time.sleep(delay)


def _with_retry(fn):
    """เรียก fn() ซ้ำเมื่อเจอ error ชั่วคราว จนครบจำนวนครั้งที่ตั้งไว้ แล้วค่อยโยน error ออกไป"""
    for attempt in range(1, GEMINI_MAX_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            if not _is_transient_error(e) or attempt == GEMINI_MAX_RETRIES:
                raise
            _retry_wait(attempt, e)


def _get_client() -> genai.Client:
    global _genai_client
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ยังไม่ได้ตั้งค่า GEMINI_API_KEY — เพิ่มใน .env แล้ว restart server "
                   "(ขอคีย์ได้ฟรีที่ https://aistudio.google.com/apikey)",
        )
    if _genai_client is None:
        # เคลียร์ GOOGLE_API_KEY ทิ้งก่อนสร้าง client เสมอ: SDK นี้มี behavior ที่ให้
        # GOOGLE_API_KEY (ถ้ามีอยู่ใน environment ของเครื่อง) ชนะค่า api_key ที่เราส่งเข้าไป
        # ตรงๆ เสมอ แม้จะระบุ genai.Client(api_key=...) ไว้ชัดเจนแล้วก็ตาม
        os.environ.pop("GOOGLE_API_KEY", None)
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


# ---------------------------------------------------------------------------
# โหลดรายการหินจาก MySQL (แทนที่ CSV เดิม)
# ---------------------------------------------------------------------------

_products_cache: Optional[List[GraniteProduct]] = None


def invalidate_products_cache() -> None:
    """เรียกหลังแอดมินเพิ่ม/แก้/ลบหิน เพื่อให้ AI เห็นรายการหินล่าสุดทันที"""
    global _products_cache
    _products_cache = None


def _load_products_from_db() -> List[GraniteProduct]:
    """
    โหลดสินค้าทั้งหมดจากตาราง granite_products
    ใช้ cache ในหน่วยความจำ เพราะข้อมูลหินไม่ได้เปลี่ยนบ่อย (เปลี่ยนตอนรัน seed_catalog.sql
    ใหม่เท่านั้น) — ถ้าต้องการให้ refresh สดทุกครั้งสามารถลบ cache logic นี้ออกได้ในอนาคต
    """
    global _products_cache
    if _products_cache is not None:
        return _products_cache
    db = SessionLocal()
    try:
        products = db.query(GraniteProduct).all()
        # ต้องอ่านค่าทุก field ออกมาตอนยัง session เปิดอยู่ (SQLAlchemy lazy-load หลัง
        # session ปิดจะ error) — เก็บเป็น dict ธรรมดาแทนที่จะเก็บ ORM object ค้างไว้
        _products_cache = [
            {
                "id": p.id,
                "product_title": p.product_title,
                "product_description": p.product_description,
                "product_price": float(p.product_price),
                "image_url": p.image_url,
            }
            for p in products
        ]
        return _products_cache
    finally:
        db.close()


def _load_products_context() -> str:
    """สร้างข้อความ context รายการหินทั้งหมด ให้ LLM ใช้แนะนำหินให้ลูกค้า"""
    products = _load_products_from_db()
    if not products:
        return ""
    lines = [
        f"- ชื่อ: {p['product_title']} | ราคา: {p['product_price']:.0f} บาท/ตร.ม. | รายละเอียด: {p['product_description']}"
        for p in products
    ]
    block = "\n".join(lines)
    return (
        "คุณเป็นผู้เชี่ยวชาญแนะนำหินแกรนิตและหินอ่อน ให้แนะนำลูกค้าจากรายการสินค้าที่มีในระบบเท่านั้น "
        "โดยอ้างอิงชื่อหิน ราคา (บาท/ตร.ม.) และรายละเอียดด้านล่างนี้:\n\n"
        f"{block}\n\n"
        "ตอบเป็นภาษาไทย อธิบายให้เหมาะกับความต้องการของลูกค้า และระบุชื่อหินกับราคาจากรายการด้านบนเมื่อแนะนำ."
    )


# ---------------------------------------------------------------------------
# ประวัติแชทต่อผู้ใช้
# - บันทึกเมื่อ "ล็อกอินอยู่" เท่านั้น (แนบ token มากับ request) ผู้ใช้ที่ไม่ได้ล็อกอินยังแชทได้เหมือนเดิม
# - บันทึกเป็นคู่ (คำถาม + คำตอบ) หลังตอบสำเร็จเท่านั้น ถ้า AI ล้มเหลวจะไม่มีคำถามค้างโดยไม่มีคำตอบ
# - บันทึกเป็น best-effort: ถ้าบันทึกไม่ได้ จะแค่ log เตือน ไม่ทำให้แชทพัง
# ---------------------------------------------------------------------------

DEFAULT_IMAGE_PROMPT = "ช่วยดูรูปนี้แล้วแนะนำหินแกรนิต/หินอ่อนที่เข้ากันหน่อยครับ"  # ข้อความอัตโนมัติจาก frontend ตอนส่งแต่รูป
MAX_STORED_PER_USER = 500
MAX_CONTENT_CHARS = 60000


def _optional_user_id(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[int]:
    """อ่าน user id จาก token ถ้ามี — ไม่มี/ผิดก็คืน None (แชทแบบไม่ล็อกอินยังใช้ได้)"""
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


def _extract_user_text(message) -> tuple:
    """คืน (ข้อความ, มีรูปแนบไหม) จากข้อความล่าสุดของผู้ใช้"""
    if message is None:
        return "", False
    if isinstance(message.content, str):
        return message.content, False
    texts, has_image = [], False
    for part in message.content:
        if part.get("type") == "text":
            texts.append(part.get("text", ""))
        elif part.get("type") == "image_url":
            has_image = True
    text = "\n".join(t for t in texts if t).strip()
    if has_image and text == DEFAULT_IMAGE_PROMPT:
        text = ""
    return text, has_image


def _save_exchange(user_id: Optional[int], messages: list, reply: str, products: list) -> None:
    if not user_id or not reply:
        return
    last_user = next((m for m in reversed(messages) if m.role == "user"), None)
    text, has_image = _extract_user_text(last_user)
    if not text and not has_image:
        return
    db = SessionLocal()
    try:
        db.add(ChatMessageRow(user_id=user_id, role="user", content=text[:MAX_CONTENT_CHARS], has_image=has_image))
        db.add(ChatMessageRow(user_id=user_id, role="assistant", content=reply[:MAX_CONTENT_CHARS],
                           products=products or None))
        db.commit()
        # เก็บแค่ MAX_STORED_PER_USER ข้อความล่าสุดต่อคน — ลบของเก่าทิ้ง
        cutoff = (
            db.query(ChatMessageRow.id).filter(ChatMessageRow.user_id == user_id)
            .order_by(ChatMessageRow.id.desc()).offset(MAX_STORED_PER_USER).first()
        )
        if cutoff:
            db.query(ChatMessageRow).filter(ChatMessageRow.user_id == user_id, ChatMessageRow.id <= cutoff[0]).delete()
            db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning("บันทึกประวัติแชทไม่สำเร็จ (ไม่กระทบการแชท): %s", e)
    finally:
        db.close()


def _find_mentioned_products(text: str) -> List[dict]:
    """
    หาว่าข้อความที่ AI ตอบกลับมา พูดถึงหินชนิดไหนบ้าง (จับคู่แบบ substring)
    คืนรายการหินที่พบ พร้อมรูปภาพ เพื่อให้ frontend แสดงเป็นการ์ดรูปประกอบคำตอบ
    """
    if not text:
        return []
    products = _load_products_from_db()
    text_upper = text.upper()
    matched = []
    seen_names = set()
    for p in sorted(products, key=lambda x: len(x["product_title"]), reverse=True):
        name_upper = p["product_title"].upper()
        if name_upper and name_upper in text_upper and name_upper not in seen_names:
            if p["image_url"]:
                matched.append({"name": p["product_title"], "image_url": p["image_url"], "price": str(p["product_price"])})
            seen_names.add(name_upper)
    return matched[:4]


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ImageUrlContent(BaseModel):
    url: str


class TextContent(BaseModel):
    type: str = "text"
    text: str


class ImageUrlPart(BaseModel):
    type: str = "image_url"
    image_url: ImageUrlContent


ChatContent = Union[str, List[Union[dict, TextContent, ImageUrlPart]]]


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: Union[str, List[dict]] = Field(
        ...,
        description="ข้อความหรือ list ของ {type: 'text', text: '...'} หรือ {type: 'image_url', image_url: {url: '...'}}",
    )

    class Config:
        extra = "allow"


class ChatCompletionsRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = Field(None, description="ถ้าไม่ส่ง ใช้ model เริ่มต้น (gemini-3.6-flash)")
    max_tokens: Optional[int] = Field(None, description="ถ้าไม่ส่ง ใช้ค่า default")
    stream: Optional[bool] = Field(False, description="ใช้ endpoint /stream แทน")


CHAT_SCHEMA_EXAMPLES = {
    "request_schema": {
        "messages": [{"role": "user", "content": "ข้อความจากลูกค้า"}],
        "model": "ไม่ส่งได้ (ใช้ model เริ่มต้น: gemini-3.6-flash)",
        "max_tokens": 1024,
    },
    "examples": [
        {
            "name": "แนะนำหินตามงบ",
            "body": {
                "messages": [
                    {"role": "user", "content": "อยากได้หินสีดำสำหรับท็อปครัว งบประมาณไม่เกิน 2500 บาท/ตร.ม. แนะนำหน่อย"}
                ],
                "max_tokens": 1024,
            },
        },
        {
            "name": "ถามรายการหินสีขาว",
            "body": {"messages": [{"role": "user", "content": "มีหินแกรนิตสีขาวอะไรบ้าง"}]},
        },
    ],
    "endpoints": {
        "completions": "POST /chat/completions — คืนคำตอบเต็มครั้งเดียว",
        "completions_stream": "POST /chat/completions/stream — คืนคำตอบแบบ streaming (SSE)",
    },
}


@router.get("/schema", summary="Schema สำหรับทดลอง")
def chat_schema():
    """คืน request schema และตัวอย่าง body สำหรับทดลอง Chat API"""
    return CHAT_SCHEMA_EXAMPLES


# ---------------------------------------------------------------------------
# แปลง ChatMessage -> google.genai.types.Content
# ---------------------------------------------------------------------------

def _image_part_from_url(url: str) -> Optional[genai_types.Part]:
    try:
        if url.startswith("data:"):
            header, b64data = url.split(",", 1)
            mime_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
            return genai_types.Part.from_bytes(data=base64.b64decode(b64data), mime_type=mime_type)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        mime_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return genai_types.Part.from_bytes(data=resp.content, mime_type=mime_type)
    except Exception as e:
        logger.warning("โหลดรูปจาก %s ไม่สำเร็จ: %s", url, e)
        return None


def _messages_to_genai(messages: List[ChatMessage]) -> tuple:
    system_parts = []
    contents = []
    for m in messages:
        if m.role == "system":
            if isinstance(m.content, str):
                system_parts.append(m.content)
            continue
        role = "model" if m.role == "assistant" else "user"
        parts = []
        if isinstance(m.content, str):
            parts.append(genai_types.Part.from_text(text=m.content))
        else:
            for item in m.content:
                item_type = item.get("type")
                if item_type == "text":
                    parts.append(genai_types.Part.from_text(text=item.get("text", "")))
                elif item_type == "image_url":
                    url = (item.get("image_url") or {}).get("url", "")
                    part = _image_part_from_url(url) if url else None
                    if part:
                        parts.append(part)
                    else:
                        parts.append(genai_types.Part.from_text(text=f"[ไม่สามารถโหลดรูปภาพจาก {url}]"))
        if parts:
            contents.append(genai_types.Content(role=role, parts=parts))
    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


# คำสั่งเพิ่มเมื่อผู้ใช้แนบรูปห้อง/พื้นที่ ให้ AI วิเคราะห์เป็นขั้นตอนและแนะนำจากแคตตาล็อกจริง
IMAGE_GUIDE = (
    "ผู้ใช้แนบรูปมาในข้อความล่าสุด ให้ทำตามลำดับนี้ ตอบเป็นภาษาไทยกระชับ:\n"
    "1) สรุปสิ่งที่เห็นใน 1-2 บรรทัด: ประเภทห้อง/พื้นที่, โทนสีหลัก, สไตล์การตกแต่ง, แสงสว่าง, วัสดุเดิม (พื้น ผนัง ตู้)\n"
    "2) แนะนำหินจากรายการด้านบน 2-3 ชนิด (พิมพ์ชื่อหินให้ตรงตามรายการทุกตัวอักษร) "
    "แต่ละชนิดบอกเหตุผลที่เข้ากับห้องนี้ และราคา บาท/ตร.ม.\n"
    "3) บอกว่าควรใช้กับส่วนไหนของห้อง (เช่น ท็อปครัว พื้น ผนัง) และข้อควรระวังสั้นๆ ถ้ามี\n"
    "ถ้ารูปไม่ใช่ห้อง/พื้นที่ที่จะใช้หิน หรือมืด/เบลอจนดูไม่ออก ให้บอกตรงๆ แล้วขอรูปใหม่หรือถามความต้องการเพิ่ม "
    "ห้ามแต่งรายละเอียดที่มองไม่เห็นในรูป และห้ามแนะนำหินที่ไม่มีในรายการ"
)


def _last_user_has_image(messages: List[ChatMessage]) -> bool:
    for m in reversed(messages):
        if m.role != "user":
            continue
        if isinstance(m.content, list):
            return any(isinstance(i, dict) and i.get("type") == "image_url" for i in m.content)
        return False
    return False


def _build_system_instruction(messages: List[ChatMessage]) -> tuple:
    products_context = _load_products_context()
    if products_context and _last_user_has_image(messages):
        products_context = f"{products_context}\n\n{IMAGE_GUIDE}"
    system_instruction, contents = _messages_to_genai(messages)
    if products_context:
        system_instruction = (
            f"{system_instruction}\n\n{products_context}" if system_instruction else products_context
        )
    return system_instruction, contents


# ---------------------------------------------------------------------------
# Non-streaming: POST /chat/completions
# ---------------------------------------------------------------------------

@router.post("/completions")
def chat_completions(request: ChatCompletionsRequest, user_id: Optional[int] = Depends(_optional_user_id)):
    client = _get_client()
    model = request.model or CHAT_MODEL
    max_tokens = request.max_tokens or MAX_TOKENS
    system_instruction, contents = _build_system_instruction(request.messages)

    try:
        response = _with_retry(lambda: client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
            ),
        ))
    except Exception as e:
        logger.exception("Gemini chat error: %s", e)
        raise HTTPException(status_code=503 if _is_transient_error(e) else 502, detail=_friendly_error(e))

    content = response.text or ""
    usage = getattr(response, "usage_metadata", None)
    products = _find_mentioned_products(content)
    _save_exchange(user_id, request.messages, content, products)
    return {
        "content": content,
        "role": "assistant",
        "products": products,
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_token_count", None) if usage else None,
            "completion_tokens": getattr(usage, "candidates_token_count", None) if usage else None,
            "total_tokens": getattr(usage, "total_token_count", None) if usage else None,
        },
    }


# ---------------------------------------------------------------------------
# Streaming: POST /chat/completions/stream (SSE)
# ---------------------------------------------------------------------------

def _stream_events(messages: List[ChatMessage], model: str, max_tokens: int, user_id: Optional[int] = None):
    try:
        client = _get_client()
        system_instruction, contents = _build_system_instruction(messages)
        full_text = ""
        for attempt in range(1, GEMINI_MAX_RETRIES + 1):
            try:
                stream = client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        max_output_tokens=max_tokens,
                    ),
                )
                for chunk in stream:
                    text = getattr(chunk, "text", None)
                    if text:
                        full_text += text
                        data = json.dumps({"content": text})
                        yield f"data: {data}\n\n"
                break  # สำเร็จ
            except Exception as e:
                # ลองใหม่เฉพาะตอนที่ "ยังไม่ได้ส่งข้อความใดๆ" ให้ผู้ใช้ — ถ้าส่งไปแล้วครึ่งทาง
                # แล้วลองใหม่ ข้อความจะซ้ำ/ต่อกันผิดๆ จึงยอมแจ้ง error ตรงๆ แทน
                if full_text or not _is_transient_error(e) or attempt == GEMINI_MAX_RETRIES:
                    raise
                _retry_wait(attempt, e)

        products = _find_mentioned_products(full_text)
        _save_exchange(user_id, messages, full_text, products)
        if products:
            yield f"data: {json.dumps({'products': products})}\n\n"
    except HTTPException as e:
        logger.exception("Gemini stream error (HTTPException): %s", e.detail)
        yield f"data: {json.dumps({'error': str(e.detail)})}\n\n"
    except Exception as e:
        logger.exception("Gemini stream error: %s", e)
        yield f"data: {json.dumps({'error': _friendly_error(e)})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post("/completions/stream")
def chat_completions_stream(request: ChatCompletionsRequest, user_id: Optional[int] = Depends(_optional_user_id)):
    model = request.model or CHAT_MODEL
    max_tokens = request.max_tokens or MAX_TOKENS

    return StreamingResponse(
        _stream_events(request.messages, model, max_tokens, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# ประวัติแชทของผู้ใช้ที่ล็อกอินอยู่
#   GET    /chat/history   — ดึงข้อความล่าสุด (เรียงเก่า -> ใหม่)
#   DELETE /chat/history   — ล้างประวัติทั้งหมดของตัวเอง
# ---------------------------------------------------------------------------

@router.get("/history", summary="ประวัติแชทของฉัน")
def get_chat_history(
    limit: int = Query(60, ge=1, le=200, description="จำนวนข้อความล่าสุดที่ต้องการ"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ChatMessageRow)
        .filter(ChatMessageRow.user_id == current_user.id)
        .order_by(ChatMessageRow.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "has_image": bool(r.has_image),
            "products": r.products or [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.delete("/history", status_code=204, summary="ล้างประวัติแชทของฉัน")
def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(ChatMessageRow).filter(ChatMessageRow.user_id == current_user.id).delete()
    db.commit()
    return None
