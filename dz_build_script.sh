#!/usr/bin/env bash
set -euo pipefail

# ── Self-destroy on exit ──────────────────────────────────────────────────────
cleanup() {
    log "Build script finished — machine will auto-destroy"
}
trap cleanup EXIT

# ── Telegram ──────────────────────────────────────────────────────────────────
tg_edit() {
    local MSG="$1"
    [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]] && return 0
    if [[ -n "${TELEGRAM_MSG_ID:-}" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/editMessageText" \
          -d "chat_id=${TELEGRAM_CHAT_ID}" \
          -d "message_id=${TELEGRAM_MSG_ID}" \
          -d "parse_mode=Markdown" \
          -d "disable_web_page_preview=true" \
          --data-urlencode "text=${MSG}" > /dev/null 2>&1 || true
    fi
}

tg_send() {
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
    printf '%dm %02ds' "$(( secs/60 ))" "$(( secs%60 ))"
}

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ── Validate ──────────────────────────────────────────────────────────────────
for v in ROM_URL DEVICE_CODENAME BUILD_NAME; do
    [[ -n "${!v:-}" ]] || { echo "ERROR: $v not set"; exit 1; }
done

BUILD_START=$(date +%s)
LOG_FILE="/tmp/dz_build.log"
rm -f "$LOG_FILE"

log "=== DeadZone Build Script starting ==="
log "Device: $DEVICE_CODENAME | Build: $BUILD_NAME"

# ── Status: Setup ─────────────────────────────────────────────────────────────
tg_edit "⚙️ *DeadZone Build — Live Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`

🔧 *Stage:* \`Setting up tools...\`
⏱ *Elapsed:* \`0m 00s\`"

cd /deadzone
bash core/setup_tools.sh >> "$LOG_FILE" 2>&1 || true

# ── Export env vars ───────────────────────────────────────────────────────────
export BUILD_NAME OUTPUT_TYPE FS_MODE VBMETA_MODE PATCH_LEVEL
export FACTORY_V2="${FACTORY_V2:-false}"
export BUILD_PROFILE="${BUILD_PROFILE:-}"
export BUILD_VARIANT="${BUILD_VARIANT:-balanced}"
export SKIP_PATCHES="${SKIP_PATCHES:-true}"
export UPLOAD_PIXELDRAIN="${UPLOAD_PIXELDRAIN:-true}"
export NOTIFY_TELEGRAM="false"
export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-true}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export PIXELDRAIN_API_KEY="${PIXELDRAIN_API_KEY:-}"

chmod +x main.sh core/*.sh bin/* 2>/dev/null || true

tg_edit "⚙️ *DeadZone Build — Live Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`

📥 *Stage:* \`Downloading ROM OTA zip...\`
⏱ *Elapsed:* \`$(elapsed_str)\`"

# ── Run build ─────────────────────────────────────────────────────────────────
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
LAST_MSG=""

# ── Live update loop every 10s ────────────────────────────────────────────────
while kill -0 $BUILD_PID 2>/dev/null; do
    sleep 10

    STAGE=$(grep -o "=== .* ===" "$LOG_FILE" 2>/dev/null | tail -n1 \
        | sed 's/=== //;s/ ===//' || echo "Running...")

    # آخر 3 سطور من اللوج
    LINES=$(tail -n 3 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g; s/\*/-/g; s/[^[:print:]\t]//g' \
        | grep -v "^[[:space:]]*$" \
        | cut -c1-60 \
        || echo "...")

    ELAPSED=$(elapsed_str)

    NEW_MSG="⚙️ *DeadZone Build — Live Status*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
⏱ *Elapsed:* \`${ELAPSED}\`

📊 *Stage:* \`${STAGE}\`

💻 *Last 3 log lines:*
\`\`\`
${LINES}
\`\`\`"

    if [[ "$NEW_MSG" != "$LAST_MSG" ]]; then
        tg_edit "$NEW_MSG"
        LAST_MSG="$NEW_MSG"
    fi
done

# ── Check result ──────────────────────────────────────────────────────────────
wait $BUILD_PID
EXIT_CODE=$?
ELAPSED=$(elapsed_str)

if [[ $EXIT_CODE -ne 0 ]]; then
    FAIL_LOG=$(tail -n 10 "$LOG_FILE" 2>/dev/null \
        | sed 's/`/"/g; s/[^[:print:]\t]//g' | cut -c1-250)

    # Edit live message to show failure
    tg_edit "❌ *DeadZone Build FAILED*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
⏱ *Total Time:* \`${ELAPSED}\`

💻 *Error:*
\`\`\`
${FAIL_LOG}
\`\`\`"
    log "Build FAILED"
    exit 1
fi

# ── Success ───────────────────────────────────────────────────────────────────
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

# Edit the live message → final success (this is the LAST edit)
tg_edit "✅ *DeadZone Build Successful!*
━━━━━━━━━━━━━━━━━━━━━━━━
📱 *Device:* \`${DEVICE_CODENAME}\`
🏷 *Build:* \`${BUILD_NAME}\`
📦 *Output:* \`${OUTPUT_TYPE:-fastboot_zip}\`
🗂 *Filesystem:* \`${FS_MODE:-erofs}\`
⏱ *Total Time:* \`${ELAPSED}\`

📥 *Download:*
${LINKS}"

log "Build completed successfully in ${ELAPSED}"
