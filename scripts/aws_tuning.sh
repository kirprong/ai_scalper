#!/bin/bash
#===============================================================================
# AWS us-east-1 Deployment Tuning Script for HFT
# Task: TASK-031 - AWS us-east-1 Deployment Tuning (Боевой Сервер)
# 
# Purpose: Configure TCP stack parameters on Ubuntu 22.04 LTS to minimize
#          network latency for high-frequency trading workloads.
#
# Usage:   sudo ./aws_tuning.sh [--apply] [--verify] [--backup]
#
# Options:
#   --apply   Apply the tuning parameters (requires root)
#   --verify  Verify current settings against recommended values
#   --backup  Create backup of current sysctl.conf before changes
#
# WARNING: This script modifies kernel network parameters. Always test in
#          a staging environment before applying to production.
#
# Author: AI Lead-Lag Scalper Team
# Date: 2026-03-09
#===============================================================================

set -euo pipefail

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration file paths
SYSCTL_CONF="/etc/sysctl.conf"
SYSCTL_BACKUP="/etc/sysctl.conf.hft-backup"
SYSCTL_HFT_CONF="/etc/sysctl.d/99-hft-tuning.conf"

# Recommended HFT parameter values
declare -A HFT_PARAMS=(
    #--------------------------------------------------------------------------
    # SOCKET BUFFER SIZES
    # Increase maximum socket receive/send buffer sizes for high throughput
    # Default: 212992 (208KB) -> 134217728 (128MB) for HFT
    #--------------------------------------------------------------------------
    ["net.core.rmem_max"]="134217728"
    ["net.core.wmem_max"]="134217728"
    
    #--------------------------------------------------------------------------
    # TCP BUFFER SIZES (min, default, max)
    # Format: min default max (in bytes)
    # Increase TCP buffer sizes for low-latency, high-throughput connections
    # min=4KB, default=16MB, max=128MB
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_rmem"]="4096 16777216 134217728"
    ["net.ipv4.tcp_wmem"]="4096 16777216 134217728"
    
    #--------------------------------------------------------------------------
    # INPUT PACKET QUEUE
    # Increase backlog for incoming packets before they're processed
    # Default: 1000 -> 5000 for burst handling
    #--------------------------------------------------------------------------
    ["net.core.netdev_max_backlog"]="5000"
    
    #--------------------------------------------------------------------------
    # TCP FASTOPEN
    # Enable TCP Fast Open (TFO) to reduce handshake latency
    # Bit flags: 1=client, 2=server, 3=both
    # Reduces initial connection setup time by allowing data in SYN
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_fastopen"]="3"
    
    #--------------------------------------------------------------------------
    # TCP SLOW START AFTER IDLE
    # Disable slow start after idle periods
    # Default: 1 (enabled) -> 0 (disabled)
    # Prevents TCP from resetting congestion window after idle
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_slow_start_after_idle"]="0"
    
    #--------------------------------------------------------------------------
    # TCP METRICS SAVE
    # Disable saving of TCP connection metrics
    # Default: 1 (enabled) -> 0 (disabled)
    # Prevents stale RTT caching that could cause suboptimal decisions
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_no_metrics_save"]="1"
    
    #--------------------------------------------------------------------------
    # TCP LOW LATENCY MODE
    # Enable low latency mode (favor latency over throughput)
    # Note: This parameter may not exist in all kernels (removed in 4.14+)
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_low_latency"]="1"
    
    #--------------------------------------------------------------------------
    # TCP CONGESTION CONTROL
    # Use BBR for better latency characteristics
    # BBR is optimized for modern networks and provides lower latency
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_congestion_control"]="bbr"
    
    #--------------------------------------------------------------------------
    # TCP SACK (Selective Acknowledgment)
    # Enable SACK for better retransmission efficiency
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_sack"]="1"
    
    #--------------------------------------------------------------------------
    # TCP FACK (Forward Acknowledgment)
    # Enable FACK for improved congestion control
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_fack"]="1"
    
    #--------------------------------------------------------------------------
    # TCP TIMESTAMP
    # Enable TCP timestamps for better RTT calculation
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_timestamps"]="1"
    
    #--------------------------------------------------------------------------
    # TCP WINDOW SCALING
    # Enable window scaling for high-bandwidth connections
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_window_scaling"]="1"
    
    #--------------------------------------------------------------------------
    # TCP FIN TIMEOUT
    # Reduce TIME_WAIT socket timeout from 60s to 10s
    # Faster socket recycling for high-frequency connections
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_fin_timeout"]="10"
    
    #--------------------------------------------------------------------------
    # TCP TW REUSE
    # Allow reuse of TIME_WAIT sockets for new connections
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_tw_reuse"]="1"
    
    #--------------------------------------------------------------------------
    # TCP MAX SYN BACKLOG
    # Increase SYN backlog for connection bursts
    #--------------------------------------------------------------------------
    ["net.ipv4.tcp_max_syn_backlog"]="8192"
    
    #--------------------------------------------------------------------------
    # SOMAXCONN
    # Maximum listen queue backlog
    #--------------------------------------------------------------------------
    ["net.core.somaxconn"]="8192"
    
    #--------------------------------------------------------------------------
    # REAL-TIME SCHEDULING
    # Allow unlimited CPU time for real-time tasks
    # -1 means no time limit for RT scheduling
    #--------------------------------------------------------------------------
    ["kernel.sched_rt_runtime_us"]="-1"
    
    #--------------------------------------------------------------------------
    # SWAPPINESS
    # Reduce swap usage to prevent latency spikes
    # Default: 60 -> 1 (minimal swapping)
    #--------------------------------------------------------------------------
    ["vm.swappiness"]="1"
    
    #--------------------------------------------------------------------------
    # DIRTY RATIO
    # Reduce dirty page ratios for more predictable I/O
    #--------------------------------------------------------------------------
    ["vm.dirty_ratio"]="10"
    ["vm.dirty_background_ratio"]="5"
)

# Additional kernel parameters (not sysctl)
KERNEL_PARAMS=(
    "net.core.default_qdisc=fq"
)

#-------------------------------------------------------------------------------
# Helper Functions
#-------------------------------------------------------------------------------

print_banner() {
    echo -e "${BLUE}"
    echo "==============================================================================="
    echo "  AWS HFT Network Tuning Script"
    echo "  Target: Ubuntu 22.04 LTS / AWS us-east-1"
    echo "===============================================================================${NC}"
    echo ""
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
            log_warn "This script is designed for Ubuntu/Debian. Current OS: $ID"
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
        log_info "Detected OS: $PRETTY_NAME"
    else
        log_warn "Cannot detect OS from /etc/os-release"
    fi
}

backup_config() {
    log_info "Creating backup of current sysctl configuration..."
    
    if [[ -f "$SYSCTL_CONF" ]]; then
        cp "$SYSCTL_CONF" "$SYSCTL_BACKUP"
        log_info "Backup created: $SYSCTL_BACKUP"
    fi
    
    # Also backup current runtime settings
    sysctl -a > /tmp/sysctl_runtime_backup_$(date +%Y%m%d_%H%M%S).conf 2>/dev/null || true
    log_info "Runtime settings backed up to /tmp/"
}

verify_settings() {
    log_info "Verifying current network settings..."
    echo ""
    printf "%-40s %-20s %-20s %-10s\n" "Parameter" "Current" "Recommended" "Status"
    printf "%-40s %-20s %-20s %-10s\n" "---------" "-------" "-----------" "------"
    
    local all_ok=true
    
    for param in "${!HFT_PARAMS[@]}"; do
        local current=""
        local recommended="${HFT_PARAMS[$param]}"
        
        # Get current value
        current=$(sysctl -n "$param" 2>/dev/null || echo "N/A")
        
        # Compare values
        local status="${GREEN}OK${NC}"
        if [[ "$current" != "$recommended" ]]; then
            status="${YELLOW}DIFF${NC}"
            all_ok=false
        fi
        
        printf "%-40s %-20s %-20s %-10b\n" "$param" "$current" "$recommended" "$status"
    done
    
    echo ""
    
    if $all_ok; then
        log_info "All parameters are configured correctly!"
    else
        log_warn "Some parameters differ from recommended values."
        log_info "Run with --apply to update settings."
    fi
}

apply_settings() {
    check_root
    log_info "Applying HFT network tuning parameters..."
    echo ""
    
    # Create dedicated config file
    log_info "Creating $SYSCTL_HFT_CONF..."
    {
        echo "#==============================================================================="
        echo "# HFT Network Tuning Configuration"
        echo "# Generated by aws_tuning.sh on $(date)"
        echo "#==============================================================================="
        echo ""
        
        for param in "${!HFT_PARAMS[@]}"; do
            echo "# $(get_param_description "$param")"
            echo "$param = ${HFT_PARAMS[$param]}"
            echo ""
        done
    } > "$SYSCTL_HFT_CONF"
    
    # Apply sysctl settings
    log_info "Applying sysctl parameters..."
    sysctl -p "$SYSCTL_HFT_CONF"
    
    # Apply qdisc setting
    log_info "Setting default queueing discipline to fq..."
    echo fq > /proc/sys/net/core/default_qdisc
    
    # Check if BBR is available
    if modprobe tcp_bbr 2>/dev/null; then
        log_info "BBR congestion control module loaded"
    else
        log_warn "BBR module not available, using current congestion control"
    fi
    
    echo ""
    log_info "Settings applied successfully!"
    log_info "To make changes persistent across reboots, the file $SYSCTL_HFT_CONF has been created."
}

get_param_description() {
    case "$1" in
        "net.core.rmem_max") echo "Maximum socket receive buffer size" ;;
        "net.core.wmem_max") echo "Maximum socket send buffer size" ;;
        "net.ipv4.tcp_rmem") echo "TCP receive buffer sizes (min default max)" ;;
        "net.ipv4.tcp_wmem") echo "TCP send buffer sizes (min default max)" ;;
        "net.core.netdev_max_backlog") echo "Input packet queue backlog" ;;
        "net.ipv4.tcp_fastopen") echo "TCP Fast Open for reduced handshake latency" ;;
        "net.ipv4.tcp_slow_start_after_idle") echo "Disable slow start after idle" ;;
        "net.ipv4.tcp_no_metrics_save") echo "Disable RTT caching" ;;
        "net.ipv4.tcp_low_latency") echo "Favor latency over throughput" ;;
        "net.ipv4.tcp_congestion_control") echo "Congestion control algorithm" ;;
        "net.ipv4.tcp_sack") echo "Selective acknowledgment" ;;
        "net.ipv4.tcp_fack") echo "Forward acknowledgment" ;;
        "net.ipv4.tcp_timestamps") echo "TCP timestamps for RTT calculation" ;;
        "net.ipv4.tcp_window_scaling") echo "TCP window scaling" ;;
        "net.ipv4.tcp_fin_timeout") echo "TIME_WAIT socket timeout" ;;
        "net.ipv4.tcp_tw_reuse") echo "Reuse TIME_WAIT sockets" ;;
        "net.ipv4.tcp_max_syn_backlog") echo "SYN backlog size" ;;
        "net.core.somaxconn") echo "Maximum listen queue backlog" ;;
        "kernel.sched_rt_runtime_us") echo "Real-time scheduling CPU time" ;;
        "vm.swappiness") echo "Swap usage aggressiveness" ;;
        "vm.dirty_ratio") echo "Dirty page ratio threshold" ;;
        "vm.dirty_background_ratio") echo "Background dirty page ratio" ;;
        *) echo "Network parameter" ;;
    esac
}

show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  --apply    Apply HFT tuning parameters (requires root)"
    echo "  --verify   Verify current settings against recommended values"
    echo "  --backup   Create backup of current sysctl configuration"
    echo "  --help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo $0 --apply     # Apply tuning parameters"
    echo "  $0 --verify         # Check current settings"
    echo "  sudo $0 --backup    # Backup current config"
}

show_network_info() {
    log_info "Network Interface Information:"
    echo ""
    
    # Show network interfaces
    ip -br addr 2>/dev/null || ifconfig 2>/dev/null || echo "Unable to get network info"
    
    echo ""
    log_info "Current TCP Congestion Control:"
    sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo "N/A"
    
    echo ""
    log_info "Available Congestion Control Algorithms:"
    sysctl -n net.ipv4.tcp_available_congestion_control 2>/dev/null || echo "N/A"
}

#-------------------------------------------------------------------------------
# Main Script
#-------------------------------------------------------------------------------

print_banner

# Parse arguments
ACTION=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --apply)
            ACTION="apply"
            shift
            ;;
        --verify)
            ACTION="verify"
            shift
            ;;
        --backup)
            ACTION="backup"
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Default action if none specified
if [[ -z "$ACTION" ]]; then
    show_usage
    echo ""
    show_network_info
    exit 0
fi

# Execute requested action
case "$ACTION" in
    "apply")
        check_os
        backup_config
        apply_settings
        verify_settings
        ;;
    "verify")
        verify_settings
        ;;
    "backup")
        check_root
        backup_config
        ;;
esac

log_info "Done!"
