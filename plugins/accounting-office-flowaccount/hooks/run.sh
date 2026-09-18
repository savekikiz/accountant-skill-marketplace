#!/bin/sh
# หา python แล้วรัน hook — ถ้าไม่มี python เลย ต้อง "ดัง" ไม่ใช่เงียบ
#
# hooks.json เรียกไฟล์นี้ ไม่เรียก .py ตรง ๆ เพราะ failure ที่มีโอกาสเกิดจริงที่สุด
# และเงียบที่สุดคือ "เครื่องไม่มี python3" — hook ที่ exit ด้วยรหัสอื่นที่ไม่ใช่ 0/2
# ถือเป็น non-blocking error แล้ว Claude Code จะปล่อย tool ทำงานต่อ
# = ด่านถูกปลดโดยไม่มีใครรู้
#
# ห้ามใช้ set -e และห้ามพึ่งคำสั่งภายนอก (dirname ฯลฯ) — เส้นทางนี้ต้องเดินได้แม้ PATH พัง

HOOK_DIR=${0%/*}
case "$HOOK_DIR" in "$0") HOOK_DIR=. ;; esac
SCRIPT="$HOOK_DIR/$1"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT"
fi
if command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT"
fi
for CANDIDATE in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
  if [ -x "$CANDIDATE" ]; then
    exec "$CANDIDATE" "$SCRIPT"
  fi
done

printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"ไม่พบ python3 ในเครื่อง — ด่านตรวจของ accounting-office ไม่ทำงาน ห้ามบันทึกข้อมูลเข้า ERP จนกว่าจะติดตั้ง python3 (macOS: xcode-select --install)","systemMessage":"accounting-office hooks disabled: python3 not found"}}'
exit 0
