#!/usr/bin/env python3
"""
benchmark_cold_start.py
Course: IT457 Cloud Computing (Autumn Semester 2026)
Theme 4: Serverless and Startups (Freshworks)

Measures live client-side round-trip latency, Lambda execution time,
and cold-start versus warm execution across 100 consecutive requests.
Calculates the AWS architectural cost model per 1,000 requests.

Generates:
1. results/data/cold_start_warm_benchmark.json
2. results/data/freshworks_serverless_latency_and_cost.csv
3. results/data/freshworks_serverless_latency_and_cost.xlsx (Native Excel workbook)
4. results/plots/cold_start_vs_warm_latency.png (300 DPI)
5. results/plots/serverless_cost_per_1000.png (300 DPI)
"""

import os
import sys
import time
import json
import shutil
import zipfile
import io
import urllib.request
import urllib.error
from pathlib import Path

# Matplotlib configuration for sandbox/headless
os.environ["MPLCONFIGDIR"] = "/tmp/mpl_cache"
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PLOTS_DIR = BASE_DIR / "plots"
LAMBDA_DIR = BASE_DIR / "lambda"

# Default live API Gateway endpoint deployed on AWS (ap-south-1)
DEFAULT_TARGET_URL = "https://896e9yx0a1.execute-api.ap-south-1.amazonaws.com/tickets"

def archive_previous_results(output_dir=None):
    """
    Safely archives any existing benchmark results before running a new experiment.
    Prevents silent overwriting of prior experimental data.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "data"
    archive_dir = output_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp_str = time.strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / "cold_start_warm_benchmark.json"
    csv_path = output_dir / "freshworks_serverless_latency_and_cost.csv"
    xlsx_path = output_dir / "freshworks_serverless_latency_and_cost.xlsx"

    archived_any = False
    if json_path.exists():
        shutil.copy2(json_path, archive_dir / f"cold_start_warm_benchmark_{timestamp_str}.json")
        archived_any = True
    if csv_path.exists():
        shutil.copy2(csv_path, archive_dir / f"freshworks_serverless_latency_and_cost_{timestamp_str}.csv")
        archived_any = True
    if xlsx_path.exists():
        shutil.copy2(xlsx_path, archive_dir / f"freshworks_serverless_latency_and_cost_{timestamp_str}.xlsx")
        archived_any = True

    if archived_any:
        print(f"✓ Prior experimental run safely preserved in: {archive_dir}/")

def run_benchmark(target_url=None, total_requests=100, simulate_local=False):
    """
    Executes a sequential 100-request benchmark against either:
    1. Live AWS API Gateway endpoint (measuring genuine client-side latency and Lambda telemetry).
    2. Local simulation mode (only when explicitly requested via simulate_local=True).
    """
    is_live_aws = bool(target_url and not simulate_local)
    experiment_id = time.strftime("EXP-%Y%m%d-%H%M%S")

    print(f"=== [IT457 Theme 4] Starting Serverless Cold Start vs Warm Benchmark ===")
    print(f"Experiment ID:  {experiment_id}")
    print(f"Total Requests: {total_requests}")
    if is_live_aws:
        print(f"Target Mode:    AWS Live Deployment (ap-south-1)")
        print(f"Endpoint URL:   {target_url}")
    else:
        print("Target Mode:    Local Direct Simulation Engine (Offline)")

    results = []

    # Local simulation setup only if running offline
    if not is_live_aws:
        sys.path.insert(0, str(LAMBDA_DIR))
        import lambda_function
        lambda_function.IS_COLD_START = True
        lambda_function.INVOCATION_COUNT = 0
        os.environ["SIMULATE_COLD_START"] = "true"

    for i in range(1, total_requests + 1):
        # Generate unique ticket payload to avoid collisions
        ticket_id = f"TCK-{experiment_id}-{i:03d}"
        ticket_payload = {
            "ticket_id": ticket_id,
            "tenant_id": "freshworks_enterprise_01",
            "customer_name": f"Enterprise User {i}",
            "customer_email": f"user{i}@corporate-client.com",
            "subject": f"Automated Support Request #{i}",
            "priority": "HIGH" if i % 10 == 0 else "MEDIUM",
            "description": "High-velocity ticket ingestion via AWS Serverless Architecture."
        }

        # Measure high-precision client-side round-trip time using monotonic perf_counter
        req_start = time.perf_counter()
        resp_body = {}
        http_status = 0
        response_headers = {}
        error_message = None
        success = False

        if is_live_aws:
            try:
                req_data = json.dumps(ticket_payload).encode('utf-8')
                req = urllib.request.Request(
                    target_url,
                    data=req_data,
                    headers={
                        'Content-Type': 'application/json',
                        'X-Tenant-ID': 'freshworks_enterprise_01',
                        'User-Agent': 'IT457-Benchmark-Harness/2.0'
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=30.0) as response:
                    http_status = response.getcode()
                    response_headers = dict(response.info())
                    raw_bytes = response.read()
                    try:
                        resp_body = json.loads(raw_bytes.decode('utf-8'))
                    except Exception as je:
                        resp_body = {"raw": raw_bytes.decode('utf-8', errors='replace')}
                    success = (http_status in [200, 201])

            except urllib.error.HTTPError as he:
                http_status = he.code
                try:
                    resp_body = json.loads(he.read().decode('utf-8'))
                except Exception:
                    resp_body = {}
                error_message = f"HTTP {he.code}: {he.reason}"
                success = False

            except urllib.error.URLError as ue:
                http_status = 0
                error_message = f"Network URLError: {ue.reason}"
                success = False

            except Exception as e:
                http_status = 0
                error_message = f"Request Exception: {str(e)}"
                success = False

        else:
            # Local simulation invocation
            try:
                mock_event = {
                    'httpMethod': 'POST',
                    'path': '/tickets',
                    'headers': {'X-Tenant-ID': 'freshworks_enterprise_01'},
                    'body': json.dumps(ticket_payload)
                }
                resp = lambda_function.lambda_handler(mock_event)
                http_status = resp.get('statusCode', 200)
                resp_body = json.loads(resp.get('body', '{}'))
                response_headers = resp.get('headers', {})
                success = (http_status in [200, 201])
            except Exception as e:
                http_status = 500
                error_message = str(e)
                success = False

        # Record exact measured client-side round-trip latency
        roundtrip_latency_ms = round((time.perf_counter() - req_start) * 1000.0, 2)

        # Extract telemetry fields genuinely returned by Lambda
        telemetry = resp_body.get('telemetry', {}) if isinstance(resp_body, dict) else {}
        server_exec_time = telemetry.get('execution_time_ms', None)
        if server_exec_time is not None:
            try:
                server_exec_time_ms = round(float(server_exec_time), 2)
            except (ValueError, TypeError):
                server_exec_time_ms = None
        else:
            server_exec_time_ms = None

        # Billed duration in AWS Lambda rounds up to the nearest 1 ms
        if server_exec_time_ms is not None:
            billed_duration_ms = max(1, int(np.ceil(server_exec_time_ms)))
        else:
            billed_duration_ms = None

        # Correct Cold-Start Detection: strictly check actual returned telemetry
        # Do NOT assume request #1 is cold, and do NOT classify UNKNOWN as warm
        raw_cold = telemetry.get('cold_start')
        if raw_cold is None and response_headers:
            header_val = response_headers.get('x-cold-start') or response_headers.get('X-Cold-Start')
            if header_val is not None:
                raw_cold = str(header_val).strip().lower() == 'true'

        if raw_cold is True or (isinstance(raw_cold, str) and raw_cold.strip().lower() == 'true'):
            state = "COLD_START"
            is_cold_start = True
        elif raw_cold is False or (isinstance(raw_cold, str) and raw_cold.strip().lower() == 'false'):
            state = "WARM"
            is_cold_start = False
        else:
            state = "UNKNOWN"
            is_cold_start = None

        # Never substitute fabricated execution times or add synthetic variance for live measurements!
        record = {
            "request_number": i,
            "ticket_id": ticket_id,
            "state": state,
            "is_cold_start": is_cold_start,
            "roundtrip_latency_ms": roundtrip_latency_ms,
            "server_execution_time_ms": server_exec_time_ms,
            "billed_duration_ms": billed_duration_ms,
            "memory_allocated_mb": telemetry.get('memory_limit_mb', 128),
            "http_status": http_status,
            "success": success,
            "error": error_message
        }
        results.append(record)

        # Terminal progress logging
        if i == 1 or i % 20 == 0 or i == total_requests or is_cold_start is True:
            exec_str = f"{server_exec_time_ms:6.2f} ms" if server_exec_time_ms is not None else "     N/A"
            status_flag = f"HTTP {http_status}" if http_status else "ERR"
            print(f" Request #{i:03d} [{state:10s}] [{status_flag}] -> Latency: {roundtrip_latency_ms:7.2f} ms | Exec: {exec_str}")

        # Minor pacing to simulate natural client arrival
        time.sleep(0.02)

    return results, experiment_id

def compute_statistics(results):
    """
    Computes rigorous, mathematically sound summary statistics from actual observations.
    Gracefully handles zero cold starts without dividing by zero or emitting 0 ms cold starts.
    """
    successful_requests = [
        r for r in results 
        if r.get("success") is True or r.get("status") == "SUCCESS" or (r.get("http_status") is not None and 200 <= r.get("http_status") < 300)
    ]
    failed_requests = [r for r in results if r not in successful_requests]

    def _check_cold(r):
        if r.get("is_cold_start") is not None:
            return r.get("is_cold_start")
        if r.get("is_cold") is not None:
            return r.get("is_cold")
        if r.get("state") == "COLD_START":
            return True
        if r.get("state") == "WARM":
            return False
        return None

    cold_requests = [r for r in successful_requests if _check_cold(r) is True]
    warm_requests = [r for r in successful_requests if _check_cold(r) is False]
    unknown_requests = [r for r in successful_requests if _check_cold(r) is None]

    cold_latencies = [r["roundtrip_latency_ms"] for r in cold_requests if r.get("roundtrip_latency_ms") is not None]
    warm_latencies = [r["roundtrip_latency_ms"] for r in warm_requests if r.get("roundtrip_latency_ms") is not None]
    all_latencies = [r["roundtrip_latency_ms"] for r in results if r.get("roundtrip_latency_ms") is not None]

    # Warm server execution times (when reported by Lambda)
    warm_exec_times = [r["server_execution_time_ms"] for r in warm_requests if r.get("server_execution_time_ms") is not None]
    cold_exec_times = [r["server_execution_time_ms"] for r in cold_requests if r.get("server_execution_time_ms") is not None]

    # Warm latency statistics
    if warm_latencies:
        warm_mean = round(float(np.mean(warm_latencies)), 2)
        warm_p50 = round(float(np.percentile(warm_latencies, 50)), 2)
        warm_p90 = round(float(np.percentile(warm_latencies, 90)), 2)
        warm_p95 = round(float(np.percentile(warm_latencies, 95)), 2)
        warm_p99 = round(float(np.percentile(warm_latencies, 99)), 2)
        warm_min = round(float(np.min(warm_latencies)), 2)
        warm_max = round(float(np.max(warm_latencies)), 2)
    else:
        warm_mean = warm_p50 = warm_p90 = warm_p95 = warm_p99 = warm_min = warm_max = None

    # Cold start statistics (distinguishing zero vs. one vs. multiple observed cold starts)
    if len(cold_latencies) == 0:
        speedup_val = None
        speedup_display = "N/A"
        cold_stats = {
            "observed": False,
            "count": 0,
            "latency_ms": None,
            "display_latency": "Not observed",
            "server_exec_ms": None,
            "observed_e2e_latency_delta_ms": None,
            "speedup_warm_vs_cold": None,
            "speedup_display": "N/A"
        }
    elif len(cold_latencies) == 1:
        c_lat = cold_latencies[0]
        c_exec = cold_exec_times[0] if cold_exec_times else None
        delta = round(c_lat - warm_mean, 2) if warm_mean is not None else None
        speedup_val = round(c_lat / warm_p50, 2) if (warm_p50 and warm_p50 > 0) else None
        speedup_display = f"{speedup_val:.2f}x" if speedup_val is not None else "N/A"
        cold_stats = {
            "observed": True,
            "count": 1,
            "latency_ms": c_lat,
            "display_latency": f"{c_lat:.2f} ms",
            "server_exec_ms": c_exec,
            "observed_e2e_latency_delta_ms": delta,
            "speedup_warm_vs_cold": speedup_val,
            "speedup_display": speedup_display
        }
    else:
        # Multiple cold starts captured (e.g., concurrent scaling)
        c_mean = round(float(np.mean(cold_latencies)), 2)
        c_p50 = round(float(np.percentile(cold_latencies, 50)), 2)
        delta = round(c_mean - warm_mean, 2) if warm_mean is not None else None
        speedup_val = round(c_p50 / warm_p50, 2) if (warm_p50 and warm_p50 > 0) else None
        speedup_display = f"{speedup_val:.2f}x" if speedup_val is not None else "N/A"
        cold_stats = {
            "observed": True,
            "count": len(cold_latencies),
            "latency_ms": c_mean,
            "mean_ms": c_mean,
            "median_ms": c_p50,
            "min_ms": round(float(np.min(cold_latencies)), 2),
            "max_ms": round(float(np.max(cold_latencies)), 2),
            "display_latency": f"{c_p50:.2f} ms (p50 of {len(cold_latencies)} cold starts)",
            "server_exec_ms": round(float(np.mean(cold_exec_times)), 2) if cold_exec_times else None,
            "observed_e2e_latency_delta_ms": delta,
            "all_cold_latencies": cold_latencies,
            "speedup_warm_vs_cold": speedup_val,
            "speedup_display": speedup_display
        }

    # Separate tracking for the 100th request per Requirement 10
    req_100 = next((r for r in results if r.get("request_number") == 100 or r.get("request_num") == 100), None)
    req_100_summary = {
        "request_number": 100,
        "request_num": 100,
        "latency_ms": req_100.get("roundtrip_latency_ms") if req_100 else None,
        "server_exec_ms": req_100.get("server_execution_time_ms") if req_100 else None,
        "state": req_100.get("state") if req_100 else "N/A",
        "http_status": req_100.get("http_status") if req_100 else None
    }

    stats = {
        "total_requests": len(results),
        "successful_requests": len(successful_requests),
        "failed_requests": len(failed_requests),
        "cold_start_count": len(cold_requests),
        "warm_count": len(warm_requests),
        "warm_request_count": len(warm_requests),
        "unknown_count": len(unknown_requests),
        "unknown_state_count": len(unknown_requests),
        "cold_start": cold_stats,
        "warm": {
            "count": len(warm_latencies),
            "mean_ms": warm_mean,
            "p50_ms": warm_p50,
            "p90_ms": warm_p90,
            "p95_ms": warm_p95,
            "p99_ms": warm_p99,
            "min_ms": warm_min,
            "max_ms": warm_max,
            "server_exec_mean_ms": round(float(np.mean(warm_exec_times)), 2) if warm_exec_times else None,
            "server_exec_p50_ms": round(float(np.percentile(warm_exec_times, 50)), 2) if warm_exec_times else None,
            "server_execution_mean_ms": round(float(np.mean(warm_exec_times)), 2) if warm_exec_times else None,
            "server_execution_p50_ms": round(float(np.percentile(warm_exec_times, 50)), 2) if warm_exec_times else None
        },
        "speedup_warm_vs_cold": speedup_val,
        "speedup_display": speedup_display,
        "request_100": req_100_summary,
        "overall_min_ms": round(float(np.min(all_latencies)), 2) if all_latencies else None,
        "overall_max_ms": round(float(np.max(all_latencies)), 2) if all_latencies else None
    }
    return stats

def compute_aws_cost_model(stats, results=None):
    """
    Computes an architectural pricing model per 1,000 requests based on published
    AWS ap-south-1 pricing. Clearly labeled as an architectural model estimate,
    not an invoice audit.
    """
    # 1. AWS Lambda Pricing (ap-south-1, ARM64 Graviton2)
    # - Invocations: $0.20 per 1M requests = $0.000200 per 1k requests
    # - Compute duration: $0.0000133334 per GB-second for ARM64 (Graviton2)
    # - Memory: 128 MB (0.125 GB)
    lambda_invocations_per_1k = 1000 * (0.20 / 1_000_000)

    # Use actual measured warm server execution time rounded up to nearest 1 ms (AWS Lambda billing granularity)
    warm_stats = stats.get("warm", {})
    measured_server_ms = warm_stats.get("server_exec_p50_ms") or warm_stats.get("server_exec_mean_ms")
    if measured_server_ms is not None and measured_server_ms > 0:
        billed_ms_used = max(1.0, float(np.ceil(measured_server_ms)))
        duration_source = f"Measured Lambda Server Execution (p50: {measured_server_ms:.1f}ms, billed: {billed_ms_used:.0f}ms)"
    else:
        # Default conservative 25 ms estimate if server telemetry missing
        billed_ms_used = 25.0
        duration_source = "Conservative 25ms baseline estimate (telemetry missing)"

    gb_seconds_per_req = (128.0 / 1024.0) * (billed_ms_used / 1000.0)
    lambda_compute_per_1k = 1000 * gb_seconds_per_req * 0.0000133334
    lambda_total_per_1k = lambda_invocations_per_1k + lambda_compute_per_1k

    # 2. Amazon API Gateway Pricing (HTTP API v2)
    # - $1.00 per 1M requests = $0.001000 per 1k requests
    api_gateway_per_1k = 1000 * (1.00 / 1_000_000)

    # 3. Amazon DynamoDB Pricing (On-Demand Pay-per-Request)
    # - 1 Write Request Unit (WRU) per ticket item (< 1 KB) = $1.25 per 1M WRU
    dynamodb_wru_per_1k = 1000 * (1.25 / 1_000_000)

    # 4. Total Serverless Architecture Spend per 1,000 requests
    total_serverless_per_1k = lambda_total_per_1k + api_gateway_per_1k + dynamodb_wru_per_1k

    # 5. Baseline Comparison: Dedicated EC2 Monolith
    # Modeled on always-on provisioned EC2 instance fleet (m5.4xlarge provisioned for peak with ~15% utilization)
    # Amortized hosting cost per 1,000 requests: $0.063472 (from Week 3 & 4 TCO models)
    monolith_cost_per_1k = 0.063472

    savings_pct = round(((monolith_cost_per_1k - total_serverless_per_1k) / monolith_cost_per_1k) * 100, 2)

    return {
        "cost_model_type": "ARCHITECTURAL_PRICING_ESTIMATE_NOT_INVOICE",
        "pricing_disclaimer": "ARCHITECTURAL_PRICING_ESTIMATE_NOT_INVOICE",
        "estimated_savings_percentage": savings_pct,
        "aws_region": "ap-south-1",
        "lambda_architecture": "arm64 (AWS Graviton2)",
        "lambda_billed_duration_ms": billed_ms_used,
        "lambda_duration_source": duration_source,
        "lambda_invocation_per_1k_usd": round(lambda_invocations_per_1k, 6),
        "lambda_compute_per_1k_usd": round(lambda_compute_per_1k, 6),
        "lambda_total_per_1k_usd": round(lambda_total_per_1k, 6),
        "api_gateway_per_1k_usd": round(api_gateway_per_1k, 6),
        "dynamodb_per_1k_usd": round(dynamodb_wru_per_1k, 6),
        "total_serverless_cost_per_1k_usd": round(total_serverless_per_1k, 6),
        "ec2_monolith_cost_per_1k_usd": round(monolith_cost_per_1k, 6),
        "modeled_savings_vs_monolith_pct": savings_pct,
        "notes": "Calculated using official AWS ap-south-1 pricing rates. Compares bursty on-demand serverless against always-on provisioned EC2 compute."
    }

def generate_csv_and_xlsx(results, stats, cost_model, output_dir=DATA_DIR):
    """
    Exports clean, validated experimental data into CSV and native multi-tab XLSX files.
    """
    # 1. Write CSV
    csv_path = output_dir / "freshworks_serverless_latency_and_cost.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("Request_Number,Ticket_ID,State,Is_Cold_Start,Roundtrip_Latency_ms,Server_Exec_ms,Billed_Duration_ms,Memory_MB,HTTP_Status,Success,Error\n")
        for r in results:
            exec_val = r.get('server_execution_time_ms', '') if r.get('server_execution_time_ms') is not None else ''
            billed_val = r.get('billed_duration_ms', '') if r.get('billed_duration_ms') is not None else ''
            err_val = f'"{r.get("error")}"' if r.get("error") else ""
            lat_val = r.get('roundtrip_latency_ms', '') if r.get('roundtrip_latency_ms') is not None else ''
            f.write(f"{r.get('request_number', '')},{r.get('ticket_id', '')},{r.get('state', '')},{r.get('is_cold_start', '')},{lat_val},{exec_val},{billed_val},{r.get('memory_allocated_mb', 128)},{r.get('http_status', '')},{r.get('success', True)},{err_val}\n")
    print(f"✓ CSV generated: {csv_path}")

    # 2. Write Multi-Tab Native XLSX via zipfile
    xlsx_path = output_dir / "freshworks_serverless_latency_and_cost.xlsx"

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Latency Log (100 Requests)" sheetId="1" r:id="rId1"/>
    <sheet name="Cost Model &amp; Summary" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""

    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""

    # Sheet 1: Raw Latency Data
    sheet1_rows = []
    sheet1_rows.append('<row r="1">'
                       '<c r="A1" t="inlineStr"><is><t>Request Number</t></is></c>'
                       '<c r="B1" t="inlineStr"><is><t>Ticket ID</t></is></c>'
                       '<c r="C1" t="inlineStr"><is><t>State</t></is></c>'
                       '<c r="D1" t="inlineStr"><is><t>Roundtrip Latency (ms)</t></is></c>'
                       '<c r="E1" t="inlineStr"><is><t>Server Execution (ms)</t></is></c>'
                       '<c r="F1" t="inlineStr"><is><t>Billed Duration (ms)</t></is></c>'
                       '<c r="G1" t="inlineStr"><is><t>Memory (MB)</t></is></c>'
                       '<c r="H1" t="inlineStr"><is><t>HTTP Status</t></is></c>'
                       '</row>')

    for idx, r in enumerate(results, start=2):
        exec_str = f'<c r="E{idx}"><v>{r.get("server_execution_time_ms")}</v></c>' if r.get("server_execution_time_ms") is not None else f'<c r="E{idx}" t="inlineStr"><is><t>N/A</t></is></c>'
        billed_str = f'<c r="F{idx}"><v>{r.get("billed_duration_ms")}</v></c>' if r.get("billed_duration_ms") is not None else f'<c r="F{idx}" t="inlineStr"><is><t>N/A</t></is></c>'
        lat_str = f'<c r="D{idx}"><v>{r.get("roundtrip_latency_ms")}</v></c>' if r.get("roundtrip_latency_ms") is not None else f'<c r="D{idx}" t="inlineStr"><is><t>N/A</t></is></c>'
        row_str = (f'<row r="{idx}">'
                   f'<c r="A{idx}"><v>{r.get("request_number", idx-1)}</v></c>'
                   f'<c r="B{idx}" t="inlineStr"><is><t>{r.get("ticket_id", "")}</t></is></c>'
                   f'<c r="C{idx}" t="inlineStr"><is><t>{r.get("state", "UNKNOWN")}</t></is></c>'
                   f'{lat_str}'
                   f'{exec_str}'
                   f'{billed_str}'
                   f'<c r="G{idx}"><v>{r.get("memory_allocated_mb", 128)}</v></c>'
                   f'<c r="H{idx}"><v>{r.get("http_status", 200)}</v></c>'
                   f'</row>')
        sheet1_rows.append(row_str)

    sheet1 = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    {''.join(sheet1_rows)}
  </sheetData>
</worksheet>"""

    # Sheet 2: Cost Model & Summary
    cold_display = stats['cold_start']['display_latency']
    warm_p50_display = f"{stats['warm']['p50_ms']} ms" if stats['warm']['p50_ms'] is not None else "N/A"
    warm_p95_display = f"{stats['warm']['p95_ms']} ms" if stats['warm']['p95_ms'] is not None else "N/A"

    sheet2_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>IT457 Theme 4: Serverless Freshworks Cloud Economics &amp; Benchmark Summary</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>Summary Metric</t></is></c><c r="B2" t="inlineStr"><is><t>Value</t></is></c><c r="C2" t="inlineStr"><is><t>Notes</t></is></c></row>
    <row r="3"><c r="A3" t="inlineStr"><is><t>Total Requests Tested</t></is></c><c r="B3"><v>{stats['total_requests']}</v></c><c r="C3" t="inlineStr"><is><t>Sequential Benchmark</t></is></c></row>
    <row r="4"><c r="A4" t="inlineStr"><is><t>Successful Requests</t></is></c><c r="B4"><v>{stats['successful_requests']}</v></c><c r="C4" t="inlineStr"><is><t>HTTP 200/201 responses</t></is></c></row>
    <row r="5"><c r="A5" t="inlineStr"><is><t>Cold Starts Observed</t></is></c><c r="B5"><v>{stats['cold_start_count']}</v></c><c r="C5" t="inlineStr"><is><t>Verified via Lambda Telemetry</t></is></c></row>
    <row r="6"><c r="A6" t="inlineStr"><is><t>Cold Start Latency</t></is></c><c r="B6" t="inlineStr"><is><t>{cold_display}</t></is></c><c r="C6" t="inlineStr"><is><t>Container provisioning overhead</t></is></c></row>
    <row r="7"><c r="A7" t="inlineStr"><is><t>Warm Median Latency (p50)</t></is></c><c r="B7" t="inlineStr"><is><t>{warm_p50_display}</t></is></c><c r="C7" t="inlineStr"><is><t>Pre-warmed execution baseline</t></is></c></row>
    <row r="8"><c r="A8" t="inlineStr"><is><t>Warm 95th Percentile (p95)</t></is></c><c r="B8" t="inlineStr"><is><t>{warm_p95_display}</t></is></c><c r="C8" t="inlineStr"><is><t>Tail latency</t></is></c></row>
    <row r="9"><c r="A9" t="inlineStr"><is><t>Cold-to-Warm Ratio</t></is></c><c r="B9" t="inlineStr"><is><t>{stats['speedup_display']}</t></is></c><c r="C9" t="inlineStr"><is><t>Execution speedup factor</t></is></c></row>

    <row r="11"><c r="A11" t="inlineStr"><is><t>Service Component</t></is></c><c r="B11" t="inlineStr"><is><t>Cost per 1,000 Requests (USD)</t></is></c><c r="C11" t="inlineStr"><is><t>AWS ap-south-1 Pricing Model Reference</t></is></c></row>
    <row r="12"><c r="A12" t="inlineStr"><is><t>AWS Lambda Invocations</t></is></c><c r="B12"><v>{cost_model['lambda_invocation_per_1k_usd']}</v></c><c r="C12" t="inlineStr"><is><t>$0.20 per 1M requests</t></is></c></row>
    <row r="13"><c r="A13" t="inlineStr"><is><t>AWS Lambda Compute (128MB ARM64)</t></is></c><c r="B13"><v>{cost_model['lambda_compute_per_1k_usd']}</v></c><c r="C13" t="inlineStr"><is><t>$0.0000133334/GB-s (Graviton2)</t></is></c></row>
    <row r="14"><c r="A14" t="inlineStr"><is><t>Amazon API Gateway (HTTP API v2)</t></is></c><c r="B14"><v>{cost_model['api_gateway_per_1k_usd']}</v></c><c r="C14" t="inlineStr"><is><t>$1.00 per 1M requests</t></is></c></row>
    <row r="15"><c r="A15" t="inlineStr"><is><t>Amazon DynamoDB (On-Demand WRU)</t></is></c><c r="B15"><v>{cost_model['dynamodb_per_1k_usd']}</v></c><c r="C15" t="inlineStr"><is><t>$1.25 per 1M Write Request Units</t></is></c></row>
    <row r="16"><c r="A16" t="inlineStr"><is><t>Total Serverless Cost per 1,000 Requests</t></is></c><c r="B16"><v>{cost_model['total_serverless_cost_per_1k_usd']}</v></c><c r="C16" t="inlineStr"><is><t>Subtotal model estimate</t></is></c></row>
    <row r="18"><c r="A18" t="inlineStr"><is><t>Comparison: Dedicated EC2 Monolith Fleet</t></is></c><c r="B18"><v>{cost_model['ec2_monolith_cost_per_1k_usd']}</v></c><c r="C18" t="inlineStr"><is><t>$0.063472 per 1,000 requests (amortized)</t></is></c></row>
    <row r="19"><c r="A19" t="inlineStr"><is><t>Modeled Cost Savings vs Monolith</t></is></c><c r="B19" t="inlineStr"><is><t>{cost_model['modeled_savings_vs_monolith_pct']}%</t></is></c><c r="C19" t="inlineStr"><is><t>Theoretical on-demand efficiency</t></is></c></row>
  </sheetData>
</worksheet>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        z.writestr('xl/worksheets/sheet1.xml', sheet1)
        z.writestr('xl/worksheets/sheet2.xml', sheet2_content)

    with open(xlsx_path, "wb") as f:
        f.write(buf.getvalue())
    print(f"✓ Excel Workbook (.xlsx) generated: {xlsx_path}")

def plot_visualizations(results, stats, cost_model, output_dir=PLOTS_DIR):
    """
    Renders publication-grade 300 DPI plots.
    Correctly handles zero, one, or multiple observed cold starts without plotting 0 ms bars.
    """
    requests = [r["request_number"] for r in results]
    latencies = [r["roundtrip_latency_ms"] for r in results if r.get("roundtrip_latency_ms") is not None]

    cold_requests = [r for r in results if r.get("is_cold_start") is True and r.get("roundtrip_latency_ms") is not None]
    warm_requests = [r for r in results if r.get("is_cold_start") is False and r.get("roundtrip_latency_ms") is not None]
    unknown_requests = [r for r in results if r.get("is_cold_start") is None and r.get("roundtrip_latency_ms") is not None]

    # --- Plot 1: Cold Start vs Warm Latency Telemetry (300 DPI) ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [2.2, 1]}, dpi=300)

    # Subplot A: Request Sequence
    # Plot client round-trip line
    ax1.plot(requests, [r["roundtrip_latency_ms"] for r in results], color="#94a3b8", linewidth=1.0, linestyle="-", alpha=0.5, zorder=1)

    # Warm points
    if warm_requests:
        w_x = [r["request_number"] for r in warm_requests]
        w_y = [r["roundtrip_latency_ms"] for r in warm_requests]
        ax1.scatter(w_x, w_y, color="#2563eb", s=25, label=f"Warm Requests (n={len(warm_requests)})", alpha=0.85, zorder=3)

    # Unknown points (if any)
    if unknown_requests:
        u_x = [r["request_number"] for r in unknown_requests]
        u_y = [r["roundtrip_latency_ms"] for r in unknown_requests]
        ax1.scatter(u_x, u_y, color="#9333ea", marker="^", s=30, label=f"Unknown State (n={len(unknown_requests)})", alpha=0.8, zorder=3)

    # Cold points (if any)
    if cold_requests:
        c_x = [r["request_number"] for r in cold_requests]
        c_y = [r["roundtrip_latency_ms"] for r in cold_requests]
        ax1.scatter(c_x, c_y, color="#dc2626", marker="D", s=60, label=f"Verified Cold Start (n={len(cold_requests)})", zorder=4)
        for cx, cy in zip(c_x, c_y):
            ax1.annotate(
                f"Cold Start (Req #{cx}):\n{cy:.1f} ms",
                xy=(cx, cy),
                xytext=(cx + 5, cy * 0.85 if cy > 100 else cy + 20),
                arrowprops=dict(facecolor="#dc2626", shrink=0.08, width=1.5, headwidth=6),
                fontsize=9.5,
                fontweight="bold",
                color="#dc2626",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#fee2e2", edgecolor="#dc2626", alpha=0.95),
                zorder=5
            )
    else:
        # Zero cold starts observed: place clear annotation instead of drawing fake cold start
        ax1.text(
            0.5, 0.88,
            "Cold Start: Not observed in this run\n(All 100 requests served by pre-warmed AWS Lambda container)",
            transform=ax1.transAxes,
            ha="center", va="center",
            fontsize=10,
            fontweight="bold",
            color="#92400e",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#fef3c7", edgecolor="#f59e0b", alpha=0.95)
        )

    # Server execution time (when reported)
    valid_server_data = [(r["request_number"], r["server_execution_time_ms"]) for r in results if r.get("server_execution_time_ms") is not None]
    if valid_server_data:
        sx, sy = zip(*valid_server_data)
        ax1.plot(sx, sy, color="#059669", linewidth=1.2, linestyle="--", label="Lambda Server Execution Time", alpha=0.85, zorder=2)

    # Reference line for Warm Median
    warm_p50 = stats["warm"]["p50_ms"]
    if warm_p50 is not None:
        ax1.axhline(warm_p50, color="#64748b", linestyle=":", linewidth=1.5, label=f"Warm Median (p50): {warm_p50:.1f} ms")

    # Reference line for Warm p95
    warm_p95 = stats["warm"]["p95_ms"]
    if warm_p95 is not None and warm_p95 != warm_p50:
        ax1.axhline(warm_p95, color="#f59e0b", linestyle="--", linewidth=1.0, alpha=0.7, label=f"Warm p95: {warm_p95:.1f} ms")

    ax1.set_title("AWS Lambda Execution Latency: 100 Consecutive Requests", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xlabel("Consecutive Request Number", fontsize=10, fontweight="bold")
    ax1.set_ylabel("Latency (Milliseconds)", fontsize=10, fontweight="bold")
    ax1.set_xlim(-2, 105)
    max_lat = max(latencies) if latencies else 100
    ax1.set_ylim(0, max_lat * 1.18)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=8.5)

    # Subplot B: Boxplot Distribution Comparison
    if cold_requests and warm_requests:
        box_data = [[r["roundtrip_latency_ms"] for r in warm_requests], [r["roundtrip_latency_ms"] for r in cold_requests]]
        bp = ax2.boxplot(box_data, patch_artist=True, tick_labels=[f"Warm State\n(n={len(warm_requests)})", f"Cold Start\n(n={len(cold_requests)})"], widths=0.5)
        bp['boxes'][0].set(facecolor="#93c5fd", edgecolor="#1d4ed8")
        bp['boxes'][1].set(facecolor="#fca5a5", edgecolor="#b91c1c")
        bp['medians'][0].set(color="#1e3a8a", linewidth=2)
        bp['medians'][1].set(color="#7f1d1d", linewidth=2)
    elif warm_requests:
        # Zero cold starts: boxplot only of warm state
        box_data = [[r["roundtrip_latency_ms"] for r in warm_requests]]
        bp = ax2.boxplot(box_data, patch_artist=True, tick_labels=[f"Warm Requests\n(n={len(warm_requests)})"], widths=0.4)
        bp['boxes'][0].set(facecolor="#93c5fd", edgecolor="#1d4ed8")
        bp['medians'][0].set(color="#1e3a8a", linewidth=2)
        ax2.text(
            0.5, 0.70,
            "Cold Start:\nNot Observed\nin this run",
            transform=ax2.transAxes,
            ha="center", va="center",
            fontsize=9.5,
            fontweight="bold",
            color="#92400e",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#fef3c7", edgecolor="#f59e0b", alpha=0.9)
        )
    else:
        ax2.text(0.5, 0.5, "Insufficient Data", transform=ax2.transAxes, ha="center")

    ax2.set_title("Latency Distribution", fontsize=12, fontweight="bold", pad=12)
    ax2.set_ylabel("Latency (Milliseconds)", fontsize=10, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plot1_path = output_dir / "cold_start_vs_warm_latency.png"
    plt.savefig(plot1_path, dpi=300)
    plt.close()
    print(f"✓ Plot 1 generated: {plot1_path}")

    # --- Plot 2: Cost per 1,000 Requests Comparison (300 DPI) ---
    fig, (ax_cost1, ax_cost2) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={'width_ratios': [1.2, 1.4]}, dpi=300)

    # Subplot A: Serverless vs EC2 Monolith
    categories = ["EC2 VM Monolith\n(Provisioned Fleet Model)", "Serverless Architecture\n(API Gateway+Lambda+DDB)"]
    costs = [cost_model["ec2_monolith_cost_per_1k_usd"], cost_model["total_serverless_cost_per_1k_usd"]]
    colors = ["#f87171", "#4ade80"]

    bars = ax_cost1.bar(categories, costs, color=colors, edgecolor="#1e293b", linewidth=1.2, width=0.55)
    ax_cost1.set_title("Modeled Hosting Cost per 1,000 Requests", fontsize=12, fontweight="bold", pad=12)
    ax_cost1.set_ylabel("Estimated Cost in USD ($)", fontsize=10, fontweight="bold")
    ax_cost1.grid(True, linestyle="--", alpha=0.4, axis="y")

    for bar in bars:
        h = bar.get_height()
        ax_cost1.text(bar.get_x() + bar.get_width() / 2.0, h + 0.0015, f"${h:.5f}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax_cost1.text(
        0.5, 0.035,
        f"{cost_model['modeled_savings_vs_monolith_pct']}% Modeled Cost Savings\n(AWS ap-south-1 Pricing Model)",
        transform=ax_cost1.transData,
        fontsize=9.5, fontweight="bold", color="#15803d",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#dcfce7", edgecolor="#16a34a")
    )

    # Subplot B: Serverless Component Breakdown
    components = ["API Gateway\nHTTP API v2", "DynamoDB\nOn-Demand WRU", "Lambda\nCompute & Invocations"]
    comp_costs = [
        cost_model["api_gateway_per_1k_usd"],
        cost_model["dynamodb_per_1k_usd"],
        cost_model["lambda_total_per_1k_usd"]
    ]
    comp_colors = ["#38bdf8", "#fbbf24", "#a855f7"]

    bars2 = ax_cost2.bar(components, comp_costs, color=comp_colors, edgecolor="#1e293b", linewidth=1.2, width=0.55)
    ax_cost2.set_title("Serverless Cost Breakdown per 1,000 Requests", fontsize=12, fontweight="bold", pad=12)
    ax_cost2.set_ylabel("Component Cost in USD ($)", fontsize=10, fontweight="bold")
    ax_cost2.grid(True, linestyle="--", alpha=0.4, axis="y")

    for bar in bars2:
        h = bar.get_height()
        ax_cost2.text(bar.get_x() + bar.get_width() / 2.0, h + 0.00004, f"${h:.6f}", ha="center", va="bottom", fontsize=9.5, fontweight="bold")

    fig.text(0.5, 0.02, "Note: Architectural cost model estimates derived from published AWS ap-south-1 rates (not verified billing invoices).",
             ha="center", fontsize=8.5, color="#64748b", fontstyle="italic")

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plot2_path = output_dir / "serverless_cost_per_1000.png"
    plt.savefig(plot2_path, dpi=300)
    plt.close()
    print(f"✓ Plot 2 generated: {plot2_path}")

def main():
    target_url = os.environ.get("TARGET_API_URL", DEFAULT_TARGET_URL)
    simulate_flag = os.environ.get("SIMULATE_LOCAL", "false").lower() == "true"

    # 1. Safely archive previous experimental run before writing new data
    archive_previous_results()

    # 2. Execute Benchmark
    results, experiment_id = run_benchmark(target_url=target_url, total_requests=100, simulate_local=simulate_flag)

    # 3. Compute Rigorous Statistics
    stats = compute_statistics(results)

    # 4. Compute Architectural Cost Model
    cost_model = compute_aws_cost_model(stats, results)

    # 5. Save Comprehensive JSON Summary
    summary_data = {
        "theme": "Theme 4: Serverless and Startups (Freshworks)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "experiment_id": experiment_id,
        "environment": "LOCAL_SIMULATION" if simulate_flag else "AWS_LIVE",
        "live_api_url": target_url,
        "architecture": "Amazon API Gateway (HTTP API v2) -> AWS Lambda (Python 3.12, 128MB, ARM64) -> Amazon DynamoDB",
        "aws_region": "ap-south-1",
        "total_requests": stats["total_requests"],
        "successful_requests": stats["successful_requests"],
        "failed_requests": stats["failed_requests"],
        "cold_start_count": stats["cold_start_count"],
        "warm_count": stats["warm_count"],
        "unknown_count": stats["unknown_count"],
        "statistics": stats,
        "cost_model": cost_model,
        "results": results
    }

    json_path = DATA_DIR / "cold_start_warm_benchmark.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"✓ Benchmark JSON data saved: {json_path}")

    # 6. Generate CSV and XLSX
    generate_csv_and_xlsx(results, stats, cost_model)

    # 7. Generate Visualizations
    plot_visualizations(results, stats, cost_model)

    print("\n=== Benchmark Summary ===")
    print(f"Experiment ID:        {experiment_id}")
    print(f"Total Requests:       {stats['total_requests']} (Success: {stats['successful_requests']}, Failed: {stats['failed_requests']})")
    print(f"Cold Starts Observed: {stats['cold_start_count']}")
    if stats['cold_start']['observed']:
        print(f"Cold Start Latency:   {stats['cold_start']['display_latency']}")
    else:
        print(f"Cold Start Latency:   Not observed (all requests served by warm container)")
    print(f"Warm Median (p50):    {stats['warm']['p50_ms']} ms")
    print(f"Warm p95:             {stats['warm']['p95_ms']} ms")
    print(f"Speedup Warm vs Cold: {stats['speedup_display']}")
    print(f"Serverless Cost/1k:   ${cost_model['total_serverless_cost_per_1k_usd']}")
    print(f"EC2 Monolith Cost/1k: ${cost_model['ec2_monolith_cost_per_1k_usd']}")
    print(f"Modeled Cost Savings: {cost_model['modeled_savings_vs_monolith_pct']}%")

if __name__ == "__main__":
    main()
