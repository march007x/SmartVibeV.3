// เวลา NTP + การตั้งชื่อคีย์
// ใช้ millis() เป็นคีย์ไม่ได้ พอ reboot ค่าย้อนกลับไป 0 แล้วหน้าเว็บดึงแต่ข้อมูลเก่าตลอดกาล
#pragma once
#include <Arduino.h>

// sync NTP คืน false ถ้ารอนานเกินกำหนด
bool timebaseBegin();

// เวลา epoch หน่วย ms
uint64_t epochMillis();

// ปัดลงตัวทีละ 20 ms — ไม่ปัดแล้ว cleanup ที่ไล่เดาคีย์จะเดาไม่ตรงสักตัว
uint64_t quantize(uint64_t ms);

// คีย์ 13 หลัก เติมศูนย์หน้า — ความยาวเท่ากันเสมอ Firebase จะเรียงถูก
String keyOf(uint64_t ms);
