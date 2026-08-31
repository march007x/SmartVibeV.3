"""ค่าตั้งต้นทั้งหมด แก้ที่นี่ที่เดียว (ความลับอยู่ใน .streamlit/secrets.toml)"""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
_SECRETS_FILE = ROOT / ".streamlit" / "secrets.toml"


@lru_cache(maxsize=1)
def _file_secrets() -> dict:
    # อ่านเอง เผื่อ streamlit หาไฟล์ไม่เจอเพราะสั่งรันจากคนละโฟลเดอร์
    if not _SECRETS_FILE.exists():
        return {}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib          # python 3.10
        return tomllib.loads(_SECRETS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def secret(key: str, default: str = "") -> str:
    """หาค่าลับจาก 4 ที่: st.secrets → ไฟล์ → env var → default"""
    try:
        val = st.secrets.get(key, None)      # st.secrets โยน error ถ้าไม่มีไฟล์เลย
        if val not in (None, ""):
            return str(val)
    except Exception:
        pass

    val = _file_secrets().get(key)
    if val not in (None, ""):
        return str(val)

    return os.environ.get(key, default)


# ---------- Firebase ----------
FIREBASE_DOMAIN = secret("FIREBASE_DOMAIN")
FIREBASE_TOKEN = secret("FIREBASE_TOKEN")
DB_PATH = "History3F"        # ต้องตรงกับในเฟิร์มแวร์เป๊ะ ๆ
META_PATH = "History3F_meta"

# ---------- ดึงข้อมูล ----------
BUFFER_SIZE = 900     # 18 วิ ที่ 50 Hz
FIRST_FETCH = 600     # ครั้งแรกดึงเท่านี้
INCR_LIMIT = 400      # ครั้งต่อไปเอาแค่ของใหม่
REFRESH_MS = 2200     # ต้องมากกว่าเวลาประมวลผลจริง (~1250 ms) ไม่งั้นงานถูกตัดกลางคัน
HTTP_TIMEOUT = 3.0

# ---------- ประมวลผลสัญญาณ ----------
NPERSEG = 512         # ต้องคงที่ ถ้าแปรตามจำนวนข้อมูล แอมพลิจูดจะกระโดดเอง
NOMINAL_FS = 50.0
SEARCH_LO = 2.0
SEARCH_HI = 24.0      # ถูกบีบไม่เกิน 0.45*fs อีกชั้นใน dsp
TRACK_HALF = 2.0
COH_MIN = 0.75        # ต่ำกว่านี้ = ไม่เอามาคำนวณ

# ---------- ตรรกะสถานะ ----------
HISTORY_SIZE = 7
MIN_CONSEC = 3        # ต้องเข้าเงื่อนไขติดกันกี่รอบถึงเปลี่ยนสี กันกระพริบ
SINE_SHARP = 40       # คมเกินนี้ = น่าจะโดนลำโพงความถี่เดียว

FLOOR_NAMES = ["ชั้น 1", "ชั้น 2", "ชั้น 3"]
N_FLOORS = 3

# ---------- ประวัติไว้ดูแนวโน้ม ----------
TREND_SAMPLE_SEC = 30    # จดทุก 30 วิ ไม่ใช่ทุกรอบรีเฟรช
TREND_MAX_POINTS = 240   # ≈ 2 ชั่วโมง


@dataclass
class Thresholds:
    """เกณฑ์เปลี่ยนสี ปรับได้จาก sidebar"""
    g2y: float = 90.0        # เขียว → เหลือง
    y2r: float = 70.0        # เหลือง → แดง
    y2g: float = 94.0        # ขาฟื้น ตั้งสูงกว่าขาลงกันกระพริบ
    r2y: float = 75.0
    rms_min: float = 0.010   # ต่ำกว่านี้ = เขย่าไม่แรงพอ
