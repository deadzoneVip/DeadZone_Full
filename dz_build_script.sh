#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# DeadZone Build Script — Fly.io Build Server
# Runs inside the Fly machine triggered by GitHub Actions.
# Sends Live Telegram status updates (edits a single message like the example).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Telegram helpers ──────────────────────────────────────────────────────────
send_tg() {
    local MSG="$1"
    local TARGET="${2:-private}"   # private | all

    # Edit the bot's status message (Live updates)
    if [ -n "${TELEGRAM_MSG_ID:-}" ]; then
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d message_id="${TELEGRAM_MSG_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    else
        # Fallback: send fresh message if triggered manually
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d chat_id="${TELEGRAM_CHAT_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi

    # If "all" → also send to group/channel
    if [ "$TARGET" == "all" ] && [ -n "${TELEGRAM_GROUP_ID:-}" ]; then
        curl -s --fail \
          -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d chat_id="${TELEGRAM_GROUP_ID}" \
          -d text="${MSG}" \
          -d parse_mode="Markdown" \
          -d disable_web_page_preview=true > /dev/null 2>&1 || true
    fi
}

get_progress_bar() {
    local pct=$1
    local filled=$(( pct / 10 ))
    local empty=$(( 10 - filled ))
    local bar=""
    for (( i=0; i<filled; i++ )); do bar+="█"; done
    for (( i=0; i<empty; i++ )); do bar+="░"; done
    echo "[$bar]"
}

elapsed_str() {
    local secs=$(( $(date +%s) - BUILD_START ))
    local m=$(( secs / 60 ))
    local s=$(( secs % 60 ))
    printf '%dm %02ds' "$m" "$s"
}

# ── Validate required env vars ────────────────────────────────────────────────
for v in ROM_URL DEVICE_CODENAME BUILD_NAME; do
    [ -n "${!v:-}" ] || { echo "ERROR: $v is not set"; exit 1; }
done

# ── Initial status ────────────────────────────────────────────────────────────
BUILD_START=$(date +%s)

send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`

⏳ *Status:* 🔧 Setting up build environment..." "private"

cd /deadzone

# ── Setup tools (payload-dumper, lpmake, etc.) ────────────────────────────────
send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`

⏳ *Status:* 🛠 Installing build tools..." "private"

bash core/setup_tools.sh 2>&1 || true

# ── Start the main build ──────────────────────────────────────────────────────
send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`
🛡 *VBMeta:* \`${VBMETA_MODE:-3}\`

⏳ *Status:* 📥 Downloading ROM OTA zip..." "private"

# Run the build in background and capture logs
LOG_FILE="/tmp/dz_build.log"
rm -f "$LOG_FILE"

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
export NOTIFY_TELEGRAM="${NOTIFY_TELEGRAM:-false}"   # We handle Telegram ourselves
export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-true}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-${G_TOKEN:-}}"
export PIXELDRAIN_API_KEY="${PIXELDRAIN_API_KEY:-}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

chmod +x main.sh core/*.sh bin/* 2>/dev/null || true

./main.sh \
    "${ROM_URL}" \
    "${DEVICE_CODENAME}" \
    "${SKIP_PATCHES:-true}" \
    "${OUTPUT_TYPE:-fastboot_zip}" \
    "${FS_MODE:-erofs}" \
    "${VBMETA_MODE:-3}" \
    "${PATCH_LEVEL:-none}" \
    > "$LOG_FILE" 2>&1 &

BUILD_PID=$!

# ── Live monitoring loop ──────────────────────────────────────────────────────
LAST_SECTION=""
LAST_MSG=""

while kill -0 $BUILD_PID 2>/dev/null; do
    sleep 8

    # Extract current section from logs (lines starting with ===)
    CURRENT_SECTION=$(grep -o "=== .* ===" "$LOG_FILE" 2>/dev/null | tail -n1 | sed 's/=== //;s/ ===//' || echo "")

    # Get last few log lines (clean up for Telegram)
    SNIPPET=$(tail -n 4 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g' \
        | sed 's/[^[:print:]\t]//g' \
        | cut -c1-70 \
        | tr '\n' '\n' \
        || echo "Processing...")

    ELAPSED=$(elapsed_str)

    # Only send update if something changed
    NEW_MSG="⚙️ *DeadZone Live Build Dashboard*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Elapsed:* \`${ELAPSED}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`

📊 *Current Stage:* \`${CURRENT_SECTION:-Running...}\`

💻 *Live Terminal:*
\`\`\`
${SNIPPET}
\`\`\`"

    if [ "$NEW_MSG" != "$LAST_MSG" ]; then
        send_tg "$NEW_MSG" "private"
        LAST_MSG="$NEW_MSG"
    fi
done

# ── Wait and check exit code ──────────────────────────────────────────────────
wait $BUILD_PID
EXIT_CODE=$?
ELAPSED=$(elapsed_str)

if [ $EXIT_CODE -ne 0 ]; then
    FAIL_SNIPPET=$(tail -n 20 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g' \
        | sed 's/[^[:print:]\t]//g' \
        | cut -c1-300 \
        || echo "Unknown error")

    send_tg "❌ *DeadZone Build FAILED*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Time:* \`${ELAPSED}\`

💻 *Error Log:*
\`\`\`
${FAIL_SNIPPET}
\`\`\`" "all"

    exit 1
fi

# ── Upload & success notification ─────────────────────────────────────────────
send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Build Time:* \`${ELAPSED}\`

⏳ *Status:* 📤 Uploading to GitHub Releases & PixelDrain..." "private"

# Read upload links if they exist
RELEASE_URL=""
PIXELDRAIN_URL=""
if [ -f "/deadzone/output_final/upload_links.txt" ]; then
    RELEASE_URL=$(grep '^GITHUB_RELEASE_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
    PIXELDRAIN_URL=$(grep '^PIXELDRAIN_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
fi

# Build download links block
LINKS=""
[ -n "$PIXELDRAIN_URL" ] && LINKS+="☁️ [PixelDrain](${PIXELDRAIN_URL})\n"
[ -n "$RELEASE_URL" ] && LINKS+="🐙 [GitHub Release](${RELEASE_URL})\n"
[ -z "$LINKS" ] && LINKS="_(check GitHub Actions for download links)_"

send_tg "🎉 *DeadZone Build Successful!*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`
⏱ *Total Time:* \`${ELAPSED}\`

📥 *Download:*
${LINKS}" "all"
