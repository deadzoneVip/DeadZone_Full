#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# DeadZone Build Script — Fly.io Build Server
# - Runs the full build inside the Fly machine
# - Streams live logs to Telegram (edits the bot's status message)
# - Self-destroys the machine when done (so it doesn't cost money)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Self-destroy on exit ──────────────────────────────────────────────────────
# This is the KEY fix: machine destroys itself when script ends (success or fail)
# so it doesn't keep running and costing money after GitHub Actions finishes.
MY_MACHINE_ID="${FLY_MACHINE_ID:-}"
cleanup() {
    if [[ -n "$MY_MACHINE_ID" ]]; then
        log "Self-destroying Fly machine $MY_MACHINE_ID..."
        flyctl machine destroy "$MY_MACHINE_ID" --force --app "${FLY_APP_NAME:-deadzone-build-server}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

# ── Telegram helpers ──────────────────────────────────────────────────────────
send_tg() {
    local MSG="$1"
    [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]] && return 0

    if [[ -n "${TELEGRAM_MSG_ID:-}" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
          -d "chat_id=${TELEGRAM_CHAT_ID}" \
          -d "message_id=${TELEGRAM_MSG_ID}" \
          -d "parse_mode=Markdown" \
          -d "disable_web_page_preview=true" \
          --data-urlencode "text=${MSG}" > /dev/null 2>&1 || true
    else
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
          -d "chat_id=${TELEGRAM_CHAT_ID}" \
          -d "parse_mode=Markdown" \
          -d "disable_web_page_preview=true" \
          --data-urlencode "text=${MSG}" > /dev/null 2>&1 || true
    fi
}

send_tg_new() {
    # Send a NEW message (for final result)
    local MSG="$1"
    [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]] && return 0
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_CHAT_ID}" \
      -d "parse_mode=Markdown" \
      -d "disable_web_page_preview=true" \
      --data-urlencode "text=${MSG}" > /dev/null 2>&1 || true
}

elapsed_str() {
    local secs=$(( $(date +%s) - BUILD_START ))
    local m=$(( secs / 60 )); local s=$(( secs % 60 ))
    printf '%dm %02ds' "$m" "$s"
}

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Validate env ──────────────────────────────────────────────────────────────
for v in ROM_URL DEVICE_CODENAME BUILD_NAME; do
    [[ -n "${!v:-}" ]] || { echo "ERROR: $v is not set"; exit 1; }
done

BUILD_START=$(date +%s)
LOG_FILE="/tmp/dz_build.log"
rm -f "$LOG_FILE"

log "=== DeadZone Build Script starting ==="
log "Device: $DEVICE_CODENAME | Build: $BUILD_NAME"

# ── Initial Telegram status ───────────────────────────────────────────────────
send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`

🔧 *Status:* Installing build tools..."

cd /deadzone
bash core/setup_tools.sh >> "$LOG_FILE" 2>&1 || true

send_tg "⚙️ *DeadZone Build Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`

📥 *Status:* Downloading ROM OTA zip..."

# ── Export all build env vars ─────────────────────────────────────────────────
export BUILD_NAME OUTPUT_TYPE FS_MODE VBMETA_MODE PATCH_LEVEL
export FACTORY_V2="${FACTORY_V2:-false}"
export BUILD_PROFILE="${BUILD_PROFILE:-}"
export BUILD_VARIANT="${BUILD_VARIANT:-balanced}"
export SKIP_PATCHES="${SKIP_PATCHES:-true}"
export UPLOAD_PIXELDRAIN="${UPLOAD_PIXELDRAIN:-true}"
export NOTIFY_TELEGRAM="false"   # We handle Telegram ourselves
export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-true}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export PIXELDRAIN_API_KEY="${PIXELDRAIN_API_KEY:-}"
export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

chmod +x main.sh core/*.sh bin/* 2>/dev/null || true

# ── Run build in background ───────────────────────────────────────────────────
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
LAST_SECTION=""
LAST_MSG=""

# ── Live log loop ─────────────────────────────────────────────────────────────
while kill -0 $BUILD_PID 2>/dev/null; do
    sleep 10

    CURRENT_SECTION=$(grep -o "=== .* ===" "$LOG_FILE" 2>/dev/null | tail -n1 \
        | sed 's/=== //;s/ ===//' || echo "Running...")

    # Last 5 log lines, cleaned for Telegram
    SNIPPET=$(tail -n 5 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g; s/\*//g; s/_//g' \
        | sed 's/[^[:print:]\t]//g' \
        | cut -c1-65 \
        | grep -v "^$" \
        | head -5 \
        || echo "Processing...")

    ELAPSED=$(elapsed_str)

    NEW_MSG="⚙️ *DeadZone Live Build*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Elapsed:* \`${ELAPSED}\`

📊 *Stage:* \`${CURRENT_SECTION}\`

💻 *Live Log:*
\`\`\`
${SNIPPET}
\`\`\`"

    if [[ "$NEW_MSG" != "$LAST_MSG" ]]; then
        send_tg "$NEW_MSG"
        LAST_MSG="$NEW_MSG"
    fi
done

# ── Check result ──────────────────────────────────────────────────────────────
wait $BUILD_PID
EXIT_CODE=$?
ELAPSED=$(elapsed_str)

if [[ $EXIT_CODE -ne 0 ]]; then
    FAIL_LOG=$(tail -n 15 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g; s/[^[:print:]\t]//g' \
        | cut -c1-280 || echo "Unknown error")

    send_tg "❌ *DeadZone Build FAILED*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Time:* \`${ELAPSED}\`

💻 *Error:*
\`\`\`
${FAIL_LOG}
\`\`\`"
    log "Build FAILED with exit code $EXIT_CODE"
    exit 1
fi

# ── Upload success ────────────────────────────────────────────────────────────
RELEASE_URL=""
PIXELDRAIN_URL=""
if [[ -f "/deadzone/output_final/upload_links.txt" ]]; then
    RELEASE_URL=$(grep '^GITHUB_RELEASE_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
    PIXELDRAIN_URL=$(grep '^PIXELDRAIN_URL=' /deadzone/output_final/upload_links.txt | cut -d= -f2- || true)
fi

LINKS=""
[[ -n "$PIXELDRAIN_URL" ]] && LINKS+="☁️ [PixelDrain](${PIXELDRAIN_URL})\n"
[[ -n "$RELEASE_URL"    ]] && LINKS+="🐙 [GitHub Release](${RELEASE_URL})\n"
[[ -z "$LINKS"          ]] && LINKS="_(check GitHub Actions for links)_"

# Edit the live status message with final result
send_tg "✅ *DeadZone Build Successful!*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`
⏱ *Total Time:* \`${ELAPSED}\`

📥 *Download:*
${LINKS}"

log "Build completed successfully in ${ELAPSED}"
