// โครงสร้างข้อมูลที่ใช้ร่วมกัน
#pragma once
#include <Arduino.h>
#include "config.h"

// 1 จังหวะเวลา อ่านครบ 3 ชั้น
struct Sample_t {
  uint64_t epoch_ms;              // คีย์ใน Firebase ปัดลงตัว 20 ms แล้ว
  float ax[N_FLOORS];
  float ay[N_FLOORS];
  float az[N_FLOORS];
};

// 1 ชุดที่ส่งขึ้นคลาวด์พร้อมกัน
struct Batch_t {
  Sample_t s[BATCH_SIZE];
  uint16_t n;
};

// ตัวนับ ส่งไปกับ heartbeat
struct Stats_t {
  volatile uint32_t sent;      // ส่งสำเร็จกี่ sample
  volatile uint32_t failed;    // ส่งไม่สำเร็จ
  volatile uint32_t dropped;   // ทิ้งเพราะคิวเต็ม
};
