#!/usr/bin/env bash
# PasarguardBot — install & management script (Docker + Native)
# https://github.com/AmirKenzo/PasarguardBot
#
# Install:
#   bash <(curl -fsSL https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/main/scripts/pasarguardbot.sh)
# Then choose Docker/Native and main (stable) or dev (testing).
set -euo pipefail

# ── Paths & constants ──────────────────────────────────────────────────────────
readonly SCRIPT_VERSION="1.2.15"
readonly CONFIG_DIR="/opt/pasarguardbot"
readonly COMPOSE_FILE="${CONFIG_DIR}/docker-compose.yml"
readonly ENV_FILE="${CONFIG_DIR}/.env"
readonly INSTALL_MODE_FILE="${CONFIG_DIR}/.install_mode"
readonly INSTALL_BRANCH_FILE="${CONFIG_DIR}/.install_branch"
readonly APP_DIR="${CONFIG_DIR}/app"
readonly CONF_DIR="${CONFIG_DIR}/conf"
readonly RUN_DIR="${CONFIG_DIR}/run"
readonly PHPMYADMIN_DIR="${CONFIG_DIR}/phpmyadmin"
readonly MANAGER_BIN="/usr/local/bin/pasarguardbot"
readonly MANAGER_SCRIPT="${CONFIG_DIR}/pasarguardbot.sh"
# Override while testing: PASARGUARDBOT_BRANCH=dev
readonly DEFAULT_REPO_BRANCH="${PASARGUARDBOT_BRANCH:-main}"
readonly REPO_BRANCH="${DEFAULT_REPO_BRANCH}"
readonly SCRIPT_RAW_URL="https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/${REPO_BRANCH}/scripts/pasarguardbot.sh"
readonly NETPLAN_FIX_SCRIPT_NAME="fix-docker-netplan.sh"
readonly NETPLAN_FIX_INSTALLED="${CONFIG_DIR}/${NETPLAN_FIX_SCRIPT_NAME}"
readonly NETPLAN_FIX_RAW_URL="${SCRIPT_RAW_URL/pasarguardbot.sh/${NETPLAN_FIX_SCRIPT_NAME}}"
readonly COMPOSE_RAW_URL="https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/${REPO_BRANCH}/docker-compose.yml"
readonly ENV_EXAMPLE_RAW_URL="https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/${REPO_BRANCH}/.env.example"
readonly REPO_GIT_URL="https://github.com/AmirKenzo/PasarguardBot.git"
readonly PHPMYADMIN_ARCHIVE_URL="https://files.phpmyadmin.net/phpMyAdmin/5.2.2/phpMyAdmin-5.2.2-all-languages.tar.gz"
readonly BOT_IMAGE="ghcr.io/amirkenzo/pasarguardbot"
readonly FASTAPI_PORT_DEFAULT=6160
readonly REDIS_PORT=6161
readonly MARIADB_PORT=6162
readonly PHPMYADMIN_PORT=6163
readonly MIN_DISK_MB=2048
readonly CURL_CONNECT_TIMEOUT=10
readonly CURL_MAX_TIME=60
readonly CURL_RETRIES=3
readonly CURL_RETRY_DELAY=2

readonly NATIVE_UNITS=(
    pasarguardbot.service
    pasarguardbot-redis.service
    pasarguardbot-mariadb.service
    pasarguardbot-phpmyadmin.service
)

# Populated by detect_os()
OS_ID=""
OS_ID_LIKE=""
OS_VERSION_ID=""
OS_PRETTY_NAME=""
PKG_MANAGER=""

# ── Colors ────────────────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
    readonly C_RESET='\033[0m'
    readonly C_BOLD='\033[1m'
    readonly C_DIM='\033[2m'
    readonly C_RED='\033[0;31m'
    readonly C_GREEN='\033[0;32m'
    readonly C_YELLOW='\033[0;33m'
    readonly C_BLUE='\033[0;34m'
    readonly C_CYAN='\033[0;36m'
else
    readonly C_RESET='' C_BOLD='' C_DIM='' C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_CYAN=''
fi

# ── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${C_BLUE}[*]${C_RESET} $*"; }
ok()      { echo -e "${C_GREEN}[✓]${C_RESET} $*"; }
warn()    { echo -e "${C_YELLOW}[!]${C_RESET} $*"; }
err()     { echo -e "${C_RED}[✗]${C_RESET} $*" >&2; }
die()     { err "$*"; exit 1; }

pause() {
    echo
    read -r -p "Press Enter to continue..." _ || true
}

rand_hex()  { openssl rand -hex "${1:-16}"; }
rand_b64()  { openssl rand -base64 "${1:-24}" | tr -d '/+=' | head -c "${1:-24}"; }

safe_clear() {
    if command -v clear &>/dev/null \
        && [[ -t 1 ]] \
        && [[ -n "${TERM:-}" ]]; then
        clear 2>/dev/null || true
    fi
}

# Always show versions as a single "vX.Y.Z" (supports both 1.0.0 and v1.0.0 tags).
format_version() {
    local v="${1:-}"
    [[ -n "$v" ]] || {
        printf '%s' '—'
        return 0
    }
    while [[ "$v" == [vV]* ]]; do
        v="${v:1}"
    done
    printf 'v%s' "$v"
}

require_root() {
    [[ "${EUID:-$(id -u)}" -eq 0 ]] || die "This script must be run as root: sudo bash $0"
}

# Allow: bash <(curl -fsSL ...scripts/pasarguardbot.sh) without an outer sudo.
elevate_if_needed() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        return 0
    fi
    command -v sudo &>/dev/null || die "This script must be run as root (sudo not found)."

    local tmp src="${BASH_SOURCE[0]:-}"
    tmp="$(mktemp)"
    if [[ -n "$src" && -r "$src" ]]; then
        cp "$src" "$tmp"
    else
        rm -f "$tmp"
        die "Re-run as root: sudo bash <(curl -fsSL ${SCRIPT_RAW_URL})"
    fi
    chmod +x "$tmp"
    info "Root required — re-running with sudo..."
    exec sudo bash "$tmp" "$@"
}

curl_get() {
    curl --fail --silent --show-error --location \
        --retry "$CURL_RETRIES" \
        --retry-delay "$CURL_RETRY_DELAY" \
        --connect-timeout "$CURL_CONNECT_TIMEOUT" \
        --max-time "$CURL_MAX_TIME" \
        -H "Cache-Control: no-cache" \
        -H "Pragma: no-cache" \
        "$@"
}

curl_download() {
    local url="$1"
    local dest="$2"
    # Cache-bust query for raw.githubusercontent.com / CDNs
    if [[ "$url" == *"?"* ]]; then
        curl_get -o "$dest" "${url}&_ts=$(date +%s)"
    else
        curl_get -o "$dest" "${url}?_ts=$(date +%s)"
    fi
}

explain_network_failure() {
    local context="${1:-download}"
    err "Failed to ${context}."
    err "Possible causes: GitHub Raw unreachable, DNS failure, firewall, or network timeout."
    err "Check connectivity, then retry."
}

set_env_var() {
    local file="$1" key="$2" value="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    elif grep -q "^# ${key}=" "$file"; then
        sed -i "s|^# ${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >>"$file"
    fi
}

docker_compose() {
    if docker compose version &>/dev/null; then
        docker compose \
            --project-directory "$CONFIG_DIR" \
            -f "$COMPOSE_FILE" \
            --env-file "$ENV_FILE" \
            "$@"
    elif command -v docker-compose &>/dev/null; then
        warn "Using legacy docker-compose; prefer Docker Compose V2 (docker compose)."
        docker-compose \
            --project-directory "$CONFIG_DIR" \
            -f "$COMPOSE_FILE" \
            --env-file "$ENV_FILE" \
            "$@"
    else
        die "Docker Compose not found. Install Docker Compose V2 (docker compose) and retry."
    fi
}

set_install_mode() {
    local mode="$1"
    mkdir -p "$CONFIG_DIR"
    printf '%s\n' "$mode" >"$INSTALL_MODE_FILE"
}

set_install_branch() {
    local branch="$1"
    mkdir -p "$CONFIG_DIR"
    printf '%s\n' "$branch" >"$INSTALL_BRANCH_FILE"
}

# GHCR tags: main → latest (release tags), other branches → branch name (e.g. dev).
bot_image_tag_for_branch() {
    local branch="${1:-main}"
    case "$branch" in
        main) printf '%s' 'latest' ;;
        *) printf '%s' "$branch" ;;
    esac
}

get_bot_image_tag() {
    local tag=""
    if [[ -f "$ENV_FILE" ]]; then
        tag="$(get_env_value PASARGUARDBOT_IMAGE_TAG "$ENV_FILE")"
    fi
    if [[ -n "$tag" ]]; then
        printf '%s' "$tag"
        return 0
    fi
    bot_image_tag_for_branch "$(get_repo_branch)"
}

apply_bot_image_tag_for_branch() {
    local branch="${1:-$(get_repo_branch)}"
    local image_tag
    image_tag="$(bot_image_tag_for_branch "$branch")"
    [[ -f "$ENV_FILE" ]] || return 0
    set_env_var "$ENV_FILE" "PASARGUARDBOT_IMAGE_TAG" "$image_tag"
}

# Resolve update/install branch: env > saved file > current git branch > default.
get_repo_branch() {
    local branch=""
    if [[ -n "${PASARGUARDBOT_BRANCH:-}" ]]; then
        printf '%s' "$PASARGUARDBOT_BRANCH"
        return 0
    fi
    if [[ -f "$INSTALL_BRANCH_FILE" ]]; then
        branch="$(tr -d '[:space:]' <"$INSTALL_BRANCH_FILE" 2>/dev/null || true)"
        if [[ -n "$branch" ]]; then
            printf '%s' "$branch"
            return 0
        fi
    fi
    if [[ -d "${APP_DIR}/.git" ]]; then
        branch="$(git -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
        if [[ -n "$branch" && "$branch" != "HEAD" ]]; then
            printf '%s' "$branch"
            return 0
        fi
    fi
    printf '%s' "$DEFAULT_REPO_BRANCH"
}

repo_archive_url() {
    local branch="${1:-$(get_repo_branch)}"
    printf 'https://github.com/AmirKenzo/PasarguardBot/archive/refs/heads/%s.tar.gz' "$branch"
}

compose_raw_url_for_branch() {
    local branch="${1:-$(get_repo_branch)}"
    printf 'https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/%s/docker-compose.yml' "$branch"
}

env_example_raw_url_for_branch() {
    local branch="${1:-$(get_repo_branch)}"
    printf 'https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/%s/.env.example' "$branch"
}

# Sets SELECTED_REPO_BRANCH. Returns 1 if cancelled/invalid.
# $1 = context label: install | update
prompt_repo_branch() {
    local context="${1:-update}"
    local current choice title
    SELECTED_REPO_BRANCH=""
    current="$(get_repo_branch)"

    if [[ "$context" == "install" ]]; then
        title="Select install branch"
    else
        title="Select update branch"
    fi

    echo -e "${C_BOLD}  ${title}${C_RESET}"
    echo
    echo "  1) main  (recommended — latest stable)"
    echo "  2) dev   (testing only — may be unstable)"
    echo "  0) Cancel"
    echo
    if [[ -n "$current" && -f "$INSTALL_BRANCH_FILE" ]]; then
        info "Last used branch: ${current}"
    fi
    read -r -p "Choice [1]: " choice || true
    choice="${choice:-1}"
    case "$choice" in
        1)
            SELECTED_REPO_BRANCH="main"
            ;;
        2)
            warn "dev is for testing. Prefer main unless you need unreleased changes."
            SELECTED_REPO_BRANCH="dev"
            ;;
        0)
            return 1
            ;;
        *)
            warn "Invalid choice."
            return 1
            ;;
    esac
    return 0
}

get_install_mode() {
    local mode=""
    if [[ -f "$INSTALL_MODE_FILE" ]]; then
        mode="$(tr -d '[:space:]' <"$INSTALL_MODE_FILE" 2>/dev/null || true)"
    fi
    if [[ -z "$mode" ]]; then
        if [[ -f "$COMPOSE_FILE" ]]; then
            mode="docker"
        elif [[ -d "$APP_DIR" ]] || [[ -f /etc/systemd/system/pasarguardbot.service ]]; then
            mode="native"
        fi
    fi
    printf '%s' "${mode:-}"
}

is_docker_mode() {
    [[ "$(get_install_mode)" == "docker" ]]
}

is_native_mode() {
    [[ "$(get_install_mode)" == "native" ]]
}

is_installed() {
    [[ -f "$ENV_FILE" ]] || return 1
    local mode
    mode="$(get_install_mode)"
    case "$mode" in
        docker) [[ -f "$COMPOSE_FILE" ]] ;;
        native)
            # Empty APP_DIR from mkdir is not a real install.
            [[ -f "${APP_DIR}/main.py" ]] || [[ -f /etc/systemd/system/pasarguardbot.service ]]
            ;;
        *) [[ -f "$COMPOSE_FILE" || -f "${APP_DIR}/main.py" ]] ;;
    esac
}

get_env_value() {
    local key="$1"
    local file="${2:-$ENV_FILE}"
    grep -E "^${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2- || true
}

require_native_os() {
    case "$PKG_MANAGER" in
        apt-get) ;;
        *)
            die "Native install is supported on Debian/Ubuntu (apt-get) only. Detected: ${OS_PRETTY_NAME} (${PKG_MANAGER}). Use Docker install instead."
            ;;
    esac
}

# ── OS detection & bootstrap ───────────────────────────────────────────────────
detect_os() {
    [[ -f /etc/os-release ]] || die "Cannot detect OS: /etc/os-release not found."

    # shellcheck disable=SC1091
    . /etc/os-release

    OS_ID="${ID:-unknown}"
    OS_ID_LIKE="${ID_LIKE:-}"
    OS_VERSION_ID="${VERSION_ID:-}"
    OS_PRETTY_NAME="${PRETTY_NAME:-$OS_ID}"
    if [[ -n "$OS_VERSION_ID" ]]; then
        OS_PRETTY_NAME="${OS_PRETTY_NAME} (${OS_VERSION_ID})"
    fi

    local family
    family="$(printf '%s %s' "$OS_ID" "$OS_ID_LIKE" | tr '[:upper:]' '[:lower:]')"

    if command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt-get"
    elif command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MANAGER="yum"
    elif command -v pacman &>/dev/null; then
        PKG_MANAGER="pacman"
    elif command -v zypper &>/dev/null; then
        PKG_MANAGER="zypper"
    elif command -v apk &>/dev/null; then
        PKG_MANAGER="apk"
    else
        die "Unsupported package manager on ${OS_PRETTY_NAME}. Supported: apt-get, dnf, yum, pacman, zypper, apk."
    fi

    case "$family" in
        *ubuntu*|*debian*|*kali*|*linuxmint*|*pop*|*raspbian*) ;;
        *rhel*|*centos*|*rocky*|*alma*|*fedora*|*amzn*|*amazon*|*ol*|*oracle*) ;;
        *arch*|*manjaro*) ;;
        *suse*|*sles*) ;;
        *alpine*) ;;
        *)
            warn "OS '${OS_PRETTY_NAME}' is not in the tested list; continuing with ${PKG_MANAGER}."
            ;;
    esac
}

pkg_is_installed() {
    local pkg="$1"
    case "$PKG_MANAGER" in
        apt-get)
            dpkg -s "$pkg" &>/dev/null
            ;;
        dnf|yum)
            rpm -q "$pkg" &>/dev/null
            ;;
        pacman)
            pacman -Qi "$pkg" &>/dev/null
            ;;
        zypper)
            rpm -q "$pkg" &>/dev/null
            ;;
        apk)
            apk info -e "$pkg" &>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

run_pkg_install() {
    local -a pkgs=("$@")
    local -a missing=()
    local pkg cmd_desc

    [[ ${#pkgs[@]} -gt 0 ]] || return 0

    for pkg in "${pkgs[@]}"; do
        if ! pkg_is_installed "$pkg"; then
            missing+=("$pkg")
        fi
    done

    [[ ${#missing[@]} -gt 0 ]] || return 0

    info "Installing packages: ${missing[*]}"
    cmd_desc="${PKG_MANAGER} install ${missing[*]}"

    case "$PKG_MANAGER" in
        apt-get)
            export DEBIAN_FRONTEND=noninteractive
            if ! apt-get update -y; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: apt-get update -y"
            fi
            if ! apt-get install -y --no-install-recommends "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        dnf)
            if ! dnf install -y "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        yum)
            if ! yum install -y "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        pacman)
            if ! pacman -Sy --noconfirm --needed "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        zypper)
            if ! zypper --non-interactive install -y "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        apk)
            if ! apk add --no-cache "${missing[@]}"; then
                die "Package install failed on ${OS_PRETTY_NAME} (${PKG_MANAGER}). Failed command: ${cmd_desc}"
            fi
            ;;
        *)
            die "Unsupported package manager: ${PKG_MANAGER}"
            ;;
    esac
}

base_packages_for_os() {
    case "$PKG_MANAGER" in
        apt-get)
            printf '%s\n' curl ca-certificates openssl coreutils ncurses-bin nano sed grep util-linux bash iproute2
            ;;
        dnf|yum)
            printf '%s\n' curl ca-certificates openssl coreutils ncurses nano sed grep util-linux bash iproute
            ;;
        pacman)
            printf '%s\n' curl ca-certificates openssl coreutils ncurses nano sed grep util-linux bash iproute2
            ;;
        zypper)
            printf '%s\n' curl ca-certificates openssl coreutils ncurses-utils nano sed grep util-linux bash iproute2
            ;;
        apk)
            printf '%s\n' curl ca-certificates openssl coreutils ncurses nano sed grep util-linux bash iproute2
            ;;
        *)
            die "Unsupported package manager: ${PKG_MANAGER}"
            ;;
    esac
}

install_base_packages() {
    local -a pkgs=()
    local line

    info "Bootstrapping base packages for ${OS_PRETTY_NAME} (${PKG_MANAGER})..."
    while IFS= read -r line; do
        [[ -n "$line" ]] && pkgs+=("$line")
    done < <(base_packages_for_os)

    run_pkg_install "${pkgs[@]}"

    for cmd in curl openssl sed grep; do
        command -v "$cmd" &>/dev/null || die "Required command '${cmd}' is missing after package install on ${OS_PRETTY_NAME}."
    done

    ok "Base packages ready."
}

bootstrap() {
    elevate_if_needed "$@"
    require_root
    detect_os
    install_base_packages
    ensure_manager_command
}

# ── Docker install ─────────────────────────────────────────────────────────────
docker_compose_available() {
    docker compose version &>/dev/null || command -v docker-compose &>/dev/null
}

docker_engine_ready() {
    command -v docker &>/dev/null && docker version &>/dev/null
}

start_docker_daemon() {
    if command -v systemctl &>/dev/null; then
        systemctl enable docker >/dev/null 2>&1 || true
        systemctl start docker 2>/dev/null || systemctl restart docker 2>/dev/null || true
        return 0
    fi
    if command -v rc-update &>/dev/null; then
        rc-update add docker default >/dev/null 2>&1 || true
        if command -v rc-service &>/dev/null; then
            rc-service docker start 2>/dev/null || true
        elif command -v service &>/dev/null; then
            service docker start 2>/dev/null || true
        fi
        return 0
    fi
    if command -v service &>/dev/null; then
        service docker start 2>/dev/null || true
    fi
}

wait_for_docker_daemon() {
    local i=0
    local max=30
    local log_out=""

    info "Waiting for Docker daemon..."
    while (( i < max )); do
        if docker info &>/dev/null; then
            ok "Docker daemon is ready."
            return 0
        fi
        sleep 1
        i=$((i + 1))
    done

    err "Docker daemon did not become ready."
    if command -v systemctl &>/dev/null; then
        log_out="$(systemctl status docker --no-pager 2>&1 || true)"
        [[ -n "$log_out" ]] && echo "$log_out" >&2
        log_out="$(journalctl -u docker -n 40 --no-pager 2>&1 || true)"
        [[ -n "$log_out" ]] && echo "$log_out" >&2
    elif command -v rc-service &>/dev/null; then
        rc-service docker status >&2 || true
    fi
    die "Docker daemon is not running. Fix Docker, then retry."
}

verify_docker_stack() {
    command -v docker &>/dev/null || die "docker command not found after install."
    docker version >/dev/null || die "docker version failed. Docker Engine is not usable."
    if docker compose version &>/dev/null; then
        ok "Docker Compose V2 available: $(docker compose version --short 2>/dev/null || docker compose version | head -1)"
    elif command -v docker-compose &>/dev/null; then
        warn "Only legacy docker-compose found; Compose V2 (docker compose) is preferred."
        docker-compose version >/dev/null || die "docker-compose is present but not working."
    else
        die "Docker Compose not found. Need 'docker compose' (V2) or docker-compose."
    fi
    wait_for_docker_daemon
    docker info >/dev/null || die "docker info failed after daemon start."
}

install_docker_via_get_docker() {
    local tmp
    tmp="$(mktemp)"
    info "Installing Docker Engine via get.docker.com..."
    if ! curl_download "https://get.docker.com" "$tmp"; then
        rm -f "$tmp"
        explain_network_failure "download get.docker.com"
        exit 1
    fi
    if ! sh "$tmp"; then
        rm -f "$tmp"
        die "get.docker.com installer failed on ${OS_PRETTY_NAME}."
    fi
    rm -f "$tmp"
}

try_install_packages_soft() {
    local -a pkgs=("$@")
    [[ ${#pkgs[@]} -gt 0 ]] || return 0
    case "$PKG_MANAGER" in
        apt-get)
            export DEBIAN_FRONTEND=noninteractive
            apt-get install -y --no-install-recommends "${pkgs[@]}" 2>/dev/null
            ;;
        dnf)
            dnf install -y "${pkgs[@]}" 2>/dev/null
            ;;
        yum)
            yum install -y "${pkgs[@]}" 2>/dev/null
            ;;
        pacman)
            pacman -Sy --noconfirm --needed "${pkgs[@]}" 2>/dev/null
            ;;
        zypper)
            zypper --non-interactive install -y "${pkgs[@]}" 2>/dev/null
            ;;
        apk)
            apk add --no-cache "${pkgs[@]}" 2>/dev/null
            ;;
        *)
            return 1
            ;;
    esac
}

install_docker_compose_plugin_fallback() {
    if docker compose version &>/dev/null; then
        return 0
    fi

    info "Installing Docker Compose plugin (fallback)..."
    case "$PKG_MANAGER" in
        apt-get)
            export DEBIAN_FRONTEND=noninteractive
            apt-get update -y >/dev/null 2>&1 || true
            try_install_packages_soft docker-compose-plugin \
                || try_install_packages_soft docker-compose \
                || true
            ;;
        dnf|yum|zypper)
            try_install_packages_soft docker-compose-plugin \
                || try_install_packages_soft docker-compose \
                || true
            ;;
        pacman)
            try_install_packages_soft docker-compose || true
            ;;
        apk)
            try_install_packages_soft docker-cli-compose \
                || try_install_packages_soft docker-compose \
                || true
            ;;
    esac
}

install_docker() {
    if docker_engine_ready && docker_compose_available && docker info &>/dev/null; then
        ok "Docker and Docker Compose are already installed."
        verify_docker_stack
        return 0
    fi

    info "Installing Docker Engine and Compose for ${OS_PRETTY_NAME}..."

    case "$PKG_MANAGER" in
        apt-get|dnf|yum|zypper)
            # Official convenience script installs Docker CE + compose plugin on these families.
            install_docker_via_get_docker
            ;;
        pacman)
            run_pkg_install docker docker-compose
            ;;
        apk)
            run_pkg_install docker docker-cli-compose
            ;;
        *)
            die "Automatic Docker install is not supported with ${PKG_MANAGER} on ${OS_PRETTY_NAME}."
            ;;
    esac

    start_docker_daemon
    install_docker_compose_plugin_fallback
    verify_docker_stack
    ok "Docker installed."
}

# ── Preflight checks ───────────────────────────────────────────────────────────
check_disk_space() {
    local target avail_kb avail_mb
    target="$CONFIG_DIR"
    [[ -d "$target" ]] || target="$(dirname "$CONFIG_DIR")"
    [[ -d "$target" ]] || target="/"

    avail_kb="$(df -Pk "$target" 2>/dev/null | awk 'NR==2 {print $4}')"
    avail_kb="${avail_kb:-0}"
    avail_mb=$((avail_kb / 1024))

    if (( avail_mb < MIN_DISK_MB )); then
        die "Insufficient disk space on ${target}: ${avail_mb}MB free, need at least ${MIN_DISK_MB}MB."
    fi
    ok "Disk space OK (${avail_mb}MB free)."
}

port_in_use() {
    local port="$1"
    if command -v ss &>/dev/null; then
        if ss -ltn 2>/dev/null | grep -qE ":${port}\\s"; then
            return 0
        fi
        return 1
    fi
    if command -v netstat &>/dev/null; then
        if netstat -ltn 2>/dev/null | grep -qE ":${port}\\s"; then
            return 0
        fi
        return 1
    fi
    return 1
}

check_required_ports() {
    local port
    local -a ports=("$FASTAPI_PORT_DEFAULT" "$REDIS_PORT" "$MARIADB_PORT" "$PHPMYADMIN_PORT")
    local busy=0
    local mode="${1:-}"

    for port in "${ports[@]}"; do
        if ! port_in_use "$port"; then
            continue
        fi
        # Allow reinstall when our own containers already own the ports.
        if command -v docker &>/dev/null; then
            if docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -qE "pasarguardbot.*:${port}->|:.*:${port}->"; then
                continue
            fi
        fi
        # Allow reinstall when our own native systemd units already own the ports.
        if [[ "$mode" == "native" ]] || is_native_mode; then
            if systemctl is-active --quiet pasarguardbot.service 2>/dev/null \
                || systemctl is-active --quiet pasarguardbot-redis.service 2>/dev/null \
                || systemctl is-active --quiet pasarguardbot-mariadb.service 2>/dev/null \
                || systemctl is-active --quiet pasarguardbot-phpmyadmin.service 2>/dev/null; then
                if ss -ltnp 2>/dev/null | grep -E ":${port}\\s" | grep -qE 'pasarguardbot|mysqld|mariadbd|redis-server|php'; then
                    continue
                fi
            fi
        fi
        warn "Port ${port} appears to be in use."
        busy=1
    done

    if (( busy )); then
        warn "Required ports may be occupied (${FASTAPI_PORT_DEFAULT} FastAPI, ${REDIS_PORT} Redis, ${MARIADB_PORT} MariaDB, ${PHPMYADMIN_PORT} phpMyAdmin)."
        read -r -p "Continue anyway? (y/N): " confirm || true
        [[ "${confirm,,}" == "y" ]] || die "Aborted due to occupied ports."
    fi
    return 0
}

ensure_config_dirs() {
    mkdir -p "$CONFIG_DIR"/{logs,sessions,data/mariadb,data/redis,conf,run,app,phpmyadmin}
    # 755 so service users (mysql) can traverse; secrets stay in .env mode 600.
    chmod 755 "$CONFIG_DIR"
    chmod 755 "$RUN_DIR" "$CONF_DIR" "${CONFIG_DIR}/data" 2>/dev/null || true
    chmod 750 "${CONFIG_DIR}/data/mariadb" "${CONFIG_DIR}/data/redis" 2>/dev/null || true
    if [[ -f "$ENV_FILE" ]]; then
        chmod 600 "$ENV_FILE" || true
    fi
    return 0
}

configure_native_mariadb_apparmor() {
    local profile="" local_file="" marker="# pasarguardbot-native"

    command -v apparmor_parser &>/dev/null || return 0

    if [[ -f /etc/apparmor.d/usr.sbin.mariadbd ]]; then
        profile="/etc/apparmor.d/usr.sbin.mariadbd"
        local_file="/etc/apparmor.d/local/usr.sbin.mariadbd"
    elif [[ -f /etc/apparmor.d/usr.sbin.mysqld ]]; then
        profile="/etc/apparmor.d/usr.sbin.mysqld"
        local_file="/etc/apparmor.d/local/usr.sbin.mysqld"
    else
        return 0
    fi

    info "Allowing MariaDB AppArmor access to ${CONFIG_DIR}..."
    mkdir -p /etc/apparmor.d/local
    touch "$local_file"

    if ! grep -qF "$marker" "$local_file" 2>/dev/null; then
        cat >>"$local_file" <<EOF

${marker}
${CONFIG_DIR}/ r,
${CONFIG_DIR}/** r,
${CONFIG_DIR}/data/mariadb/ r,
${CONFIG_DIR}/data/mariadb/** rwk,
${CONFIG_DIR}/run/ r,
${CONFIG_DIR}/run/** rwk,
${CONF_DIR}/ r,
${CONF_DIR}/** r,
EOF
    fi

    if ! apparmor_parser -r "$profile" 2>/dev/null; then
        warn "Could not reload AppArmor profile ${profile}; MariaDB may still hit Permission denied."
        warn "If init fails, run: aa-complain ${profile}  OR  systemctl reload apparmor"
    else
        ok "AppArmor profile updated for isolated MariaDB datadir."
    fi
}

init_native_mariadb_datadir() {
    local install_db
    local mysql_user="mysql"

    id -u "$mysql_user" &>/dev/null || die "System user '${mysql_user}' not found (install mariadb-server first)."

    mkdir -p "${CONFIG_DIR}/data/mariadb" "$RUN_DIR"
    chmod 755 "$CONFIG_DIR"
    chmod 1777 "$RUN_DIR" 2>/dev/null || chmod 755 "$RUN_DIR"
    configure_native_mariadb_apparmor

    if [[ -d "${CONFIG_DIR}/data/mariadb/mysql" ]]; then
        chown -R "${mysql_user}:${mysql_user}" "${CONFIG_DIR}/data/mariadb"
        chmod 750 "${CONFIG_DIR}/data/mariadb"
        ok "MariaDB datadir already initialized."
        return 0
    fi

    install_db="$(find_mariadb_install_db)" || die "mariadb-install-db not found."
    info "Initializing isolated MariaDB datadir..."

    # Clear any partial failed init (often left as root-owned files).
    find "${CONFIG_DIR}/data/mariadb" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
    chown -R "${mysql_user}:${mysql_user}" "${CONFIG_DIR}/data/mariadb"
    chmod 750 "${CONFIG_DIR}/data/mariadb"

    if ! "$install_db" --user="$mysql_user" --datadir="${CONFIG_DIR}/data/mariadb"; then
        warn "Primary mariadb-install-db failed; retrying with basedir..."
        if ! "$install_db" --user="$mysql_user" --basedir=/usr --datadir="${CONFIG_DIR}/data/mariadb"; then
            err "Failed to initialize MariaDB datadir."
            err "Check ownership (must be mysql:mysql) and AppArmor for custom datadir under ${CONFIG_DIR}."
            die "Failed to initialize MariaDB datadir."
        fi
    fi
    chown -R "${mysql_user}:${mysql_user}" "${CONFIG_DIR}/data/mariadb"
    ok "MariaDB datadir initialized."
}

# ── Version / status (no network in menu) ──────────────────────────────────────
get_installed_bot_version() {
    local mode version revision digest short_id pyproject

    mode="$(get_install_mode)"
    if [[ "$mode" == "native" ]]; then
        pyproject="${APP_DIR}/pyproject.toml"
        if [[ -f "$pyproject" ]]; then
            version="$(grep -m1 '^version[[:space:]]*=' "$pyproject" | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
            if [[ -n "$version" ]]; then
                format_version "$version"
                return 0
            fi
        fi
        if [[ -d "${APP_DIR}/.git" ]] && command -v git &>/dev/null; then
            version="$(git -C "$APP_DIR" describe --tags --always 2>/dev/null || true)"
            if [[ -n "$version" ]]; then
                format_version "$version"
                return 0
            fi
        fi
        printf '%s' '—'
        return 0
    fi

    if ! command -v docker &>/dev/null; then
        printf '%s' '—'
        return 0
    fi

    if ! docker image inspect "${BOT_IMAGE}:$(get_bot_image_tag)" &>/dev/null; then
        printf '%s' '—'
        return 0
    fi

    version="$(docker image inspect "${BOT_IMAGE}:$(get_bot_image_tag)" \
        --format '{{index .Config.Labels "org.opencontainers.image.version"}}' 2>/dev/null || true)"
    if [[ -n "$version" && "$version" != "<no value>" && "$version" != "null" ]]; then
        format_version "$version"
        return 0
    fi

    revision="$(docker image inspect "${BOT_IMAGE}:$(get_bot_image_tag)" \
        --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true)"
    if [[ -n "$revision" && "$revision" != "<no value>" && "$revision" != "null" ]]; then
        printf 'sha-%s' "${revision:0:7}"
        return 0
    fi

    digest="$(docker image inspect "${BOT_IMAGE}:$(get_bot_image_tag)" \
        --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' 2>/dev/null || true)"
    if [[ -n "$digest" && "$digest" == *"@"* ]]; then
        printf '%s' "${digest##*@}"
        return 0
    fi

    short_id="$(docker image inspect "${BOT_IMAGE}:$(get_bot_image_tag)" \
        --format '{{.Id}}' 2>/dev/null | sed 's/^sha256://' | cut -c1-12 || true)"
    if [[ -n "$short_id" ]]; then
        printf '%s' "$short_id"
        return 0
    fi

    printf '%s' '—'
}

detect_server_ip() {
    local ip=""
    ip="$(curl_get --max-time 5 https://api.ipify.org 2>/dev/null || true)"
    if [[ -z "$ip" ]]; then
        ip="$(curl_get --max-time 5 https://ifconfig.me 2>/dev/null || true)"
    fi
    if [[ -z "$ip" ]]; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    [[ -n "$ip" ]] || ip="YOUR_SERVER_IP"
    printf '%s' "$ip"
}

show_service_urls() {
    [[ -f "$ENV_FILE" ]] || return 0

    local ip fastapi_port webhook_secret webhook_url pma_url
    ip="$(detect_server_ip)"
    fastapi_port="$(get_env_value "FASTAPI_PORT")"
    fastapi_port="${fastapi_port:-$FASTAPI_PORT_DEFAULT}"
    webhook_secret="$(get_env_value "WEBHOOK_SECRET")"
    webhook_url="http://${ip}:${fastapi_port}/api/webhook"
    pma_url="http://${ip}:${PHPMYADMIN_PORT}"

    echo
    info "Webhook (set in Pasarguard panel):"
    echo -e "  ${C_DIM}URL:${C_RESET}     ${webhook_url}"
    if [[ -n "$webhook_secret" ]]; then
        echo -e "  ${C_DIM}Header:${C_RESET}  x-webhook-secret: ${webhook_secret}"
    else
        warn "WEBHOOK_SECRET not found in ${ENV_FILE}"
    fi
    echo
    info "phpMyAdmin:"
    echo -e "  ${C_DIM}URL:${C_RESET}  ${pma_url}"
    echo
    warn "Replace the IP with your domain if you use one."
}

get_container_state() {
    local name="$1"
    docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || printf '%s' 'missing'
}

get_bot_runtime_summary() {
    local running total bot_state mode active
    mode="$(get_install_mode)"

    if ! is_installed; then
        printf '%s' '—'
        return 0
    fi

    if [[ "$mode" == "native" ]]; then
        if systemctl is-active --quiet pasarguardbot.service 2>/dev/null; then
            printf '%s' 'active (systemd)'
        elif systemctl is-failed --quiet pasarguardbot.service 2>/dev/null; then
            printf '%s' 'failed (systemd)'
        else
            active="$(systemctl is-active pasarguardbot.service 2>/dev/null || printf '%s' 'inactive')"
            printf '%s (systemd)' "$active"
        fi
        return 0
    fi

    if ! command -v docker &>/dev/null; then
        printf '%s' '—'
        return 0
    fi
    if ! docker info &>/dev/null; then
        printf '%s' 'docker unavailable'
        return 0
    fi
    running="$(docker_compose ps --status running -q 2>/dev/null | wc -l | tr -d ' ' || true)"
    total="$(docker_compose ps -a -q 2>/dev/null | wc -l | tr -d ' ' || true)"
    running="${running:-0}"
    total="${total:-0}"
    bot_state="$(get_container_state pasarguardbot)"
    printf '%s (%s/%s services running)' "$bot_state" "$running" "$total"
}

show_install_info() {
    local installed_ver bot_runtime fastapi_port mode

    echo -e "  ${C_DIM}Manager script:${C_RESET}  $(format_version "$SCRIPT_VERSION")"
    echo -e "  ${C_DIM}Host OS:${C_RESET}         ${OS_PRETTY_NAME:-unknown}"

    if is_installed; then
        mode="$(get_install_mode)"
        installed_ver="$(get_installed_bot_version)" || installed_ver="—"
        bot_runtime="$(get_bot_runtime_summary)" || bot_runtime="—"
        fastapi_port="$(get_env_value "FASTAPI_PORT")"
        fastapi_port="${fastapi_port:-$FASTAPI_PORT_DEFAULT}"

        echo -e "  ${C_DIM}Install mode:${C_RESET}    ${mode:-unknown}"
        echo -e "  ${C_DIM}Branch:${C_RESET}         $(get_repo_branch)"
        echo -e "  ${C_DIM}Bot version:${C_RESET}     ${installed_ver}"
        echo -e "  ${C_DIM}Bot runtime:${C_RESET}     ${bot_runtime}"
        echo -e "  ${C_DIM}API port:${C_RESET}        ${fastapi_port}"
        echo -e "  ${C_DIM}Config:${C_RESET}          ${CONFIG_DIR}"
    fi
    echo
}

draw_banner() {
    safe_clear
    echo -e "${C_CYAN}${C_BOLD}PasarguardBot${C_RESET} ${C_DIM}— manager $(format_version "$SCRIPT_VERSION")${C_RESET}"
    echo
    show_install_info || true
}

draw_menu() {
    local mode
    mode="$(get_install_mode)"
    draw_banner
    if is_installed; then
        echo -e "  ${C_GREEN}●${C_RESET} Status: ${C_GREEN}Installed${C_RESET} ${C_DIM}(${mode:-unknown})${C_RESET}"
    else
        echo -e "  ${C_RED}●${C_RESET} Status: ${C_RED}Not installed${C_RESET}"
    fi
    echo
    echo -e "${C_BOLD}  ┌─────────────────────────────────────────┐${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  1) Install bot                           ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  2) Uninstall bot                         ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  3) Update bot                            ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  4) View logs                             ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  5) Edit .env file                        ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  6) Full restart                          ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  7) Service status                        ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  8) Show webhook & URLs                   ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  │${C_RESET}  9) Update manager script                 ${C_BOLD}│${C_RESET}"
    if [[ "$mode" == "native" ]]; then
        echo -e "${C_BOLD}  │${C_RESET} ${C_DIM}10) Fix Docker network (Docker only)      ${C_RESET}${C_BOLD}│${C_RESET}"
    else
        echo -e "${C_BOLD}  │${C_RESET} 10) Fix Docker network                     ${C_BOLD}│${C_RESET}"
    fi
    echo -e "${C_BOLD}  │${C_RESET}  0) Exit                                   ${C_BOLD}│${C_RESET}"
    echo -e "${C_BOLD}  └─────────────────────────────────────────┘${C_RESET}"
    echo
}

# ── Env generation ────────────────────────────────────────────────────────────
prompt_required() {
    local _var_name="$1"
    local prompt_text="$2"
    local value=""
    while [[ -z "$value" ]]; do
        read -r -p "$prompt_text: " value || true
        value="${value// /}"
        [[ -n "$value" ]] || warn "This value is required."
    done
    printf '%s' "$value"
}

prompt_with_default() {
    local prompt_text="$1"
    local default_value="$2"
    local value=""
    read -r -p "${prompt_text} [${default_value}]: " value || true
    value="${value// /}"
    if [[ -z "$value" ]]; then
        value="$default_value"
    fi
    printf '%s' "$value"
}

append_mariadb_vars() {
    local db_pass="$1"
    local db_root_pass="$2"

    set_env_var "$ENV_FILE" "MARIADB_ROOT_PASSWORD" "$db_root_pass"
    set_env_var "$ENV_FILE" "MARIADB_DATABASE" "pasarguardbot"
    set_env_var "$ENV_FILE" "MARIADB_USER" "pasarguardbot"
    set_env_var "$ENV_FILE" "MARIADB_PASSWORD" "$db_pass"
}

append_deploy_paths() {
    set_env_var "$ENV_FILE" "PASARGUARDBOT_CONFIG_DIR" "$CONFIG_DIR"
}

generate_env_file() {
    local install_mode="${1:-docker}"
    local branch="${2:-$(get_repo_branch)}"
    local api_id api_hash bot_token admin_id
    local db_pass db_root_pass webhook_secret crypto_key
    local tmp db_host redis_url env_url

    if [[ -f "$ENV_FILE" ]]; then
        warn ".env already exists — keeping the existing file."
        chmod 600 "$ENV_FILE" 2>/dev/null || true
        set_install_mode "$install_mode"
        set_install_branch "$branch"
        return 0
    fi

    ensure_config_dirs
    env_url="$(env_example_raw_url_for_branch "$branch")"

    tmp="$(mktemp)"
    info "Downloading .env.example from GitHub (${branch})..."
    if ! curl_download "$env_url" "$tmp"; then
        rm -f "$tmp"
        explain_network_failure "download .env.example"
        exit 1
    fi
    if [[ ! -s "$tmp" ]] || ! grep -q '^API_ID=' "$tmp"; then
        rm -f "$tmp"
        die "Downloaded .env.example is empty or invalid."
    fi

    echo
    info "Enter your Telegram credentials:"
    api_id=$(prompt_with_default "  API_ID (from my.telegram.org)" "2040")
    api_hash=$(prompt_with_default "  API_HASH" "b18441a1ff607e10a989891a5462e627")
    bot_token=$(prompt_required "BOT_TOKEN" "  BOT_TOKEN (from @BotFather)")
    admin_id=$(prompt_required "ADMIN_ID" "  ADMIN_ID (numeric Telegram user ID)")

    db_pass="$(rand_b64 24)"
    db_root_pass="$(rand_b64 32)"
    webhook_secret="$(rand_hex 16)"
    crypto_key="$(rand_b64 32)"

    if [[ "$install_mode" == "native" ]]; then
        db_host="127.0.0.1:${MARIADB_PORT}"
        redis_url="redis://127.0.0.1:${REDIS_PORT}/0"
    else
        db_host="mariadb:3306"
        redis_url="redis://redis:6379/0"
    fi

    cp "$tmp" "$ENV_FILE"
    rm -f "$tmp"
    chmod 600 "$ENV_FILE"

    set_env_var "$ENV_FILE" "API_ID" "$api_id"
    set_env_var "$ENV_FILE" "API_HASH" "$api_hash"
    set_env_var "$ENV_FILE" "BOT_TOKEN" "$bot_token"
    set_env_var "$ENV_FILE" "ADMIN_ID" "$admin_id"
    set_env_var "$ENV_FILE" "SQLALCHEMY_DATABASE_URL" "mysql+asyncmy://pasarguardbot:${db_pass}@${db_host}/pasarguardbot"
    set_env_var "$ENV_FILE" "FASTAPI_PORT" "$FASTAPI_PORT_DEFAULT"
    set_env_var "$ENV_FILE" "WEBHOOK_SECRET" "$webhook_secret"
    set_env_var "$ENV_FILE" "CRYPTO_KEY" "$crypto_key"
    set_env_var "$ENV_FILE" "REDIS_URL" "$redis_url"
    set_env_var "$ENV_FILE" "REDIS_NAMESPACE_PREFIX" "pasarguardbot:mainbot"
    set_env_var "$ENV_FILE" "TELETHON_SESSION_PATH" "sessions/KenzoSession"
    set_env_var "$ENV_FILE" "LOG_DIR" "./logs"
    set_env_var "$ENV_FILE" "LOG_TO_FILE" "true"
    set_env_var "$ENV_FILE" "LOG_LEVEL" "INFO"
    set_env_var "$ENV_FILE" "PASARGUARDBOT_IMAGE_TAG" "$(bot_image_tag_for_branch "$branch")"
    append_mariadb_vars "$db_pass" "$db_root_pass"
    append_deploy_paths
    set_install_mode "$install_mode"
    set_install_branch "$branch"

    chmod 600 "$ENV_FILE"

    ok ".env created at ${ENV_FILE}"
    echo
    info "Database credentials (saved in .env):"
    echo -e "  ${C_DIM}Database:${C_RESET} pasarguardbot"
    echo -e "  ${C_DIM}User:${C_RESET}     pasarguardbot"
    echo -e "  ${C_DIM}Password:${C_RESET} ${db_pass}"
    echo -e "  ${C_DIM}Root:${C_RESET}     ${db_root_pass}"
}

# ── Compose download & validation ──────────────────────────────────────────────
validate_compose_file() {
    local file="$1"

    [[ -s "$file" ]] || {
        err "Compose file is empty."
        return 1
    }
    grep -qE 'ghcr\.io/amirkenzo/pasarguardbot(:|\$\{)' "$file" || {
        err "Compose file missing required image ghcr.io/amirkenzo/pasarguardbot"
        return 1
    }
    if grep -E '^\s+build:' "$file" >/dev/null 2>&1; then
        err "Production Compose must not contain build: for services."
        return 1
    fi
    return 0
}

setup_compose() {
    local tmp
    local branch="${1:-$(get_repo_branch)}"
    local compose_url

    ensure_config_dirs
    tmp="$(mktemp)"
    compose_url="$(compose_raw_url_for_branch "$branch")"

    info "Downloading production docker-compose.yml from GitHub (${branch})..."
    if ! curl_download "$compose_url" "$tmp"; then
        rm -f "$tmp"
        explain_network_failure "download docker-compose.yml"
        exit 1
    fi

    if ! validate_compose_file "$tmp"; then
        rm -f "$tmp"
        die "Downloaded docker-compose.yml failed validation."
    fi

    # Validate with docker compose config when .env exists (or create a stub for config check).
    if [[ -f "$ENV_FILE" ]]; then
        if ! docker compose --project-directory "$CONFIG_DIR" -f "$tmp" --env-file "$ENV_FILE" config >/dev/null; then
            rm -f "$tmp"
            die "docker compose config failed for downloaded Compose file (invalid YAML or references)."
        fi
    fi

    cp "$tmp" "$COMPOSE_FILE"
    rm -f "$tmp"
    apply_bot_image_tag_for_branch "$branch"
    ok "docker-compose.yml updated at ${COMPOSE_FILE} (image tag: $(bot_image_tag_for_branch "$branch"))"
}

pull_images() {
    info "Pulling Docker images..."
    if ! docker_compose pull; then
        err "Failed to pull one or more images."
        err "If the bot image fails: check GHCR availability and that your CPU architecture is supported (amd64/arm64)."
        die "docker compose pull failed."
    fi
    ok "Images pulled."
}

wait_for_containers_healthy() {
    local i=0
    local max=90
    local bot_state

    info "Waiting for containers..."
    while (( i < max )); do
        bot_state="$(get_container_state pasarguardbot)"
        if [[ "$bot_state" == "running" ]]; then
            ok "Bot container is running."
            return 0
        fi
        sleep 2
        i=$((i + 2))
    done

    warn "Timed out waiting for bot container. Current status:"
    docker_compose ps || true
    return 1
}

cleanup_stale_named_containers() {
    # Only remove known PasarguardBot container names (not unrelated resources).
    docker rm -f pasarguardbot-redis pasarguardbot-mariadb pasarguardbot-phpmyadmin pasarguardbot 2>/dev/null || true
}

prune_dangling_images_safe() {
    # Only dangling images; never prune volumes or running containers.
    docker image prune -f >/dev/null 2>&1 || true
}

install_manager_from_file() {
    local src="$1"
    head -1 "$src" | grep -q '#!/usr/bin/env bash' || {
        die "Manager script is invalid (missing bash shebang)."
    }
    mkdir -p "$CONFIG_DIR"
    cp "$src" "$MANAGER_SCRIPT"
    chmod +x "$MANAGER_SCRIPT"
    ln -sf "$MANAGER_SCRIPT" "$MANAGER_BIN"
    hash -r 2>/dev/null || true
    sync_netplan_fix_script || true
}

sync_netplan_fix_script() {
    local src_dir tmp

    src_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || src_dir=""
    if [[ -n "$src_dir" && -r "${src_dir}/${NETPLAN_FIX_SCRIPT_NAME}" ]]; then
        mkdir -p "$CONFIG_DIR"
        cp "${src_dir}/${NETPLAN_FIX_SCRIPT_NAME}" "$NETPLAN_FIX_INSTALLED"
        chmod +x "$NETPLAN_FIX_INSTALLED"
        return 0
    fi

    tmp="$(mktemp)"
    if curl_download "$NETPLAN_FIX_RAW_URL" "$tmp"; then
        head -1 "$tmp" | grep -q '#!/usr/bin/env bash' || {
            rm -f "$tmp"
            warn "Downloaded ${NETPLAN_FIX_SCRIPT_NAME} is invalid."
            return 1
        }
        mkdir -p "$CONFIG_DIR"
        cp "$tmp" "$NETPLAN_FIX_INSTALLED"
        chmod +x "$NETPLAN_FIX_INSTALLED"
        rm -f "$tmp"
        return 0
    fi

    rm -f "$tmp"
    warn "Could not sync ${NETPLAN_FIX_SCRIPT_NAME} to ${CONFIG_DIR}."
    return 1
}

resolve_netplan_fix_script() {
    local src_dir script tmp

    src_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || src_dir=""
    if [[ -n "$src_dir" && -r "${src_dir}/${NETPLAN_FIX_SCRIPT_NAME}" ]]; then
        printf '%s' "${src_dir}/${NETPLAN_FIX_SCRIPT_NAME}"
        return 0
    fi

    if [[ -r "$NETPLAN_FIX_INSTALLED" ]]; then
        printf '%s' "$NETPLAN_FIX_INSTALLED"
        return 0
    fi

    tmp="$(mktemp)"
    info "Downloading ${NETPLAN_FIX_SCRIPT_NAME} from GitHub..."
    if ! curl_download "$NETPLAN_FIX_RAW_URL" "$tmp"; then
        rm -f "$tmp"
        return 1
    fi
    if ! head -1 "$tmp" | grep -q '#!/usr/bin/env bash'; then
        rm -f "$tmp"
        return 1
    fi
    chmod +x "$tmp"
    printf '%s' "$tmp"
}

confirm_yes() {
    local prompt="${1:-Continue?}"
    local confirm=""
    read -r -p "${prompt} [y/N]: " confirm || true
    [[ "${confirm,,}" == "y" ]]
}

is_ubuntu_host() {
    [[ "$OS_ID" == "ubuntu" ]]
}

docker_network_precheck() {
    if ! is_ubuntu_host; then
        warn "Docker Bridge repair is supported only on Ubuntu."
        return 1
    fi
    if ! command -v docker &>/dev/null; then
        err "Docker is not installed."
        return 1
    fi
    if command -v systemctl &>/dev/null && ! systemctl is-active --quiet docker 2>/dev/null; then
        err "Docker is installed but not running."
        return 1
    fi
    return 0
}

run_netplan_fix_command() {
    local cmd="$1"
    local script="" status=0 cleanup_script=""
    local src_dir=""

    script="$(resolve_netplan_fix_script)" || {
        err "Could not find or download ${NETPLAN_FIX_SCRIPT_NAME}."
        return 1
    }

    src_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)" || src_dir=""
    if [[ "$script" != "$NETPLAN_FIX_INSTALLED" ]] \
        && [[ -z "$src_dir" || "$script" != "${src_dir}/${NETPLAN_FIX_SCRIPT_NAME}" ]]; then
        cleanup_script="$script"
    fi

    set +e
    PASARGUARDBOT_CONFIG_DIR="$CONFIG_DIR" bash "$script" "$cmd"
    status=$?
    set -e

    [[ -n "$cleanup_script" ]] && rm -f "$cleanup_script"
    return "$status"
}

handle_netplan_reboot_prompt() {
    if confirm_yes "Reboot the server now?"; then
        warn "Rebooting..."
        sync
        systemctl reboot
    else
        warn "Run \`reboot\` manually, then run PasarguardBot manager again."
    fi
}

handle_netplan_repair_exit() {
    local status="$1"

    case "$status" in
        0)
            ok "Docker Bridge networking is working or was repaired successfully."
            info "No server reboot is required."
            ;;
        10)
            ok "The network configuration was repaired."
            handle_netplan_reboot_prompt
            ;;
        20)
            err "This operating system or required tools are not supported."
            ;;
        21)
            err "The known Netplan wildcard file was not found."
            warn "The Docker Bridge issue may have a different cause."
            ;;
        30)
            err "Could not download the Docker test image."
            warn "Check internet connectivity and Docker registry access."
            ;;
        40)
            warn "Automatic repair was refused to keep the network safe."
            info "No changes were made."
            ;;
        41)
            err "Netplan validation failed; the script attempted to roll back."
            ;;
        50)
            err "Rollback of the repair attempt failed."
            ;;
        *)
            err "Unexpected exit code from ${NETPLAN_FIX_SCRIPT_NAME}: ${status}"
            ;;
    esac
}

handle_netplan_check_exit() {
    local status="$1"

    case "$status" in
        0)
            ok "Docker Bridge networking is healthy."
            ;;
        1)
            err "Docker Bridge test failed."
            ;;
        20)
            err "This operating system or required tools are not supported."
            ;;
        30)
            err "Could not download the Docker test image."
            warn "Check internet connectivity and Docker registry access."
            ;;
        *)
            err "Unexpected exit code from ${NETPLAN_FIX_SCRIPT_NAME}: ${status}"
            ;;
    esac
}

handle_netplan_rollback_exit() {
    local status="$1"

    case "$status" in
        0)
            ok "Netplan rollback completed."
            ;;
        10)
            ok "Original Netplan file restored."
            handle_netplan_reboot_prompt
            ;;
        20)
            err "This operating system or required tools are not supported."
            ;;
        50)
            err "No repair marker or disabled Netplan file was found."
            ;;
        *)
            err "Unexpected exit code from ${NETPLAN_FIX_SCRIPT_NAME}: ${status}"
            ;;
    esac
}

action_docker_network_check() {
    local status

    draw_banner
    docker_network_precheck || {
        pause
        return 0
    }

    info "Checking Docker Bridge networking..."
    echo
    run_netplan_fix_command check
    status=$?
    echo
    handle_netplan_check_exit "$status"
    pause
}

action_docker_network_repair() {
    local status

    draw_banner
    docker_network_precheck || {
        pause
        return 0
    }

    echo -e "${C_YELLOW}${C_BOLD}  ⚠  Repair Docker Bridge${C_RESET}"
    echo
    echo "  This operation checks Docker Bridge networking and may:"
    echo "  - back up and disable the broken Netplan wildcard file"
    echo "  - restart Docker"
    echo "  - require one server reboot"
    echo
    warn "Existing Docker containers may restart."
    echo
    confirm_yes "Continue?" || {
        info "Cancelled."
        pause
        return 0
    }

    echo
    info "Running Docker Bridge repair..."
    echo
    run_netplan_fix_command fix
    status=$?
    echo
    handle_netplan_repair_exit "$status"
    pause
}

action_docker_network_rollback() {
    local status

    draw_banner
    docker_network_precheck || {
        pause
        return 0
    }

    echo -e "${C_YELLOW}${C_BOLD}  ⚠  Rollback Netplan Repair${C_RESET}"
    echo
    echo "  This will restore the Netplan file disabled by the Docker network repair."
    echo "  A server reboot may be required."
    echo
    confirm_yes "Continue?" || {
        info "Cancelled."
        pause
        return 0
    }

    echo
    info "Rolling back Netplan repair..."
    echo
    run_netplan_fix_command rollback
    status=$?
    echo
    handle_netplan_rollback_exit "$status"
    pause
}

action_docker_network() {
    if is_native_mode; then
        draw_banner
        warn "Docker network tools are only available for Docker installs."
        pause
        return 0
    fi

    while true; do
        draw_banner
        echo -e "${C_BOLD}  Docker network${C_RESET}"
        echo
        echo "  1) Check Docker Bridge"
        echo "  2) Repair Docker Bridge"
        echo "  3) Rollback Netplan Repair"
        echo "  0) Back"
        echo
        read -r -p "Choice: " choice || return 0

        case "$choice" in
            1) action_docker_network_check ;;
            2) action_docker_network_repair ;;
            3) action_docker_network_rollback ;;
            0) return 0 ;;
            *) warn "Invalid choice."; sleep 1 ;;
        esac
    done
}

manager_command_ready() {
    [[ -x "$MANAGER_SCRIPT" && -e "$MANAGER_BIN" ]]
}

install_manager_command() {
    local tmp src="${BASH_SOURCE[0]:-}"

    # Prefer the script that is currently running (e.g. curl from dev),
    # so we do not overwrite it with an older copy from another branch.
    if [[ -n "$src" && -r "$src" && -s "$src" ]] && head -1 "$src" | grep -q '#!/usr/bin/env bash'; then
        info "Installing manager script from the running copy ($(format_version "$SCRIPT_VERSION"), branch=${REPO_BRANCH})..."
        install_manager_from_file "$src"
        ok "pasarguardbot command installed at ${MANAGER_BIN}"
        return 0
    fi

    tmp="$(mktemp)"
    info "Installing manager script from GitHub (${REPO_BRANCH})..."
    if ! curl_download "$SCRIPT_RAW_URL" "$tmp"; then
        rm -f "$tmp"
        explain_network_failure "download manager script"
        exit 1
    fi

    install_manager_from_file "$tmp"
    rm -f "$tmp"
    ok "pasarguardbot command installed at ${MANAGER_BIN}"
}

# Register /usr/local/bin/pasarguardbot when missing (e.g. first curl | bash run).
ensure_manager_command() {
    if manager_command_ready; then
        return 0
    fi

    local src="${BASH_SOURCE[0]:-}"
    if [[ -n "$src" && -r "$src" && -s "$src" ]]; then
        info "Registering pasarguardbot command..."
        install_manager_from_file "$src"
        ok "pasarguardbot command installed at ${MANAGER_BIN}"
        return 0
    fi

    install_manager_command
}

# ── Native install (no Docker) ─────────────────────────────────────────────────
find_mysqld_bin() {
    local candidate
    for candidate in mariadbd mysqld /usr/sbin/mariadbd /usr/sbin/mysqld; do
        if command -v "$candidate" &>/dev/null; then
            command -v "$candidate"
            return 0
        fi
        if [[ -x "$candidate" ]]; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

find_mariadb_install_db() {
    local candidate
    for candidate in mariadb-install-db mysql_install_db; do
        if command -v "$candidate" &>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

install_native_packages() {
    info "Installing native packages (isolated instances — system MariaDB/Redis defaults untouched)..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    run_pkg_install \
        mariadb-server \
        mariadb-client \
        redis-server \
        php-cli \
        php-mysqli \
        php-mbstring \
        php-xml \
        php-curl \
        php-zip \
        curl \
        ca-certificates \
        git \
        tar \
        build-essential \
        libffi-dev \
        libssl-dev \
        pkg-config

    # Leave any pre-existing system MariaDB/Redis services alone (they keep 3306/6379).
    # PasarguardBot uses isolated instances on 6162/6161 only.
    ok "Native packages ready."
}

write_native_redis_conf() {
    cat >"${CONF_DIR}/redis.conf" <<EOF
bind 127.0.0.1
protected-mode yes
port ${REDIS_PORT}
daemonize no
dir ${CONFIG_DIR}/data/redis
pidfile ${RUN_DIR}/redis.pid
logfile ""
save 60 1
loglevel warning
dbfilename dump.rdb
EOF
}

write_native_mariadb_conf() {
    # Socket lives inside datadir (owned by mysql) to avoid /run permission denials.
    cat >"${CONF_DIR}/mariadb.cnf" <<EOF
[mysqld]
user=mysql
basedir=/usr
datadir=${CONFIG_DIR}/data/mariadb
socket=${CONFIG_DIR}/data/mariadb/pasarguardbot.sock
pid-file=${CONFIG_DIR}/data/mariadb/pasarguardbot.pid
port=${MARIADB_PORT}
bind-address=127.0.0.1
character-set-server=utf8mb4
collation-server=utf8mb4_unicode_ci
skip-character-set-client-handshake
innodb_buffer_pool_size=128M
log_error=${CONFIG_DIR}/data/mariadb/error.log

[client]
# Do NOT set host=127.0.0.1 here — that forces TCP and breaks unix_socket root auth.
port=${MARIADB_PORT}
socket=${CONFIG_DIR}/data/mariadb/pasarguardbot.sock
EOF
    chmod 644 "${CONF_DIR}/mariadb.cnf"
    chown root:root "${CONF_DIR}/mariadb.cnf"
}

write_native_systemd_units() {
    local mysqld_bin uv_bin redis_bin
    mysqld_bin="$(find_mysqld_bin)" || die "mysqld/mariadbd not found after package install."
    uv_bin="$(command -v uv)" || die "uv not found after install."
    redis_bin="$(command -v redis-server)" || die "redis-server not found after package install."

    cat >/etc/systemd/system/pasarguardbot-redis.service <<EOF
[Unit]
Description=PasarguardBot Redis (isolated)
After=network.target

[Service]
Type=simple
ExecStart=${redis_bin} ${CONF_DIR}/redis.conf
Restart=on-failure
RestartSec=3
WorkingDirectory=${CONFIG_DIR}

[Install]
WantedBy=multi-user.target
EOF

    # AppArmorProfile=unconfined: Ubuntu AppArmor blocks custom datadirs outside /var/lib/mysql.
    cat >/etc/systemd/system/pasarguardbot-mariadb.service <<EOF
[Unit]
Description=PasarguardBot MariaDB (isolated)
After=network.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=mysql
Group=mysql
AppArmorProfile=unconfined
ExecStartPre=+/bin/mkdir -p ${RUN_DIR} ${CONFIG_DIR}/data/mariadb
ExecStartPre=+/bin/chown mysql:mysql ${CONFIG_DIR}/data/mariadb
ExecStartPre=+/bin/chmod 1777 ${RUN_DIR}
ExecStart=${mysqld_bin} --defaults-file=${CONF_DIR}/mariadb.cnf
Restart=on-failure
RestartSec=3
LimitNOFILE=65535
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

    cat >/etc/systemd/system/pasarguardbot-phpmyadmin.service <<EOF
[Unit]
Description=PasarguardBot phpMyAdmin
After=network.target pasarguardbot-mariadb.service
Wants=pasarguardbot-mariadb.service

[Service]
Type=simple
WorkingDirectory=${PHPMYADMIN_DIR}
ExecStart=/usr/bin/php -S 0.0.0.0:${PHPMYADMIN_PORT} -t ${PHPMYADMIN_DIR}
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

    cat >/etc/systemd/system/pasarguardbot.service <<EOF
[Unit]
Description=PasarguardBot
After=network.target pasarguardbot-mariadb.service pasarguardbot-redis.service
Wants=pasarguardbot-mariadb.service pasarguardbot-redis.service

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin
EnvironmentFile=-${ENV_FILE}
ExecStartPre=${uv_bin} run alembic upgrade head
ExecStart=${uv_bin} run main.py
Restart=on-failure
RestartSec=5
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
}

dump_native_mariadb_logs() {
    err "MariaDB service diagnostics:"
    systemctl status pasarguardbot-mariadb.service --no-pager -l 2>&1 | tail -n 40 || true
    echo
    journalctl -u pasarguardbot-mariadb -n 60 --no-pager 2>&1 || true
    if [[ -f "${CONFIG_DIR}/data/mariadb/error.log" ]]; then
        echo
        err "MariaDB error.log:"
        tail -n 40 "${CONFIG_DIR}/data/mariadb/error.log" || true
    fi
}

# Connect as OS root via unix socket (Ubuntu auth_socket). Avoid -h so we don't force TCP.
mariadb_socket_root() {
    local sock="${CONFIG_DIR}/data/mariadb/pasarguardbot.sock"
    if command -v mariadb &>/dev/null; then
        mariadb --socket="$sock" -u root "$@"
    else
        mysql --socket="$sock" -u root "$@"
    fi
}

mariadb_socket_root_check() {
    mariadb_socket_root -e "SELECT 1" &>/dev/null
}

wait_for_native_mariadb() {
    local i=0
    local max=90
    info "Waiting for isolated MariaDB on port ${MARIADB_PORT}..."

    while (( i < max )); do
        if systemctl is-failed --quiet pasarguardbot-mariadb.service 2>/dev/null; then
            dump_native_mariadb_logs
            die "pasarguardbot-mariadb.service failed to start."
        fi

        # Prefer unix_socket root auth (works as system root on Ubuntu).
        if [[ -S "${CONFIG_DIR}/data/mariadb/pasarguardbot.sock" ]] && mariadb_socket_root_check; then
            ok "MariaDB is ready (unix socket)."
            return 0
        fi

        # TCP up is a weaker signal; keep waiting for usable root socket auth.
        if bash -c "echo >/dev/tcp/127.0.0.1/${MARIADB_PORT}" 2>/dev/null; then
            if mariadb_socket_root_check; then
                ok "MariaDB is ready."
                return 0
            fi
        fi

        sleep 1
        i=$((i + 1))
        if (( i % 15 == 0 )); then
            warn "Still waiting for MariaDB... (${i}s) status=$(systemctl is-active pasarguardbot-mariadb.service 2>/dev/null || echo unknown)"
        fi
    done

    dump_native_mariadb_logs
    die "Isolated MariaDB did not become ready within ${max}s."
}

mariadb_admin_cli() {
    # Admin tasks always go through unix socket as root (auth_socket).
    mariadb_socket_root "$@"
}

setup_native_mariadb_user() {
    local db_pass db_root_pass
    db_pass="$(get_env_value "MARIADB_PASSWORD")"
    db_root_pass="$(get_env_value "MARIADB_ROOT_PASSWORD")"
    [[ -n "$db_pass" ]] || die "MARIADB_PASSWORD missing from .env"
    [[ -n "$db_root_pass" ]] || die "MARIADB_ROOT_PASSWORD missing from .env"

    info "Creating PasarguardBot database and user..."
    mariadb_socket_root_check || die "Cannot connect to MariaDB as root via unix socket."

    # Keep root@localhost on unix_socket for CLI; add password auth for TCP/phpMyAdmin.
    # MariaDB syntax requires USING PASSWORD(...), not BY '...', for VIA plugins.
    mariadb_admin_cli <<SQL
CREATE DATABASE IF NOT EXISTS pasarguardbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'pasarguardbot'@'127.0.0.1' IDENTIFIED BY '${db_pass}';
CREATE USER IF NOT EXISTS 'pasarguardbot'@'localhost' IDENTIFIED BY '${db_pass}';
ALTER USER 'pasarguardbot'@'127.0.0.1' IDENTIFIED BY '${db_pass}';
ALTER USER 'pasarguardbot'@'localhost' IDENTIFIED BY '${db_pass}';
GRANT ALL PRIVILEGES ON pasarguardbot.* TO 'pasarguardbot'@'127.0.0.1';
GRANT ALL PRIVILEGES ON pasarguardbot.* TO 'pasarguardbot'@'localhost';
CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${db_root_pass}';
ALTER USER 'root'@'127.0.0.1' IDENTIFIED BY '${db_root_pass}';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;
ALTER USER 'root'@'localhost' IDENTIFIED VIA unix_socket OR mysql_native_password USING PASSWORD('${db_root_pass}');
FLUSH PRIVILEGES;
SQL
    ok "Database user ready."
}

install_phpmyadmin_files() {
    local tmp tmpdir
    if [[ -f "${PHPMYADMIN_DIR}/index.php" ]]; then
        ok "phpMyAdmin already present."
        return 0
    fi

    info "Downloading phpMyAdmin..."
    tmp="$(mktemp)"
    tmpdir="$(mktemp -d)"
    if ! curl_download "$PHPMYADMIN_ARCHIVE_URL" "$tmp"; then
        rm -f "$tmp"
        rm -rf "$tmpdir"
        explain_network_failure "download phpMyAdmin"
        exit 1
    fi
    tar -xzf "$tmp" -C "$tmpdir"
    mkdir -p "$PHPMYADMIN_DIR"
    rm -rf "${PHPMYADMIN_DIR:?}/"*
    mv "$tmpdir"/phpMyAdmin-*-all-languages/* "$PHPMYADMIN_DIR"/
    rm -f "$tmp"
    rm -rf "$tmpdir"

    cat >"${PHPMYADMIN_DIR}/config.inc.php" <<EOF
<?php
\$cfg['blowfish_secret'] = '$(rand_hex 16)$(rand_hex 16)';
\$i = 0;
\$i++;
\$cfg['Servers'][\$i]['auth_type'] = 'cookie';
// Force TCP so root/password works (unix_socket root@localhost rejects phpMyAdmin).
\$cfg['Servers'][\$i]['host'] = '127.0.0.1';
\$cfg['Servers'][\$i]['port'] = '${MARIADB_PORT}';
\$cfg['Servers'][\$i]['connect_type'] = 'tcp';
\$cfg['Servers'][\$i]['compress'] = false;
\$cfg['Servers'][\$i]['AllowNoPassword'] = false;
\$cfg['UploadDir'] = '';
\$cfg['SaveDir'] = '';
EOF
    ok "phpMyAdmin installed at ${PHPMYADMIN_DIR}"
}

install_uv_binary() {
    if command -v uv &>/dev/null; then
        ok "uv already installed: $(uv --version 2>/dev/null | head -1)"
        return 0
    fi
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
    hash -r 2>/dev/null || true
    if ! command -v uv &>/dev/null && [[ -x /root/.local/bin/uv ]]; then
        ln -sf /root/.local/bin/uv /usr/local/bin/uv
    fi
    if ! command -v uv &>/dev/null && [[ -x "${HOME}/.local/bin/uv" ]]; then
        ln -sf "${HOME}/.local/bin/uv" /usr/local/bin/uv
    fi
    command -v uv &>/dev/null || die "uv install failed."
    ok "uv installed."
}

# Force local APP_DIR git tree to match remote branch (drops dirty tracked files).
# Needed because MariaDB/uv may leave local edits that block plain `git checkout`.
git_sync_app_dir_to_branch() {
    local branch="$1" target_ref=""
    git -C "$APP_DIR" remote set-url origin "$REPO_GIT_URL" 2>/dev/null || true
    git -C "$APP_DIR" fetch --depth 1 origin "$branch" \
        || die "git fetch origin ${branch} failed."

    # Shallow fetch may only update FETCH_HEAD (origin/<branch> can be missing).
    if git -C "$APP_DIR" rev-parse --verify "origin/${branch}" >/dev/null 2>&1; then
        target_ref="origin/${branch}"
    else
        target_ref="FETCH_HEAD"
    fi

    git -C "$APP_DIR" reset --hard HEAD >/dev/null 2>&1 || true
    git -C "$APP_DIR" clean -fd >/dev/null 2>&1 || true
    git -C "$APP_DIR" checkout -f -B "$branch" "$target_ref" \
        || die "git checkout ${branch} failed."
    git -C "$APP_DIR" reset --hard "$target_ref" \
        || die "git reset --hard ${target_ref} failed."
}

fetch_bot_source() {
    local tmp tmpdir force_refresh="${1:-0}" branch="${2:-}" extracted="" archive_url
    if [[ -z "$branch" ]]; then
        branch="$(get_repo_branch)"
    fi
    archive_url="$(repo_archive_url "$branch")"
    ensure_config_dirs

    if [[ "$force_refresh" == "1" ]] && [[ -d "${APP_DIR}/.git" ]]; then
        info "Updating existing git checkout in ${APP_DIR} (branch ${branch})..."
        git_sync_app_dir_to_branch "$branch"
        set_install_branch "$branch"
        ok "Source updated ($(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown))."
        return 0
    fi

    if [[ "$force_refresh" == "1" ]] && [[ -f "${APP_DIR}/main.py" ]]; then
        info "Refreshing bot source from GitHub archive (${branch})..."
        tmp="$(mktemp)"
        tmpdir="$(mktemp -d)"
        if ! curl_download "$archive_url" "$tmp"; then
            rm -f "$tmp"
            rm -rf "$tmpdir"
            explain_network_failure "download bot source archive"
            exit 1
        fi
        tar -xzf "$tmp" -C "$tmpdir"
        extracted="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d | head -1)"
        [[ -n "$extracted" ]] || die "Could not find extracted source directory."
        # Preserve local venv / uv cache if present.
        rm -rf "${APP_DIR}.bak"
        mv "$APP_DIR" "${APP_DIR}.bak"
        mv "$extracted" "$APP_DIR"
        if [[ -d "${APP_DIR}.bak/.venv" ]]; then
            mv "${APP_DIR}.bak/.venv" "${APP_DIR}/.venv"
        fi
        rm -rf "${APP_DIR}.bak" "$tmpdir"
        rm -f "$tmp"
        set_install_branch "$branch"
        ok "Source refreshed at ${APP_DIR}"
        return 0
    fi

    if [[ -d "${APP_DIR}/.git" ]]; then
        info "Updating existing git checkout in ${APP_DIR} (branch ${branch})..."
        git_sync_app_dir_to_branch "$branch"
        set_install_branch "$branch"
        ok "Source updated ($(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown))."
        return 0
    fi

    if [[ -f "${APP_DIR}/main.py" && -f "${APP_DIR}/pyproject.toml" ]]; then
        ok "App source already present at ${APP_DIR}"
        set_install_branch "$branch"
        return 0
    fi

    info "Downloading bot source from GitHub (${branch})..."
    rm -rf "${APP_DIR}"
    mkdir -p "$(dirname "$APP_DIR")"

    if command -v git &>/dev/null && git clone --depth 1 --branch "$branch" "$REPO_GIT_URL" "$APP_DIR"; then
        set_install_branch "$branch"
        ok "Cloned repository to ${APP_DIR}"
        return 0
    fi

    warn "git clone failed — falling back to source tarball."
    tmp="$(mktemp)"
    tmpdir="$(mktemp -d)"
    if ! curl_download "$archive_url" "$tmp"; then
        rm -f "$tmp"
        rm -rf "$tmpdir"
        explain_network_failure "download bot source archive"
        exit 1
    fi
    tar -xzf "$tmp" -C "$tmpdir"
    extracted="$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d | head -1)"
    [[ -n "$extracted" ]] || die "Could not find extracted source directory."
    mv "$extracted" "$APP_DIR"
    rm -f "$tmp"
    rm -rf "$tmpdir"
    set_install_branch "$branch"
    ok "Source extracted to ${APP_DIR}"
}

link_native_app_paths() {
    ln -sfn "$ENV_FILE" "${APP_DIR}/.env"
    ln -sfn "${CONFIG_DIR}/logs" "${APP_DIR}/logs"
    ln -sfn "${CONFIG_DIR}/sessions" "${APP_DIR}/sessions"
}

sync_native_python_deps() {
    info "Installing Python 3.14 and project dependencies with uv..."
    (
        cd "$APP_DIR"
        uv python install 3.14
        if [[ -f uv.lock ]]; then
            uv sync --frozen --no-dev
        else
            uv sync --no-dev
        fi
    ) || die "uv sync failed."
    ok "Python dependencies ready."
}

native_systemctl() {
    systemctl "$@"
}

start_native_services() {
    info "Starting native systemd services..."
    configure_native_mariadb_apparmor || true
    systemctl reset-failed pasarguardbot-redis.service pasarguardbot-mariadb.service 2>/dev/null || true
    native_systemctl enable pasarguardbot-redis.service
    native_systemctl restart pasarguardbot-redis.service || native_systemctl start pasarguardbot-redis.service
    systemctl daemon-reload
    native_systemctl enable pasarguardbot-mariadb.service
    # restart applies latest mariadb.cnf (socket path, etc.)
    if ! native_systemctl restart pasarguardbot-mariadb.service; then
        dump_native_mariadb_logs
        die "Failed to start pasarguardbot-mariadb.service"
    fi
    wait_for_native_mariadb
    setup_native_mariadb_user
    native_systemctl enable --now pasarguardbot-phpmyadmin.service
    native_systemctl enable --now pasarguardbot.service
    ok "Native services started."
}

stop_native_services() {
    local unit
    for unit in pasarguardbot.service pasarguardbot-phpmyadmin.service pasarguardbot-mariadb.service pasarguardbot-redis.service; do
        native_systemctl stop "$unit" 2>/dev/null || true
        native_systemctl disable "$unit" 2>/dev/null || true
    done
}

remove_native_systemd_units() {
    local unit
    stop_native_services
    for unit in "${NATIVE_UNITS[@]}"; do
        rm -f "/etc/systemd/system/${unit}"
        rm -f "/etc/systemd/system/multi-user.target.wants/${unit}"
    done
    systemctl daemon-reload 2>/dev/null || true
    systemctl reset-failed 2>/dev/null || true
}

# Full wipe for native + docker leftovers (safe for reinstall testing).
purge_pasarguardbot_everything() {
    info "Purging all PasarguardBot install files and services..."

    # Native systemd
    remove_native_systemd_units 2>/dev/null || true
    for unit in pasarguardbot.service pasarguardbot-phpmyadmin.service pasarguardbot-mariadb.service pasarguardbot-redis.service; do
        systemctl stop "$unit" 2>/dev/null || true
        systemctl disable "$unit" 2>/dev/null || true
        rm -f "/etc/systemd/system/${unit}" \
            "/etc/systemd/system/multi-user.target.wants/${unit}"
    done

    # Docker compose stack (if present)
    if [[ -f "$COMPOSE_FILE" ]] && command -v docker &>/dev/null; then
        docker_compose down --remove-orphans 2>/dev/null || true
    fi
    docker rm -f pasarguardbot pasarguardbot-redis pasarguardbot-mariadb pasarguardbot-phpmyadmin 2>/dev/null || true

    # Kill anything still bound to our ports / leftover mysqld on our datadir
    if command -v fuser &>/dev/null; then
        fuser -k 6160/tcp 6161/tcp 6162/tcp 6163/tcp 2>/dev/null || true
    fi
    pkill -f '/opt/pasarguardbot/conf/mariadb.cnf' 2>/dev/null || true
    pkill -f '/opt/pasarguardbot/conf/redis.conf' 2>/dev/null || true

    # AppArmor local rules we added
    for f in /etc/apparmor.d/local/usr.sbin.mariadbd /etc/apparmor.d/local/usr.sbin.mysqld; do
        if [[ -f "$f" ]] && grep -qF '# pasarguardbot-native' "$f" 2>/dev/null; then
            # Remove our marker block (best-effort).
            sed -i '/# pasarguardbot-native/,+8d' "$f" 2>/dev/null || true
        fi
    done
    if command -v apparmor_parser &>/dev/null; then
        apparmor_parser -r /etc/apparmor.d/usr.sbin.mariadbd 2>/dev/null || true
        apparmor_parser -r /etc/apparmor.d/usr.sbin.mysqld 2>/dev/null || true
    fi

    rm -rf "$CONFIG_DIR"
    rm -f "$MANAGER_BIN"
    systemctl daemon-reload 2>/dev/null || true
    systemctl reset-failed 2>/dev/null || true
    ok "PasarguardBot fully purged from this server."
}

wait_for_native_bot() {
    local i=0
    local max=90
    info "Waiting for bot service..."
    while (( i < max )); do
        if systemctl is-active --quiet pasarguardbot.service; then
            ok "Bot service is active."
            return 0
        fi
        if systemctl is-failed --quiet pasarguardbot.service; then
            warn "Bot service failed. Recent logs:"
            journalctl -u pasarguardbot -n 40 --no-pager || true
            return 1
        fi
        sleep 2
        i=$((i + 2))
    done
    warn "Timed out waiting for bot service."
    systemctl status pasarguardbot --no-pager || true
    return 1
}

show_native_install_summary() {
    echo
    ok "Installation completed successfully (native)!"
    echo
    info "Paths:"
    echo -e "  ${C_DIM}Config:${C_RESET}  ${CONFIG_DIR}"
    echo -e "  ${C_DIM}.env:${C_RESET}    ${ENV_FILE}"
    echo -e "  ${C_DIM}App:${C_RESET}     ${APP_DIR}"
    echo -e "  ${C_DIM}Logs:${C_RESET}    ${CONFIG_DIR}/logs"
    echo -e "  ${C_DIM}Data:${C_RESET}    ${CONFIG_DIR}/data"
    echo
    info "Version:"
    echo -e "  ${C_DIM}Bot:${C_RESET}  $(get_installed_bot_version)"
    echo
    info "Ports:"
    echo -e "  ${C_DIM}FastAPI:${C_RESET}      ${FASTAPI_PORT_DEFAULT} (public)"
    echo -e "  ${C_DIM}phpMyAdmin:${C_RESET}   ${PHPMYADMIN_PORT} (public)"
    echo -e "  ${C_DIM}Redis:${C_RESET}        ${REDIS_PORT} (localhost only)"
    echo -e "  ${C_DIM}MariaDB:${C_RESET}      ${MARIADB_PORT} (localhost only)"
    show_service_urls
    echo
    info "Commands:"
    echo -e "  ${C_DIM}Manage:${C_RESET}   pasarguardbot"
    echo -e "  ${C_DIM}Status:${C_RESET}   pasarguardbot → option 7"
}

action_install_docker() {
    local branch="${1:-main}"
    info "Starting PasarguardBot Docker installation (branch=${branch})..."
    echo

    if is_installed; then
        warn "Bot appears already installed (${CONFIG_DIR})."
        read -r -p "Continue (will keep existing .env and data)? (y/N): " confirm || true
        [[ "${confirm,,}" == "y" ]] || return 0
    fi

    set_install_branch "$branch"
    check_disk_space
    install_docker
    check_required_ports docker
    ensure_config_dirs
    generate_env_file docker "$branch"
    setup_compose "$branch"
    install_manager_command
    cleanup_stale_named_containers

    pull_images

    info "Starting services..."
    if ! docker_compose up -d; then
        die "docker compose up failed. Check logs with: docker compose -f ${COMPOSE_FILE} logs"
    fi

    wait_for_containers_healthy || true
    set_install_mode docker
    set_install_branch "$branch"

    echo
    ok "Installation completed successfully (docker, branch=${branch})!"
    echo
    info "Paths:"
    echo -e "  ${C_DIM}Config:${C_RESET}  ${CONFIG_DIR}"
    echo -e "  ${C_DIM}.env:${C_RESET}    ${ENV_FILE}"
    echo -e "  ${C_DIM}Logs:${C_RESET}    ${CONFIG_DIR}/logs"
    echo -e "  ${C_DIM}Data:${C_RESET}    ${CONFIG_DIR}/data"
    echo
    info "Image:"
    echo -e "  ${C_DIM}Bot:${C_RESET}  ${BOT_IMAGE}:$(get_bot_image_tag) ($(get_installed_bot_version))"
    echo -e "  ${C_DIM}Branch:${C_RESET}  ${branch}"
    echo
    info "Ports:"
    echo -e "  ${C_DIM}FastAPI:${C_RESET}      ${FASTAPI_PORT_DEFAULT} (public)"
    echo -e "  ${C_DIM}phpMyAdmin:${C_RESET}   ${PHPMYADMIN_PORT} (public)"
    echo -e "  ${C_DIM}Redis:${C_RESET}        ${REDIS_PORT} (localhost only)"
    echo -e "  ${C_DIM}MariaDB:${C_RESET}      ${MARIADB_PORT} (localhost only)"
    show_service_urls
    echo
    info "Commands:"
    echo -e "  ${C_DIM}Manage:${C_RESET}   pasarguardbot"
    echo -e "  ${C_DIM}Status:${C_RESET}   pasarguardbot → option 7"
    pause
}

action_install_native() {
    local branch="${1:-main}"
    info "Starting PasarguardBot native installation (branch=${branch}, no Docker)..."
    echo
    require_native_os

    if is_installed; then
        warn "Bot appears already installed (${CONFIG_DIR})."
        read -r -p "Continue (will keep existing .env and data)? (y/N): " confirm || true
        [[ "${confirm,,}" == "y" ]] || return 0
    fi

    set_install_branch "$branch"
    check_disk_space
    check_required_ports native
    ensure_config_dirs
    install_native_packages
    generate_env_file native "$branch"
    write_native_redis_conf
    write_native_mariadb_conf
    init_native_mariadb_datadir
    install_phpmyadmin_files
    install_uv_binary
    fetch_bot_source 0 "$branch"
    link_native_app_paths
    sync_native_python_deps
    write_native_systemd_units
    install_manager_command
    start_native_services
    wait_for_native_bot || true
    set_install_mode native
    set_install_branch "$branch"
    show_native_install_summary
    echo -e "  ${C_DIM}Branch:${C_RESET}  ${branch}"
    pause
}

# ── Actions ───────────────────────────────────────────────────────────────────
action_install() {
    local branch
    draw_banner
    echo -e "${C_BOLD}  Install mode${C_RESET}"
    echo
    echo "  1) Docker (full stack — Redis/MariaDB/phpMyAdmin/bot in containers)"
    echo "  2) Native (no Docker — services on host, isolated ports ${REDIS_PORT}/${MARIADB_PORT}/${PHPMYADMIN_PORT})"
    echo "  0) Cancel"
    echo
    read -r -p "Choice: " choice || return 0

    case "$choice" in
        1|2) ;;
        0)
            info "Cancelled."
            return 0
            ;;
        *)
            warn "Invalid choice."
            sleep 1
            return 0
            ;;
    esac

    echo
    prompt_repo_branch install || {
        info "Cancelled."
        return 0
    }
    branch="$SELECTED_REPO_BRANCH"
    echo
    info "Selected branch: ${branch}"
    echo

    case "$choice" in
        1) action_install_docker "$branch" ;;
        2) action_install_native "$branch" ;;
    esac
}

action_uninstall_docker() {
    local choice confirm img_id
    echo -e "${C_RED}${C_BOLD}  ⚠  Uninstall PasarguardBot (Docker)${C_RESET}"
    echo
    echo "  1) Remove containers only (keep .env and data)"
    echo "  2) Remove containers + data (keep .env / config if present)"
    echo "  3) Full remove (${CONFIG_DIR} and ${MANAGER_BIN})"
    echo "  0) Cancel"
    echo
    read -r -p "Choice: " choice || true

    case "$choice" in
        1)
            info "Stopping and removing containers..."
            if [[ -f "$COMPOSE_FILE" && -f "$ENV_FILE" ]]; then
                docker_compose down --remove-orphans 2>/dev/null || true
            else
                cleanup_stale_named_containers
            fi
            ok "Containers removed. .env and data were kept."
            ;;
        2)
            read -r -p "Delete database/redis data under ${CONFIG_DIR}/data? Type 'yes' to confirm: " confirm || true
            [[ "$confirm" == "yes" ]] || {
                info "Cancelled."
                return 0
            }
            if [[ -f "$COMPOSE_FILE" && -f "$ENV_FILE" ]]; then
                docker_compose down --remove-orphans 2>/dev/null || true
            else
                cleanup_stale_named_containers
            fi
            rm -rf "${CONFIG_DIR}/data"
            ok "Containers and data removed. Config/.env kept if present."
            ;;
        3)
            read -r -p "Everything under ${CONFIG_DIR} will be deleted! Type 'yes' to confirm: " confirm || true
            [[ "$confirm" == "yes" ]] || {
                info "Cancelled."
                return 0
            }
            while IFS= read -r img_id; do
                [[ -n "$img_id" ]] && docker rmi "$img_id" 2>/dev/null || true
            done < <(docker images "${BOT_IMAGE}" -q 2>/dev/null || true)
            purge_pasarguardbot_everything
            ;;
        *)
            info "Cancelled."
            ;;
    esac
}

action_uninstall_native() {
    local choice confirm
    echo -e "${C_RED}${C_BOLD}  ⚠  Uninstall PasarguardBot (Native)${C_RESET}"
    echo
    echo "  1) Stop services only (keep .env, app, and data)"
    echo "  2) Stop services + delete data (keep .env / app / config)"
    echo "  3) Full remove (${CONFIG_DIR}, systemd units, and ${MANAGER_BIN})"
    echo "  0) Cancel"
    echo
    read -r -p "Choice: " choice || true

    case "$choice" in
        1)
            info "Stopping native services..."
            stop_native_services
            ok "Services stopped. .env, app, and data were kept."
            ;;
        2)
            read -r -p "Delete database/redis data under ${CONFIG_DIR}/data? Type 'yes' to confirm: " confirm || true
            [[ "$confirm" == "yes" ]] || {
                info "Cancelled."
                return 0
            }
            stop_native_services
            rm -rf "${CONFIG_DIR}/data"
            mkdir -p "${CONFIG_DIR}/data/mariadb" "${CONFIG_DIR}/data/redis"
            ok "Services stopped and data removed. Config/.env/app kept if present."
            ;;
        3)
            read -r -p "Everything under ${CONFIG_DIR} will be deleted! Type 'yes' to confirm: " confirm || true
            [[ "$confirm" == "yes" ]] || {
                info "Cancelled."
                return 0
            }
            purge_pasarguardbot_everything
            ;;
        *)
            info "Cancelled."
            ;;
    esac
}

action_uninstall() {
    local mode
    draw_banner
    if ! is_installed && [[ ! -d "$CONFIG_DIR" ]]; then
        warn "Bot is not installed."
        pause
        return 0
    fi

    mode="$(get_install_mode)"
    case "$mode" in
        native) action_uninstall_native ;;
        docker|"") action_uninstall_docker ;;
        *)
            warn "Unknown install mode '${mode}'. Showing both uninstall menus is not supported; defaulting to Docker path."
            action_uninstall_docker
            ;;
    esac
    pause
}

action_update_docker() {
    local old_ver new_ver branch="${1:-main}" script_url tmp_mgr
    command -v docker &>/dev/null || die "Docker is not installed."
    docker info &>/dev/null || die "Docker daemon is not running."

    old_ver="$(get_installed_bot_version)"
    set_install_branch "$branch"

    info "Updating production Compose from branch '${branch}' (image ${BOT_IMAGE}:$(bot_image_tag_for_branch "$branch"))..."
    setup_compose "$branch"
    pull_images

    info "Recreating containers..."
    if ! docker_compose up -d --force-recreate --remove-orphans; then
        die "Update failed during docker compose up."
    fi

    wait_for_containers_healthy || true
    prune_dangling_images_safe

    script_url="https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/${branch}/scripts/pasarguardbot.sh"
    tmp_mgr="$(mktemp)"
    if curl_download "$script_url" "$tmp_mgr"; then
        info "Refreshing manager script from branch '${branch}'..."
        install_manager_from_file "$tmp_mgr"
    fi
    rm -f "$tmp_mgr"

    new_ver="$(get_installed_bot_version)"
    ok "Update complete (${old_ver} → ${new_ver}) [branch=${branch}, image=$(get_bot_image_tag)]."
}

action_update_native() {
    local old_ver new_ver branch="${1:-main}"
    require_native_os
    [[ -d "$APP_DIR" ]] || die "Native app directory missing: ${APP_DIR}"

    old_ver="$(get_installed_bot_version)"
    set_install_branch "$branch"
    info "Updating bot source from branch '${branch}'..."
    fetch_bot_source 1 "$branch"
    link_native_app_paths
    sync_native_python_deps
    if [[ -f "${APP_DIR}/scripts/pasarguardbot.sh" ]]; then
        info "Refreshing manager script from updated source..."
        install_manager_from_file "${APP_DIR}/scripts/pasarguardbot.sh"
    fi
    write_native_systemd_units

    info "Restarting native services..."
    native_systemctl restart pasarguardbot-redis.service || true
    native_systemctl restart pasarguardbot-mariadb.service || true
    native_systemctl restart pasarguardbot-phpmyadmin.service || true
    native_systemctl restart pasarguardbot.service
    wait_for_native_bot || true

    new_ver="$(get_installed_bot_version)"
    ok "Update complete (${old_ver} → ${new_ver}) [branch=${branch}]."
}

action_update() {
    local branch
    draw_banner
    is_installed || die "Install the bot first (option 1)."

    prompt_repo_branch update || {
        info "Cancelled."
        pause
        return 0
    }
    branch="$SELECTED_REPO_BRANCH"
    echo
    info "Selected branch: ${branch}"
    echo

    case "$(get_install_mode)" in
        native) action_update_native "$branch" ;;
        docker) action_update_docker "$branch" ;;
        *) die "Unknown install mode. Reinstall or set ${INSTALL_MODE_FILE}." ;;
    esac
    pause
}

action_update_script() {
    draw_banner

    local tmp new_ver old_ver branch script_url
    tmp="$(mktemp)"
    branch="$(get_repo_branch)"
    script_url="https://raw.githubusercontent.com/AmirKenzo/PasarguardBot/${branch}/scripts/pasarguardbot.sh"

    info "Downloading latest manager script from GitHub (branch ${branch})..."
    if ! curl_download "$script_url" "$tmp"; then
        rm -f "$tmp"
        explain_network_failure "download manager script"
        pause
        return 1
    fi

    head -1 "$tmp" | grep -q '#!/usr/bin/env bash' || {
        rm -f "$tmp"
        die "Downloaded file does not look like a valid script."
    }

    new_ver="$(grep -m1 '^readonly SCRIPT_VERSION=' "$tmp" | sed -E 's/^readonly SCRIPT_VERSION="(.*)"/\1/')"
    old_ver="$SCRIPT_VERSION"

    if [[ -z "$new_ver" ]]; then
        rm -f "$tmp"
        die "Could not read SCRIPT_VERSION from downloaded script."
    fi

    # Always install (even when versions match) so /usr/local/bin/pasarguardbot exists.
    install_manager_from_file "$tmp"
    rm -f "$tmp"

    if [[ "$new_ver" == "$old_ver" ]]; then
        ok "Manager script is already up to date ($(format_version "$old_ver"))."
        ok "pasarguardbot command ensured at ${MANAGER_BIN}"
        pause
        return 0
    fi

    ok "Manager script updated: $(format_version "$old_ver") → $(format_version "$new_ver")"
    warn "Run pasarguardbot again to use the new script."
    pause
}

compose_running_services() {
    docker_compose ps --status running --services 2>/dev/null
}

action_logs_live() {
    is_installed || die "Install the bot first (option 1)."

    if is_native_mode; then
        info "Live bot logs — press Ctrl+C to exit"
        journalctl -u pasarguardbot -f -n 200
        return 0
    fi

    local -a services=()
    local svc

    while IFS= read -r svc; do
        [[ -n "$svc" ]] && services+=("$svc")
    done < <(compose_running_services)

    if [[ ${#services[@]} -eq 0 ]]; then
        die "No running containers found."
    fi

    info "Live logs (${services[*]}) — press Ctrl+C to exit"
    echo
    docker_compose logs -f --tail=200 -t "${services[@]}"
}

action_logs() {
    draw_banner
    is_installed || die "Install the bot first (option 1)."

    if is_native_mode; then
        echo "  1) Bot logs"
        echo "  2) MariaDB logs"
        echo "  3) Redis logs"
        echo "  4) phpMyAdmin logs"
        echo "  5) Live bot logs (Ctrl+C to exit)"
        echo "  0) Back"
        echo
        read -r -p "Choice: " choice || true
        case "$choice" in
            1) journalctl -u pasarguardbot -n 200 --no-pager ;;
            2) journalctl -u pasarguardbot-mariadb -n 200 --no-pager ;;
            3) journalctl -u pasarguardbot-redis -n 200 --no-pager ;;
            4) journalctl -u pasarguardbot-phpmyadmin -n 200 --no-pager ;;
            5)
                info "Live logs — press Ctrl+C to exit"
                journalctl -u pasarguardbot -f -n 200
                ;;
            0) return 0 ;;
            *) warn "Invalid choice." ;;
        esac
        pause
        return 0
    fi

    echo "  1) Bot logs"
    echo "  2) MariaDB logs"
    echo "  3) Redis logs"
    echo "  4) All services"
    echo "  5) Live bot logs (Ctrl+C to exit)"
    echo "  0) Back"
    echo
    read -r -p "Choice: " choice || true

    case "$choice" in
        1) docker_compose logs --tail=200 bot ;;
        2) docker_compose logs --tail=200 mariadb ;;
        3) docker_compose logs --tail=200 redis ;;
        4) docker_compose logs --tail=100 ;;
        5)
            info "Live logs — press Ctrl+C to exit"
            docker_compose logs -f bot
            ;;
        0) return 0 ;;
        *) warn "Invalid choice." ;;
    esac
    pause
}

action_edit_env() {
    draw_banner
    is_installed || die "Install the bot first (option 1)."

    local editor="${EDITOR:-nano}"
    command -v "$editor" &>/dev/null || editor="nano"

    info "Editing ${ENV_FILE} with ${editor}"
    echo
    "$editor" "$ENV_FILE"

    echo
    read -r -p "Restart the bot? (Y/n): " restart || true
    if [[ "${restart,,}" != "n" ]]; then
        action_restart_quiet
    fi
    pause
}

action_restart_quiet() {
    if is_native_mode; then
        native_systemctl restart pasarguardbot-redis.service || true
        native_systemctl restart pasarguardbot-mariadb.service || true
        native_systemctl restart pasarguardbot-phpmyadmin.service || true
        native_systemctl restart pasarguardbot.service
        ok "Full restart completed (native)."
        return 0
    fi
    docker_compose pull bot || true
    docker_compose down
    docker_compose up -d
    ok "Full restart completed."
}

action_restart() {
    draw_banner
    is_installed || die "Install the bot first (option 1)."

    info "Performing a full restart of all services..."
    action_restart_quiet
    pause
}

action_status() {
    local unit
    draw_banner
    is_installed || die "Install the bot first (option 1)."

    if is_native_mode; then
        info "Systemd status:"
        echo
        for unit in "${NATIVE_UNITS[@]}"; do
            printf '  %-32s %s\n' "$unit" "$(systemctl is-active "$unit" 2>/dev/null || echo missing)"
        done
        echo
        info "Listening ports (expected ${FASTAPI_PORT_DEFAULT}/${REDIS_PORT}/${MARIADB_PORT}/${PHPMYADMIN_PORT}):"
        ss -ltn 2>/dev/null | grep -E ":(${FASTAPI_PORT_DEFAULT}|${REDIS_PORT}|${MARIADB_PORT}|${PHPMYADMIN_PORT})\\s" || true
        show_service_urls
        pause
        return 0
    fi

    info "Container status:"
    echo
    docker_compose ps
    echo
    info "Resource usage:"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        pasarguardbot pasarguardbot-mariadb pasarguardbot-redis pasarguardbot-phpmyadmin 2>/dev/null \
        || true
    show_service_urls
    pause
}

action_urls() {
    draw_banner
    is_installed || die "Install the bot first (option 1)."
    show_service_urls
    pause
}

# ── Main ──────────────────────────────────────────────────────────────────────
main_menu() {
    while true; do
        draw_menu
        read -r -p "  Select an option: " choice || exit 0
        case "$choice" in
            1) action_install ;;
            2) action_uninstall ;;
            3) action_update ;;
            4) action_logs ;;
            5) action_edit_env ;;
            6) action_restart ;;
            7) action_status ;;
            8) action_urls ;;
            9) action_update_script ;;
            10) action_docker_network ;;
            0|q|Q) draw_banner; ok "Goodbye!"; exit 0 ;;
            *) warn "Invalid option."; sleep 1 ;;
        esac
    done
}

bootstrap "$@"

case "${1:-}" in
    install)        action_install ;;
    uninstall)      action_uninstall ;;
    purge)
        require_root
        purge_pasarguardbot_everything
        ;;
    update)         action_update ;;
    update-script)  action_update_script ;;
    logs)           action_logs_live ;;
    restart)        action_restart ;;
    status)         action_status ;;
    urls)           action_urls ;;
    ""|menu)        main_menu ;;
    *)
        echo "Usage: pasarguardbot [install|uninstall|purge|update|update-script|logs|restart|status|urls|menu]"
        exit 1
        ;;
esac
