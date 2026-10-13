# Cost estimate

Source: AWS Price List files (list prices), read through [tools/pricing](../../../tools/pricing/README.md) and computed by [cost/estimate.py](../cost/estimate.py). Planning only, nothing deployed. Every figure here is an estimate from list prices under the assumptions below, never a bill.

Region: `ap-southeast-1` (Singapore), proposed in [decisions.md](decisions.md) D8. The repo default `ap-southeast-3` (Jakarta) has no Textract and no embedding model. WAF for CloudFront is global scope and is priced from the `us-east-1` file. Prices were read on 2026-10-13.

## Assumptions

Scenario B, "light personal use", is the base case. Each number can be changed in `BASE` and `SCENARIOS` at the top of `cost/estimate.py`, then the tables re-run.

| Item | Value |
|---|---|
| Hours per month | 730 |
| Questions per month | 3,000 (about 100 a day) |
| One question | 60 tokens to embed, 2,400 input tokens to the model (six chunks of about 330 tokens plus the question), 500 output tokens |
| New documents per month | 100, about 7 chunks each (about 231,000 embedding tokens) |
| Scanned documents | 20% of new documents, 30 pages each, so 600 Textract pages |
| Lambda | arm64. Embedder 1 GB for 45 s per document. `query-api` 0.5 GB for 4 s per question. `ingest-api` 128 MB for 0.1 s per call |
| API calls | 3,000 `/query` plus 300 `/ingest` through an API Gateway HTTP API |
| SQS | About 650,000 requests a month from the Lambda event source mapping polling the queue, plus 4 per message |
| S3 | 2.2 GB Standard, requests for uploads and reads |
| Logs and alarms | 0.5 GB ingested, 0.5 GB stored, 11 alarms |
| KMS and Secrets Manager | One key with 50,000 requests, one secret with 10,000 calls |
| WAF | One web ACL, three rules (rate limit plus two managed groups), about 39,000 requests |
| RDS | `db.t4g.micro` PostgreSQL, single-AZ, 20 GB gp3 |
| Endpoints | Three interface endpoints (Bedrock runtime, Textract, Secrets Manager) in one AZ, plus the free S3 gateway endpoint |
| Generation model | Claude Sonnet 5.5 through global cross-Region inference |
| Embedding model | Cohere Embed Multilingual v3 |

## Estimate

### Scenario B in detail (monthly, USD)

| Service | Item | USD |
|---|---|---|
| RDS PostgreSQL | db.t4g.micro, single-AZ, 730 h | 18.25 |
| RDS PostgreSQL | 20 GB gp3 storage | 2.76 |
| VPC endpoints | 3 interface endpoints x 1 AZ, 730 h | 28.47 |
| VPC endpoints | 1 GB processed | 0.01 |
| WAF | 1 web ACL + 3 rules | 8.00 |
| WAF | 39,300 requests | 0.02 |
| Bedrock generation | Claude Sonnet 5.5 (global): 7.20M in, 1.50M out tokens | 29.40 |
| Bedrock embeddings | Cohere Embed Multilingual v3, 0.41M tokens | 0.04 |
| Textract | 600 pages text detection | 0.90 |
| Lambda | arm64, 10,504 GB-s, 3,400 requests | 0.14 |
| API Gateway | HTTP API, 3,300 requests | 0.00 |
| SQS | 650,400 requests (mostly Lambda polling) | 0.26 |
| S3 | 2.2 GB Standard + requests | 0.06 |
| CloudWatch | 0.5 GB logs ingested, 0.5 GB stored, 11 alarms | 1.47 |
| KMS | 1 key + 50,000 requests | 1.09 |
| Secrets Manager | 1 secret + 10,000 API calls | 0.45 |
| Route 53 | 39,300 DNS queries (hosted zone not in Price List, excluded) | 0.02 |
| **Total** | with Claude Sonnet 5.5 (global) | **91.34** |

### Totals by scenario and generation model (monthly, USD)

| Scenario | Claude Sonnet 5.5 (global) | Claude Haiku 5.5 (global) | Nova Lite |
|---|---|---|---|
| A. Idle (no use) | 60.35 | 60.35 | 60.35 |
| B. Light personal use | 91.34 | 63.41 | 63.01 |
| C. Heavy (10x the questions and documents) | 363.93 | 84.63 | 80.62 |

Fixed monthly cost that does not depend on use (RDS, endpoints, WAF, KMS, Secrets Manager): about 59.04 USD.

One-time load of the existing corpus (5,686 chunks, about 1.88M tokens):

| Embedding model | USD per 1M tokens | One-time USD |
|---|---|---|
| Cohere Embed Multilingual v3 | 0.1 | 0.19 |
| Titan Text Embeddings V2 | 0.028 | 0.05 |

## What is not in these numbers

- CloudFront edge requests and data transfer out to users, and the Route 53 hosted zone. The CloudFront and Route 53 price files for these regions list no such rows, so they are left out rather than guessed. Data transfer from the Singapore region to CloudFront is listed at 0 USD per GB in the data transfer file. At this traffic the missing items are expected to be small, which is an expectation and not a checked figure.
- Domain registration. Ordinary ACM public certificates and the S3 gateway endpoint have no price row in the files (the ACM rows cover private CA and certificate export), so they are counted as 0.
- Free tiers for new accounts, reserved terms, savings plans, cross-AZ data transfer, and RDS backup storage above the free allocation. None is applied or expected at 20 GB.
- SNS email stays inside the first 1,000 notifications a month, which the price file lists as free.

## Cost drivers

- **Fixed cost is about 59 USD a month at zero use.** RDS (21.01), the interface endpoints (28.47) and WAF (8.00) make up almost all of it.
- **The generation model decides the variable cost.** Per 1,000 questions at the assumed size: Claude Sonnet 5.5 costs 9.80 USD, Claude Haiku 5.5 costs 0.49 USD, Nova Lite costs 0.36 USD. At 30,000 questions a month Sonnet reaches 363.93 USD while Haiku stays at 84.63 USD.
- Embeddings, Textract, Lambda, API Gateway, SQS, S3, KMS and Secrets Manager together are under 4 USD in the base case.
- SQS costs about 0.26 USD even when idle, because the event source mapping keeps polling.
- Claude Haiku 5.5 has a separate long-context price that is five times the standard one (0.50 against 0.10 USD per 1M input tokens). The price file does not state the threshold, so keep prompts short and check it before relying on the Haiku figure.

## Endpoints versus a NAT gateway

Hourly charges only, per month. A NAT gateway also bills 0.059 USD per GB processed.

| Option | USD |
|---|---|
| 4 interface endpoints including CloudWatch Logs, 2 AZ | 75.92 |
| 3 interface endpoints (Bedrock, Textract, Secrets Manager), 2 AZ | 56.94 |
| 3 interface endpoints, 1 AZ (base case) | 28.47 |
| 2 interface endpoints (Secrets Manager dropped), 1 AZ | 18.98 |
| 1 NAT gateway, 1 AZ | 43.07 |
| 2 NAT gateways, 2 AZ | 86.14 |

Endpoints are not cheaper than NAT for this design. One-AZ endpoints cost less than one NAT gateway, and two-AZ endpoints cost more. The reason to choose endpoints is that the private subnets have no route to the internet, as set out in [decisions.md](decisions.md) D2.

## Optimization levers

| Lever | Effect on scenario B |
|---|---|
| Claude Haiku 5.5 or Nova Lite instead of Sonnet 5.5 | 91.34 down to 63.41 or 63.01 |
| Keep endpoints in one AZ | Saves 28.47 against two AZs |
| IAM database authentication instead of a Secrets Manager secret, which removes one endpoint | About 9.9 less (one endpoint 9.49, plus the secret). To verify before adopting |
| Stop RDS when the knowledge base is not in use | Saves up to 18.25 of instance hours. Storage is still billed, and RDS restarts a stopped instance after seven days |
| Fewer WAF rules | 1.00 each |
| Titan Text Embeddings V2 instead of Cohere | Under 0.03 a month, so not a real lever. Quality decides |

Production shape for comparison: Multi-AZ `db.t4g.micro` with 20 GB costs 42.75 against 21.01 single-AZ, and endpoints in two AZs add 28.47. That is about 50 USD more a month.

Database options, 20 GB gp3, single-AZ unless noted: `db.t4g.micro` 21.01, `db.t4g.small` 39.99, `db.t4g.micro` Multi-AZ 42.75.

## Conflicts and open points

- The Singapore price file lists Titan Text Embeddings V2 at 0.028 USD per 1M tokens, while the Bedrock availability table does not list the model in that region. The two AWS sources disagree. Confirm in the console before choosing between Cohere and Titan (decisions D8 and D9).
- Claude prices in the Singapore file are for global cross-Region inference. Where the request is processed and billed is a console check.
- Scenario C assumes ten times the questions and documents with unchanged sizes per question. Real use can differ in both directions.

## Reproduce

```bash
python tools/pricing/pricing.py update --region ap-southeast-1 --raw-dir <raw folder>
python tools/pricing/pricing.py update --region us-east-1 --only awswaf --raw-dir <raw folder>
python blueprints/rag-aws/cost/estimate.py
```

The script stops with an error if a price is missing or ambiguous, instead of guessing.

## Price files used

| Service file | Region | Published | Version |
|---|---|---|---|
| AmazonRDS | ap-southeast-1 | 2026-10-06 | 20261006224050 |
| AmazonVPC | ap-southeast-1 | 2026-09-17 | 20260917190528 |
| AmazonEC2 (NAT gateway) | ap-southeast-1 | 2026-10-12 | 20261012193925 |
| AmazonTextract | ap-southeast-1 | 2026-09-11 | 20260911124513 |
| AmazonBedrock | ap-southeast-1 | 2026-10-10 | 20261010182242 |
| AmazonBedrockFoundationModels | ap-southeast-1 | 2026-10-12 | 20261012084008 |
| AWSLambda | ap-southeast-1 | 2026-10-12 | 20261012223257 |
| AmazonApiGateway | ap-southeast-1 | 2026-10-13 | 20261013003044 |
| AWSQueueService | ap-southeast-1 | 2026-09-11 | 20260911124607 |
| AmazonS3 | ap-southeast-1 | 2026-10-12 | 20261012231102 |
| AmazonCloudWatch | ap-southeast-1 | 2026-10-07 | 20261007115540 |
| awskms | ap-southeast-1 | 2026-09-11 | 20260911124601 |
| AWSSecretsManager | ap-southeast-1 | 2026-09-11 | 20260911124610 |
| AmazonSNS | ap-southeast-1 | 2026-09-15 | 20260915151944 |
| AmazonRoute53 | ap-southeast-1 | 2026-09-11 | 20260911124504 |
| awswaf | us-east-1 | 2026-09-14 | 20260914163921 |
