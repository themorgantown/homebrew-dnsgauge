#!/usr/bin/env python3
"""
DNS response tester (UDP + DoH) with live status + ETA.

Examples:
  python3 dnstest.py
  python3 dnstest.py -dohnly
  python3 dnstest.py --udp 8.8.8.8 --doh https://dns.google/dns-query
"""

from __future__ import annotations

import argparse
import base64
import random
import sys
import time
import httpx
from dataclasses import dataclass
from typing import Callable, Iterable, List, Tuple

import dns.message
import dns.query
import dns.rdatatype


DEFAULT_DOMAINS = [
    "google.com", "youtube.com", "facebook.com", "amazon.com", "wikipedia.org",
    "reddit.com", "github.com", "stackoverflow.com", "netflix.com", "apple.com",
    "microsoft.com", "twitter.com", "instagram.com", "linkedin.com", "ebay.com",
    "nytimes.com", "cnn.com", "vercel.com", "spotify.com", "dropbox.com", "cloudflare.com",
]


@dataclass(frozen=True)
class ServerTarget:
    provider: str
    protocol: str  # "UDP" or "DoH"
    endpoint: str


DEFAULT_SERVERS: List[ServerTarget] = [
    # Cloudflare
    ServerTarget("Cloudflare", "UDP", "1.1.1.1"),
    ServerTarget("Cloudflare", "DoH", "https://cloudflare-dns.com/dns-query"),
    # Google
    ServerTarget("Google", "UDP", "8.8.8.8"),
    ServerTarget("Google", "DoH", "https://dns.google/dns-query"),
    # NextDNS
    ServerTarget("NextDNS", "UDP", "45.90.28.0"),
    ServerTarget("NextDNS", "UDP", "45.90.30.0"),
    ServerTarget("NextDNS", "DoH", "https://dns.nextdns.io"),
    # Quad9 - recommended and alternate DoH endpoints
    ServerTarget("Quad9", "UDP", "9.9.9.9"),
    ServerTarget("Quad9", "DoH", "https://dns.quad9.net/dns-query"),
    ServerTarget("Quad9-secure", "DoH", "https://dns9.quad9.net/dns-query"),
    ServerTarget("Quad9-unsecure", "DoH", "https://dns10.quad9.net/dns-query"),
    ServerTarget("Quad9-ECS", "DoH", "https://dns11.quad9.net/dns-query"),
    # Mullvad
    ServerTarget("Mullvad", "UDP", "194.242.2.2"),
    ServerTarget("Mullvad", "DoH", "https://dns.mullvad.net/dns-query"),
    # AdGuard (privacy + ad-blocking)
    ServerTarget("AdGuard", "UDP", "94.140.14.14"),
    ServerTarget("AdGuard", "DoH", "https://dns.adguard.com/dns-query"),
    # LibreDNS (privacy)
    ServerTarget("LibreDNS", "DoH", "https://doh.libredns.gr/dns-query"),
    # OpenDNS
    ServerTarget("OpenDNS", "UDP", "208.67.222.222"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DNS response tester (UDP + DoH).")
    parser.add_argument(
        "-dohnly",
        "--doh-only",
        action="store_true",
        help="Run only DNS-over-HTTPS tests.",
    )
    parser.add_argument(
        "--no-keepalive",
        action="store_true",
        help="Disable HTTP Keep-Alive (use new connection per query).",
    )
    parser.add_argument(
        "--udp",
        action="append",
        default=[],
        help="Add a UDP DNS server IP (repeatable).",
    )
    parser.add_argument(
        "--doh",
        action="append",
        default=[],
        help="Add a DoH server URL (repeatable).",
    )
    parser.add_argument(
        "--domains",
        type=int,
        default=10,
        help="Number of random domains to test (default: 10).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.5,
        help="Timeout per query in seconds (default: 2.5).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for domain selection.",
    )
    return parser.parse_args()


def pick_domains(count: int, seed: int | None) -> List[str]:
    if seed is not None:
        random.seed(seed)
    count = max(1, min(count, len(DEFAULT_DOMAINS)))
    return random.sample(DEFAULT_DOMAINS, count)


def doh_query(
    url: str,
    domain: str,
    timeout: float,
    client: httpx.Client | None = None,
) -> float | None:
    query = dns.message.make_query(domain, dns.rdatatype.A)
    wire = query.to_wire()
    
    headers = {
        "Content-Type": "application/dns-message",
        "Accept": "application/dns-message",
    }

    start = time.perf_counter()
    try:
        # If client is provided, use it (keepalive/http2). If not, use one-off request.
        if client:
            resp = client.post(url, content=wire, headers=headers, timeout=timeout)
        else:
            resp = httpx.post(url, content=wire, headers=headers, timeout=timeout)
            
        if resp.status_code != 200:
            return None
            
    except Exception:
        return None

    end = time.perf_counter()
    return (end - start) * 1000.0


def udp_query(server_ip: str, domain: str, timeout: float) -> float | None:
    query = dns.message.make_query(domain, dns.rdatatype.A)
    start = time.perf_counter()
    try:
        dns.query.udp(query, server_ip, timeout=timeout)
    except Exception:
        return None
    end = time.perf_counter()
    return (end - start) * 1000.0


def format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(seconds):02d}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}m{secs:02d}s"


def status_line(done: int, total: int, avg_ms: float, eta_s: float) -> str:
    pct = 0 if total == 0 else int((done / total) * 100)
    return f"Progress {done}/{total} ({pct}%) | avg {avg_ms:.0f}ms | ETA {format_duration(eta_s)}"


def print_status(line: str) -> None:
    sys.stdout.write("\r" + line + " " * 10)
    sys.stdout.flush()


def compute_stats(values: List[float | None]) -> Tuple[float | None, float | None, float | None, int, float]:
    ok = [v for v in values if v is not None]
    timeouts = len(values) - len(ok)
    if not ok:
        return None, None, None, timeouts, 0.0
    avg = sum(ok) / len(ok)
    return avg, min(ok), max(ok), timeouts, (len(ok) / len(values)) * 100.0


def make_table(headers: List[str], rows: List[List[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def fmt_row(row: Iterable[str]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    lines = [fmt_row(headers), fmt_row(["-" * w for w in widths])]
    lines.extend(fmt_row(row) for row in rows)
    return "\n".join(lines)


def build_servers(udp_list: List[str], doh_list: List[str], doh_only: bool) -> List[ServerTarget]:
    servers = list(DEFAULT_SERVERS)
    servers.extend(ServerTarget("Custom", "UDP", ip) for ip in udp_list)
    servers.extend(ServerTarget("Custom", "DoH", url) for url in doh_list)
    if doh_only:
        servers = [s for s in servers if s.protocol == "DoH"]
    return servers


def compute_score(row: List[str]) -> float:
    """
    Compute a quality score for a DNS server.
    Incorporates: success rate, avg latency, and consistency (min/max range).
    Higher score = better performance.
    """
    avg = float("inf") if row[3] == "—" else float(row[3])
    min_val = float("inf") if row[4] == "—" else float(row[4])
    max_val = float("inf") if row[5] == "—" else float(row[5])
    success = float(row[6].rstrip("%"))

    # If all queries failed, score is 0
    if success == 0:
        return 0.0

    # Success rate component (0-1)
    success_component = success / 100.0

    # Latency component: lower avg is better; scale inversely
    # Use 100 / (avg + 1) so lower avg gives higher score
    latency_component = 100.0 / (avg + 1.0)

    # Consistency component: tight min/max range is better
    # If min==max, consistency is 1.0; wider range reduces it
    if min_val == float("inf") or max_val == float("inf"):
        consistency = 0.0
    else:
        range_val = max_val - min_val
        consistency = 1.0 - min(range_val / (avg + 1.0), 1.0)

    # Combined score: weighted average
    # Success is most important, then latency, then consistency
    score = (success_component * 50) + (latency_component * 40) + (consistency * 10)

    return score


def sort_rows(rows: List[List[str]]) -> None:
    """Sort rows by computed score (highest first)."""
    rows.sort(key=compute_score, reverse=True)


def run_tests(
    servers: List[ServerTarget],
    domains: List[str],
    timeout: float,
    use_keepalive: bool,
    progress_cb: Callable[[int, int, float, float], None] | None = None,
) -> Tuple[List[List[str]], List[str]]:
    if not servers:
        return [], domains

    total = len(servers) * len(domains)
    done = 0
    ema_ms: float | None = None
    all_results: dict[ServerTarget, List[float | None]] = {s: [] for s in servers}

    # Pre-create a client if keepalive is requested.
    # Note: If use_keepalive is False, we pass client=None to doh_query.
    client = None
    if use_keepalive:
        # httpx.Client with http2=True effectively handles connections for multiple hosts.
        # We don't need to manually manage per-host connections like in http.client.
        client = httpx.Client(http2=True, verify=True)

    try:
        for server in servers:
            for domain in domains:
                if server.protocol == "UDP":
                    latency = udp_query(server.endpoint, domain, timeout)
                else:
                    latency = doh_query(server.endpoint, domain, timeout, client=client)
    
                all_results[server].append(latency)
                done += 1
    
                if latency is None:
                    sample_ms = timeout * 1000
                else:
                    sample_ms = latency
    
                if ema_ms is None:
                    ema_ms = sample_ms
                else:
                    ema_ms = (0.2 * sample_ms) + (0.8 * ema_ms)
    
                remaining = total - done
                eta_s = (ema_ms / 1000.0) * remaining if ema_ms is not None else 0.0
                if progress_cb is not None:
                    progress_cb(done, total, ema_ms or 0.0, eta_s)
                    
    finally:
        if client:
            client.close()

    rows: List[List[str]] = []
    for server in servers:
        avg, min_v, max_v, timeouts, success = compute_stats(all_results[server])
        avg_s = "—" if avg is None else f"{avg:.0f}"
        min_s = "—" if min_v is None else f"{min_v:.0f}"
        max_s = "—" if max_v is None else f"{max_v:.0f}"
        rows.append(
            [
                server.provider,
                server.protocol,
                server.endpoint,
                avg_s,
                min_s,
                max_s,
                f"{success:.0f}%",
                str(timeouts),
            ]
        )

    sort_rows(rows)
    return rows, domains


def main() -> int:
    args = parse_args()

    servers = build_servers(args.udp, args.doh, args.doh_only)
    if not servers:
        print("No DNS servers configured.")
        return 1

    domains = pick_domains(args.domains, args.seed)
    print(f"Testing {len(domains)} domains against {len(servers)} servers...")
    
    use_keepalive = not args.no_keepalive
    if use_keepalive:
        print("Keep-Alive (connection reuse) ENABLED for DoH. (Use --no-keepalive to disable)")
    else:
        print("Keep-Alive DISABLED (new connection per query).")

    def cli_progress(done: int, total: int, avg_ms: float, eta_s: float) -> None:
        print_status(status_line(done, total, avg_ms, eta_s))

    rows, _ = run_tests(servers, domains, args.timeout, use_keepalive, progress_cb=cli_progress)
    print("\n")

    table = make_table(
        ["Provider", "Proto", "Endpoint", "Avg ms", "Min", "Max", "Success", "Timeouts"],
        rows,
    )
    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
