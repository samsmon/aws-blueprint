# Decisions

Trade-offs and prototype shortcuts for `rag-aws`, each with what production would change. Facts about regions and quotas come from AWS documentation read on 2026-10-13; AWS adds regions and models often, so confirm in the console before building.

Status: D1 to D7 are decided. D8 to D10 are proposed and wait for a check in the console and an eval run. The last section lists what is not decided yet.

## D1: Custom ingest pipeline instead of Bedrock Knowledge Bases
Context: Knowledge Bases would chunk, embed and sync a S3 bucket for me. `rag-kb` already has its own chunking, source metadata and citation format, and the point of this blueprint is to show the mechanism.
Decision: S3 event, SQS, an embedder Lambda, and pgvector on RDS.
Trade-off: More code to own and no managed sync. In return the vector store matches `rag-kb` (Postgres + pgvector), metadata stays under my control, and the vector store has no minimum capacity charge of its own.
Production: Reconsider Knowledge Bases if the team wants less code more than control over chunking.

## D2: VPC endpoints instead of a NAT gateway
Context: The embedder and `query-api` run in private subnets next to RDS. They must reach S3, Bedrock, Textract, Secrets Manager and CloudWatch Logs. SQS needs no endpoint because the Lambda event source mapping polls the queue from outside the VPC.
Decision: A gateway endpoint for S3 and interface endpoints for the rest. No NAT gateway and no internet route from the private subnets.
Trade-off: Each interface endpoint is billed per hour per AZ, so the endpoint count is a cost driver (counted in `cost.md`). The Lambdas cannot call anything outside AWS, which also rules out calling the Voyage API from the cloud.
Production: A NAT gateway or an egress proxy if a Lambda has to call an external API.

## D3: `ingest-api` runs outside the VPC
Context: `ingest-api` only checks the file and signs an S3 URL. It never touches RDS.
Decision: No VPC attachment for it.
Trade-off: It needs no endpoints and has no network setup to maintain. It also cannot reach RDS, so a feature such as "list my documents" needs a rethink.
Production: Same, unless such a feature is added.

## D4: Browser uploads straight to S3 with a presigned URL
Context: Sending files through API Gateway and Lambda is limited by payload size (10 MB for API Gateway, 6 MB for a synchronous Lambda invocation), and scanned PDFs are larger.
Decision: `ingest-api` returns a presigned URL and the browser uploads to the raw bucket.
Trade-off: Two round trips for the client. Size and type checks happen when the URL is issued, so the bucket policy must also enforce them.
Production: Same.

## D5: SQS between S3 and the embedder
Context: Bulk uploads would otherwise start many embedder runs at once. Textract's default quota in regions outside the big ones is low (1 transaction per second for `DetectDocumentText` and for `AnalyzeDocument` in "Other Regions" in the quota table), and Bedrock has its own limits.
Decision: S3 sends `ObjectCreated` to an SQS queue with a dead-letter queue. The Lambda event source mapping caps concurrency.
Trade-off: One more moving part. In return retries, back pressure and a place to look at failures.
Production: Add an alarm on the dead-letter queue depth. It is already linked to CloudWatch on the diagram.

## D6: Textract replaces Tesseract
Context: `rag-kb` OCRs scans with Tesseract. Shipping a Tesseract binary in a Lambda is possible but awkward.
Decision: Textract for scanned PDFs and images.
Trade-off: Billed per page, with low default quotas (see D5), and available in fewer regions: it is not offered in Jakarta or Tokyo.
Production: Same, with a quota increase if volume grows.

## D7: RDS is single-AZ in the prototype
Context: A DB subnet group needs subnets in at least two AZs, so the VPC spans two. The database itself can still run in one.
Decision: Single-AZ RDS PostgreSQL with pgvector. The diagram says so on the RDS label and says "2 AZs" for the subnets.
Trade-off: An AZ outage takes the knowledge base down until it recovers. Acceptable for a personal prototype, and cheaper.
Production: Turn on Multi-AZ.

## D8: Region `ap-southeast-1` (Singapore), proposed
Context: The repo default is `ap-southeast-3` (Jakarta), which is closest to me. The pieces this design needs are not all available there.

| Need | Jakarta | Singapore | Mumbai |
|---|---|---|---|
| Textract | No | Yes | Yes |
| An embedding model in the region (Titan Text Embeddings V2) | Not listed | Not listed | Listed |
| Cohere Embed Multilingual v3 (knowledge base model list) | Not listed | Listed | Listed |
| Claude models | Global cross-Region inference only | Global cross-Region inference only | Not checked |

Decision: Use Singapore. It is the nearest region with Textract and a multilingual embedding model. Mumbai is the fallback, because it has both Titan V2 and Cohere. Estimates in `cost.md` state the region they assume.
Trade-off: Higher latency than Jakarta and no single-Region option for Claude. The Cohere row comes from the knowledge base page, not the runtime page, so it is the first thing to confirm.
Production: Pick the region that holds the data's residency requirements, then check models again.

## D9: Embedding model Cohere Embed Multilingual v3, proposed
Context: The corpus is Indonesian and English course material. `voyage-4` gives 1024 dimensions. The model must be multilingual, and vectors from different models cannot be compared, so the whole corpus is embedded again whichever model is chosen.
Decision: Cohere Embed Multilingual v3, which is multilingual and 1024 wide, so the pgvector column keeps its width. Titan Text Embeddings V2 (1024, 512 or 256 dimensions) is the alternative if Mumbai is chosen.
Trade-off: Unproven on this corpus. Run the `rag-kb` eval set against both models and compare with the 0.96 recall@5 baseline before locking it in.
Production: Keep the eval set in CI-like use so a model change is measured, not guessed.

## D10: Answers generated by a Claude model through global cross-Region inference, proposed
Context: In both Jakarta and Singapore the documentation lists Claude only through global cross-Region inference. Nova Lite is available with geographic cross-Region inference in Singapore.
Decision: Claude via the global inference profile for the generation step.
Trade-off: Prompts, which contain retrieved text from my documents, may be processed in another region. That is fine for course notes and not for anything sensitive. Nova Lite is the lower-cost, lower-quality alternative that stays in a geographic group.
Production: Decide per data classification, and use a geographic profile if data must stay in a region group.

## Not decided yet
- Authentication. There is no login, so the API would be open behind WAF rate limits. A real deployment adds Cognito and an authorizer.
- Chunk size and overlap. They should start from the `rag-kb` settings and be tuned with the eval set.
- Which Bedrock quotas apply to the account, and whether the embedder concurrency cap in D5 needs to be lower.
- Bedrock pricing assumptions for `cost.md`, which depend on D8 to D10.
- How multi-page scanned PDFs are OCRed: the synchronous Textract call suits short documents, and long ones need the asynchronous API and a second step (see architecture.md, open design points).

## Sources
- [Bedrock regional availability](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html), page text was truncated after part of the Anthropic section.
- [Bedrock knowledge base supported models and regions](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-supported.html)
- [Titan Text Embeddings models](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Textract endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/textract.html)
