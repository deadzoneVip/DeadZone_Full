#!/usr/bin/env bash
set -euo pipefail

# ── Telegram helpers (Smart Edit/Send) ────────────────────────────────────────
send_tg() {
    local MSG="$1"
    local TARGET="${2:-private}"
    
    if [ -n "${TELEGRAM_MSG_ID:-}" ]; then
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d message_id="${TELEGRAM_MSG_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    else
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi

    if [ "$TARGET" == "all" ] && [ -n "${TELEGRAM_GROUP_ID:-}" ]; then
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d chat_id="${TELEGRAM_GROUP_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi
}

elapsed_str() {
    local secs=$(( $(date +%s) - BUILD_START ))
    local m=$(( secs / 60 ))
    local s=$(( secs % 60 ))
    printf '%dm %02ds' "$m" "$s"
}

cleanup() {
    echo "[$(date '+%H:%M:%S')] Build script finished — machine will auto-destroy"
}
trap cleanup EXIT

for v in ROM_URL DEVICE_CODENAME BUILD_NAME; do
    [ -n "${!v:-}" ] || { echo "ERROR: $v is not set"; exit 1; }
done

BUILD_START=$(date +%s)
LOG_FILE="/tmp/dz_build_progress.log"
rm -f "$LOG_FILE"

send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`

⏳ *Status:* 🔧 Setting up build environment..." "private"

cd /deadzone
bash core/setup_tools.sh >> "$LOG_FILE" 2>&1 || true

export BUILD_NAME="${BUILD_NAME}"
export STORAGE_VARIANT="${STORAGE_VARIANT:-350}"
export RAM_VARIANT="${RAM_VARIANT:-32}"
export FS_MODE="${FS_MODE:-erofs}"
export VBMETA_MODE="${VBMETA_MODE:-3}"
export PATCH_LEVEL="${PATCH_LEVEL:-none}"
export FACTORY_V2="${FACTORY_V2:-false}"
export BUILD_PROFILE="${BUILD_PROFILE:-}"
export BUILD_VARIANT="${BUILD_VARIANT:-balanced}"
export UPLOAD_PIXELDRAIN="${UPLOAD_PIXELDRAIN:-true}"
export NOTIFY_TELEGRAM="false" # Disable internal bot notifications
export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-true}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export PIXELDRAIN_API_KEY="${PIXELDRAIN_API_KEY:-}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

chmod +x main.sh core/*.sh bin/* 2>/dev/null || true

send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`

⏳ *Status:* 📥 Launching ROM Kitchen compiler..." "private"

set +e
./main.sh \
    "${ROM_URL}" \
    "${DEVICE_CODENAME}" \
    "${SKIP_PATCHES:-true}" \
    "${OUTPUT_TYPE:-fastboot_zip}" \
    "${FS_MODE:-erofs}" \
    "${VBMETA_MODE:-3}" \
    "${PATCH_LEVEL:-none}" \
    >> "$LOG_FILE" 2>&1 &
BUILD_PID=$!
set -e

LAST_MSG=""
while kill -0 $BUILD_PID 2>/dev/null; do
    sleep 8
    
    STAGE=$(grep -o "=== .* ===" "$LOG_FILE" 2>/dev/null | tail -n1 | sed 's/=== //;s/ ===//' || echo "Processing...")
    SNIPPET=$(tail -n 3 "$LOG_FILE" 2>/dev/null | sed 's/`/"/g' | sed 's/[^[:print:]\t]//g' | cut -c1-60 | tr '\n' '\n' || echo "...")
    ELAPSED=$(elapsed_str)

    NEW_MSG="⚙️ *DeadZone Live Build Dashboard*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Target:* \`${OUTPUT_TYPE:-fastboot_zip}\`
⏱️ *Elapsed Time:* \`${ELAPSED}\`

📊 *Current Stage:* \`> ${STAGE}\`

💻 *Live Terminal Output:*
\`\`\`text
${SNIPPET}
\`\`\`"

    if [ "$NEW_MSG" != "$LAST_MSG" ]; then
        send_tg "$NEW_MSG" "private"
        LAST_MSG="$NEW_MSG"
    fi
done

wait $BUILD_PID
EXIT_CODE=$?
ELAPSED=$(elapsed_str)

if [ $EXIT_CODE -ne 0 ]; then
    FAIL_SNIPPET=$(tail -n 15 "$LOG_FILE" 2>/dev/null | sed 's/`/"/g' | sed 's/[^[:print:]\t]//g' | cut -c1-150 || echo "Unknown error")
    send_tg "❌ *DeadZone Build FAILED*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Time:* \`${ELAPSED}\`

💻 *Error Log Snippet:*
\`\`\`text
${FAIL_SNIPPET}
\`\`\`" "all"
    exit 1
fi

RELEASE_URL=""
PIXELDRAIN_URL=""
if [ -f "/deadzone/output_final/upload_links.txt" ]; then
    RELEASE_URL=$(grep '^GITHUB_RELEASE_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
    PIXELDRAIN_URL=$(grep '^PIXELDRAIN_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
fi

LINKS=""
[ -n "$PIXELDRAIN_URL" ] && LINKS+="☁️ [PixelDrain](${PIXELDRAIN_URL})\n"
[ -n "$RELEASE_URL" ] && LINKS+="🐙 [GitHub Release](${RELEASE_URL})\n"
[ -z "$LINKS" ] && LINKS="_(check GitHub Actions for links)_"

send_tg "🎉 *DeadZone Build & Upload Successful!*
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ **Total Time:** \`${ELAPSED}\`

📱 **Device:** \`${DEVICE_CODENAME}\`
🏷 **Build Name:** \`${BUILD_NAME}\`
📦 **Artifact:** \`${OUTPUT_TYPE:-fastboot_zip}\`

🔗 **Download Links:**
${LINKS}" "all"
