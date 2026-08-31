# SmartVibe

เฝ้าระวังความเสียหายโครงสร้างอาคารจำลอง 3 ชั้น จากการเปลี่ยนแปลงของความถี่ธรรมชาติ
และอัตราส่วนการสั่นระหว่างชั้น ใช้เซ็นเซอร์ราคาหลักร้อยต่อจุด

## โครงสร้าง

```
streamlit_app.py     จุดเริ่มต้น ประกอบร่างอย่างเดียว
requirements.txt     ต้องอยู่ที่รากเท่านั้น (Streamlit Cloud อ่านจากที่นี่)

smartvibe/
├── config.py        ค่าตั้งต้นทั้งหมด
├── core/            สมอง ห้าม import streamlit จะได้เทสต์ได้
│   ├── dsp.py           ประมวลผลสัญญาณ
│   ├── damage.py        สูตร Health + เครื่องสถานะ
│   ├── analysis.py      ท่อหลัก ข้อมูลดิบ → ผลวิเคราะห์
│   ├── rules.py         ตัวตัดสินหลัก กฎวิศวกรรมล้วน ๆ
│   ├── buffer.py        ถังเก็บข้อมูลล่าสุด
│   ├── firebase_client.py
│   └── state.py         ค่าที่จำข้ามรอบรีเฟรช
├── services/        ของเสริม ถอดออกได้ (AI, Telegram)
└── ui/              วาดอย่างเดียว ห้ามคำนวณ

firmware/   ESP32-S3
tests/      pytest
docs/       SETUP.md (คู่มือติดตั้ง) · DECISIONS.md (ทำไมถึงเขียนแบบนี้)
```

## กฎ 3 ข้อ

1. `core/` ห้าม import streamlit
2. `ui/` ห้ามคำนวณ — เปลี่ยนสีแก้แค่ `theme.py`
3. ลูกศรพึ่งพาชี้ทางเดียว `ui → core` ไม่มีย้อนกลับ

## เริ่มใช้

```bash
pip install -r requirements-dev.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # แล้วกรอกค่าจริง
streamlit run streamlit_app.py
pytest
```

## ความลับ

คีย์ทั้งหมดอยู่นอก repo เสมอ — บนเครื่องอยู่ใน `.streamlit/secrets.toml`
บนคลาวด์อยู่ในหน้า Settings → Secrets ฝั่งบอร์ดอยู่ใน `firmware/.../secrets.h`
ทั้งสามไฟล์อยู่ใน `.gitignore` แล้ว

ในโค้ดเห็นแค่ *ชื่อ* ของคีย์ เช่น `"GROQ_API_KEY"` ตัวจริงหยิบมาตอนรันด้วย `config.secret()`
