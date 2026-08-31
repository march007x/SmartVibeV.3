"""แจ้งเตือนผ่าน Telegram

หน้าเว็บรีเฟรชทุก 2 วิ ถ้าไม่กันจะยิงซ้ำจนโดนแบน — กัน 3 ชั้น
  1. ยิงตอน "สถานะเปลี่ยน" ไม่ใช่ตอน "สถานะเป็น"
  2. เรื่องเดิมห้ามซ้ำใน 5 นาที
  3. จำที่ระดับ process ไม่ใช่ session (เปิด 3 แท็บจะได้ไม่ยิง 3 ครั้ง)
"""
import time
import requests
import streamlit as st

from smartvibe.config import FLOOR_NAMES, secret

COOLDOWN_SEC    = 300     # เรื่องเดิมห้ามซ้ำใน 5 นาที
HEALTH_DROP_PCT = 15.0    # Health ตกเกินกี่ %
HEALTH_WINDOW_S = 600.0   # ...ภายในกี่วินาที


@st.cache_resource
def _state():
    """state ร่วมทุกแท็บ"""
    return {"last_sent": {}, "prev_status": {}, "health_log": {}, "prev_stuck": False}


def enabled() -> bool:
    return bool(secret("TELEGRAM_TOKEN") and secret("TELEGRAM_CHAT_ID"))


def _send(text: str) -> bool:
    token, chat = secret("TELEGRAM_TOKEN"), secret("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "parse_mode": "HTML"},
            timeout=5)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _fire(event_key: str, text: str, cooldown: float = COOLDOWN_SEC) -> bool:
    """ชั้น 2 — พ้น cooldown แล้วค่อยส่ง"""
    st_ = _state()
    now = time.time()
    if now - st_["last_sent"].get(event_key, 0.0) < cooldown:
        return False
    if _send(text):
        st_["last_sent"][event_key] = now
        return True
    return False


def on_status_change(floor_idx: int, status: str, pct):
    """ชั้น 1 — ส่งเฉพาะตอนสีเปลี่ยนจริง"""
    st_ = _state()
    prev = st_["prev_status"].get(floor_idx)
    st_["prev_status"][floor_idx] = status
    if prev is None or prev == status:
        return

    name = FLOOR_NAMES[floor_idx]
    p = f"{pct:.1f}%" if pct is not None else "—"

    if status == "red":
        _fire(f"red_{floor_idx}",
              f"🔴 <b>เตือนภัย: {name}</b>\n"
              f"สถานะ {prev} → <b>อันตราย</b>\n"
              f"Health เทียบ baseline: <b>{p}</b>\n"
              f"⚠️ ควรหยุดการทดลองและตรวจจุดยึดของชั้นนี้")
    elif status == "yellow" and prev == "green":
        _fire(f"yellow_{floor_idx}",
              f"🟡 <b>เฝ้าระวัง: {name}</b>\nHealth ลดเหลือ <b>{p}</b>")
    elif status == "green" and prev != "green":
        _fire(f"recover_{floor_idx}",
              f"🟢 <b>กลับสู่ปกติ: {name}</b>\nHealth ฟื้นเป็น <b>{p}</b>")


def on_stuck(stuck_counter: int, threshold: int = 4):
    """เตือนตอนข้อมูลนิ่ง และตอนกลับมาปกติ"""
    st_ = _state()
    is_stuck = stuck_counter >= threshold
    was = st_["prev_stuck"]
    st_["prev_stuck"] = is_stuck

    if is_stuck and not was:
        _fire("stuck",
              "🚨 <b>ข้อมูลหยุดนิ่ง</b>\nตรวจสอบตามลำดับ:\n"
              "1. heartbeat/server_ts ใน Firebase ขยับไหม\n"
              "2. WiFi ของ ESP32\n"
              "3. โควตา bandwidth ของ Firebase")
    elif was and not is_stuck:
        _fire("stuck_ok", "✅ <b>ข้อมูลกลับมาแล้ว</b>")


def on_health_sample(floor_idx: int, pct):
    """ชั้น 3 — เตือนตอนค่าร่วงเร็ว แม้สียังไม่ทันเปลี่ยน"""
    if pct is None:
        return
    st_ = _state()
    now = time.time()
    log = st_["health_log"].setdefault(floor_idx, [])
    log.append((now, float(pct)))
    st_["health_log"][floor_idx] = [x for x in log if now - x[0] <= HEALTH_WINDOW_S]
    log = st_["health_log"][floor_idx]
    if len(log) < 5:
        return
    oldest = log[0][1]
    drop = oldest - pct
    if drop >= HEALTH_DROP_PCT:
        _fire(f"drop_{floor_idx}",
              f"📉 <b>Health ร่วงเร็ว: {FLOOR_NAMES[floor_idx]}</b>\n"
              f"{oldest:.1f}% → {pct:.1f}% "
              f"(ลด {drop:.1f}% ใน {HEALTH_WINDOW_S/60:.0f} นาที)")


def test() -> bool:
    """ปุ่มทดสอบใน sidebar"""
    return _send("✅ SmartVibe เชื่อมต่อ Telegram สำเร็จ")
