// อ่าน MPU6050 x3 ผ่าน TCA9548A — ไม่รู้จัก WiFi/Firebase เลย
#pragma once
#include <Arduino.h>
#include "types.h"

// เริ่มต้น + ปรับศูนย์ ~10 วิ ต้องวางบอร์ดนิ่ง
bool sensorsBegin();

// อ่านครบ 3 ชั้นใส่ลง out (ยังไม่ใส่เวลา) คืน false ถ้ารอคิว I2C ไม่ทัน
bool sensorsRead(Sample_t &out, uint32_t timeoutMs = 10);

// ไว้ไล่หาสายหลุด
void sensorsScan();
