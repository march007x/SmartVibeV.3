// ค่าคงที่ทั้งหมด แก้ที่นี่ที่เดียว (ไม่มีความลับในไฟล์นี้)
#pragma once

// ---------- Firebase ----------
// DB_PATH ต้องตรงกับใน smartvibe/config.py เป๊ะ ๆ ไม่งั้นข้อมูลไม่มาถึงหน้าเว็บ
#define DB_PATH    "/History3F"
#define META_PATH  "/History3F_meta"

// ---------- ขา I2C (ESP32-S3) ----------
#define I2C_SDA      8
#define I2C_SCL      9
#define TCA_ADDR     0x70
#define I2C_FREQ     400000

// เซ็นเซอร์แต่ละชั้นอยู่ช่องไหนของ TCA
#define CH_FLOOR1    0
#define CH_FLOOR2    1
#define CH_FLOOR3    2
#define N_FLOORS     3

// ---------- อัตราการสุ่มตัวอย่าง ----------
#define SAMPLE_HZ    50
#define KEY_STEP_MS  (1000 / SAMPLE_HZ)   // 20 ms ใช้เป็นระยะห่างคีย์ด้วย

// ---------- การส่งข้อมูล ----------
#define BATCH_SIZE   25    // ครบ 25 จุด (0.5 วิ) ค่อยส่งทีเดียว
#define QUEUE_DEPTH  8     // พักได้ 8 ชุด เผื่อเน็ตหน่วง

// หน้าเว็บใช้แค่แกน X ส่ง Y/Z ไปก็ทิ้งเปล่า แถมกินโควตา 3 เท่า
// เปลี่ยนแล้วต้องแฟลชใหม่ หน้าเว็บรองรับทั้งสองแบบ
#define SEND_ALL_AXES  false

// ---------- การลบข้อมูลเก่า ----------
#define ENABLE_AUTO_CLEANUP  true
#define KEEP_SECONDS         60UL     // เก่ากว่านี้ลบทิ้ง
#define CLEANUP_EVERY_MS     15000UL
#define CLEANUP_CHUNK        200      // ลบครั้งละไม่เกินกี่คีย์

// ---------- คาบงานประจำ ----------
#define HEARTBEAT_MS   5000UL
#define WATCHDOG_MS    10000UL
#define NVS_WRITE_MS   300000UL   // เขียน NVS ทุก 5 นาที เขียนบ่อยไปแฟลชพัง

// ---------- เกณฑ์ watchdog ----------
#define RSSI_MIN       -85
#define HEAP_MIN       30000

// ---------- NTP ----------
#define NTP_SERVER1    "pool.ntp.org"
#define NTP_SERVER2    "time.nist.gov"
#define GMT_OFFSET_SEC (7 * 3600)
#define DST_OFFSET_SEC 0
#define NTP_TIMEOUT_MS 20000
