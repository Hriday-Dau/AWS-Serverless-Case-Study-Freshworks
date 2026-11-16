# IT457 Cloud Computing: Final Course Project Deliverables Submission (Freshworks on AWS: Serverless Case Study)
## AWS-Serverless-Case-Study-Freshworks
### Theme 4: Serverless & Startups — Freshworks on AWS
This is the course project for IT457-Cloud Computing, wherein we are studying a real-world cloud computing case study of a startup (Freshworks) and implement a hands-on exercise. This exercise involves the deploying of a POC of the AWS Serverless model using AWS Lambda, DynamoDB and APIGateway services.
---

Academic course project for **IT457 Cloud Computing (Autumn 2026)** at **Dhirubhai Ambani University**, developed for **Theme 4: Serverless and Startups**.

### Academic Information & Attribution
* **Institution:** Dhirubhai Ambani University (Formerly DA-IICT), Gandhinagar, Gujarat, India
* **Course:** IT457 Cloud Computing (Autumn Semester 2026)
* **Course Instructor & Evaluator:** Prof. P S Kalyan Sasidhar
* **Target Enterprise Case Study:** Freshworks Inc. (NASDAQ: `FRSH`), AWS Serverless Ecosystem
* **Mandated Project Theme:** **Theme 4: Serverless and Startups (Shaadi.com, Freshworks)**
* **Project Team Members:**
  1. **Jayaditya Shah** (Student ID: **202301254**) — *AWS Architecture Management*
  2. **Hriday Asnani** (Student ID: **202301282**) — *Report Documentation, Benchmark & Performance Analysis*
  3. **Maharshi Patel** (Student ID: **202301486**) — *Documentation, Metric Measurement and System validation*

---

This repository combines:

1. A research-based study of how Freshworks scales a multi-tenant SaaS platform on AWS.
2. A small, independently implemented serverless ticket-ingestion proof of concept.
3. A live benchmark comparing AWS Lambda cold-start and warm-request latency.
4. An architectural cost model for 1,000 requests.

> **Scope note:** Freshworks is not represented as a purely serverless company. Its core Freshdesk platform is documented as a large Ruby on Rails system with load balancers, HAProxy shells, and sharded databases. The serverless implementation in this repository is an analogue of the event-driven Lambda pattern used by Freshworks' developer and Marketplace platform, not a reconstruction of Freshworks' proprietary production system.

## Architecture

```text
Client
  |
  v
Amazon API Gateway HTTP API v2
  |
  v
AWS Lambda (Python 3.12, ARM64, 128 MB)
  |
  v
Amazon DynamoDB (PAY_PER_REQUEST)
```

The ticket service exposes:

- `POST /tickets` — accepts a JSON ticket and writes it to DynamoDB.
- `GET /tickets` — returns a service health/status response.
- `OPTIONS /tickets` — returns the configured CORS response.

Each ticket is keyed by:

- Partition key: `tenant_id`
- Sort key: `ticket_id`

The Lambda handler also reports cold-start state, invocation number, execution time, memory, and region in its response telemetry. When Boto3 or AWS resources are unavailable, the handler uses an in-memory store so the request path can be exercised locally; this is not a substitute for DynamoDB validation.

## Compliance Matrix: Official Course Deliverables

Per the official **IT457 Project: Final Deliverables & Step-by-Step Implementation** instructions, all mandatory deliverables for **Theme 4: Serverless and Startups** are fully implemented, verified, and packaged:

| Course Requirement | Specific Deliverable File | Verification / Evidence |
| :--- | :--- | :--- |
| **1. Live API URL** | Deployed on AWS API Gateway HTTP API v2 | **Live Invoke URL:** `https://896e9yx0a1.execute-api.ap-south-1.amazonaws.com/tickets`<br>HTTP Method: `POST /tickets`<br>Live Status: `HTTP 201 Created` |
| **2. Architecture Screenshots** | `theme4_serverless_submission/screenshots/` | 1. `architecture_api_gw_lambda_dynamodb.png` (End-to-End Topology)<br>2. `aws_console_api_gateway.png` (API Gateway Routes & Live Invoke URL)<br>3. `aws_console_lambda.png` (Lambda Python 3.12, ARM64, 128MB, Triggers)<br>4. `aws_console_dynamodb.png` (DynamoDB Table Schema & Ingested Items) |
| **3. Latency & Cost Spreadsheet** | Root directory | `202301254_IT457_Freshworks_Serverless_Latency_and_Cost.xlsx`<br>`202301254_IT457_Freshworks_Serverless_Latency_and_Cost.csv` |
| **4. Latency & Cost Graphs** | `theme4_serverless_submission/plots/` | 1. `cold_start_vs_warm_latency.png` (300 DPI Cold Start vs 99 Warm Requests)<br>2. `serverless_cost_per_1000.png` (300 DPI Cost Model & Component Breakdown) |
| **5. Technical Implementation Report** | Root directory | `202301254_IT457_Theme4_Serverless_Freshworks.pdf` (9-page definitive report) |
| **6. Case Study Master Report** | Root directory | `202301254_IT457_Freshworks_Final_Master_Report.pdf` (14-page synthesis) |
| **7. Step-by-Step Source Code** | `theme4_serverless_submission/` | `lambda/lambda_function.py` (Lambda handler & telemetry)<br>`benchmark/benchmark_cold_start.py` (100-request benchmark harness)<br>`iac/template.yaml` (AWS SAM Template)<br>`iac/serverless.yml` (Serverless Framework IaC) |

## Repository layout

```text
AWS-Serverless-Case-Study-Freshworks/
├── README.md
├── documentation/
│   ├── Week-1/
│   │   ├── evidence_matrix.md
│   │   ├── week1_summary.md
│   │   ├── Group15_Freshworks_Week1_Report.pdf
│   │   └── sources.pdf
│   ├── Week-2/
│   │   ├── week_2_report.tex
│   │   └── Group15_Freshworks_Week2_Report.pdf
│   ├── Week-3/
│   │   ├── draft_results.docx
│   │   └── week3_draftreport.docx
│   └── Week-4/
│       ├── Final_Report_Latex_Source_Code.tex
│       └── IT457_Grp15_Final_Report.pdf
└── implementation/
    ├── Lambda/
    │   └── lambda_function.py
    ├── iac/
    │   ├── serverless.yml
    │   └── template.yaml
    ├── aws_console_screenshots/
    └── measure_analysis/
        ├── benchmark_cold_start.py
        └── results/
            ├── data/
            │   ├── cold_start_warm_benchmark.json
            │   ├── IT457_Freshworks_Serverless_Latency_and_Cost.csv
            │   └── Freshworks_Serverless_Latency_and_Cost.xlsx
            └── plots/
                ├── cold_start_vs_warm_latency.png
                └── serverless_cost_per_1000.png
```

## Documentation

- **[Week 1 evidence matrix](documentation/Week-1/evidence_matrix.md)** — source-backed findings about Freshworks' business, architecture, scaling challenges, and cloud economics.
- **[Week 1 summary](documentation/Week-1/week1_summary.md)** — concise case-study summary.
- **[Week 2 report source](documentation/Week-2/week_2_report.tex)** — corrected architecture analysis and experiment plan.
- **[Week 3 reports](documentation/Week-3/)** — PDF and DOCX files contain the corresponding submitted and draft reports.
- **[Week 4 final report and source code](documentation/Week-4/IT457_Grp15_Final_Report.pdf)** — consolidated case study, implementation, benchmark, FinOps analysis, limitations, and conclusions.

The research identifies recurring Freshworks scaling concerns such as slow requests, noisy-neighbor effects, database replication lag, third-party code execution, and hosting-cost governance. It also examines defensive mechanisms including HAProxy shell routing, circuit breaking, Freno-aware background jobs, and AWS Lambda isolation for Marketplace applications.

## Implementation files

### Lambda handler

[`implementation/Lambda/lambda_function.py`](implementation/Lambda/lambda_function.py) contains:

- The `lambda_handler` entry point.
- `POST`, `GET`, and `OPTIONS` request handling.
- DynamoDB persistence through Boto3.
- Local in-memory fallback for offline execution.
- High-resolution execution timing using `time.perf_counter_ns()`.
- Module-level cold-start detection.

### Infrastructure as code

- [`implementation/iac/template.yaml`](implementation/iac/template.yaml) is an AWS SAM template defining an HTTP API, an ARM64 Lambda function, an encrypted point-in-time-recoverable DynamoDB table, and CloudFormation outputs.
- [`implementation/iac/serverless.yml`](implementation/iac/serverless.yml) is a Serverless Framework configuration for the same API, function, and on-demand table.

Both templates are deployment definitions for the proof of concept. Before deploying from a case-sensitive environment, verify the relative `CodeUri` and handler paths against the checked-out directory names.

## Benchmarking and results

[`implementation/measure_analysis/benchmark_cold_start.py`](implementation/measure_analysis/benchmark_cold_start.py) sends 100 sequential requests, records client round-trip latency and Lambda telemetry, classifies requests using returned cold-start telemetry, and generates JSON, CSV, XLSX, and 300-DPI plots. It supports:

- Live AWS API benchmarking.
- Explicit local simulation through `SIMULATE_LOCAL=true`.
- Archiving previous generated result files before a new run.
- Warm latency percentiles (`p50`, `p90`, `p95`, and `p99`).
- A component-level AWS pricing estimate.

The checked-in live run is `EXP-20261116-102200`:

| Metric | Observed value |
| --- | ---: |
| Requests | 100 |
| Successful responses | 100 (`HTTP 201`) |
| Cold starts | 1 |
| Warm requests | 99 |
| Cold-start round-trip latency | 4,231.67 ms |
| Warm round-trip latency (`p50`) | 160.87 ms |
| Warm round-trip latency (`p95`) | 200.49 ms |
| Warm round-trip latency (`p99`) | 220.63 ms |
| Warm Lambda execution (`p50`) | 13.27 ms |
| Cold-to-warm latency ratio | 26.30x |

The raw benchmark is available in [`cold_start_warm_benchmark.json`](implementation/measure_analysis/results/data/cold_start_warm_benchmark.json), with tabular data in [`IT457_Freshworks_Serverless_Latency_and_Cost.csv`](implementation/measure_analysis/results/data/IT457_Freshworks_Serverless_Latency_and_Cost.csv) and [`Freshworks_Serverless_Latency_and_Cost.xlsx`](implementation/measure_analysis/results/data/Freshworks_Serverless_Latency_and_Cost.xlsx).

## Cost model

The benchmark's architectural estimate for `ap-south-1` is:

| Component | Estimated cost per 1,000 requests |
| --- | ---: |
| Lambda invocations | `$0.000200` |
| Lambda compute | `$0.000023` |
| API Gateway HTTP API | `$0.001000` |
| DynamoDB on-demand writes | `$0.001250` |
| **Total serverless estimate** | **`$0.002473`** |

The model compares this bursty, on-demand workload with an always-on provisioned EC2 baseline of `$0.063472` per 1,000 requests, producing a modeled **96.1% reduction**.

These are pricing-model outputs, not AWS billing records. They depend on the assumed region, memory size, measured billed duration, request size, DynamoDB capacity usage, and comparison baseline.

## Running the benchmark

The script uses Python and imports `numpy` and `matplotlib`. A live run requires:

- Python 3.12 or a compatible Python 3 release.
- Network access to the API Gateway endpoint.
- A deployed API and Lambda/DynamoDB resources.
- The required Python packages installed in the active environment.

From the repository root:

```powershell
python implementation\measure_analysis\benchmark_cold_start.py
```

By default, the script targets the endpoint recorded in the benchmark source. To use another deployment:

```powershell
$env:TARGET_API_URL = "https://<api-id>.execute-api.<region>.amazonaws.com/tickets"
python implementation\measure_analysis\benchmark_cold_start.py
```

To run the offline simulation path instead of making live requests:

```powershell
$env:SIMULATE_LOCAL = "true"
python implementation\measure_analysis\benchmark_cold_start.py
```

The checked-in artifacts are organized under `implementation\measure_analysis\results\`. The current script constants resolve generated data and plots to sibling `implementation\data\` and `implementation\plots\` directories, and its local-import path uses a lowercase `implementation\lambda\` name. On case-sensitive systems, align those paths with the repository's `Lambda\` and `results\` directories before reproducing a run; this README does not claim that a new run will overwrite the checked-in artifacts.

## Team

| Member | Student ID | Focus |
| --- | --- | --- |
| Jayaditya Shah | 202301254 | AWS architecture and backend implementation |
| Hriday Asnani | 202301282 | Benchmarking, telemetry, and performance analysis |
| Maharshi Patel | 202301486 | Documentation, FinOps analysis, and validation |

## Limitations and responsible use

- Client latency includes public Internet, TLS, and API Gateway overhead; it is not the same as Lambda execution time.
- A single small ticket service is not representative of Freshworks' complete production fleet.
- The cold-start sample contains one observed cold start, so it should not be treated as a general AWS latency guarantee.
- The cost model excludes items such as data transfer, CloudWatch storage, free-tier effects, and other workload-specific charges.
- The live endpoint and AWS resources may be unavailable, changed, or removed after the recorded experiment.

## Attribution

Prepared for IT457 Cloud Computing at Dhirubhai Ambani University, Autumn 2026. Research sources and detailed citations are included in the weekly reports and final report source under [`documentation/`](documentation/).
