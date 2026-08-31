"""จุดเริ่มต้นของหน้าเว็บ — ประกอบร่างอย่างเดียว ไม่มีสูตรคำนวณ

รัน: streamlit run streamlit_app.py
"""
import json
import time

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from smartvibe import config as C
from smartvibe.core import rules, state
from smartvibe.core.analysis import analyze
from smartvibe.core.buffer import RollingBuffer
from smartvibe.core.firebase_client import FirebaseClient
from smartvibe.services import ai_assistant, telegram
from smartvibe.ui import charts, debug, floors, insight, sidebar, theme

st.set_page_config(page_title="SmartVibe", layout="wide")
theme.inject()
st.title("SmartVibe — เฝ้าระวังโครงสร้างอาคารจากการสั่นสะเทือน")

ss = st.session_state
state.init(ss)

# ต้องอยู่ข้ามรอบรีเฟรช
if "client" not in ss:
    ss.client = FirebaseClient()
    ss.buffer = RollingBuffer()


def run_ai_job() -> bool:
    """ทำงาน AI ที่ค้างคิว ต้องเรียกก่อนอย่างอื่นทั้งหมด

    autorefresh ยิงคำขอ rerun ตามเวลา ถ้าเรียก AI ระหว่างนั้นงานจะถูกตัดกลางคัน
    เลยแยกเป็น กดปุ่ม = จดคิว → รอบถัดไปค่อยถาม (ดู docs/DECISIONS.md)
    """
    job = ss.pop("ai_job", None)
    if not job:
        return False
    kind, provider, payload = job
    slot = "ai_result" if kind == "now" else "ai_trend"
    try:
        if kind == "now":
            ss[slot] = ai_assistant.analyze_cached(
                provider, ai_assistant.hash_of(payload), payload)
        else:
            ss[slot] = ai_assistant.analyze_trend_cached(
                provider, ai_assistant.hash_of(payload), payload)
    except Exception as e:
        ss[slot] = f"⚠️ เรียก AI ไม่สำเร็จ: {type(e).__name__}: {e}"
    return True


def main():
    t0 = time.perf_counter()

    mode, th = sidebar.render(ss.client)

    # 1) ดึงข้อมูล
    df = ss.buffer.extend(ss.client.fetch_new())
    if ss.client.last_error:
        st.sidebar.error(ss.client.last_error)
    if len(df) <= 100:
        st.info("⏳ กำลังรอข้อมูลจากเซ็นเซอร์... "
                f"(ได้ {len(df)} จุด ต้องการมากกว่า 100)")
        return

    # 2) ข้อมูลยังขยับไหม
    stuck = state.update_stuck(ss, df)
    telegram.on_stuck(stuck)
    if stuck >= 4:
        theme.banner("error", "ข้อมูลหยุดนิ่ง อาจเกิดปัญหาบางอย่าง")

    # 3) วิเคราะห์
    result = analyze(df, ss, mode, th)

    if result.sine_detected and result.active_mode == "fn":
        theme.banner("warning",
                     "ตรวจพบการกระตุ้นแบบไซน์ความถี่เดียว แต่โหมดปัจจุบันคือติดตาม fn "
                     "— ค่าที่เห็นคือความถี่ลำโพง ไม่ใช่ของตึก")

    # คำเตือนอื่น ๆ ย้ายไปอยู่ในแผง debug หมด ไม่ให้บังหน้าจอตอนนำเสนอ

    # 4) ปุ่มควบคุม
    c1, c2 = st.columns([2, 1], gap="medium")
    with c1:
        if st.button("🔒  ล็อก Baseline ขณะโครงสร้างสมบูรณ์",
                     type="primary", key="btn_lock", use_container_width=True):
            if state.lock_baseline(ss, result):
                st.rerun()
            else:
                theme.banner("warning",
                             "ยังล็อกไม่ได้ — สัญญาณอ่อน หาพีคไม่เจอ หรือ coherence ต่ำ")
    with c2:
        if st.button("🗑️  ล้างค่าทั้งหมด", key="btn_reset", use_container_width=True):
            state.reset_all(ss)
            st.rerun()

    st.markdown("---")

    # 5) วาดผล
    floors.render(result, ss, th)
    st.markdown("---")
    charts.amplitude_bar(result, ss)
    st.markdown("---")
    charts.spectrum(result)

    # 6) จดค่าไว้ดูแนวโน้ม (ทุก 30 วิ ไม่ใช่ทุกรอบ)
    state.log_health(ss, result)

    # 7) สรุปผล 2 ใบวางคู่กัน
    st.markdown("---")
    col_rule, col_ai = st.columns([1.15, 1], gap="large")

    # ซ้าย: ตัวตัดสินหลัก กฎวิศวกรรมล้วน ๆ ไม่ต้องใช้เน็ต
    with col_rule:
        st.markdown('<div class="sv-h">วิเคราะห์ข้อมูลจากความถี่</div>',
                    unsafe_allow_html=True)
        # พังก็ให้พังอยู่ในกรอบนี้ กราฟกับสถานะรายชั้นจะได้ไม่ตายไปด้วย
        try:
            insight.render(rules.evaluate(result, ss, th))
        except Exception as e:
            theme.banner("error", f"สรุปผลรอบนี้ไม่สำเร็จ ({type(e).__name__}) "
                                  "ส่วนอื่นของหน้าจอยังใช้งานได้ตามปกติ")

    # ขวา: AI เป็นแค่ตัวเสริม
    with col_ai:
        st.markdown('<div class="sv-h">AI วิเคราะห์เบื้องต้น</div>',
                    unsafe_allow_html=True)
        providers = ai_assistant.available_providers()
        provider = st.selectbox("ผู้ให้บริการ", providers, index=0)

        level, msg = ai_assistant.status_line(provider)
        theme.banner(level, msg)

        snap = ai_assistant.snapshot(result, ss)
        n_log = len(ss.get("health_log", []))
        ready = ai_assistant.is_ready(provider)

        pending = ss.get("ai_job")

        b1, b2 = st.columns(2, gap="medium")
        with b1:
            # กดปุ่ม = จดคิวเท่านั้น (ดู run_ai_job)
            if st.button("🔍  วิเคราะห์สถานะตอนนี้", key="btn_ai_now",
                         use_container_width=True,
                         disabled=not ready or bool(pending)):
                ss.ai_job = ("now", provider, snap)
                pending = ss.ai_job
        with b2:
            if st.button(f"📈  วิเคราะห์แนวโน้ม ({n_log} จุด)", key="btn_ai_trend",
                         use_container_width=True,
                         disabled=not ready or bool(pending)):
                ss.ai_job = ("trend", provider,
                             json.dumps(ss["health_log"], ensure_ascii=False))
                pending = ss.ai_job

        if pending:
            theme.banner("info", "กำลังส่งคำถามให้ AI… คำตอบจะขึ้นภายในไม่กี่วินาที")

        if ss.get("ai_result"):
            st.info("**สถานะตอนนี้**\n\n" + ss.ai_result)
        if ss.get("ai_trend"):
            st.warning("**แนวโน้ม**\n\n" + ss.ai_trend)

    st.markdown("---")
    debug.render(result, df, t0, ss.client, stuck)

    # จำเวลาที่ใช้จริงไว้ตั้งจังหวะรีเฟรชรอบหน้า
    ss["last_elapsed_ms"] = (time.perf_counter() - t0) * 1000


# ต้องอยู่ก่อน main() ตอนที่ยังไม่มีคำขอ rerun ค้าง
if run_ai_job():
    st.rerun()

try:
    main()
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดระหว่างประมวลผล: {type(e).__name__}: {e}")
    st.exception(e)
    # ไม่ raise ซ้ำ ให้ autorefresh ข้างล่างยังทำงาน หน้าเว็บจะได้ลองใหม่เอง

# คาบรีเฟรชต้องยาวกว่าเวลาประมวลผลจริงเสมอ ไม่งั้นงานถูกตัดกลางคัน
if ss.get("ai_job"):
    _interval = 300                      # มีคิว AI ค้าง รีบเข้ารอบใหม่
else:
    _interval = max(C.REFRESH_MS, int(ss.get("last_elapsed_ms", 0) * 2))
st_autorefresh(interval=_interval, limit=None, key="smartvibe_autorefresh")
