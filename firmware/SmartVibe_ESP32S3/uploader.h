// ทุกอย่างที่คุยกับ Firebase อยู่ที่นี่ ไฟล์อื่นจะได้ไม่ต้องรู้จัก
#pragma once
#include <Arduino.h>
#include "types.h"

// ต่อ WiFi + Firebase เรียกหลัง timebaseBegin()
bool uploaderBegin();

// ส่ง 1 batch ถ้าพลาดจะพิมพ์บอกว่าเพราะอะไร
bool uploaderSendBatch(const Batch_t &b);

// ลบของเก่ากว่า KEEP_SECONDS — เช็คผลทุกครั้ง เคยลบพลาดแล้วไม่มีใครรู้
void uploaderCleanup();

// heartbeat ไว้แยกปัญหาตอน Serial ขึ้น OK แต่ Firebase ไม่มีข้อมูล
//   server_ts ไม่ขยับ = บอร์ดส่งไม่ถึงจริง · ขยับ = ปัญหาอยู่ฝั่งเว็บ
void uploaderHeartbeat();

// เช็ค WiFi/RSSI/heap ผิดปกติก็ซ่อมตัวเอง
void uploaderWatchdog();

extern Stats_t g_stats;
