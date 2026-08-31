#include "tasks.h"
#include "config.h"
#include "types.h"
#include "sensors.h"
#include "timebase.h"
#include "uploader.h"

static QueueHandle_t batchQueue = nullptr;

// คอร์ 1 — อ่านเซ็นเซอร์ที่ 50 Hz
static void samplerTask(void *pv) {
  Batch_t buf;
  buf.n = 0;
  uint64_t prevKey = 0;
  TickType_t lastWake = xTaskGetTickCount();
  const TickType_t period = pdMS_TO_TICKS(KEY_STEP_MS);

  for (;;) {
    vTaskDelayUntil(&lastWake, period);   // นอนจนถึงจังหวะถัดไปพอดี

    Sample_t s;
    if (!sensorsRead(s)) continue;

    s.epoch_ms = quantize(epochMillis());
    // กันคีย์ชนตอนสองรอบตกในช่อง 20 ms เดียวกัน
    if (s.epoch_ms <= prevKey) s.epoch_ms = prevKey + KEY_STEP_MS;
    prevKey = s.epoch_ms;

    buf.s[buf.n++] = s;

    if (buf.n >= BATCH_SIZE) {
      // คิวเต็มก็ทิ้ง ดีกว่ารอแล้วจังหวะการอ่านเสีย
      if (xQueueSend(batchQueue, &buf, 0) != pdTRUE) g_stats.dropped += buf.n;
      buf.n = 0;
    }
  }
}

// คอร์ 0 — ส่งข้อมูล + cleanup / heartbeat / watchdog
static void uploaderTask(void *pv) {
  Batch_t buf;
  uint32_t lastCleanup = 0, lastHb = 0, lastWd = 0;

  for (;;) {
    if (xQueueReceive(batchQueue, &buf, pdMS_TO_TICKS(200)) == pdTRUE) {
      uploaderSendBatch(buf);
    }

    uint32_t now = millis();
    if (now - lastCleanup >= CLEANUP_EVERY_MS) { lastCleanup = now; uploaderCleanup();  }
    if (now - lastHb      >= HEARTBEAT_MS)     { lastHb      = now; uploaderHeartbeat();}
    if (now - lastWd      >= WATCHDOG_MS)      { lastWd      = now; uploaderWatchdog(); }
  }
}

bool tasksBegin() {
  batchQueue = xQueueCreate(QUEUE_DEPTH, sizeof(Batch_t));
  if (!batchQueue) { Serial.println("❌ สร้างคิวไม่สำเร็จ"); return false; }

  xTaskCreatePinnedToCore(samplerTask,  "sampler",   6144, NULL, 3, NULL, 1);
  xTaskCreatePinnedToCore(uploaderTask, "uploader", 12288, NULL, 2, NULL, 0);
  return true;
}
