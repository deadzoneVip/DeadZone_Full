#!/usr/bin/env bash
set -euo pipefail

export WORKSPACE="${WORKSPACE:-$(pwd)}"
export BIN="$WORKSPACE/bin"
export INPUT="$WORKSPACE/input"
export EXTRACTED="$WORKSPACE/extracted"
export OUTPUT="$WORKSPACE/output"
export OUTPUT_FINAL="$WORKSPACE/output_final"
export LOGS="$OUTPUT/logs"
export DEVICES="$WORKSPACE/devices"
export PATH="$BIN:$PATH"

source "$WORKSPACE/core/utils.sh"
source "$WORKSPACE/core/unpacker.sh"
source "$WORKSPACE/core/repacker.sh"
source "$WORKSPACE/core/fs_detect.sh"
source "$WORKSPACE/core/collect_images.sh"
source "$WORKSPACE/core/vbmeta_patch.sh"
source "$WORKSPACE/core/package_fastboot.sh"
source "$WORKSPACE/core/upload_release.sh"
source "$WORKSPACE/core/validate_build.sh"

main() {
  local rom_url="${1:-${ROM_URL:-}}"
  export DEVICE_CODENAME="${2:-${DEVICE_CODENAME:-}}"
  export SKIP_PATCHES="${3:-${SKIP_PATCHES:-true}}"
  export OUTPUT_TYPE="${4:-${OUTPUT_TYPE:-super_zst}}"
  export FS_MODE="${5:-${FS_MODE:-erofs}}"
  export VBMETA_MODE="${6:-${VBMETA_MODE:-3}}"
  export PATCH_LEVEL="${7:-${PATCH_LEVEL:-none}}"
  export FACTORY_V2="${FACTORY_V2:-false}"
  export BUILD_PROFILE="${BUILD_PROFILE:-}"
  export BUILD_VARIANT="${BUILD_VARIANT:-balanced}"
  export BUILD_NAME="${BUILD_NAME:-DeadZone_v1}"
  export UPLOAD_PIXELDRAIN="${UPLOAD_PIXELDRAIN:-false}"
  export NOTIFY_TELEGRAM="${NOTIFY_TELEGRAM:-false}"
  export CREATE_GITHUB_RELEASE="${CREATE_GITHUB_RELEASE:-false}"

  [[ -n "$rom_url" ]] || die "Usage: ./main.sh <ROM_URL> <DEVICE_CODENAME> [SKIP_PATCHES] [OUTPUT_TYPE] [FS_MODE] [VBMETA_MODE] [PATCH_LEVEL]"
  [[ -n "$DEVICE_CODENAME" ]] || die "device_codename is required"
  case "$OUTPUT_TYPE" in
    super_zst|fastboot_zip|full_release|detect_only) ;;
    *) die "Unsupported output_type=$OUTPUT_TYPE" ;;
  esac
  case "$FS_MODE" in preserve|erofs) ;; *) die "Unsupported fs_mode=$FS_MODE" ;; esac
  case "$VBMETA_MODE" in 0|1|2|3) ;; *) die "Unsupported vbmeta_mode=$VBMETA_MODE" ;; esac
  case "$PATCH_LEVEL" in none|safe|full) ;; *) die "Unsupported patch_level=$PATCH_LEVEL" ;; esac

  section "DeadZone ROM Kitchen"
  log "Device codename: $DEVICE_CODENAME"
  log "Build name: $BUILD_NAME"
  log "Skip patches: $SKIP_PATCHES"
  log "Output type: $OUTPUT_TYPE"
  log "Factory v2: $FACTORY_V2"
  log "fs_mode: $FS_MODE"
  log "vbmeta_mode: $VBMETA_MODE"
  log "patch_level: $PATCH_LEVEL"

  if [[ "$OUTPUT_TYPE" == "detect_only" ]]; then
    section "Factory v2 Detect Only"
    python3 -m dzfactory.cli detect --rom "$rom_url" --device-hint "$DEVICE_CODENAME" --profile "$BUILD_PROFILE" --variant "$BUILD_VARIANT"
    section "Done"
    log "Manifest path: $OUTPUT/manifest/build_manifest.json"
    exit 0
  fi

  if [[ "$FACTORY_V2" == "true" ]]; then
    section "Factory v2 Build"
    python3 -m dzfactory.cli detect --rom "$rom_url" --device-hint "$DEVICE_CODENAME" --profile "$BUILD_PROFILE" --variant "$BUILD_VARIANT"
    python3 -m dzfactory.cli build --manifest "$OUTPUT/manifest/build_manifest.json"
    section "Done"
    log "Manifest path: $OUTPUT/manifest/build_manifest.json"
    log "Logs path: $LOGS"
    exit 0
  fi

  if [[ "$SKIP_PATCHES" != "true" || "$PATCH_LEVEL" != "none" ]]; then
    warn "ROM modifications are intentionally disabled for this build server version"
  fi

  prepare_env
  load_device_defaults
  load_device_profile || die "Missing device profile: devices/$DEVICE_CODENAME.conf"
  fetch_rom "$rom_url"
  export ROM_URL="$rom_url"
  detect_rom_version "$rom_url"

  section "Payload Extraction"
  extract_payload_all_images
  detect_partition_images
  detect_dynamic_filesystems

  section "Super Build"
  build_super_image
  compress_super_image
  validate_super_image

  if [[ "$OUTPUT_TYPE" == "fastboot_zip" || "$OUTPUT_TYPE" == "full_release" ]]; then
    section "Fastboot Package"
    collect_fastboot_images
    patch_vbmeta_images
    package_fastboot_zip
    validate_build
    if [[ "$CREATE_GITHUB_RELEASE" == "true" || "$UPLOAD_PIXELDRAIN" == "true" || "$NOTIFY_TELEGRAM" == "true" ]]; then
      section "Release Uploads"
      upload_release_artifacts
      validate_build
    fi
  else
    validate_super_zst
  fi

  section "Done"
  if [[ "$OUTPUT_TYPE" == "super_zst" ]]; then
    log "Output path: $OUTPUT/super.img.zst"
  else
    log "Output path: $OUTPUT_FINAL/${BUILD_NAME}_${DEVICE_CODENAME}_fastboot.zip"
  fi
  log "Logs path: $LOGS"
}

main "$@"
