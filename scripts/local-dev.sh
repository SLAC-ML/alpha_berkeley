#!/bin/bash
# Local Development Helper for Alpha Berkeley
# Simplifies common development tasks and container management

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
CONFIG_FILE="${PROJECT_ROOT}/config.yml"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    printf "${BLUE}ℹ${NC} %s\n" "$1"
}

print_success() {
    printf "${GREEN}✓${NC} %s\n" "$1"
}

print_warning() {
    printf "${YELLOW}⚠${NC} %s\n" "$1"
}

print_error() {
    printf "${RED}✗${NC} %s\n" "$1"
}

print_header() {
    printf "\n"
    printf "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
    printf "${BLUE}  %s${NC}\n" "$1"
    printf "${BLUE}═══════════════════════════════════════════════════════${NC}\n"
    printf "\n"
}

# Function to show usage
show_usage() {
    printf "${BLUE}Local Development Helper for Alpha Berkeley${NC}\n\n"
    printf "${GREEN}Usage:${NC}\n"
    printf "  ./scripts/local-dev.sh <command> [options]\n\n"
    printf "${GREEN}Commands:${NC}\n"
    printf "  ${BLUE}up${NC}              Start all services (rebuilds code from src/)\n"
    printf "  ${BLUE}down${NC}            Stop all services\n"
    printf "  ${BLUE}restart${NC}         Restart all services (rebuilds code)\n"
    printf "  ${BLUE}rebuild${NC}         Full clean rebuild (stops, removes, rebuilds)\n"
    printf "  ${BLUE}logs [service]${NC}  Show logs (optional: specify service name)\n"
    printf "  ${BLUE}sync${NC}            Quick sync src/ to build/ and restart pipelines\n"
    printf "  ${BLUE}status${NC}          Show status of all services\n"
    printf "  ${BLUE}shell <service>${NC} Open a shell in a running service\n"
    printf "  ${BLUE}help${NC}            Show this help message\n\n"
    printf "${GREEN}Examples:${NC}\n"
    printf "  ./scripts/local-dev.sh up              # Start services with updated code\n"
    printf "  ./scripts/local-dev.sh logs pipelines  # Show pipelines logs\n"
    printf "  ./scripts/local-dev.sh sync            # Quick code update\n"
    printf "  ./scripts/local-dev.sh restart         # Restart with updated config/code\n"
    printf "  ./scripts/local-dev.sh shell pipelines # Open shell in pipelines container\n\n"
    printf "${GREEN}Notes:${NC}\n"
    printf "  - ${BLUE}up/restart${NC} automatically copies code from src/ to build/\n"
    printf "  - ${BLUE}sync${NC} is faster but less thorough than up/restart\n"
    printf "  - All commands run from project root directory\n\n"
}

# Change to project root
cd "$PROJECT_ROOT"

# Parse command
COMMAND="${1:-help}"

case "$COMMAND" in
    up)
        print_header "Starting Services"
        print_info "This will:"
        echo "  1. Copy source code from src/ to build/"
        echo "  2. Regenerate docker-compose files"
        echo "  3. Start/restart all services"
        echo ""

        python3 ./deployment/container_manager.py config.yml up -d

        print_success "Services started successfully!"
        print_info "View logs with: ./scripts/local-dev.sh logs"
        ;;

    down)
        print_header "Stopping Services"

        python3 ./deployment/container_manager.py config.yml down

        print_success "Services stopped successfully!"
        ;;

    restart)
        print_header "Restarting Services"
        print_info "Stopping services..."

        python3 ./deployment/container_manager.py config.yml down

        print_info "Starting services with updated code..."
        python3 ./deployment/container_manager.py config.yml up -d

        print_success "Services restarted successfully!"
        ;;

    rebuild)
        print_header "Full Rebuild"
        print_warning "This will remove all containers, images, and volumes!"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            python3 ./deployment/container_manager.py config.yml rebuild -d
            print_success "Full rebuild completed!"
        else
            print_info "Rebuild cancelled"
        fi
        ;;

    logs)
        SERVICE="${2:-}"
        if [ -z "$SERVICE" ]; then
            print_header "All Service Logs"
            print_info "Showing logs from all services (Ctrl+C to exit)..."
            /opt/podman/bin/podman compose -f build/services/docker-compose.yml \
                --env-file .env logs -f
        else
            print_header "Logs: $SERVICE"
            print_info "Showing logs for $SERVICE (Ctrl+C to exit)..."
            /opt/podman/bin/podman logs -f "$SERVICE"
        fi
        ;;

    sync)
        print_header "Quick Sync"
        print_info "Syncing src/ to build/ and restarting pipelines..."

        ./scripts/sync_src_to_build.sh

        print_success "Quick sync completed!"
        ;;

    status)
        print_header "Service Status"

        /opt/podman/bin/podman ps -a --filter "network=alpha-berkeley-network" \
            --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        ;;

    shell)
        SERVICE="${2:-pipelines}"
        print_header "Opening Shell: $SERVICE"
        print_info "Opening interactive shell in $SERVICE container..."
        print_info "Type 'exit' to leave the shell"
        echo ""

        /opt/podman/bin/podman exec -it "$SERVICE" /bin/bash
        ;;

    help|--help|-h)
        show_usage
        ;;

    *)
        print_error "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
