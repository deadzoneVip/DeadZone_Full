#!/bin/bash
set -e

# ==============================================================================
# Telegram Notification Script (Smart Edit/Send) - Adapted from OrangeFox logic
# ==============================================================================
send_tg() {
    local MSG="$1"
    local TARGET="$2"
    
    # 1. If TELEGRAM_MSG_ID is provided, edit that specific message (Live updates)
    if [ -n "${TELEGRAM_MSG_ID}" ]; then
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d message_id="${TELEGRAM_MSG_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    else
        # Fallback: Send a fresh message if build is started manually without bot
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi
      
    # 2. Send to group chat only if TARGET is "all" and group ID is set
    if [ "$TARGET" == "all" ] && [ -n "${TELEGRAM_GROUP_ID}" ]; then
      curl -s --fail \
        -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_GROUP_ID}" \
        -d text="${MSG}" \
        -d parse_mode="Markdown" \
        -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi
}

# ── Self-destroy on exit
cleanup() {
    echo "[$(date '+%H:%M:%S')] Build script finished — machine will auto-destroy"
}
trap cleanup EXIT

# ── Validations
for v in ROM_URL DEVICE_CODENAME BUILD_NAME; do
    if [ -z "${!v}" ]; then
        echo "ERROR: $v not set"
        exit 1
    fi
done

BUILD_START=$(date +%s)
LOG_FILE="/tmp/dz_build_progress.log"
rm -f "$LOG_FILE"

# Initial Telegram Status Setup
send_tg "⚙️ *DeadZone Build Status*
📱 **Device:** \`${DEVICE_CODENAME}\`
🏷 **Build:** \`${BUILD_NAME}\`

⏳ *Status:* 🛠️ Setting up environment & tools..." "private"

cd /deadzone

# Run tools setup and capture to log
bash core/setup_tools.sh >> "$LOG_FILE" 2>&1 || true

# ── Export Environment Variables
export BUILD_NAME OUTPUT_TYPE FS_MODE VBMETA_MODE PATCH_LEVEL
export FACTORY_V2="${FACTORY_V2:-false}"
export BUILD_PROFILE="${BUILD_PROFILE:-}"
export BUILD_VARIANT="${BUILD_VARIANT:-balanced}"
export SKIP_PATCHES="${SKIP_PATCHES:-true}"
export UPLOAD_PIXELDRAIN="${UPLOAD_PIXELDRAIN:-true}"
export NOTIFY_TELEGRAM="false" # Disable native shell notifications to use our bot logic
export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-true}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export PIXELDRAIN_API_KEY="${PIXELDRAIN_API_KEY:-}"

chmod +x main.sh core/*.sh bin/* 2>/dev/null || true

# Update Status to Downloading
send_tg "⚙️ *DeadZone Build Status*
📱 **Device:** \`${DEVICE_CODENAME}\`
🏷 **Build:** \`${BUILD_NAME}\`

⏳ *Status:* 📥 Starting ROM Kitchen operations..." "private"

# ── Launch Kitchen Process in Background
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

# ── Live Build Monitor (Runs while main.sh is active)
LAST_MSG=""
while kill -0 $BUILD_PID 2>/dev/null; do
    # Extract current stage based on "=== STAGE ===" markers from main.sh logs
    STAGE=$(grep -o "=== .* ===" "$LOG_FILE" 2>/dev/null | tail -n1 | sed 's/=== //;s/ ===//' || echo "Processing...")
    
    # Extract safe terminal snippet (Replace backticks with quotes to preserve Markdown)
    CONSOLE_SNIPPET=$(tail -n 3 "$LOG_FILE" 2>/dev/null | sed 's/`/"/g; s/\*/-/g; s/[^[:print:]\t]//g' | grep -v "^[[:space:]]*$" | cut -c1-60 || echo "...")
    
    # Calculate Time
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - BUILD_START))
    MINS=$((ELAPSED / 60))
    SECS=$((ELAPSED % 60))

    NEW_MSG="⚙️ *DeadZone Live Build Dashboard*
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Target:* \`${OUTPUT_TYPE:-fastboot_zip}\`
⏱️ *Elapsed Time:* \`${MINS}m ${SECS}s\`

📊 *Current Stage:* 
\`> ${STAGE}\`

💻 *Live Terminal Output:*
\`\`\`text
${CONSOLE_SNIPPET}
\`\`\`"

    # Only send API request if the message actually changed (saves rate limits)
    if [ "$NEW_MSG" != "$LAST_MSG" ]; then
        send_tg "$NEW_MSG" "private"
        LAST_MSG="$NEW_MSG"
    fi
    
    sleep 5
done

# ── Check Completion Results
wait $BUILD_PID
EXIT_CODE=$?

# Final Time Calculation
BUILD_END=$(date +%s)
BUILD_DIFF=$((BUILD_END - BUILD_START))
FINAL_MINS=$((BUILD_DIFF / 60))
FINAL_SECS=$((BUILD_DIFF % 60))

# ── Handle Failure
if [ $EXIT_CODE -ne 0 ]; then
    FAILED_LOG=$(tail -n 25 "$LOG_FILE" 2>/dev/null | sed 's/`/"/g; s/[^[:print:]\t]//g' | cut -c1-200)
    send_tg "❌ *DeadZone Build Failed!*
An error occurred during ROM modification.

📱 **Device:** \`${DEVICE_CODENAME}\`
🏷 **Build:** \`${BUILD_NAME}\`
⏱️ **Failed After:** \`${FINAL_MINS}m ${FINAL_SECS}s\`

💻 *Failure Log Snippet:*
\`\`\`text
${FAILED_LOG}
\`\`\`" "all"
    exit 1
fi

# ── Handle Success & Links Extraction
RELEASE_URL=""
PIXELDRAIN_URL=""
if [ -f "/deadzone/output_final/upload_links.txt" ]; then
    RELEASE_URL=$(grep '^GITHUB_RELEASE_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
    PIXELDRAIN_URL=$(grep '^PIXELDRAIN_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
fi

LINKS=""
[ -n "$PIXELDRAIN_URL" ] && LINKS+="☁️ [Download from PixelDrain](${PIXELDRAIN_URL})\n"
[ -n "$RELEASE_URL" ] && LINKS+="🐙 [Download from GitHub](${RELEASE_URL})\n"
[ -z "$LINKS" ] && LINKS="_(Links unavailable, check GitHub Actions)_"

# Send Final Success Notification
send_tg "🎉 *DeadZone Build & Upload Successful!*
━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ **Total Time:** \`${FINAL_MINS} mins and ${FINAL_SECS} secs\`

📱 **Device:** \`${DEVICE_CODENAME}\`
🏷 **Build Name:** \`${BUILD_NAME}\`
📦 **Artifact:** \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 **Filesystem:** \`${FS_MODE:-erofs}\`

🔗 **Download Links:**
${LINKS}" "all"
