"""ผู้ช่วย AI ไว้เรียบเรียงคำอธิบาย ไม่ใช่ตัวตัดสิน

ห้ามเรียกทุกรอบรีเฟรช โควตาหมดใน 6 นาที — เรียกเฉพาะตอนกดปุ่ม แล้ว cache ไว้
"""
import hashlib
import json
import os

import requests
import streamlit as st

from smartvibe.config import secret

# "key" คือชื่อของคีย์ ไม่ใช่ตัวคีย์ · cloud_ok = ใช้บน Streamlit Cloud ได้ไหม
PROVIDERS = {
    "Groq (แนะนำ — ใช้ตัวนี้)": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": "GROQ_API_KEY",
        "model": "llama-3.3-70b-versatile",
        "fallback_models": ["openai/gpt-oss-120b", "llama-3.1-8b-instant"],
        "cloud_ok": True,
        "note": "ฟรี ~14k req/วัน · latency ต่ำมาก · ใช้บน Streamlit Cloud ได้ "
                "· ขอคีย์ที่ console.groq.com → API Keys",
    },
    "OpenRouter (สำรอง)": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": "OPENROUTER_API_KEY",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "fallback_models": [],
        "cloud_ok": True,
        "note": "โมเดลฟรีหลายตัว แต่โควตาน้อย ~50 req/วัน · ใช้เป็นตัวสำรองเวลา Groq ล่ม",
    },
    "Ollama (รันบนเครื่องตัวเองเท่านั้น)": {
        "url": "http://localhost:11434/v1/chat/completions",
        "key": None,
        "model": "qwen2.5:7b",
        "fallback_models": [],
        "cloud_ok": False,
        "note": "ไม่จำกัดโควตา ออฟไลน์ได้ · ต้อง RAM ≥ 8GB "
                "· ❌ ใช้บน Streamlit Cloud ไม่ได้ เพราะ localhost ของเซิร์ฟเวอร์ไม่ใช่เครื่องคุณ",
    },
}

DEFAULT_PROVIDER = "Groq (แนะนำ — ใช้ตัวนี้)"

SYSTEM_PROMPT = """คุณคือวิศวกรผู้เชี่ยวชาญ Structural Health Monitoring
กำลังช่วยครูฟิสิกส์มัธยมปลายวิเคราะห์อาคารจำลอง 3 ชั้น ติด accelerometer
MPU-6050 ชั้นละ 1 ตัว

หลักการที่ต้องยึด:
- fn ∝ sqrt(k/m) → stiffness k ลด ทำให้ fn ลด
- Health = (fn/fn₀)² x 100 = % ของ stiffness ที่เหลืออยู่
- ถ้ากระตุ้นด้วย sine ความถี่เดียวคงที่ แล้วแอมพลิจูดลดลง แปลว่าพีค
  เรโซแนนซ์เลื่อนหนีจากความถี่ลำโพง ไม่ได้แปลว่าแข็งแรงขึ้น และบอก
  ทิศทางไม่ได้ (คลายน็อตหรือขันแน่นก็ทำให้ลดลงทั้งคู่)
- Transmissibility เปลี่ยน = ความเสียหายอยู่ที่จุดต่อระหว่างชั้นนั้น
- coherence ต่ำ = ข้อมูลไม่น่าเชื่อ อย่าเพิ่งสรุป

ตอบภาษาไทย กระชับ ไม่เกิน 5 บรรทัด ใช้ภาษาที่นักเรียน ม.ปลาย เข้าใจ
ถ้าข้อมูลไม่พอ ให้บอกตรง ๆ ว่าต้องเก็บอะไรเพิ่ม"""


def is_cloud() -> bool:
    """รันบน Streamlit Cloud อยู่ไหม (ดูจาก /mount/src)"""
    return os.path.isdir("/mount/src") or bool(os.environ.get("STREAMLIT_SHARING_MODE"))


def available_providers() -> list:
    """โชว์เฉพาะที่ใช้ได้จริง ไม่งั้น Ollama จะโผล่บนคลาวด์แล้วกดเจอ error งง ๆ"""
    if is_cloud():
        return [k for k, v in PROVIDERS.items() if v["cloud_ok"]]
    return list(PROVIDERS.keys())


def is_ready(provider: str) -> bool:
    """ตั้ง API key ครบหรือยัง"""
    cfg = PROVIDERS[provider]
    return True if cfg["key"] is None else bool(secret(cfg["key"]))


def status_line(provider: str) -> tuple:
    """คืน (ระดับ, ข้อความ) ไว้โชว์บนหน้าเว็บ"""
    cfg = PROVIDERS[provider]
    if cfg["key"] is None:
        if is_cloud():
            return "error", "ตัวเลือกนี้ใช้บนคลาวด์ไม่ได้ — เลือก Groq แทน"
        return "info", "ต้องสั่ง ollama serve บนเครื่องนี้ก่อนจึงจะใช้ได้"
    if not secret(cfg["key"]):
        return "warning", (f"ยังไม่ได้ตั้งค่า {cfg['key']} "
                           "— ใส่ใน Settings → Secrets ก่อนใช้งาน")
    return "success", "AI พร้อมใช้งานแล้ว"


def _post(url: str, headers: dict, model: str, messages: list, temperature: float):
    return requests.post(url, headers=headers, timeout=30,
                         json={"model": model, "messages": messages,
                               "temperature": temperature, "max_tokens": 700})


def chat(provider: str, messages: list, temperature: float = 0.3) -> str:
    cfg = PROVIDERS[provider]
    headers = {"Content-Type": "application/json"}
    if cfg["key"]:
        api_key = secret(cfg["key"])
        if not api_key:
            return (f"⚠️ ยังไม่ได้ตั้ง {cfg['key']}\n\n"
                    "• รันบนเครื่อง → ใส่ใน `dashboard/.streamlit/secrets.toml`\n"
                    "• Streamlit Cloud → Settings → Secrets")
        headers["Authorization"] = f"Bearer {api_key}"

    # ลองตัวหลักก่อน ถ้าโมเดลถูกปลดระวางค่อยไล่ตัวสำรอง
    models = [cfg["model"]] + list(cfg.get("fallback_models") or [])
    last_msg = ""

    for i, model in enumerate(models):
        try:
            r = _post(cfg["url"], headers, model, messages, temperature)
        except requests.RequestException as e:
            if "localhost" in cfg["url"]:
                return ("⚠️ ต่อ Ollama ไม่ได้ — สั่ง `ollama serve` และ "
                        "`ollama pull qwen2.5:7b` ก่อน "
                        "(ถ้าอยู่บน Streamlit Cloud ให้เปลี่ยนไปใช้ Groq)")
            return f"⚠️ เชื่อมต่อไม่สำเร็จ: {e}"

        if r.status_code == 200:
            try:
                out = r.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError):
                return "⚠️ อ่านคำตอบไม่ได้ — รูปแบบ response ผิดคาด"
            if i > 0:
                out = f"_(โมเดลหลักใช้ไม่ได้ สลับไปใช้ `{model}` แทน)_\n\n{out}"
            return out

        # โมเดลไม่มีแล้ว ลองตัวถัดไป
        if r.status_code in (400, 404) and i < len(models) - 1:
            last_msg = f"โมเดล `{model}` ใช้ไม่ได้ (HTTP {r.status_code})"
            continue

        msgs = {
            401: "⚠️ API key ไม่ถูกต้อง (401) — ตรวจว่าคัดลอกครบและไม่มีช่องว่างท้าย",
            403: "⚠️ 403 — ยังไม่ได้เปิด API ในโปรเจกต์ หรือ region ไม่รองรับ",
            429: "⚠️ โควตาหมดชั่วคราว (429) รอสักครู่ หรือสลับผู้ให้บริการ",
        }
        if r.status_code in msgs:
            return msgs[r.status_code]
        return f"⚠️ HTTP {r.status_code}: {r.text[:200]}"

    return f"⚠️ ลองครบทุกโมเดลแล้วไม่สำเร็จ ({last_msg})"


def snapshot(result, ss) -> str:
    """รวบสถานะตอนนี้เป็น JSON ก้อนเดียวส่งให้ AI"""
    return json.dumps({
        "โหมด": result.active_mode,
        "fs_Hz": round(result.fs, 2),
        "f_drive_Hz": round(result.f_drive, 3) if result.f_drive else None,
        "fn_ปัจจุบัน": [round(f.fn, 3) if f.fn else None for f in result.floors],
        "fn_baseline": [ss.get(f"base_fn{i}") for i in range(3)],
        "health_pct": [round(f.health, 1) if f.health else None for f in result.floors],
        "สถานะ": [ss.get(f"status{i}") for i in range(3)],
        "RMS": [round(f.rms, 5) for f in result.floors],
        "แอมพลิจูด": [round(f.amp, 5) if f.amp else None for f in result.floors],
        "T21": round(result.T21, 4) if result.T21 else None,
        "T32": round(result.T32, 4) if result.T32 else None,
        "coherence": [round(result.coh21, 2), round(result.coh32, 2)],
        "แรงกระตุ้นพอ": result.excitation_ok,
    }, ensure_ascii=False, indent=1)


@st.cache_data(ttl=300, show_spinner=False)
def analyze_cached(provider: str, snap_hash: str, snap: str) -> str:
    """สถานะเหมือนเดิม = ใช้คำตอบเดิม ไม่ยิงซ้ำ"""
    return chat(provider, [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"ข้อมูลล่าสุด:\n{snap}\n\nสรุปให้: "
            "(1) ตอนนี้โครงสร้างเป็นอย่างไร "
            "(2) ชั้นไหนน่าห่วงที่สุดและเพราะอะไร "
            "(3) ควรทำอะไรต่อ"}])


def hash_of(snap: str) -> str:
    return hashlib.md5(snap.encode()).hexdigest()[:12]


def analyze_trend(history: list, provider: str) -> str:
    """ดูว่าค่าไหลลงเรื่อย ๆ ไหม (history มาจาก state.log_health)"""
    if len(history) < 6:
        need = 6 - len(history)
        return (f"ข้อมูลย้อนหลังยังน้อยเกินไป (มี {len(history)} จุด ต้องการ 6) — "
                f"เก็บอีกประมาณ {need * 30 // 60 + 1} นาทีแล้วลองใหม่")

    return chat(provider, [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content":
            f"ข้อมูลย้อนหลัง (เก็บทุก ~30 วินาที, t = วินาทีนับจากเริ่มบันทึก):\n"
            f"{json.dumps(history[-40:], ensure_ascii=False)}\n\n"
            "Health มีแนวโน้มลดลงต่อเนื่องไหม ถ้าลด ประเมินว่าอีกกี่นาทีจะแตะ "
            "เกณฑ์อันตราย (70%) และบอกระดับความมั่นใจด้วย"}], temperature=0.2)


@st.cache_data(ttl=120, show_spinner=False)
def analyze_trend_cached(provider: str, hist_hash: str, history_json: str) -> str:
    """กันกดปุ่มรัว ๆ เผาโควตา"""
    return analyze_trend(json.loads(history_json), provider)
