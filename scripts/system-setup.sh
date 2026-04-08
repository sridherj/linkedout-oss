#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# LinkedOut OSS — System Setup (requires sudo)
# This script installs system-level dependencies.
# Read it before running: cat scripts/system-setup.sh
#
# What this script does:
#   1. Installs postgresql + postgresql-contrib (for pg_trgm)
#   2. Installs postgresql-XX-pgvector (version-matched)
#   3. Ensures PostgreSQL service is running
#   4. Creates the 'linkedout' database user
#   5. Creates the 'linkedout' database
#   6. Installs SQL extensions (vector, pg_trgm) as superuser
#
# What this script does NOT do:
#   - Install Python (user should have Python 3.11+ already)
#   - Create venvs or install pip packages
#   - Write any config files
#   - Touch ~/linkedout-data/
#
# Exit codes:
#   0 = success
#   1 = package install failed
#   2 = PostgreSQL won't start
#   3 = DB/extension creation failed
#
# Usage:
#   sudo bash scripts/system-setup.sh
#   sudo bash scripts/system-setup.sh --platform ubuntu
#   sudo bash scripts/system-setup.sh --platform macos
#   sudo bash scripts/system-setup.sh --platform arch
#   sudo bash scripts/system-setup.sh --platform fedora

set -euo pipefail

# ── Argument parsing ────────────────────────────────────────────

PLATFORM_OVERRIDE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --platform)
            PLATFORM_OVERRIDE="$2"
            shift 2
            ;;
        --platform=*)
            PLATFORM_OVERRIDE="${1#*=}"
            shift
            ;;
        -h|--help)
            head -32 "$0"
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: sudo bash $0 [--platform ubuntu|macos|arch|fedora]" >&2
            exit 1
            ;;
    esac
done

# ── Platform detection ──────────────────────────────────────────

detect_platform() {
    if [[ -n "$PLATFORM_OVERRIDE" ]]; then
        echo "$PLATFORM_OVERRIDE"
        return
    fi

    local system
    system="$(uname -s)"

    if [[ "$system" == "Darwin" ]]; then
        echo "macos"
        return
    fi

    if [[ "$system" != "Linux" ]]; then
        echo "unsupported"
        return
    fi

    # Read /etc/os-release for Linux distribution
    local distro_id=""
    if [[ -f /etc/os-release ]]; then
        distro_id="$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')"
    fi

    case "$distro_id" in
        ubuntu|debian|linuxmint|pop)
            echo "ubuntu"  # Debian-family, use apt
            ;;
        arch|manjaro|endeavouros)
            echo "arch"
            ;;
        fedora|rhel|centos|rocky|alma)
            echo "fedora"
            ;;
        *)
            # Check ID_LIKE for derivatives
            local id_like=""
            if [[ -f /etc/os-release ]]; then
                id_like="$(grep '^ID_LIKE=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')"
            fi
            if echo "$id_like" | grep -q "ubuntu\|debian"; then
                echo "ubuntu"
            elif echo "$id_like" | grep -q "arch"; then
                echo "arch"
            elif echo "$id_like" | grep -q "fedora\|rhel"; then
                echo "fedora"
            else
                echo "unsupported"
            fi
            ;;
    esac
}

# ── Helpers ─────────────────────────────────────────────────────

info()  { echo "  [INFO]  $*"; }
ok()    { echo "  [OK]    $*"; }
warn()  { echo "  [WARN]  $*"; }
fail()  { echo "  [FAIL]  $*" >&2; }

# Get the installed PostgreSQL major version number
get_pg_major_version() {
    local version_output
    if command -v psql &>/dev/null; then
        version_output="$(psql --version 2>/dev/null || true)"
        echo "$version_output" | grep -oP '\d+' | head -1
    elif command -v pg_config &>/dev/null; then
        version_output="$(pg_config --version 2>/dev/null || true)"
        echo "$version_output" | grep -oP '\d+' | head -1
    else
        echo ""
    fi
}

# ── Package installation per platform ───────────────────────────

install_ubuntu() {
    info "Installing PostgreSQL and pgvector (Debian/Ubuntu)..."

    # Install PostgreSQL and contrib (provides pg_trgm)
    apt-get update -qq
    if ! apt-get install -y postgresql postgresql-contrib; then
        fail "Failed to install postgresql packages via apt."
        exit 1
    fi

    # Detect installed major version and install matching pgvector
    local pg_major
    pg_major="$(get_pg_major_version)"
    if [[ -z "$pg_major" ]]; then
        fail "Could not determine PostgreSQL version after install."
        exit 1
    fi

    info "PostgreSQL major version: $pg_major"
    if ! apt-get install -y "postgresql-${pg_major}-pgvector"; then
        warn "postgresql-${pg_major}-pgvector not in default repos."
        warn "Trying to add pgvector PPA..."
        # pgvector may require the official PGDG repo or a PPA
        if command -v add-apt-repository &>/dev/null; then
            add-apt-repository -y ppa:pgvector/pgvector 2>/dev/null || true
            apt-get update -qq
        fi
        if ! apt-get install -y "postgresql-${pg_major}-pgvector"; then
            fail "Failed to install postgresql-${pg_major}-pgvector."
            fail "Install pgvector manually: https://github.com/pgvector/pgvector#installation"
            exit 1
        fi
    fi

    ok "PostgreSQL $pg_major and pgvector installed."
}

install_macos() {
    info "Installing PostgreSQL and pgvector (macOS / Homebrew)..."

    if ! command -v brew &>/dev/null; then
        fail "Homebrew is not installed. Install it from https://brew.sh"
        exit 1
    fi

    # Install PostgreSQL 16 and pgvector via Homebrew (no sudo needed)
    if ! brew install postgresql@16; then
        fail "Failed to install postgresql@16 via Homebrew."
        exit 1
    fi

    if ! brew install pgvector; then
        fail "Failed to install pgvector via Homebrew."
        exit 1
    fi

    ok "PostgreSQL 16 and pgvector installed via Homebrew."
}

install_arch() {
    info "Installing PostgreSQL and pgvector (Arch)..."

    if ! pacman -S --noconfirm --needed postgresql; then
        fail "Failed to install postgresql via pacman."
        exit 1
    fi

    # pgvector is typically in the AUR; check if it's available
    if pacman -Qi pgvector &>/dev/null; then
        ok "pgvector already installed."
    else
        warn "pgvector is not in the official Arch repos."
        warn "Install it from the AUR: yay -S pgvector"
        warn "Or build from source: https://github.com/pgvector/pgvector#installation"
        warn "Continuing — you can install pgvector after this script finishes."
    fi

    ok "PostgreSQL installed."
}

install_fedora() {
    info "Installing PostgreSQL and pgvector (Fedora/RPM)..."

    if ! dnf install -y postgresql-server postgresql-contrib; then
        fail "Failed to install postgresql-server via dnf."
        exit 1
    fi

    # Initialize the database cluster if it doesn't exist
    if [[ ! -d /var/lib/pgsql/data/base ]]; then
        info "Initializing PostgreSQL database cluster..."
        postgresql-setup --initdb || true
    fi

    # Try to install pgvector
    local pg_major
    pg_major="$(get_pg_major_version)"
    if [[ -n "$pg_major" ]]; then
        if ! dnf install -y "pgvector_${pg_major}" 2>/dev/null; then
            warn "pgvector_${pg_major} not in default repos."
            warn "Install pgvector from source: https://github.com/pgvector/pgvector#installation"
        fi
    fi

    ok "PostgreSQL installed."
}

# ── Start PostgreSQL service ────────────────────────────────────

start_postgres() {
    local platform="$1"

    if [[ "$platform" == "macos" ]]; then
        # Homebrew services
        info "Starting PostgreSQL via Homebrew services..."
        brew services start postgresql@16 2>/dev/null || brew services restart postgresql@16 2>/dev/null || true
        # Give it a moment to start
        sleep 2
    else
        # systemd-based Linux
        info "Ensuring PostgreSQL service is running..."
        if command -v systemctl &>/dev/null; then
            systemctl enable postgresql 2>/dev/null || true
            systemctl start postgresql 2>/dev/null || systemctl restart postgresql 2>/dev/null || true
        elif command -v service &>/dev/null; then
            service postgresql start 2>/dev/null || service postgresql restart 2>/dev/null || true
        fi
        sleep 2
    fi

    # Verify PostgreSQL is accepting connections
    local retries=5
    while [[ $retries -gt 0 ]]; do
        if pg_isready -q 2>/dev/null; then
            ok "PostgreSQL is running and accepting connections."
            return 0
        fi
        sleep 2
        retries=$((retries - 1))
    done

    fail "PostgreSQL is not accepting connections after starting."
    fail "Check the service logs: journalctl -u postgresql --no-pager -n 20"
    exit 2
}

# ── Database and extension setup ────────────────────────────────

setup_database() {
    local platform="$1"

    info "Creating database user 'linkedout'..."
    if [[ "$platform" == "macos" ]]; then
        # On macOS with Homebrew, the current user is the superuser
        createuser --no-superuser --createdb --no-createrole linkedout 2>/dev/null || true
    else
        sudo -u postgres createuser --no-superuser --createdb --no-createrole linkedout 2>/dev/null || true
    fi
    ok "Database user 'linkedout' ready."

    info "Creating database 'linkedout'..."
    if [[ "$platform" == "macos" ]]; then
        createdb --owner=linkedout linkedout 2>/dev/null || true
    else
        sudo -u postgres createdb --owner=linkedout linkedout 2>/dev/null || true
    fi
    ok "Database 'linkedout' ready."

    info "Installing SQL extensions (vector, pg_trgm)..."
    local psql_cmd
    if [[ "$platform" == "macos" ]]; then
        psql_cmd="psql -d linkedout"
    else
        psql_cmd="sudo -u postgres psql -d linkedout"
    fi

    if ! $psql_cmd -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null; then
        fail "Failed to create 'vector' extension. Is pgvector installed?"
        exit 3
    fi

    if ! $psql_cmd -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null; then
        fail "Failed to create 'pg_trgm' extension."
        exit 3
    fi
    ok "Extensions 'vector' and 'pg_trgm' installed."
}

# ── Main ────────────────────────────────────────────────────────

main() {
    echo ""
    echo "LinkedOut OSS — System Setup"
    echo "============================"
    echo ""

    local platform
    platform="$(detect_platform)"
    info "Detected platform: $platform"

    if [[ "$platform" == "unsupported" ]]; then
        fail "Unsupported platform. LinkedOut requires Linux (Debian/Ubuntu, Arch, Fedora) or macOS."
        fail "If you're on Windows, use WSL2: https://learn.microsoft.com/en-us/windows/wsl/install"
        exit 1
    fi

    # Step 1 & 2: Install packages
    case "$platform" in
        ubuntu)  install_ubuntu  ;;
        macos)   install_macos   ;;
        arch)    install_arch    ;;
        fedora)  install_fedora  ;;
    esac

    # Step 3: Start PostgreSQL
    start_postgres "$platform"

    # Step 4, 5, 6: Create user, database, extensions
    setup_database "$platform"

    echo ""
    echo "============================"
    ok "System setup complete."
    echo ""
    echo "  PostgreSQL is running with pgvector and pg_trgm."
    echo "  Database user 'linkedout' and database 'linkedout' are ready."
    echo ""
    echo "  Next: run the LinkedOut setup flow to configure your environment."
    echo ""
}

main "$@"
