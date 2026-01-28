#!/usr/bin/env python3
"""
DNSgauge: DNS response tester (UDP + DoH) with live status + ETA.

Examples:
  dnsgauge
  dnsgauge --comprehensive
  dnsgauge --passes 3 --mode warm
  dnsgauge --qtypes A,AAAA,HTTPS
  dnsgauge -dohnly
  dnsgauge --udp 8.8.8.8 --doh https://dns.google/dns-query
"""

from __future__ import annotations

import argparse
import base64  # kept for compatibility with earlier revisions (unused)
import random
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import dns.flags
import dns.message
import dns.query
import dns.rdatatype
import dns.resolver


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
    # NextDNS (NOTE: Many NextDNS DoH deployments require a config path; customize with --doh)
    ServerTarget("NextDNS", "UDP", "45.90.28.0"),
    ServerTarget("NextDNS", "UDP", "45.90.30.0"),
    ServerTarget("NextDNS", "DoH", "https://dns.nextdns.io"),
    # Quad9
    ServerTarget("Quad9", "UDP", "9.9.9.9"),
    ServerTarget("Quad9", "DoH", "https://dns.quad9.net/dns-query"),
    ServerTarget("Quad9-ECS", "DoH", "https://dns11.quad9.net/dns-query"),
    # Mullvad
    ServerTarget("Mullvad", "UDP", "194.242.2.2"),
    ServerTarget("Mullvad", "DoH", "https://dns.mullvad.net/dns-query"),
    # AdGuard
    ServerTarget("AdGuard", "UDP", "94.140.14.14"),
    ServerTarget("AdGuard", "DoH", "https://dns.adguard.com/dns-query"),
    # LibreDNS
    ServerTarget("LibreDNS", "DoH", "https://doh.libredns.gr/dns-query"),
    # OpenDNS
    ServerTarget("OpenDNS", "UDP", "208.67.222.222"),
]


# -----------------------------
# Measurement + aggregation
# -----------------------------

@dataclass
class Measurement:
    latency_ms: Optional[float]
    ok: bool
    error_kind: str  # "ok", "timeout", "http_err", "parse_err", "nxdomain", "servfail", "other"
    resp_bytes: int
    qtype: str
    pass_index: int  # 1-based
    # UDP-only
    trunc: bool = False
    tcp_fallback: bool = False
    # DoH-only
    http_version: str = ""


def percentile(sorted_vals: List[float], p: float) -> float:
    """
    Simple inclusive percentile.
    p in [0,100]. Assumes sorted_vals is non-empty and sorted.
    """
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return d0 + d1


@dataclass
class Metrics:
    n: int
    success_pct: float
    timeout_pct: float
    p50_ms: Optional[float]
    p95_ms: Optional[float]
    avg_ms: Optional[float]
    jitter_ms: Optional[float]  # stdev
    # error breakdown
    nxdomain_pct: float
    servfail_pct: float
    http_err_pct: float
    parse_err_pct: float
    other_err_pct: float
    # transport
    trunc_pct: float
    tcpfb_pct: float
    resp_kb_p95: Optional[float]
    # DoH-only
    http_version_mode: str
    conn_reuse_est_pct: Optional[float]  # estimated, if applicable


def compute_metrics(
    measures: List[Measurement],
    protocol: str,
    use_keepalive: bool,
    doh_host_count: int,
) -> Metrics:
    n = len(measures)
    if n == 0:
        return Metrics(
            n=0,
            success_pct=0.0,
            timeout_pct=0.0,
            p50_ms=None,
            p95_ms=None,
            avg_ms=None,
            jitter_ms=None,
            nxdomain_pct=0.0,
            servfail_pct=0.0,
            http_err_pct=0.0,
            parse_err_pct=0.0,
            other_err_pct=0.0,
            trunc_pct=0.0,
            tcpfb_pct=0.0,
            resp_kb_p95=None,
            http_version_mode="",
            conn_reuse_est_pct=None,
        )

    ok_lat = [m.latency_ms for m in measures if m.ok and m.latency_ms is not None]
    ok_lat_sorted = sorted(ok_lat)
    avg = (sum(ok_lat) / len(ok_lat)) if ok_lat else None
    p50 = percentile(ok_lat_sorted, 50) if ok_lat_sorted else None
    p95 = percentile(ok_lat_sorted, 95) if ok_lat_sorted else None
    jitter = statistics.pstdev(ok_lat) if len(ok_lat) >= 2 else (0.0 if len(ok_lat) == 1 else None)

    def pct(kind: str) -> float:
        return (sum(1 for m in measures if m.error_kind == kind) / n) * 100.0

    success_pct = (sum(1 for m in measures if m.ok) / n) * 100.0
    timeout_pct = pct("timeout")
    nxdomain_pct = pct("nxdomain")
    servfail_pct = pct("servfail")
    http_err_pct = pct("http_err")
    parse_err_pct = pct("parse_err")
    other_err_pct = pct("other")

    trunc_pct = (sum(1 for m in measures if m.trunc) / n) * 100.0
    tcpfb_pct = (sum(1 for m in measures if m.tcp_fallback) / n) * 100.0

    resp_sizes = sorted([m.resp_bytes for m in measures if m.resp_bytes > 0])
    resp_kb_p95 = (percentile(resp_sizes, 95) / 1024.0) if resp_sizes else None

    # DoH HTTP version "mode" (most common)
    hv = [m.http_version for m in measures if m.http_version]
    http_version_mode = ""
    if hv:
        counts: Dict[str, int] = {}
        for v in hv:
            counts[v] = counts.get(v, 0) + 1
        http_version_mode = max(counts.items(), key=lambda kv: kv[1])[0]

    # Connection reuse estimate:
    # - If keepalive is enabled for DoH, we approximate "new connections" as 1 per unique host.
    # - If keepalive is disabled, we treat each request as new connection.
    # This is an estimate; httpx does not expose precise per-request connection reuse.
    conn_reuse_est_pct: Optional[float] = None
    if protocol == "DoH":
        if n > 0:
            if use_keepalive:
                new_conns_est = max(1, doh_host_count)
            else:
                new_conns_est = n
            conn_reuse_est_pct = max(0.0, (1.0 - (new_conns_est / n)) * 100.0)

    return Metrics(
        n=n,
        success_pct=success_pct,
        timeout_pct=timeout_pct,
        p50_ms=p50,
        p95_ms=p95,
        avg_ms=avg,
        jitter_ms=jitter,
        nxdomain_pct=nxdomain_pct,
        servfail_pct=servfail_pct,
        http_err_pct=http_err_pct,
        parse_err_pct=parse_err_pct,
        other_err_pct=other_err_pct,
        trunc_pct=trunc_pct,
        tcpfb_pct=tcpfb_pct,
        resp_kb_p95=resp_kb_p95,
        http_version_mode=http_version_mode,
        conn_reuse_est_pct=conn_reuse_est_pct,
    )


# -----------------------------
# CLI / selection
# -----------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DNS response tester (UDP + DoH).")
    parser.add_argument(
        "--version",
        action="version",
        version="dnsgauge 1.1.0",
    )
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
        "--comprehensive",
        action="store_true",
        help="Print comprehensive drilldown table instead of summary table.",
    )
    parser.add_argument(
        "--mode",
        choices=["mixed", "warm"],
        default="mixed",
        help="Aggregation mode. 'warm' excludes pass 1 when --passes > 1.",
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=1,
        help="Number of passes to run over the same queries (default: 1).",
    )
    parser.add_argument(
        "--qtypes",
        type=str,
        default="A,AAAA,HTTPS",
        help="Comma-separated QTYPEs to test (default: A,AAAA,HTTPS).",
    )
    parser.add_argument(
        "--edns-payload",
        type=int,
        default=1232,
        help="EDNS0 UDP payload size (default: 1232).",
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


def parse_qtypes(qtypes_csv: str) -> List[Tuple[str, int]]:
    """
    Returns list of (label, rdatatype_int). Supports at least A, AAAA, HTTPS, SVCB.
    Falls back to numeric if dnspython lacks attribute.
    """
    raw = [x.strip().upper() for x in qtypes_csv.split(",") if x.strip()]
    out: List[Tuple[str, int]] = []
    for label in raw:
        if label == "A":
            out.append(("A", dns.rdatatype.A))
        elif label == "AAAA":
            out.append(("AAAA", dns.rdatatype.AAAA))
        elif label == "HTTPS":
            # dnspython supports HTTPS in recent versions; fallback to 65
            rt = getattr(dns.rdatatype, "HTTPS", 65)
            out.append(("HTTPS", int(rt)))
        elif label == "SVCB":
            rt = getattr(dns.rdatatype, "SVCB", 64)
            out.append(("SVCB", int(rt)))
        else:
            # Try dnspython constant, else numeric
            rt = getattr(dns.rdatatype, label, None)
            if rt is not None:
                out.append((label, int(rt)))
            else:
                try:
                    out.append((label, int(label)))
                except ValueError:
                    # Skip unknown token
                    continue
    # Ensure at least A
    return out or [("A", dns.rdatatype.A)]


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


def get_system_resolvers() -> List[str]:
    """Retrieve system-configured DNS resolvers."""
    try:
        resolver = dns.resolver.get_default_resolver()
        return list(resolver.nameservers)
    except Exception:
        return []


def build_servers(udp_list: List[str], doh_list: List[str], doh_only: bool) -> List[ServerTarget]:
    system_ips = get_system_resolvers()
    servers: List[ServerTarget] = []

    for s in DEFAULT_SERVERS:
        provider = s.provider
        if s.protocol == "UDP" and s.endpoint in system_ips:
            provider = f"{provider} (current)"
        servers.append(ServerTarget(provider, s.protocol, s.endpoint))

    if not doh_only:
        for ip in system_ips:
            if not any(s.endpoint == ip for s in servers):
                servers.append(ServerTarget("System (selected)", "UDP", ip))

    for ip in udp_list:
        provider = "Custom"
        if ip in system_ips:
            provider = f"{provider} (current)"
        servers.append(ServerTarget(provider, "UDP", ip))

    for url in doh_list:
        servers.append(ServerTarget("Custom", "DoH", url))

    if doh_only:
        servers = [s for s in servers if s.protocol == "DoH"]
    return servers


# -----------------------------
# Query implementations
# -----------------------------

def make_dns_query(domain: str, rdatatype_int: int, edns_payload: int) -> dns.message.Message:
    q = dns.message.make_query(domain, rdatatype_int)
    # EDNS0 to reflect modern clients; payload defaults vary, so we set it explicitly.
    q.use_edns(edns=0, payload=edns_payload)
    return q


def classify_dns_rcode(resp: dns.message.Message) -> str:
    rcode = resp.rcode()
    if rcode == dns.rcode.NOERROR:
        return "ok"
    if rcode == dns.rcode.NXDOMAIN:
        return "nxdomain"
    if rcode == dns.rcode.SERVFAIL:
        return "servfail"
    return "other"


def udp_query(
    server_ip: str,
    domain: str,
    qtype_label: str,
    qtype_int: int,
    timeout: float,
    edns_payload: int,
) -> Measurement:
    query = make_dns_query(domain, qtype_int, edns_payload)
    start = time.perf_counter()
    try:
        resp = dns.query.udp(query, server_ip, timeout=timeout)
        end = time.perf_counter()

        trunc = bool(resp.flags & dns.flags.TC)
        resp_bytes = len(resp.to_wire()) if resp is not None else 0

        if trunc:
            # TCP fallback (more realistic client behavior)
            try:
                start_tcp = time.perf_counter()
                resp2 = dns.query.tcp(query, server_ip, timeout=timeout)
                end_tcp = time.perf_counter()
                resp_bytes2 = len(resp2.to_wire()) if resp2 is not None else resp_bytes
                kind = classify_dns_rcode(resp2)
                ok = (kind == "ok") or (kind in ("nxdomain",))  # NXDOMAIN is not transport failure
                return Measurement(
                    latency_ms=(end_tcp - start_tcp) * 1000.0,
                    ok=ok,
                    error_kind=kind if ok else kind,
                    resp_bytes=resp_bytes2,
                    qtype=qtype_label,
                    pass_index=1,  # overwritten by caller
                    trunc=True,
                    tcp_fallback=True,
                )
            except Exception:
                # We saw truncation but TCP failed
                return Measurement(
                    latency_ms=(end - start) * 1000.0,
                    ok=False,
                    error_kind="other",
                    resp_bytes=resp_bytes,
                    qtype=qtype_label,
                    pass_index=1,
                    trunc=True,
                    tcp_fallback=True,
                )

        kind = classify_dns_rcode(resp)
        ok = (kind == "ok") or (kind in ("nxdomain",))
        return Measurement(
            latency_ms=(end - start) * 1000.0,
            ok=ok,
            error_kind=kind if ok else kind,
            resp_bytes=resp_bytes,
            qtype=qtype_label,
            pass_index=1,
            trunc=False,
            tcp_fallback=False,
        )
    except dns.exception.Timeout:
        return Measurement(
            latency_ms=None,
            ok=False,
            error_kind="timeout",
            resp_bytes=0,
            qtype=qtype_label,
            pass_index=1,
        )
    except Exception:
        return Measurement(
            latency_ms=None,
            ok=False,
            error_kind="other",
            resp_bytes=0,
            qtype=qtype_label,
            pass_index=1,
        )


def doh_query(
    url: str,
    domain: str,
    qtype_label: str,
    qtype_int: int,
    timeout: float,
    edns_payload: int,
    client: httpx.Client | None = None,
) -> Measurement:
    query = make_dns_query(domain, qtype_int, edns_payload)
    wire = query.to_wire()

    headers = {
        "Content-Type": "application/dns-message",
        "Accept": "application/dns-message",
    }

    start = time.perf_counter()
    try:
        if client:
            resp = client.post(url, content=wire, headers=headers, timeout=timeout)
        else:
            resp = httpx.post(url, content=wire, headers=headers, timeout=timeout)
        end = time.perf_counter()

        http_ver = getattr(resp, "http_version", "") or ""

        if resp.status_code != 200:
            return Measurement(
                latency_ms=(end - start) * 1000.0,
                ok=False,
                error_kind="http_err",
                resp_bytes=len(resp.content or b""),
                qtype=qtype_label,
                pass_index=1,
                http_version=http_ver,
            )

        # Parse and classify DNS result
        try:
            dns_resp = dns.message.from_wire(resp.content)
        except Exception:
            return Measurement(
                latency_ms=(end - start) * 1000.0,
                ok=False,
                error_kind="parse_err",
                resp_bytes=len(resp.content or b""),
                qtype=qtype_label,
                pass_index=1,
                http_version=http_ver,
            )

        kind = classify_dns_rcode(dns_resp)
        ok = (kind == "ok") or (kind in ("nxdomain",))
        return Measurement(
            latency_ms=(end - start) * 1000.0,
            ok=ok,
            error_kind=kind if ok else kind,
            resp_bytes=len(resp.content or b""),
            qtype=qtype_label,
            pass_index=1,
            http_version=http_ver,
        )

    except httpx.TimeoutException:
        return Measurement(
            latency_ms=None,
            ok=False,
            error_kind="timeout",
            resp_bytes=0,
            qtype=qtype_label,
            pass_index=1,
        )
    except Exception:
        return Measurement(
            latency_ms=None,
            ok=False,
            error_kind="other",
            resp_bytes=0,
            qtype=qtype_label,
            pass_index=1,
        )


# -----------------------------
# Scoring + table composition
# -----------------------------

def compute_score(m: Metrics) -> float:
    """
    Higher score = better.
    Prioritize success, then tail latency (p95), then median, then stability.
    """
    if m.n == 0 or m.success_pct == 0:
        return 0.0

    # Defaults if not available
    p50 = m.p50_ms if m.p50_ms is not None else 10_000.0
    p95 = m.p95_ms if m.p95_ms is not None else 10_000.0
    jitter = m.jitter_ms if m.jitter_ms is not None else 10_000.0

    success_component = (m.success_pct / 100.0) * 60.0
    tail_component = 25.0 * (100.0 / (p95 + 25.0))   # damped
    med_component = 10.0 * (100.0 / (p50 + 25.0))
    stable_component = 5.0 * (100.0 / (jitter + 10.0))

    return success_component + tail_component + med_component + stable_component


def fmt_ms(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.0f}"


def fmt_pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.0f}%"


def fmt_kb(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.1f}"


def doh_host_key(url: str) -> str:
    try:
        u = urlparse(url)
        host = u.hostname or ""
        port = u.port or (443 if u.scheme == "https" else 80)
        return f"{u.scheme}://{host}:{port}"
    except Exception:
        return url


def run_tests(
    servers: List[ServerTarget],
    domains: List[str],
    qtypes: List[Tuple[str, int]],
    timeout: float,
    edns_payload: int,
    passes: int,
    mode: str,
    use_keepalive: bool,
    progress_cb: Callable[[int, int, float, float], None] | None = None,
) -> Tuple[List[List[str]], List[List[str]]]:
    """
    Returns: (summary_rows, comprehensive_rows)
    """
    if not servers:
        return [], []

    passes = max(1, passes)
    total = len(servers) * len(domains) * len(qtypes) * passes
    done = 0
    ema_ms: float | None = None

    # Prepare DoH client if keepalive requested
    client = None
    if use_keepalive:
        client = httpx.Client(http2=True, verify=True)

    # For connection reuse estimate we need the number of distinct DoH hosts we actually contact.
    doh_hosts = set()
    for s in servers:
        if s.protocol == "DoH":
            doh_hosts.add(doh_host_key(s.endpoint))
    doh_host_count = len(doh_hosts)

    # Collect measurements per server
    results: Dict[ServerTarget, List[Measurement]] = {s: [] for s in servers}

    try:
        for p in range(1, passes + 1):
            for server in servers:
                for domain in domains:
                    for qlabel, qint in qtypes:
                        if server.protocol == "UDP":
                            meas = udp_query(server.endpoint, domain, qlabel, qint, timeout, edns_payload)
                        else:
                            meas = doh_query(server.endpoint, domain, qlabel, qint, timeout, edns_payload, client=client)

                        meas.pass_index = p
                        results[server].append(meas)

                        done += 1
                        sample_ms = (timeout * 1000.0) if (meas.latency_ms is None) else meas.latency_ms
                        ema_ms = sample_ms if ema_ms is None else (0.2 * sample_ms) + (0.8 * ema_ms)
                        remaining = total - done
                        eta_s = (ema_ms / 1000.0) * remaining if ema_ms is not None else 0.0
                        if progress_cb is not None:
                            progress_cb(done, total, ema_ms or 0.0, eta_s)

    finally:
        if client:
            client.close()

    # Aggregate selection (warm excludes pass 1 if passes > 1)
    def select_measures(allm: List[Measurement]) -> List[Measurement]:
        if mode == "warm" and passes > 1:
            return [m for m in allm if m.pass_index >= 2]
        return allm

    # Build row sets
    summary_rows: List[List[str]] = []
    comp_rows: List[List[str]] = []

    for server in servers:
        sel = select_measures(results[server])
        m = compute_metrics(sel, server.protocol, use_keepalive, doh_host_count)
        score = compute_score(m)

        # Notes: compact “one-liner”
        notes_parts: List[str] = []
        if server.protocol == "UDP":
            if m.tcpfb_pct >= 1.0:
                notes_parts.append(f"tcpfb {m.tcpfb_pct:.0f}%")
            if m.trunc_pct >= 1.0:
                notes_parts.append(f"trunc {m.trunc_pct:.0f}%")
        else:
            if m.http_version_mode:
                notes_parts.append(m.http_version_mode)
            if m.conn_reuse_est_pct is not None:
                notes_parts.append(f"reuse~{m.conn_reuse_est_pct:.0f}%")
        note = ", ".join(notes_parts) if notes_parts else "—"

        # Summary row (UX-focused)
        summary_rows.append([
            f"{score:05.1f}",
            server.provider,
            server.protocol,
            "warm" if (mode == "warm" and passes > 1) else "mixed",
            f"{m.success_pct:.0f}%",
            fmt_ms(m.p50_ms),
            fmt_ms(m.p95_ms),
            fmt_ms(m.jitter_ms),
            fmt_pct(m.timeout_pct),
            note,
        ])

        # Comprehensive row (drilldown)
        comp_rows.append([
            f"{score:05.1f}",
            server.provider,
            server.protocol,
            server.endpoint,
            "warm" if (mode == "warm" and passes > 1) else "mixed",
            "/".join([qt[0] for qt in qtypes]),
            str(m.n),
            f"{m.success_pct:.0f}%",
            fmt_ms(m.p50_ms),
            fmt_ms(m.p95_ms),
            fmt_ms(m.avg_ms),
            fmt_ms(m.jitter_ms),
            fmt_pct(m.timeout_pct),
            fmt_pct(m.nxdomain_pct),
            fmt_pct(m.servfail_pct),
            fmt_pct(m.http_err_pct) if server.protocol == "DoH" else "—",
            fmt_pct(m.parse_err_pct) if server.protocol == "DoH" else "—",
            fmt_pct(m.other_err_pct),
            fmt_pct(m.trunc_pct) if server.protocol == "UDP" else "—",
            fmt_pct(m.tcpfb_pct) if server.protocol == "UDP" else "—",
            fmt_kb(m.resp_kb_p95),
            (m.http_version_mode if server.protocol == "DoH" else "—"),
            (fmt_pct(m.conn_reuse_est_pct) if server.protocol == "DoH" else "—"),
        ])

    # Sort by score desc (first col)
    summary_rows.sort(key=lambda r: float(r[0]), reverse=True)
    comp_rows.sort(key=lambda r: float(r[0]), reverse=True)

    # Add rank numbers
    for i, r in enumerate(summary_rows, start=1):
        r.insert(0, str(i))
    for i, r in enumerate(comp_rows, start=1):
        r.insert(0, str(i))

    return summary_rows, comp_rows


def main() -> int:
    args = parse_args()

    servers = build_servers(args.udp, args.doh, args.doh_only)
    if not servers:
        print("No DNS servers configured.")
        return 1

    domains = pick_domains(args.domains, args.seed)
    qtypes = parse_qtypes(args.qtypes)
    passes = max(1, args.passes)
    mode = args.mode

    use_keepalive = not args.no_keepalive

    # Header describing run scope (prevents misreading tables)
    qtypes_label = "/".join([q[0] for q in qtypes])
    agg_label = "warm" if (mode == "warm" and passes > 1) else "mixed"
    print(
        f"Run: mode={agg_label}, passes={passes}, qtypes={qtypes_label}, "
        f"domains={len(domains)}, servers={len(servers)}, timeout={args.timeout:.1f}s, "
        f"edns_payload={args.edns_payload}, DoH_keepalive={'on' if use_keepalive else 'off'}"
    )

    def cli_progress(done: int, total: int, avg_ms: float, eta_s: float) -> None:
        print_status(status_line(done, total, avg_ms, eta_s))

    summary_rows, comp_rows = run_tests(
        servers=servers,
        domains=domains,
        qtypes=qtypes,
        timeout=args.timeout,
        edns_payload=args.edns_payload,
        passes=passes,
        mode=mode,
        use_keepalive=use_keepalive,
        progress_cb=cli_progress,
    )
    print("\n")

    if args.comprehensive:
        table = make_table(
            [
                "Rank", "Score", "Provider", "Proto", "Endpoint", "Mode", "QTypes", "N",
                "Success", "p50", "p95", "Avg", "Jitter", "Timeout",
                "NX", "SF", "HTTPerr", "ParseErr", "OtherErr",
                "Trunc", "TCPfb", "RespKB_p95", "HTTPver", "Reuse~",
            ],
            comp_rows,
        )
    else:
        table = make_table(
            ["Rank", "Score", "Provider", "Proto", "Mode", "Success", "p50", "p95", "Jitter", "Timeout", "Notes"],
            summary_rows,
        )

    print(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())