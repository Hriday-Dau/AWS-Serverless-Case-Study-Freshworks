# SC452 Case Study — Week 1 Summary: Freshworks Inc.

**Course:** SC452 (Processes on Networks / Cloud Computing Case Study)  
**Topic:** Freshworks — Scaling Multi-Tenant Global SaaS on AWS Infrastructure  
**Author:** Jayaditya Shah (Student ID: 202301254) | **Date:** October 14, 2026  

---

### 1. Business Context & Problem Statement
Founded in 2010 in Chennai, India, as Freshdesk by Girish Mathrubootham and Shan Krishnasamy (rebranded to Freshworks in 2017; NASDAQ: FRSH), the company offers cloud-native customer engagement (Freshdesk) and IT service management (Freshservice) SaaS [[1]](#references), [[3]](#references). Rather than building costly private data centers, Freshworks built natively on Amazon Web Services (AWS) [[1]](#references), [[4]](#references). Scaling from an Indian startup to an enterprise serving over 67,000 customers in 140+ countries required solving three distributed systems challenges: sub-second global latency, fragmented data sovereignty regulations (e.g., EU GDPR, UK and UAE residency), and multi-tenant "noisy neighbor" resource contention [[3]](#references), [[4]](#references).

### 2. Verified Cloud Architecture Findings
Freshworks operates across AWS regions in North America, Europe (Frankfurt, Ireland, London), APAC, and the Middle East (Dubai) [[3]](#references), [[4]](#references):
* **Ingress & Isolation:** Incoming traffic (`tenant.freshdesk.com`) resolves via Amazon Route 53 to AWS Application Load Balancers (ALBs) for TLS termination, routing into an HAProxy tier [[4]](#references), [[5]](#references). HAProxy implements a "Shell Architecture," partitioning database shards and application servers into isolated pools (capping traffic at ~60,000 requests per minute [RPM] per shell) to restrict blast radiuses during incidents [[5]](#references), [[6]](#references).
* **Application & Circuit Breaking:** The core monolith runs containerized Ruby on Rails on Passenger workers behind Nginx [[4]](#references). Outbound microservice traffic traverses local Envoy sidecars for connection pooling and rate-limiting [[4]](#references). To prevent cascading failures, applications use Shopify’s Semian circuit breaker gem, while an automated MySQL event aborts transactions exceeding 25 seconds via `CALL mysql.rds_kill()` [[4]](#references).
* **Data & Async Scaling:** Relational storage uses sharded Amazon RDS for MySQL with dedicated read replicas [[4]](#references), [[6]](#references). In-memory caching runs on Amazon EKS via a custom Kubernetes Operator managing self-hosted Redis clusters; an algorithmic placement engine distributes nodes across AWS Availability Zones, improving fault tolerance by >50% [[7]](#references). Sidekiq background workers throttle against database replication lag via GitHub’s Freno [[6]](#references), while central analytics queries (44M+/week) execute asynchronously to prevent data warehouse overload [[8]](#references).

### 3. Cost Economics & Missing Data Boundaries
Audited SEC Form 10-K filings demonstrate sublinear infrastructure cost growth [[1]](#references), [[2]](#references):
* **Hosting Trends & Margins:** Revenue rose from $371.0M (FY2021) to $498.0M (FY2022), $596.4M (FY2023), and $720.4M (FY2024), while gross margin expanded from 78.9% to 80.8%, 82.7%, and 84.3% [[1]](#references), [[2]](#references). Annual increases in third-party hosting costs decelerated from +$8.5M (FY2022) to +$4.0M (FY2023) and +$1.6M (FY2024) through architectural efficiency [[1]](#references), [[2]](#references).
* **Purchase Commitments:** As of Dec 31, 2023, Freshworks maintained $337.5M in non-cancelable purchase commitments (primarily AWS hosting) through 2028 ($63.7M due in 2024) [[1]](#references).
* *Public Data Boundary:* Freshworks does not disclose itemized per-service bills (e.g., EC2 vs. S3) or cost-per-ticket metrics; data is reported solely as aggregate hosting costs [[1]](#references).

### 4. Outcomes, Lessons & Limitations
* **Scale Achieved:** Handles ~500,000 RPM at peak, 44M+ weekly analytics queries, and 67,000+ paying organizations [[1]](#references), [[4]](#references), [[8]](#references).
* **Core Lesson:** Cloud autoscaling is insufficient without application-layer resilience—such as blast-radius partitioning (Shells), database lag-aware queue throttling (Freno), and asynchronous decoupling (5× load multiplier without scaling warehouse hardware) [[5]](#references), [[6]](#references), [[8]](#references).
* **Limitation:** Deep architectural lock-in to AWS remains a documented operational risk [[1]](#references).

---

### References
<a id="references"></a>
* **[1]** Freshworks Inc., *Form 10-K Annual Report (FY2023)*, SEC, Feb. 16, 2024. [sec.gov](https://www.sec.gov/Archives/edgar/data/1544522/000154452224000012/frsh-20231231.htm)
* **[2]** Freshworks Inc., *Form 10-K Annual Report (FY2024)*, SEC, Feb. 20, 2025. [sec.gov](https://www.sec.gov/Archives/edgar/data/1544522/000154452225000010/frsh-20241231.htm)
* **[3]** AWS, *"Freshworks Expands Globally via AWS Global Passport,"* Case Study, 2024. [aws.amazon.com](https://aws.amazon.com/solutions/case-studies/freshworks-global-passport/)
* **[4]** B. Kumar, *"Scaling Freshdesk Web App for High Availability,"* Freshworks Eng., Jul. 2020. [freshworks.com](https://www.freshworks.com/explore-cx/scaling-the-freshdesk-web-app-for-high-availability/)
* **[5]** Freshworks Eng., *"How Freshdesk Uses HAProxy at Scale,"* Medium, Jun. 2020. [medium.com](https://medium.com/freshworks-engineering-blog/how-freshdesk-uses-haproxy-at-scale-c6839bc1f784)
* **[6]** Freshworks Eng., *"Safeguarding Infra from Runaway Background Jobs,"* Medium, 2020. [medium.com](https://medium.com/freshworks-engineering-blog/freshdesk-safeguard-infra-background-jobs-d56c734c494f)
* **[7]** Freshworks Eng., *"Self-Hosted Redis Cluster Infrastructure,"* Medium, 2023. [medium.com](https://medium.com/freshworks-engineering-blog/redis-cluster-90cf30934fd0)
* **[8]** R. Misra & S. KNV, *"The Async Shift: Scaling Data Without Scaling Costs,"* Medium, 2021. [medium.com](https://medium.com/freshworks-engineering-blog/the-async-shift-scaling-our-data-service-without-scaling-our-costs-625e5506770f)
