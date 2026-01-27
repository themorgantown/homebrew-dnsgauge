# DNS Response Tester

A command-line tool to benchmark DNS servers and DNS-over-HTTPS (DoH) endpoints. Tests default providers (Cloudflare, NextDNS, Quad9, Mullvad) or custom servers, measuring latency and success rates across multiple domains. After running `python3 dnstest.py`, the results will be displayed in a table sorted by latency and success rate like: 


| Provider | Proto | Endpoint | Avg ms | Min | Max | Success | Timeouts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| NextDNS | UDP | 45.90.28.0 | 27 | 21 | 34 | 100% | 0 |
| NextDNS | UDP | 45.90.30.0 | 28 | 23 | 38 | 100% | 0 |
| Quad9 | UDP | 9.9.9.9 | 28 | 20 | 41 | 100% | 0 |
| Mullvad | UDP | 194.242.2.2 | 27 | 22 | 32 | 80% | 2 |
| Cloudflare | UDP | 1.1.1.1 | 30 | 23 | 36 | 100% | 0 |
| Google | UDP | 8.8.8.8 | 34 | 24 | 48 | 100% | 0 |
| OpenDNS | UDP | 208.67.222.222 | 40 | 22 | 95 | 100% | 0 |
| Quad9-secure | DoH | https://dns9.quad9.net/dns-query | 54 | 20 | 130 | 100% | 0 |
| AdGuard | UDP | 94.140.14.14 | 55 | 19 | 175 | 100% | 0 |
| Google | DoH | https://dns.google/dns-query | 60 | 42 | 126 | 100% | 0 |
| Mullvad | DoH | https://dns.mullvad.net/dns-query | 60 | 29 | 116 | 100% | 0 |

These results give you an idea about which DNS server is the best for you based on response times. The tool places the best performing servers at the top of the list.

## Features

- **Dual protocol support**: UDP (port 53) and DNS-over-HTTPS (DoH)
- **Default providers**: Cloudflare, NextDNS, Quad9, Mullvad (both UDP and DoH endpoints)
- **Live status updates**: Progress, average latency, and ETA while running
- **Results table**: Sorted by latency and success rate
- **Simulates Keep-Alive**: Reuses connections for DoH queries to reduce latency. Most routers support this feature.
- **Customizable**: Add your own servers and domains


## Quick Start

### Usage

```bash
# Run default test (UDP + DoH, 10 random domains)
# Note: Keep-Alive (connection reuse) is ENABLED by default for DoH
python3 dnstest.py

# DoH only
python3 dnstest.py -dohnly

# Disable Keep-Alive (force new connection per query)
python3 dnstest.py --no-keepalive

# Custom test count and timeout
python3 dnstest.py --domains 15 --timeout 3.0

# Add custom servers
python3 dnstest.py --udp 8.8.8.8 --doh https://dns.google/dns-query
```

## Setup & Development

### Prerequisites

- Python 3.11+ (macOS, Linux, or Windows)
- pip or conda

### Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt
```

### Files

- **dnstest.py**: Core CLI engine with `run_tests()`, `build_servers()`, and argument parsing
- **requirements.txt**: Python dependencies (`dnspython`, `httpx[http2]`)

## CLI Arguments

```
usage: dnstest.py [-h] [-dohnly] [--no-keepalive] [--udp IP] [--doh URL] [--domains N] [--timeout S] [--seed N]

optional arguments:
  -h, --help           show this help message and exit
  -dohnly              Run only DNS-over-HTTPS tests
  --no-keepalive       Disable HTTP Keep-Alive (use new connection per query)
  --udp IP             Add a UDP DNS server IP (repeatable, e.g., --udp 8.8.8.8)
  --doh URL            Add a DoH server URL (repeatable, e.g., --doh https://dns.google/dns-query)
  --domains N          Number of random domains to test (default: 10, max: 21)
  --timeout S          Timeout per query in seconds (default: 2.5)
  --seed N             Random seed for domain selection (default: None, random)
```

## Examples

### Test 15 domains against default providers with 3-second timeout

```bash
python3 dnstest.py --domains 15 --timeout 3.0
```

Output:
```
Testing 15 domains against 8 servers...
Progress 120/120 (100%) | avg 45ms | ETA 00s

Provider      Proto  Endpoint                          Avg ms  Min  Max  Success  Timeouts
Cloudflare    UDP    1.1.1.1                           42      18   67   100%     0
Mullvad       UDP    194.242.2.2                       48      22   71   100%     0
Cloudflare    DoH    cloudflare-dns.com               45      20   68   100%     0
...
```

### Test only DoH endpoints with custom timeout

```bash
python3 dnstest.py -dohnly --timeout 5.0
```

### Add a custom DNS server

```bash
python3 dnstest.py --udp 1.0.0.1
```

### Use a fixed random seed (reproducible results)

```bash
python3 dnstest.py --seed 42
```

## Customizing Default Servers

Edit `dnstest.py` and modify `DEFAULT_SERVERS`:

```python
DEFAULT_SERVERS: List[ServerTarget] = [
    ServerTarget("Cloudflare", "UDP", "1.1.1.1"),
    ServerTarget("Cloudflare", "DoH", "https://cloudflare-dns.com/dns-query"),
    # Add your own:
    ServerTarget("MyProvider", "UDP", "192.0.2.1"),
]
```

## Customizing Test Domains

Edit `dnstest.py` and modify `DEFAULT_DOMAINS`:

```python
DEFAULT_DOMAINS = [
    "google.com", "example.com", "your-domain.com", ...
]
```

## Development Notes

### Core APIs

**run_tests()**: Execute tests and collect results
```python
rows, domains = run_tests(
    servers=[ServerTarget(...)],
    domains=["example.com", ...],
    timeout=2.5,
    progress_cb=lambda done, total, avg_ms, eta_s: print(...)
)
```

**build_servers()**: Build server list from defaults and custom inputs
```python
servers = build_servers(
    udp_list=["8.8.8.8"],
    doh_list=["https://dns.google/dns-query"],
    doh_only=False
)
```

### Adding Features

- **More providers**: Add entries to `DEFAULT_SERVERS`.
- **Custom metrics**: Modify `compute_stats()` to calculate additional stats.
- **Export formats**: Add JSON/CSV output in `run_tests()` or a new export function.
- **Web UI**: Port `run_tests()` to Flask/FastAPI and add a web frontend.

### Testing

Run manual tests with small domain counts:

```bash
python3 dnstest.py --domains 3 --seed 42 --timeout 1.0
```

## Troubleshooting

### ModuleNotFoundError: No module named 'dns'

Install dependencies:
```bash
pip install -r requirements.txt
```


### DoH timeouts

DoH queries may be slower or blocked by network policies. Increase `--timeout` or check DNS provider endpoints are correct.

## License

Provided as-is for personal/internal use.
