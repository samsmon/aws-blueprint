---
title: rag-kb on AWS
slug: rag-aws
status: drafted
tags: [rag, bedrock, lambda, pgvector, serverless]
created: 2026-10-12
updated: 2026-10-13
---

# rag-kb on AWS

An AWS design for a personal RAG knowledge base: upload documents to S3, embed them automatically, and ask questions through a chat page backed by Bedrock.

> **Status: drafted.** Design only. It has not been deployed and there is no AWS account behind it. Cost figures in [docs/cost.md](docs/cost.md) are estimates from list prices, never a bill. The one real part is `rag-kb`, which runs on my own homelab; this blueprint shows how I would move it to AWS.

## What is real and what is not

| Layer | Status |
|---|---|
| `rag-kb` (CLI, chunking, OCR, retrieval) | Real, runs on the homelab. About 5,686 chunks at the end of its first phase, recall@5 of 0.96 on its eval set |
| Postgres + pgvector, Voyage `voyage-4` embeddings (1024 dimensions) | Real, in `rag-kb` |
| Everything on the diagram below | Design only |
| Generated answers (the LLM step) | New. `rag-kb` returns chunks and an outside agent writes the answer |

## Goal

Show how `rag-kb` would run as a managed, event-driven service on AWS: ingest on upload, retrieve and generate on request, with the security and operations pieces a real deployment needs.

## Scope

In scope:
- Two Lambda APIs behind API Gateway: `ingest-api` and `query-api`.
- Automatic chunk, embed and store when a document lands in S3.
- Retrieval over RDS PostgreSQL with pgvector, answer generation on Bedrock, with source citations.
- A static chat page on S3 behind CloudFront and WAF.
- Private networking without NAT, encryption with KMS, alarms to email.

Out of scope:
- User login and multi-tenancy. A real deployment would add Cognito.
- Re-ranking and hybrid search.
- Terraform. This blueprint is docs and a diagram until the design settles.

## Architecture

![rag-kb on AWS](docs/img/architecture.svg)

Source: [diagrams/architecture.yml](diagrams/architecture.yml), rendered with [tools/diagram](../../tools/diagram/README.md).

### Ingest path

| Step | What happens |
|---|---|
| 1 | The chat page calls `POST /ingest` through CloudFront and API Gateway |
| 2 | `ingest-api` checks type and size and returns a presigned URL. The browser uploads straight to the S3 raw bucket, so files never pass through Lambda |
| 3 | S3 raises an `ObjectCreated` event into an SQS queue. The queue absorbs bulk uploads and gives retries and a dead-letter queue |
| 4 | The embedder Lambda takes a message, fetches the object from S3 using the key in the event, and extracts text |
| 5 | Scans go through Textract. This replaces Tesseract OCR from `rag-kb` |
| 6 | The text is chunked and each chunk is embedded with a Bedrock embedding model |
| 7 | Chunks, vectors and source metadata are written to RDS. The metadata makes citations and per-document deletes possible |

The fetch in step 4 is not drawn. Adding that arrow would cross the CloudWatch and KMS links in the same band.

### Query path

| Step | What happens |
|---|---|
| 1 | The chat page calls `POST /query`; `query-api` receives it |
| 2 | `query-api` calls Bedrock twice: first to embed the question, then to generate the answer from the retrieved chunks. The diagram shows one arrow for both |
| 3 | `query-api` retrieves the top-k chunks from RDS with pgvector |

### Supporting services

Dashed links on the diagram: red is security, pink is operations.

| Service | Links to |
|---|---|
| WAF | CloudFront |
| KMS | S3 raw bucket, SQS, RDS, Secrets Manager |
| Secrets Manager | RDS (credentials) |
| CloudWatch | API Gateway, the three Lambdas, SQS (dead-letter alarm), RDS, and SNS |
| SNS | Alarm emails, fed by CloudWatch |

### Network

The embedder, `query-api` and RDS sit in private subnets across two AZs. There is no NAT gateway, so the VPC endpoint icon on the VPC border stands for the endpoints that let them reach S3, Bedrock, Textract and Secrets Manager. Interface endpoints are billed per hour, which will be one of the cost drivers. `ingest-api` stays outside the VPC because it only signs URLs.

RDS is single-AZ in the prototype, as the diagram says. A production design would turn on Multi-AZ.

## From `rag-kb` to AWS

| `rag-kb` today | On AWS |
|---|---|
| Postgres + pgvector on the homelab | RDS PostgreSQL with pgvector |
| Voyage `voyage-4`, 1024 dimensions | A Bedrock embedding model, Cohere Embed Multilingual v3 proposed (D9) |
| Tesseract OCR | Textract |
| `kb` CLI, run on demand, no daemon | `ingest-api` and `query-api`, event-driven ingest |
| Reached over Tailscale | CloudFront and API Gateway |
| Answers written by an outside agent | Generated on Bedrock (new) |

## Open questions

1. **Region and models.** The repo default `ap-southeast-3` (Jakarta) has no Textract and no embedding model. [docs/decisions.md](docs/decisions.md) (D8 to D10) proposes Singapore with Cohere Embed Multilingual v3 and a Claude model through global cross-Region inference. These come from AWS documentation, which can be incomplete or out of date, so confirm them in the Bedrock console.
2. **Embedding model.** Vectors from different models are not comparable, so moving over means re-embedding the whole corpus. The `rag-kb` eval set can measure the change against its 0.96 baseline (D9).
3. **Cost.** [docs/cost.md](docs/cost.md) estimates about 91 USD a month for light use with Claude Sonnet 5.5, or about 63 USD with Claude Haiku 5.5, of which about 59 USD is fixed (RDS, endpoints, WAF). The Singapore price file lists a Titan embedding price that the availability table does not support; confirm in the console.

## Docs

- [docs/decisions.md](docs/decisions.md): trade-offs and what production would change.
- [docs/architecture.md](docs/architecture.md): components, data model, networking, security, observability.
- [docs/cost.md](docs/cost.md): estimate with assumptions, cost drivers and levers; [cost/estimate.py](cost/estimate.py) recomputes it from the AWS Price List.

## Related

- [`rag-kb`](https://github.com/samsmon/rag-kb) (private): the system this design migrates.
- [`yado-aws`](../yado-aws/): the reference blueprint; shares the diagram house style and the RDS and secrets patterns.
