# TASK-031: AWS us-east-1 Deployment Tuning (Боевой Сервер)

## Overview

This document describes the TCP stack tuning parameters applied to Ubuntu 22.04 LTS servers in AWS us-east-1 for high-frequency trading (HFT) workloads.

## Objective

Minimize network latency for the Polymarket AI Lead-Lag Scalper by optimizing kernel network parameters.

## Tuning Script Location

- **Script**: [`scripts/aws_tuning.sh`](../../scripts/aws_tuning.sh)
- **Config Output**: `/etc/sysctl.d/99-hft-tuning.conf`

---

## Parameters Tuned

### 1. Socket Buffer Sizes

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.core.rmem_max` | 212992 | 134217728 | Maximum socket receive buffer (128MB) |
| `net.core.wmem_max` | 212992 | 134217728 | Maximum socket send buffer (128MB) |

**Rationale**: Larger buffers prevent packet loss during burst traffic and reduce the need for retransmissions.

### 2. TCP Buffer Sizes

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.ipv4.tcp_rmem` | 4096 131072 6291456 | 4096 16777216 134217728 | TCP receive buffer (min/default/max) |
| `net.ipv4.tcp_wmem` | 4096 16384 4194304 | 4096 16777216 134217728 | TCP send buffer (min/default/max) |

**Rationale**: Increased default and max buffer sizes allow TCP to maintain high throughput without blocking.

### 3. Network Queue Settings

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.core.netdev_max_backlog` | 1000 | 5000 | Input packet queue backlog |
| `net.core.somaxconn` | 128 | 8192 | Maximum listen queue backlog |
| `net.ipv4.tcp_max_syn_backlog` | 128 | 8192 | SYN backlog for connection bursts |

**Rationale**: Larger queues prevent packet drops during traffic spikes common in HFT scenarios.

### 4. TCP Latency Optimization

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.ipv4.tcp_fastopen` | 0 | 3 | Enable TCP Fast Open (client + server) |
| `net.ipv4.tcp_slow_start_after_idle` | 1 | 0 | Disable slow start after idle |
| `net.ipv4.tcp_no_metrics_save` | 0 | 1 | Disable RTT caching |
| `net.ipv4.tcp_low_latency` | 0 | 1 | Favor latency over throughput |

**Rationale**: 
- **TCP Fast Open**: Reduces handshake latency by allowing data in SYN packet
- **Slow Start After Idle**: Prevents congestion window reset after idle periods
- **No Metrics Save**: Prevents stale RTT data from affecting new connections
- **Low Latency**: Instructs kernel to prioritize latency (note: removed in kernel 4.14+)

### 5. TCP Connection Recycling

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.ipv4.tcp_fin_timeout` | 60 | 10 | TIME_WAIT timeout (seconds) |
| `net.ipv4.tcp_tw_reuse` | 0 | 1 | Allow TIME_WAIT socket reuse |

**Rationale**: Faster socket recycling is critical for high-frequency connection churn.

### 6. Congestion Control

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.ipv4.tcp_congestion_control` | cubic | bbr | Congestion control algorithm |
| `net.core.default_qdisc` | fq_codel | fq | Queueing discipline |

**Rationale**: BBR (Bottleneck Bandwidth and RTT) provides better latency characteristics for modern networks compared to loss-based algorithms like CUBIC.

### 7. TCP Reliability Features

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `net.ipv4.tcp_sack` | 1 | 1 | Selective acknowledgment |
| `net.ipv4.tcp_fack` | 1 | 1 | Forward acknowledgment |
| `net.ipv4.tcp_timestamps` | 1 | 1 | TCP timestamps |
| `net.ipv4.tcp_window_scaling` | 1 | 1 | Window scaling |

**Rationale**: These features improve TCP efficiency and should remain enabled.

### 8. System Tuning

| Parameter | Default | HFT Value | Purpose |
|-----------|---------|-----------|---------|
| `kernel.sched_rt_runtime_us` | 950000 | -1 | Unlimited RT scheduling time |
| `vm.swappiness` | 60 | 1 | Minimal swap usage |
| `vm.dirty_ratio` | 20 | 10 | Dirty page threshold |
| `vm.dirty_background_ratio` | 10 | 5 | Background dirty page threshold |

**Rationale**:
- **RT Scheduling**: Allows real-time tasks unlimited CPU time
- **Swappiness**: Prevents swap-induced latency spikes
- **Dirty Ratios**: More predictable I/O behavior

---

## How to Apply

### Prerequisites

- Ubuntu 22.04 LTS (or compatible Debian-based system)
- Root/sudo access
- Tested in staging environment first

### Step 1: Verify Current Settings

```bash
# Check current network settings
./scripts/aws_tuning.sh --verify
```

### Step 2: Backup Current Configuration

```bash
# Create backup before changes
sudo ./scripts/aws_tuning.sh --backup
```

### Step 3: Apply Tuning

```bash
# Apply all HFT tuning parameters
sudo ./scripts/aws_tuning.sh --apply
```

### Step 4: Verify Changes

```bash
# Verify settings were applied correctly
./scripts/aws_tuning.sh --verify
```

### Step 5: Make Persistent (Automatic)

The script creates `/etc/sysctl.d/99-hft-tuning.conf` which persists across reboots.

---

## Verification Commands

### Check Individual Parameters

```bash
# Check socket buffer sizes
sysctl net.core.rmem_max net.core.wmem_max

# Check TCP buffers
sysctl net.ipv4.tcp_rmem net.ipv4.tcp_wmem

# Check congestion control
sysctl net.ipv4.tcp_congestion_control

# Check all HFT parameters
sysctl -a | grep -E "(rmem|wmem|tcp_fastopen|tcp_slow_start|tcp_congestion)"
```

### Check Runtime Configuration

```bash
# List all sysctl settings
sysctl -a

# Check specific config file
sysctl -p /etc/sysctl.d/99-hft-tuning.conf
```

### Network Performance Testing

```bash
# Check network interface statistics
ip -s link

# Monitor network latency
ping -i 0.1 -c 100 <polymarket-api-endpoint>

# Check TCP connection states
ss -s

# Monitor real-time network stats
watch -n 1 'netstat -i'
```

---

## Rollback Procedure

If issues occur after applying tuning:

### Option 1: Restore Backup

```bash
# Restore original sysctl.conf
sudo cp /etc/sysctl.conf.hft-backup /etc/sysctl.conf

# Remove HFT config
sudo rm /etc/sysctl.d/99-hft-tuning.conf

# Reload sysctl
sudo sysctl -p
```

### Option 2: Reset to Defaults

```bash
# Remove HFT config
sudo rm /etc/sysctl.d/99-hft-tuning.conf

# Reload system defaults
sudo sysctl --system

# Reboot for full reset
sudo reboot
```

---

## AWS-Specific Considerations

### EC2 Instance Types

Recommended instance types for HFT in us-east-1:
- **c6i.xlarge** or larger - Compute optimized
- **c6a.xlarge** or larger - AMD EPYC based
- **z1d.xlarge** or larger - High frequency (4.0 GHz)

### Enhanced Networking

Ensure Enhanced Networking is enabled:
```bash
# Check if ENA is enabled
ethtool -i eth0 | grep driver

# Should show "ena" for AWS Enhanced Networking
```

### Placement Groups

For lowest latency:
- Use **Cluster Placement Groups** for instances that need low-latency communication
- Place instances in the same Availability Zone

### Network Performance

```bash
# Check network bandwidth capability
ethtool -k eth0 | grep -i offload

# Enable all offload features for best performance
sudo ethtool -K eth0 gro on gso on tso on
```

---

## Monitoring

### Key Metrics to Monitor

1. **Network Latency**: RTT to Polymarket API endpoints
2. **Packet Loss**: `netstat -i` for errors/drops
3. **TCP Retransmissions**: `netstat -s | grep retransmit`
4. **Socket Buffer Usage**: `ss -m`

### CloudWatch Metrics

Monitor these EC2 metrics:
- `NetworkIn` / `NetworkOut`
- `NetworkPacketsIn` / `NetworkPacketsOut`

---

## Security Considerations

1. **Firewall Rules**: Ensure tuning doesn't bypass security groups
2. **Rate Limiting**: May need adjustment for higher connection rates
3. **Monitoring**: Log any unusual network patterns

---

## Testing Checklist

- [ ] Script runs without errors
- [ ] All parameters applied correctly
- [ ] Settings persist after reboot
- [ ] Network connectivity verified
- [ ] Application connectivity tested
- [ ] Latency benchmarks improved
- [ ] No packet loss observed
- [ ] Rollback procedure tested

---

## References

- [Linux Kernel TCP Parameters](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt)
- [AWS Enhanced Networking](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/enhanced-networking.html)
- [TCP BBR Congestion Control](https://research.google/pubs/pub45646/)
- [RFC 7413 - TCP Fast Open](https://tools.ietf.org/html/rfc7413)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-09 | 1.0 | Initial implementation |
