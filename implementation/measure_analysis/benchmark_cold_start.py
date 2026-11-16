#!/usr/bin/env python3
"""
benchmark_cold_start.py
Course: IT457 Cloud Computing (Autumn Semester 2026)
Theme 4: Serverless and Startups (Freshworks)

Measures live client-side round-trip latency, Lambda execution time,
and cold-start versus warm execution across 100 consecutive requests.
Calculates the AWS architectural cost model per 1,000 requests.

Generates:
1. data/cold_start_warm_benchmark.json
2. data/freshworks_serverless_latency_and_cost.csv
3. data/freshworks_serverless_latency_and_cost.xlsx (Native Excel workbook)
4. plots/cold_start_vs_warm_latency.png (300 DPI)
5. plots/serverless_cost_per_1000.png (300 DPI)
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
