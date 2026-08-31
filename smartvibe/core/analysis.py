"""ท่อหลัก: DataFrame ดิบ → ผลวิเคราะห์ ไม่วาดอะไรทั้งนั้น"""
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from smartvibe import config as C
from smartvibe.core import dsp
from smartvibe.core.damage import health_from_fn, median_filter, similarity_pct


@dataclass
class FloorResult:
    index: int
    fn: Optional[float] = None          # ความถี่ยอด (กรอง median แล้ว)
    sharpness: float = 0.0
    rms: float = 0.0
    amp: Optional[float] = None         # แรงสั่นที่ความถี่อ้างอิง
    wideband: float = 0.0
    f_peak: Optional[float] = None
    df_shift: float = 0.0
    health: Optional[float] = None
    psd: Optional[np.ndarray] = None
    peaks: List[tuple] = field(default_factory=list)   # ยอดเด่น 3 อันดับ


@dataclass
class AnalysisResult:
    fs: float = C.NOMINAL_FS
    freqs: Optional[np.ndarray] = None
    floors: List[FloorResult] = field(default_factory=list)
    active_mode: str = "fn"             # "fn" = กระตุ้นกว้าง, "sine" = ลำโพงความถี่เดียว
    sine_detected: bool = False
    f_drive: Optional[float] = None
    excitation_ok: bool = False
    T21: Optional[float] = None
    T32: Optional[float] = None
    coh21: float = 0.0
    coh32: float = 0.0
    n_points: int = 0
    amp_ratio_hint: str = ""            # คำเตือนตอนรูปทรงการแกว่งผิดปกติ
    other_resonances: List[float] = field(default_factory=list)


def _detect_sine(fns, sharps, fn_hists) -> bool:
    """ยอดคมมาก หรือ 3 ชั้นเห็นความถี่เดียวกันแล้วค่านิ่งผิดปกติ"""
    valid = [f for f in fns if f]
    very_sharp = float(np.median([s for s in sharps if s > 0] or [0])) > C.SINE_SHARP
    same_freq = len(valid) == C.N_FLOORS and (max(valid) - min(valid)) < 0.15
    cvs = [(np.std(h) / (np.mean(h) + 1e-12) * 100) if len(h) >= 3 else 99
           for h in fn_hists]
    frozen = all(c < 0.3 for c in cvs)
    return very_sharp or (same_freq and frozen)


def analyze(df: pd.DataFrame, ss, mode_choice: str, th) -> AnalysisResult:
    """ss = session_state ใช้เก็บ history ของ median filter"""
    res = AnalysisResult(n_points=len(df))
    t_ms = df["uptime_ms"].values.astype(float)
    res.fs = dsp.estimate_fs(t_ms)

    signals, spectra, fns, sharps = [], [], [], []

    # 1) สเปกตรัมของแต่ละชั้น
    for i in range(C.N_FLOORS):
        col = f"AccX_CH{i}"
        fr = FloorResult(index=i)
        if col not in df.columns:
            signals.append(None); spectra.append(None)
            fns.append(None); sharps.append(0.0); res.floors.append(fr)
            continue

        sig = dsp.resample_uniform(t_ms, df[col].values.astype(float), res.fs)
        signals.append(sig)
        fr.rms = float(np.sqrt(np.mean((sig - np.mean(sig)) ** 2)))

        fw, psd = dsp.compute_psd(sig, res.fs)
        if fw is None:
            spectra.append(None); fns.append(None); sharps.append(0.0)
            res.floors.append(fr); continue

        spectra.append((fw, psd))
        if res.freqs is None:
            res.freqs = fw
        fr.psd = psd

        fn_raw, sh = dsp.peak_frequency(fw, psd, fs=res.fs)
        fr.sharpness = sh
        fr.fn = median_filter(ss[f"fn_hist{i}"], fn_raw, C.HISTORY_SIZE) if fn_raw else None
        fr.wideband = dsp.wideband_energy(fw, psd, fs=res.fs)
        fr.peaks = dsp.top_peaks(fw, psd, fs=res.fs)

        fns.append(fr.fn); sharps.append(sh)
        res.floors.append(fr)

    # 2) เลือกโหมด
    res.sine_detected = _detect_sine(
        fns, sharps, [ss[f"fn_hist{i}"] for i in range(C.N_FLOORS)])
    if mode_choice.startswith("อัตโนมัติ"):
        res.active_mode = "sine" if res.sine_detected else "fn"
    elif mode_choice.startswith("ติดตาม"):
        res.active_mode = "fn"
    else:
        res.active_mode = "sine"

    # ความถี่อ้างอิง = median ของยอดที่แต่ละชั้นหาได้
    # เคยลองวิธีพับฮาร์มอนิกกลับลงมาแล้วอันตรายกว่า ชั้นเดียวจับยอดหลอกก็ลากทั้งระบบไปด้วย
    valid_fns = [f for f in fns if f]
    res.f_drive = float(np.median(valid_fns)) if valid_fns else None
    res.excitation_ok = all(f.rms >= th.rms_min for f in res.floors)

    # 3) แอมพลิจูดที่ความถี่อ้างอิง
    for i, fr in enumerate(res.floors):
        if spectra[i] is None:
            continue
        fw, psd = spectra[i]

        if res.active_mode == "sine":
            center = res.f_drive                      # อ่านที่ความถี่ลำโพง
        else:
            center = ss.get(f"base_fn{i}") or fr.fn   # ตามยอดรอบ baseline ของชั้นนั้น
            if center:
                f_pk, _, shift = dsp.tracked_peak(fw, psd, center)
                fr.f_peak, fr.df_shift = f_pk, shift

        if center:
            a_raw = dsp.band_rms(fw, psd, center - 0.5, center + 0.5)
            fr.amp = median_filter(ss[f"amp_hist{i}"], a_raw, C.HISTORY_SIZE)

    # 4) ตึกขยายการสั่นพอหรือยัง — ปกติชั้นบนต้องแรงกว่าชั้นล่างเป็นขั้นบันได
    amps = [f.amp for f in res.floors]
    if all(a for a in amps):
        top_ratio = amps[-1] / amps[0]
        if amps[1] < min(amps[0], amps[2]) * 0.95:
            # ชั้นกลางนิ่งกว่าทั้งบนและล่าง = อยู่ใกล้จุดโหนด แปลว่าไม่ใช่โหมดที่ 1
            res.amp_ratio_hint = (
                f"ชั้นกลางแกว่งน้อยกว่าทั้งชั้นบนและชั้นล่าง "
                f"({amps[0]:.4f} / {amps[1]:.4f} / {amps[2]:.4f}) "
                "— แปลว่าชั้น 2 อยู่ใกล้จุดโหนดของโหมดการสั่นที่ถูกกระตุ้นอยู่ "
                "ความถี่นี้ไม่ใช่โหมดที่ 1 ไม่ควรใช้ล็อก baseline")
        elif top_ratio < 1.25:
            res.amp_ratio_hint = (
                f"ชั้นบนสุดแกว่งแรงกว่าชั้นล่างเพียง {top_ratio:.2f} เท่า "
                "— ตึกยังแทบไม่ขยายการสั่น มักเกิดจากกระตุ้นที่ความถี่ห่างจาก "
                "ความถี่ธรรมชาติมาก ควรปรับความถี่เข้าใกล้เรโซแนนซ์ หรือเปลี่ยนเป็นการเคาะ")

    # 5) ความถี่อื่นที่ตึกตอบสนอง ไว้ช่วยหาเรโซแนนซ์
    cand = {}
    for fr in res.floors:
        for f, sharp in fr.peaks:
            if res.f_drive and abs(f - res.f_drive) < 0.8:
                continue                        # ข้ามความถี่ที่กำลังขับอยู่
            key = round(f * 2) / 2               # จับกลุ่มทุก 0.5 Hz
            cand[key] = cand.get(key, 0.0) + sharp
    res.other_resonances = [f for f, _ in
                            sorted(cand.items(), key=lambda kv: -kv[1])[:3]]

    # 6) Transmissibility (เฉพาะโหมดไซน์)
    if res.active_mode == "sine" and res.f_drive and all(s is not None for s in signals):
        t21, res.coh21 = dsp.transmissibility_h1(signals[0], signals[1], res.fs, res.f_drive)
        t32, res.coh32 = dsp.transmissibility_h1(signals[1], signals[2], res.fs, res.f_drive)
        if t21:
            res.T21 = median_filter(ss["T_hist21"], t21, C.HISTORY_SIZE)
        if t32:
            res.T32 = median_filter(ss["T_hist32"], t32, C.HISTORY_SIZE)

    # 7) Health
    if res.active_mode == "fn":
        for i, fr in enumerate(res.floors):
            fr.health = health_from_fn(fr.fn, ss.get(f"base_fn{i}"))
    else:
        # โหมดไซน์ใช้ชั้น 1 เป็นตัวหาร เลยไม่มี Health ของตัวเอง
        res.floors[1].health = similarity_pct(res.T21, ss.get("base_T21"))
        res.floors[2].health = similarity_pct(res.T32, ss.get("base_T32"))

    return res
