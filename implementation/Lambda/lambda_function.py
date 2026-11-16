"""
Freshworks Serverless Ticket Processing Service
Course: IT457 Cloud Computing (Autumn Semester 2026)
Theme 4: Serverless and Startups (Freshworks)
Team:
  - Jayaditya Shah (Student ID: 202301254) - Lead Cloud Architect
  - Hriday Asnani (Student ID: 202301282) - Benchmark Engineer
  - Maharshi Patel (Student ID: 202301486) - Data Persistence & FinOps

Architecture: Amazon API Gateway -> AWS Lambda (Python 3.12) -> Amazon DynamoDB
"""

import os
import json
import time
import uuid
from datetime import datetime

# Cold Start Detection: Module-level global state
# Variables initialized outside the handler persist across warm invocations.
MODULE_INIT_TIME = time.time()
IS_COLD_START = True
INVOCATION_COUNT = 0

# DynamoDB Client Initialization (Boto3 or Mock fallback for local benchmarking)
try:
    import boto3
    dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'ap-south-1'))
    table_name = os.environ.get('DYNAMODB_TABLE', 'FreshworksTickets')
    table = dynamodb.Table(table_name)
    HAS_BOTO3 = True
except Exception:
    HAS_BOTO3 = False
    table = None

# In-memory store for local testing/simulation fallback
LOCAL_TICKET_STORE = {}

def simulate_cold_start_overhead():
    """
    Simulates AWS Lambda runtime container initialization and connection handshake
    overhead during a cold start (approx 700-800ms for Python with SDK init).
    """
    time.sleep(0.75)  # 750ms container spin-up & TLS handshake

def lambda_handler(event, context=None):
    global IS_COLD_START, INVOCATION_COUNT

    start_ns = time.perf_counter_ns()
    INVOCATION_COUNT += 1

    # Record cold start state for this invocation
    cold_start_occurred = IS_COLD_START
    if IS_COLD_START:
        # Simulate realistic AWS container initialization if running in benchmark harness
        if os.environ.get("SIMULATE_COLD_START", "false").lower() == "true":
            simulate_cold_start_overhead()
        IS_COLD_START = False  # Pre-warmed for subsequent calls

    # Extract HTTP Method & Path
    http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('path') or event.get('rawPath', '/tickets')

    # CORS Headers
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Tenant-ID, Authorization',
        'X-Freshworks-Serverless-Engine': 'AWS Lambda Python 3.12',
        'X-Cold-Start': 'true' if cold_start_occurred else 'false'
    }

    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}

    # Route: POST /tickets
    if http_method == 'POST':
        try:
            body = event.get('body', {})
            if isinstance(body, str):
                body = json.loads(body) if body else {}

            tenant_id = body.get('tenant_id', event.get('headers', {}).get('X-Tenant-ID', 'tenant_enterprise_01'))
            ticket_id = body.get('ticket_id', f"TCK-{uuid.uuid4().hex[:8].upper()}")
            subject = body.get('subject', 'Customer Support Inquiry')
            priority = body.get('priority', 'MEDIUM')
            customer_email = body.get('customer_email', 'customer@example.com')
            description = body.get('description', 'Ticket generated via Freshworks Serverless Ingestion Engine.')
            created_at = datetime.utcnow().isoformat() + "Z"

            ticket_item = {
                'tenant_id': tenant_id,          # Partition Key (PK)
                'ticket_id': ticket_id,          # Sort Key (SK)
                'subject': subject,
                'priority': priority,
                'status': 'OPEN',
                'customer_email': customer_email,
                'description': description,
                'created_at': created_at,
                'channel': 'API_GATEWAY_HTTP'
            }

            # Persistence to DynamoDB
            if HAS_BOTO3 and table is not None:
                table.put_item(Item=ticket_item)
            else:
                LOCAL_TICKET_STORE[f"{tenant_id}#{ticket_id}"] = ticket_item

            elapsed_ns = time.perf_counter_ns() - start_ns
            elapsed_ms = elapsed_ns / 1_000_000

            response_payload = {
                'status': 'SUCCESS',
                'message': 'Ticket successfully ingested into Freshworks Serverless Platform',
                'ticket': ticket_item,
                'telemetry': {
                    'cold_start': cold_start_occurred,
                    'invocation_number': INVOCATION_COUNT,
                    'execution_time_ms': elapsed_ms,
                    'execution_time_ns': elapsed_ns,
                    'execution_time_ms_precise': f"{elapsed_ns // 1_000_000}.{elapsed_ns % 1_000_000:06d}",
                    'memory_limit_mb': getattr(context, 'memory_limit_in_mb', 128) if context else 128,
                    'aws_region': os.environ.get('AWS_REGION', 'ap-south-1'),
                    'serverless_database': 'Amazon DynamoDB (Pay-Per-Request On-Demand)'
                }
            }

            return {
                'statusCode': 201,
                'headers': headers,
                'body': json.dumps(response_payload)
            }

        except Exception as e:
            elapsed_ns = time.perf_counter_ns() - start_ns
            elapsed_ms = elapsed_ns / 1_000_000
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'ERROR',
                    'error': str(e),
                    'execution_time_ms': elapsed_ms,
                    'execution_time_ns': elapsed_ns,
                    'execution_time_ms_precise': f"{elapsed_ns // 1_000_000}.{elapsed_ns % 1_000_000:06d}"
                })
            }

    # Route: GET /tickets or Health Check
    elif http_method == 'GET':
        elapsed_ns = time.perf_counter_ns() - start_ns
        elapsed_ms = elapsed_ns / 1_000_000
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'status': 'ONLINE',
                'service': 'Freshworks Serverless Ticket Processor',
                'theme': 'IT457 Theme 4: Serverless and Startups',
                'runtime': 'AWS Lambda Python 3.12 + Amazon DynamoDB',
                'cold_start': cold_start_occurred,
                'invocation_count': INVOCATION_COUNT,
                'execution_time_ms': elapsed_ms,
                'execution_time_ns': elapsed_ns,
                'execution_time_ms_precise': f"{elapsed_ns // 1_000_000}.{elapsed_ns % 1_000_000:06d}"
            })
        }

    return {
        'statusCode': 405,
        'headers': headers,
        'body': json.dumps({'error': f'Method {http_method} Not Allowed'})
    }

