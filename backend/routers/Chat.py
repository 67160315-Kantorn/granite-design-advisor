"""
API Chat: Chatbot เรียก Gemini API โดยตรงผ่าน Google GenAI SDK (native) รองรับข้อความและรูปภาพ
- โหลด product_title, product_description, product_price จาก CSV เป็น context ให้ LLM แนะนำหินให้ลูกค้า
- POST /chat/completions: คืนคำตอบแบบเต็ม (ไม่ stream)
- POST /chat/completions/stream: คืนคำตอบแบบ streaming (SSE)

การตั้งค่า (.env หรือ environment variables):
    GEMINI_API_KEY=xxxxxxxx        (จำเป็น — ขอได้ฟรีที่ https://aistudio.google.com/apikey)
    GEMINI_CHAT_MODEL=gemini-3.6-flash   (ไม่ใส่ก็ได้ มีค่า default ให้)

หมายเหตุสำคัญ — ทำไมใช้ SDK นี้แทน OpenAI-compatible endpoint:
    Google กำลังเปลี่ยน API key ที่ออกใหม่จาก Google AI Studio จากฟอร์แมตเดิม `AIza...`
    (เรียกว่า "Standard key") ไปเป็นฟอร์แมตใหม่ `AQ....` (เรียกว่า "Auth key") คีย์แบบ Auth key
    ใช้กับ endpoint ที่เข้ากันได้กับ OpenAI (/v1beta/openai/) ไม่ได้ จะเจอ error
    "Please pass a valid API key" ทั้งที่คีย์ถูกต้อง — ต้องใช้ไลบรารี `google-genai` (native
    Google SDK) เรียก Gemini โดยตรงแทนถึงจะใช้ได้กับคีย์ทั้งสองแบบ
    อ้างอิง: https://ai.google.dev/gemini-api/docs/api-key
"""
import base64
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Union

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from google import genai
from google.genai import types as genai_types
from pydantic import BaseModel, Field

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
from scrape_granite import CSV_PATH

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

# ---------------------------------------------------------------------------
# Gemini config — อ่านจาก environment variable เท่านั้น (ห้าม hardcode คีย์ในโค้ด!)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# โมเดล Gemini ที่แนะนำสำหรับแชทบอทแบบนี้ (เร็ว ราคาถูก รองรับรูปภาพ):
#   gemini-3.6-flash       -> สมดุลระหว่างคุณภาพ/ราคา/ความเร็ว (ค่า default)
#   gemini-2.5-flash-lite  -> ถูกและเร็วที่สุด เหมาะกับงานตอบคำถามสั้นๆ (ถ้ายังใช้ได้กับบัญชีคุณ)
#   gemini-2.5-pro         -> ฉลาดที่สุด แต่ช้ากว่าและแพงกว่า
# ตรวจสอบรายชื่อ/ราคาโมเดลล่าสุดได้ที่ https://ai.google.dev/gemini-api/docs/models ก่อนใช้งานจริง
CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "8192"))

_genai_client: Optional[genai.Client] = None


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
        # GOOGLE_API_KEY (ถ้ามีอยู่ใน environment ของเครื่อง เช่น ค้างมาจากการติดตั้งเครื่องมือ
        # อื่นของ Google ก่อนหน้านี้) ชนะค่า api_key ที่เราส่งเข้าไปตรงๆ เสมอ แม้จะระบุ
        # genai.Client(api_key=...) ไว้ชัดเจนแล้วก็ตาม — ถ้าปล่อยไว้ ผู้ใช้ที่มี GOOGLE_API_KEY
        # เก่า/ผิดค้างอยู่ในเครื่องจะเจอ "API key not valid" ทั้งที่ GEMINI_API_KEY ใน .env ถูกต้อง
        os.environ.pop("GOOGLE_API_KEY", None)
        _genai_client = genai.Client(api_key=GEMINI_API_KEY)
    return _genai_client


def _load_products_context() -> str:
    """
    โหลด product_title, product_description, product_price จาก CSV
    สร้างเป็นข้อความ context ให้ LLM ใช้แนะนำหินให้ลูกค้า
    """
    if not CSV_PATH.exists():
        return ""
    lines = []
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            title = (row.get("product_title") or "").strip()
            desc = (row.get("product_description") or "").strip()
            price = (row.get("product_price") or "").strip().replace(",", "")
            if not title:
                continue
            lines.append(f"- ชื่อ: {title} | ราคา: {price} บาท/ตร.ม. | รายละเอียด: {desc}")
    if not lines:
        return ""
    block = "\n".join(lines)
    return (
        "คุณเป็นผู้เชี่ยวชาญแนะนำหินแกรนิตและหินอ่อน ให้แนะนำลูกค้าจากรายการสินค้าที่มีในระบบเท่านั้น "
        "โดยอ้างอิงชื่อหิน ราคา (บาท/ตร.ม.) และรายละเอียดด้านล่างนี้:\n\n"
        f"{block}\n\n"
        "ตอบเป็นภาษาไทย อธิบายให้เหมาะกับความต้องการของลูกค้า และระบุชื่อหินกับราคาจากรายการด้านบนเมื่อแนะนำ."
    )


_products_cache: Optional[List[dict]] = None


def _load_products_list() -> List[dict]:
    """
    โหลดรายการหินแบบโครงสร้าง (ชื่อ, ราคา, รูป) สำหรับจับคู่กับข้อความที่ AI ตอบกลับมา
    ใช้ cache ในหน่วยความจำ เพราะไฟล์ CSV ไม่ได้เปลี่ยนบ่อย (เปลี่ยนเมื่อรัน /estimate/refresh เท่านั้น)
    """
    global _products_cache
    if _products_cache is not None:
        return _products_cache
    if not CSV_PATH.exists():
        return []
    products = []
    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = (row.get("product_title") or "").strip()
            image_url = (row.get("image_url") or "").strip()
            price = (row.get("product_price") or "").strip()
            if not title:
                continue
            products.append({"name": title, "image_url": image_url, "price": price})
    _products_cache = products
    return products


def _find_mentioned_products(text: str) -> List[dict]:
    """
    หาว่าข้อความที่ AI ตอบกลับมา พูดถึงหินชนิดไหนบ้าง (จับคู่แบบ substring, ไม่สนตัวพิมพ์เล็ก/ใหญ่)
    คืนรายการหินที่พบ พร้อมรูปภาพ เพื่อให้ frontend แสดงเป็นการ์ดรูปประกอบคำตอบ
    เรียงตามความยาวชื่อจากมากไปน้อยก่อนจับคู่ กันปัญหาเช่น "White" ไป match ทับ "Kashmir White"
    """
    if not text:
        return []
    products = _load_products_list()
    text_upper = text.upper()
    matched = []
    seen_names = set()
    for p in sorted(products, key=lambda x: len(x["name"]), reverse=True):
        name_upper = p["name"].upper()
        # ตัดวงเล็บท้ายชื่อออกก่อน match เช่น "BLACK GALAXY (ดำเกล็ดทอง)" -> "BLACK GALAXY"
        base_name = name_upper.split("(")[0].strip()
        if base_name and base_name in text_upper and base_name not in seen_names:
            if p["image_url"]:
                matched.append(p)
            seen_names.add(base_name)
    return matched[:4]  # จำกัดไม่เกิน 4 รูปต่อคำตอบ กันข้อความยาวๆ ที่พูดถึงหินเยอะเกินไป


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ImageUrlContent(BaseModel):
    """รูปภาพส่งเป็น URL"""
    url: str


class TextContent(BaseModel):
    """ข้อความธรรมดา"""
    type: str = "text"
    text: str


class ImageUrlPart(BaseModel):
    """ส่วน content แบบ image_url (สำหรับ vision)"""
    type: str = "image_url"
    image_url: ImageUrlContent


# Message content: ได้ทั้ง string หรือ list ของ text/image_url
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
    """Body เหมือน OpenAI Chat Completions (โครงสร้างคงเดิม เพื่อไม่ต้องแก้ frontend)"""
    messages: List[ChatMessage]
    model: Optional[str] = Field(None, description="ถ้าไม่ส่ง ใช้ model เริ่มต้น (gemini-3.6-flash)")
    max_tokens: Optional[int] = Field(None, description="ถ้าไม่ส่ง ใช้ค่า default")
    stream: Optional[bool] = Field(False, description="ใช้ endpoint /stream แทน")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {"role": "user", "content": "อยากได้หินสีดำสำหรับท็อปครัว งบประมาณไม่เกิน 2500 บาท/ตร.ม. แนะนำหน่อย"}
                    ],
                    "max_tokens": 1024,
                },
                {
                    "messages": [
                        {"role": "user", "content": "มีหินแกรนิตสีขาวอะไรบ้าง"}
                    ],
                },
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "รูปนี้เป็นหินชนิดไหน อธิบายและแนะนำหินใกล้เคียงจากรายการ"},
                                {"type": "image_url", "image_url": {"url": "https://example.com/stone.jpg"}},
                            ],
                        }
                    ],
                    "max_tokens": 1024,
                },
            ]
        }
    }


# ---------------------------------------------------------------------------
# แปลง ChatMessage (รูปแบบ OpenAI-style) -> google.genai.types.Content
# ---------------------------------------------------------------------------

def _image_part_from_url(url: str) -> Optional[genai_types.Part]:
    """โหลดรูปจาก URL (หรือ data: URI) แล้วแปลงเป็น genai Part สำหรับ vision"""
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
    """
    แปลง messages แบบ OpenAI-style เป็น (system_instruction, contents) สำหรับ google-genai SDK
    system message ทั้งหมดถูกรวมเป็น system_instruction เดียว
    user/assistant กลายเป็น Content(role="user"/"model", parts=[...])
    """
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


def _build_system_instruction(messages: List[ChatMessage]) -> tuple:
    """ใส่ context รายการหินรวมกับ system message อื่นๆ (ถ้ามี) แล้วแปลงเป็น genai contents"""
    products_context = _load_products_context()
    system_instruction, contents = _messages_to_genai(messages)
    if products_context:
        system_instruction = (
            f"{system_instruction}\n\n{products_context}" if system_instruction else products_context
        )
    return system_instruction, contents


# ---------------------------------------------------------------------------
# Schema สำหรับทดลอง: GET /chat/schema
# ---------------------------------------------------------------------------

CHAT_SCHEMA_EXAMPLES = {
    "request_schema": {
        "messages": [
            {"role": "user", "content": "ข้อความจากลูกค้า"}
        ],
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
            "body": {
                "messages": [{"role": "user", "content": "มีหินแกรนิตสีขาวอะไรบ้าง"}],
            },
        },
        {
            "name": "ข้อความ + รูป (vision)",
            "body": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "รูปนี้เป็นหินชนิดไหน แนะนำหินใกล้เคียงจากรายการ"},
                            {"type": "image_url", "image_url": {"url": "https://example.com/stone.jpg"}},
                        ],
                    }
                ],
                "max_tokens": 1024,
            },
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
# Non-streaming: POST /chat/completions
# ---------------------------------------------------------------------------

@router.post("/completions")
def chat_completions(request: ChatCompletionsRequest):
    """
    ส่งข้อความ (และ optional รูปภาพ) ไปที่ Gemini ได้คำตอบแบบเต็มครั้งเดียว
    มี context รายการหิน (ชื่อ, รายละเอียด, ราคา) ให้ LLM แนะนำหินให้ลูกค้า
    """
    client = _get_client()
    model = request.model or CHAT_MODEL
    max_tokens = request.max_tokens or MAX_TOKENS
    system_instruction, contents = _build_system_instruction(request.messages)

    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
            ),
        )
    except Exception as e:
        logger.exception("Gemini chat error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))

    content = response.text or ""
    usage = getattr(response, "usage_metadata", None)
    return {
        "content": content,
        "role": "assistant",
        "products": _find_mentioned_products(content),
        "usage": {
            "prompt_tokens": getattr(usage, "prompt_token_count", None) if usage else None,
            "completion_tokens": getattr(usage, "candidates_token_count", None) if usage else None,
            "total_tokens": getattr(usage, "total_token_count", None) if usage else None,
        },
    }


# ---------------------------------------------------------------------------
# Streaming: POST /chat/completions/stream (SSE)
# ---------------------------------------------------------------------------

def _stream_events(messages: List[ChatMessage], model: str, max_tokens: int):
    """
    Generator ส่ง SSE chunks จาก Gemini stream

    สำคัญ: ต้อง try/except ทั้งหมด "ในนี้" (ไม่ใช่รอบๆ StreamingResponse ที่ route ด้านล่าง)
    เพราะ generator นี้จะถูกเรียกจริงหลังจาก HTTP headers (200, text/event-stream) ถูกส่งไปแล้ว
    ถ้า error หลุดออกจาก generator โดยไม่ถูกจับ ฝั่ง browser จะเห็นแค่ "network error" ไม่เห็น
    ข้อความ error จริง — ดักไว้ในนี้แล้วส่งเป็น SSE event พิเศษ {"error": "..."} แทน
    """
    try:
        client = _get_client()
        system_instruction, contents = _build_system_instruction(messages)
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
            ),
        )
        full_text = ""
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                full_text += text
                data = json.dumps({"content": text})
                yield f"data: {data}\n\n"

        # หลังตอบจบแล้ว ค่อยจับคู่ว่าพูดถึงหินชนิดไหนบ้าง แล้วส่งรูปประกอบเป็น event สุดท้าย
        # (ต้องรอข้อความเต็มก่อน เพราะชื่อหินอาจถูกตัดขาดกลางคันถ้าเช็คทีละ chunk)
        products = _find_mentioned_products(full_text)
        if products:
            yield f"data: {json.dumps({'products': products})}\n\n"
    except HTTPException as e:
        logger.exception("Gemini stream error (HTTPException): %s", e.detail)
        yield f"data: {json.dumps({'error': str(e.detail)})}\n\n"
    except Exception as e:
        logger.exception("Gemini stream error: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


@router.post("/completions/stream")
def chat_completions_stream(request: ChatCompletionsRequest):
    """
    Chatbot แบบ streaming (SSE): คืนข้อความทีละส่วน
    มี context รายการหิน (ชื่อ, รายละเอียด, ราคา) ให้ LLM แนะนำหินให้ลูกค้า
    """
    model = request.model or CHAT_MODEL
    max_tokens = request.max_tokens or MAX_TOKENS

    return StreamingResponse(
        _stream_events(request.messages, model, max_tokens),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
