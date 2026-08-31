"""ประมวลผลสัญญาณล้วน ๆ — pytest tests/test_dsp.py"""
import numpy as np
from scipy.signal import coherence, csd, welch

from smartvibe import config as C

try:
    _integrate = np.trapezoid
except AttributeError:          # numpy 1.x
    _integrate = np.trapz


def estimate_fs(t_ms: np.ndarray, nominal: float = C.NOMINAL_FS) -> float:
    """อัตราสุ่มจริงจาก median ของ dt"""
    dt = np.diff(np.asarray(t_ms, dtype=float))
    dt = dt[(dt >= 5) & (dt <= 150)]        # ตัดค่าเพี้ยนทิ้งก่อน
    return float(1000.0 / np.median(dt)) if len(dt) >= 10 else nominal


def resample_uniform(t_ms: np.ndarray, sig: np.ndarray, fs: float) -> np.ndarray:
    """จัดข้อมูลที่มาไม่ตรงจังหวะให้ห่างเท่ากัน (welch สมมติว่าสม่ำเสมอ)"""
    t = (np.asarray(t_ms, float) - t_ms[0]) / 1000.0
    if t[-1] <= 0:
        return np.asarray(sig, float)
    return np.interp(np.arange(0.0, t[-1], 1.0 / fs), t, np.asarray(sig, float))


def compute_psd(sig: np.ndarray, fs: float):
    """Welch PSD — nperseg ต้องคงที่ ไม่งั้นแอมพลิจูดกระโดดเองตอนข้อมูลสั้นยาวไม่เท่ากัน"""
    sig = np.asarray(sig, float)
    n = min(C.NPERSEG, len(sig))
    if n < 64:
        return None, None
    return welch(sig, fs=fs, nperseg=n, noverlap=n // 2,
                 window="hann", detrend="linear", scaling="density")


def band_rms(fw, psd, lo: float, hi: float) -> float:
    """RMS ในย่าน = sqrt(∫PSD df) — ต้องอินทิเกรต ไม่ใช่ sum เพราะ PSD หน่วยเป็น /Hz"""
    m = (fw >= lo) & (fw <= hi)
    if not m.any():
        return 0.0
    return float(np.sqrt(max(_integrate(psd[m], fw[m]), 0.0)))


def _parabolic(fw, psd, idx: int) -> float:
    """ฟิตโค้งผ่าน 3 จุดรอบยอด ให้ละเอียดกว่าความกว้าง bin"""
    if idx <= 0 or idx >= len(psd) - 1:
        return float(fw[idx])
    y0, y1, y2 = (np.log(psd[j] + 1e-20) for j in (idx - 1, idx, idx + 1))
    den = y0 - 2 * y1 + y2
    d = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5)) if abs(den) > 1e-12 else 0.0
    return float(fw[idx] + d * (fw[1] - fw[0]))


def peak_frequency(fw, psd, fs=None, lo=C.SEARCH_LO, hi=C.SEARCH_HI):
    """หายอดสูงสุด คืน (ความถี่, ความคม)"""
    if fs is not None:
        hi = min(hi, fs * 0.45)     # เกินนี้มองไม่เห็น และจะพับกลับมาเป็นยอดปลอม
    m = (fw >= lo) & (fw <= hi)
    if not m.any():
        return None, 0.0
    band = psd[m]
    idx = np.where(m)[0][int(np.argmax(band))]
    sharp = float(psd[idx] / (np.median(band) + 1e-20))
    return _parabolic(fw, psd, idx), sharp


def top_peaks(fw, psd, fs=None, n=3, lo=C.SEARCH_LO, hi=C.SEARCH_HI, min_sep=1.0):
    """ยอดเด่น n อันดับ ห่างกันอย่างน้อย min_sep Hz — ไว้ดูว่ามีฮาร์มอนิกปนไหม"""
    if fs is not None:
        hi = min(hi, fs * 0.45)
    m = (fw >= lo) & (fw <= hi)
    if not m.any():
        return []
    idxs = np.where(m)[0]
    med = float(np.median(psd[idxs])) + 1e-20
    out = []
    for i in idxs[np.argsort(psd[idxs])[::-1]]:
        f = _parabolic(fw, psd, int(i))
        if all(abs(f - g) >= min_sep for g, _ in out):
            out.append((f, float(psd[i] / med)))
        if len(out) >= n:
            break
    return out


def tracked_peak(fw, psd, center, half=C.TRACK_HALF):
    """ตามยอดรอบ center คืน (ความถี่, แรงสั่น, Δf)

    ใช้ได้เฉพาะตอนกระตุ้นแบบกว้าง ถ้าเป็นไซน์นิ่ง ๆ ตึกจะสั่นที่ความถี่ลำโพงอย่างเดียว
    fn จริงไม่โผล่ในสเปกตรัมเลย ฟังก์ชันนี้จะคืนค่าเดิมทุกครั้ง
    """
    if center is None:
        return None, 0.0, 0.0
    m = (fw >= center - half) & (fw <= center + half)
    if not m.any():
        return None, 0.0, 0.0
    idx = np.where(m)[0][int(np.argmax(psd[m]))]
    f_pk = _parabolic(fw, psd, idx)
    df = fw[1] - fw[0]
    amp = band_rms(fw, psd, f_pk - 3 * df, f_pk + 3 * df)
    return f_pk, amp, float(f_pk - center)


def wideband_energy(fw, psd, fs=None, lo=C.SEARCH_LO, hi=C.SEARCH_HI) -> float:
    """พลังงานรวมทั้งย่าน ตัวสำรองเวลาหายอดไม่เจอ"""
    if fs is not None:
        hi = min(hi, fs * 0.45)
    return band_rms(fw, psd, lo, hi)


def transmissibility_h1(sig_in, sig_out, fs, f_center, half=0.5):
    """T = |Sxy/Sxx| คืน (T, coherence) — T เป็น None ถ้า coherence ต่ำกว่าเกณฑ์

    ทนสัญญาณรบกวนกว่าการหารแอมพลิจูดตรง ๆ และได้ coherence มาบอกว่าเชื่อได้ไหม
    """
    n = min(C.NPERSEG, len(sig_in), len(sig_out))
    if n < 64:
        return None, 0.0
    kw = dict(fs=fs, nperseg=n, noverlap=n // 2, window="hann", detrend="linear")
    f, Pxx = welch(sig_in, **kw)
    _, Pxy = csd(sig_in, sig_out, **kw)
    _, Cxy = coherence(sig_in, sig_out, **kw)

    m = (f >= f_center - half) & (f <= f_center + half)
    if not m.any():
        return None, 0.0
    T = float(np.abs(np.sum(Pxy[m]) / (np.sum(Pxx[m]) + 1e-20)))
    coh = float(np.mean(Cxy[m]))
    return (T if coh >= C.COH_MIN else None), coh
