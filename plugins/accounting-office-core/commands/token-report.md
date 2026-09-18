---
description: รายงานการใช้ token และต้นทุน (USD/บาท) ของ Claude Code — ราย session, ราย turn, ราย skill หรือขนาดไฟล์ prompt
argument-hint: [session|skills|prompt] [ตัวเลือกเพิ่มเติม เช่น --since 2026-09-01 --fx 32.5]
---

# รายงานการใช้ token และต้นทุน

ใช้ skill `token-meter` — ทำตามขั้นตอนใน SKILL.md

สิ่งที่ผู้ใช้ระบุ: `$ARGUMENTS`

## เลือกสคริปต์ตามคำถาม

| ผู้ใช้อยากรู้ | รัน |
|---|---|
| session/โปรเจกต์นี้ใช้ไปเท่าไร, งานไหนกินเยอะ | `scripts/session_usage.py` |
| skill แต่ละตัวกิน context เท่าไร | `scripts/skill_footprint.py` |
| prompt / CLAUDE.md / system prompt ยาวกี่ token | `scripts/count_prompt.py` |

ทุกสคริปต์อยู่ที่ `${CLAUDE_PLUGIN_ROOT}/skills/token-meter/scripts/` — เรียกด้วย path เต็ม เช่น

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/token-meter/scripts/session_usage.py" --turns
python3 "${CLAUDE_PLUGIN_ROOT}/skills/token-meter/scripts/skill_footprint.py" "${CLAUDE_PLUGIN_ROOT}/skills"
```

ถ้าไม่ได้ระบุอะไรมา → รัน `session_usage.py` ของ session ล่าสุด

## ก่อนเริ่ม
1. ถ้าผู้ใช้อยากได้ตัวเลขเป็น **บาท** → ถามอัตราแลกเปลี่ยนที่จะใช้ก่อน แล้วส่งผ่าน `--fx` และบอกในรายงานว่าใช้อัตราเท่าไร
2. ไม่มี `ANTHROPIC_API_KEY` → `skill_footprint.py` / `count_prompt.py` จะเป็น **ค่าประมาณ (±30%)** ต้องบอกผู้ใช้ทุกครั้ง
3. `session_usage.py` อ่านจาก transcript จริง จึงเป็นตัวเลขจาก API ไม่ใช่ค่าประมาณ

## ข้อห้าม
- **ห้ามบอกว่านี่คือเงินที่ผู้ใช้จ่ายจริง** ถ้าผู้ใช้อยู่ในแพ็กเกจ Pro/Max — ตัวเลข USD คือราคาเทียบ API ใช้ดูขนาดงานเท่านั้น
- ห้ามอ่านเนื้อหาในไฟล์ transcript ของลูกค้าออกมาแสดง — รายงานเฉพาะตัวเลขการใช้งาน
  (🔒 hook บล็อกการ `Read` ไฟล์ `.jsonl` ใน `~/.claude/projects/` ไว้แล้ว — สคริปต์ที่พิมพ์ออกมาแค่ยอดรวมยังรันได้ปกติ)
- ห้ามยืนยันราคาต่อลูกค้าโดยไม่ให้ผู้ใช้ตรวจ `references/pricing.json` เทียบกับหน้าราคาทางการก่อน
