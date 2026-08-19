#!/usr/bin/env bash

# Spotify Connect support is provided by go-librespot (https://github.com/devgianlu/go-librespot),
# a self-contained Go binary. There is no apt/pip package for it, so this routine
# downloads a prebuilt release binary for the detected architecture. It is only run
# when the user opts in via ENABLE_SPOTIFY (see customize_options.sh).
#
# The binary and its own state/config live entirely under the shared folder so they
# survive like any other user data; nothing is installed system-wide and no systemd
# service is registered. The Jukebox Core itself starts/stops go-librespot as a child
# process (see src/jukebox/components/player/backends/spotify.py) only while
# spotify.enable is set to true in jukebox.yaml.

GO_LIBRESPOT_REPO="devgianlu/go-librespot"
GO_LIBRESPOT_VERSION="${GO_LIBRESPOT_VERSION:-latest}"
SPOTIFY_INSTALL_DIR="${SHARED_PATH}/spotify"
SPOTIFY_BIN_DIR="${SPOTIFY_INSTALL_DIR}/bin"
SPOTIFY_BINARY_PATH="${SPOTIFY_BIN_DIR}/go-librespot"

# Map our architecture names (see get_architecture in 02_helpers.sh) onto go-librespot's
# release asset names. go-librespot does not publish a dedicated armv7 build; the armv6
# ('rpi'-optimized) binary is used instead, since armv7 CPUs run armv6 code natively.
_spotify_asset_name() {
    local arch
    arch=$(get_architecture)
    case "$arch" in
        arm64)
            echo "go-librespot_linux_arm64.tar.gz"
            ;;
        armv7|armv6)
            echo "go-librespot_linux_armv6_rpi.tar.gz"
            ;;
        x86_64)
            echo "go-librespot_linux_x86_64.tar.gz"
            ;;
        *)
            echo ""
            ;;
    esac
}

_spotify_install_go_librespot() {
    print_lc "  Install go-librespot (Spotify Connect client)"

    local asset_name
    asset_name=$(_spotify_asset_name)
    if [[ -z "$asset_name" ]]; then
        print_lc "  WARNING: No go-librespot build is available for architecture '$(uname -m)'."
        print_lc "  WARNING: Skipping Spotify install. You can build go-librespot from source"
        print_lc "  WARNING: yourself later - see https://github.com/devgianlu/go-librespot"
        ENABLE_SPOTIFY=false
        return
    fi

    local download_url
    if [[ "$GO_LIBRESPOT_VERSION" == "latest" ]]; then
        download_url="https://github.com/${GO_LIBRESPOT_REPO}/releases/latest/download/${asset_name}"
    else
        download_url="https://github.com/${GO_LIBRESPOT_REPO}/releases/download/${GO_LIBRESPOT_VERSION}/${asset_name}"
    fi

    mkdir -p "${SPOTIFY_BIN_DIR}"
    local tmp_archive="/tmp/${asset_name}"

    log "  Downloading ${download_url}"
    download_from_url "${download_url}" "${tmp_archive}"
    tar -xzf "${tmp_archive}" -C "${SPOTIFY_BIN_DIR}" go-librespot || exit_on_error "ERROR: Could not extract go-librespot archive"
    rm -f "${tmp_archive}"
    chmod +x "${SPOTIFY_BINARY_PATH}"
}

_spotify_check() {
    print_verify_installation

    verify_dirs_exists "${SPOTIFY_INSTALL_DIR}"
    verify_files_chown "${CURRENT_USER}" "${CURRENT_USER_GROUP}" "${SPOTIFY_BINARY_PATH}"

    if [[ ! -x "${SPOTIFY_BINARY_PATH}" ]]; then
        exit_on_error "ERROR: '${SPOTIFY_BINARY_PATH}' is not executable"
    fi
    log "  CHECK"
}

_run_setup_spotify() {
    mkdir -p "${SPOTIFY_INSTALL_DIR}"
    _spotify_install_go_librespot
    if [[ "$ENABLE_SPOTIFY" == true ]]; then
        _spotify_check
    fi
}

setup_spotify() {
    # Install/update only if enabled: fully skipped (no download, no shared/spotify
    # folder) for anyone who does not opt in.
    if [[ "$ENABLE_SPOTIFY" == true ]]; then
        run_with_log_frame _run_setup_spotify "Install Spotify Connect support (go-librespot)"
    fi
}
