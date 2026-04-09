# DNS Caching for Pingu

## Problem

Pingu monitors sites across many different providers. When the upstream DNS
resolver is flaky, resolution fails for *all* monitored sites simultaneously,
creating a storm of false UP/DOWN transitions and spurious alert emails.

This is made worse by the short TTLs (~300s) on most of the monitored domains —
DNS lookups happen frequently and can't be served from the system's default
cache.

## Solution

A local **Unbound** DNS resolver runs on `127.0.0.1:53` with:

- **Minimum TTL of 24 hours** (`cache-min-ttl: 86400`) — all DNS records are
  cached for at least 24h regardless of the upstream TTL.
- **Serve-expired** — if the cached record expires *and* the upstream is
  unreachable, stale records are served for up to 48h while Unbound retries in
  the background.
- **Dual upstream forwarders** — queries are forwarded to `1.1.1.1` (Cloudflare)
  and `8.8.8.8` (Google) for redundancy.

This is safe because Pingu is the only DNS consumer on this host, and we know
in advance when we're moving a monitored server (so we can flush manually).

## Configuration

Config file: `/etc/unbound/unbound.conf.d/pingu-cache.conf`

```ini
server:
    interface: 127.0.0.1
    access-control: 127.0.0.0/8 allow

    cache-min-ttl: 86400

    serve-expired: yes
    serve-expired-ttl: 172800
    serve-expired-client-timeout: 1800

    msg-cache-size: 8m
    rrset-cache-size: 16m

forward-zone:
    name: "."
    forward-addr: 1.1.1.1
    forward-addr: 8.8.8.8
```

System resolver (`/etc/resolv.conf`):

```
nameserver 127.0.0.1
nameserver 1.1.1.1
```

## Operations

### Check status

```bash
sudo systemctl status unbound
sudo unbound-control stats_noreset
```

### Flush cache after a server migration

```bash
# Flush a specific domain
sudo unbound-control flush example.com

# Flush everything
sudo unbound-control flush_zone .
```

### Restart

```bash
sudo systemctl restart unbound
```

### Validate config after editing

```bash
sudo unbound-checkconf
```
