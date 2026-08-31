"""สูตร Health และตัวคุมการเปลี่ยนสี"""
import numpy as np

from smartvibe.config import MIN_CONSEC, Thresholds


def health_from_fn(fn_now, fn_base):
    """% ความแข็งเกร็งที่เหลือ

    fn ∝ √(k/m) → k/k₀ = (fn/fn₀)²
    ใช้ได้เฉพาะตอนกระตุ้นแบบกว้าง ถ้าเป็นลำโพงความถี่เดียวค่านี้ไม่มีความหมาย
    """
    if not fn_now or not fn_base:
        return None
    return float(np.clip((fn_now / fn_base) ** 2 * 100.0, 0.0, 130.0))


def similarity_pct(now, base):
    """สองค่านี้เหมือนกันกี่ % — เพิ่มหรือลดก็ตกเท่ากัน"""
    if base is None or now is None or base <= 0 or now <= 0:
        return None
    return float(100.0 * min(now, base) / max(now, base))


def next_status(status: str, consec: int, direction, pct: float, th: Thresholds):
    """คืน (สีใหม่, นับได้กี่รอบ, ทิศทาง) — ต้องติดกันครบ MIN_CONSEC ถึงเปลี่ยนสี"""
    if status == "green":
        consec = consec + 1 if pct < th.g2y else 0
        if consec >= MIN_CONSEC:
            return "yellow", 0, None
        return "green", consec, direction

    if status == "yellow":
        cur = "up" if pct >= th.y2g else ("down" if pct < th.y2r else None)
        if cur != direction:            # เปลี่ยนทิศ = เริ่มนับใหม่
            consec = 0
        if cur is None:
            return "yellow", 0, None
        consec += 1
        if consec >= MIN_CONSEC:
            return ("green" if cur == "up" else "red"), 0, None
        return "yellow", consec, cur

    consec = consec + 1 if pct >= th.r2y else 0
    if consec >= MIN_CONSEC:
        return "yellow", 0, None
    return "red", consec, direction


def median_filter(history: list, value: float, size: int) -> float:
    """ใส่ค่าใหม่ คืนค่ากลางของ N รอบล่าสุด (แก้ list ที่ส่งเข้ามาเลย)"""
    history.append(value)
    while len(history) > size:
        history.pop(0)
    return float(np.median(history))
