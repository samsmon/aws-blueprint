#!/usr/bin/env python3
"""Monthly cost estimate for rag-aws, computed from the local AWS price database.

    python blueprints/rag-aws/cost/estimate.py            # markdown tables for docs/cost.md
    python blueprints/rag-aws/cost/estimate.py --json     # the same numbers as JSON

Prices come from tools/pricing (`pricing.py update`), region ap-southeast-1, plus us-east-1 for WAF
(global scope). Every price is looked up by usage type, so a missing or ambiguous price stops the run
instead of being guessed. Free tiers, reserved terms and savings plans are NOT applied. The result is an
estimate from list prices under the assumptions below, never a bill.
"""
import argparse
import json
import os
import sqlite3
from pathlib import Path

DB = Path(os.environ.get("AWS_PRICING_DIR") or Path.home() / "aws-pricing") / "prices.db"
SG, US = "ap-southeast-1", "us-east-1"
db = sqlite3.connect(DB)


def price(offer, region, usagetype, like=None, begin=None, unlike=None):
    """One unit price. `like`/`unlike` filter the description; `begin` picks a tier start; else the first tier."""
    rows = db.execute("SELECT usd, begin_range, description FROM prices WHERE offer=? AND region=? AND usagetype=?",
                      (offer, region, usagetype)).fetchall()
    if like:
        rows = [r for r in rows if like.lower() in r[2].lower()]
    if unlike:
        rows = [r for r in rows if unlike.lower() not in r[2].lower()]
    if begin is not None:
        rows = [r for r in rows if str(r[1]) == str(begin)]
    if not rows:
        raise KeyError(f"no price: {offer} {region} {usagetype} like={like} begin={begin}")
    first = min(float(r[1] or 0) for r in rows)
    vals = {r[0] for r in rows if float(r[1] or 0) == first}
    if len(vals) != 1:
        raise KeyError(f"ambiguous price: {offer} {usagetype} like={like}: {sorted(vals)}")
    return vals.pop()


def fm_price(model, kind, scope, exclude=("long_ctx", "cache", "batch", "reserved", "provisioned", "image")):
    """Bedrock third-party model price per 1M tokens, by the model attribute in the price list."""
    rows = db.execute("SELECT usagetype, usd, attrs FROM prices WHERE offer='AmazonBedrockFoundationModels' AND region=?", (SG,)).fetchall()
    vals = set()
    for u, usd, at in rows:
        a = json.loads(at)
        ul = u.lower()
        if a.get("model") != model or a.get("inferenceType") != kind or a.get("feature") != "On-demand Inference":
            continue
        if any(x in ul for x in exclude) or (scope == "global") != ("global" in ul):
            continue
        vals.add(usd)
    if len(vals) != 1:
        raise KeyError(f"fm price {model} {kind} {scope}: {sorted(vals)}")
    return vals.pop()


HOURS = 730
BASE = dict(queries=3000, docs=100, scan_share=0.2, pages_per_scan=30, chunks_per_doc=7, tokens_per_chunk=330,
            q_embed_tokens=60, q_in_tokens=2400, q_out_tokens=500, embedder_gb=1.0, embedder_sec=45.0,
            query_gb=0.5, query_sec=4.0, ingest_calls=300, ui_requests=36000, sqs_poll_requests=650000,
            s3_gb=2.2, logs_gb=0.5, log_store_gb=0.5, alarms=11, kms_requests=50000, secrets_requests=10000,
            waf_rules=3, rds_gb=20, endpoints=3, endpoint_azs=1, endpoint_gb=1.0)
SCENARIOS = {"A. Idle (no use)": dict(queries=0, docs=0, scan_share=0, ingest_calls=0, ui_requests=0, sqs_poll_requests=650000, logs_gb=0.05, kms_requests=1000, secrets_requests=100, endpoint_gb=0.0),
             "B. Light personal use": {},
             "C. Heavy (10x)": dict(queries=30000, docs=500, ingest_calls=1500, ui_requests=360000, logs_gb=3.0, kms_requests=300000, secrets_requests=50000, endpoint_gb=8.0)}
LLMS = {"Claude Sonnet 5.5 (global)": ("Claude Sonnet 5.5", None), "Claude Haiku 5.5 (global)": ("Claude Haiku 5.5", None), "Nova Lite": (None, None)}


def llm_prices(name):
    if name.startswith("Nova"):
        return price("AmazonBedrock", SG, "APS1-NovaLite-input-tokens") * 1000, price("AmazonBedrock", SG, "APS1-NovaLite-output-tokens") * 1000
    model = LLMS[name][0]
    return fm_price(model, "Input tokens", "global"), fm_price(model, "Output tokens", "global")


def estimate(over, llm, rds="micro"):
    a = {**BASE, **over}
    P = {}
    P["rds_hour"] = price("AmazonRDS", SG, f"APS1-InstanceUsage:db.t4g.{rds}", like="PostgreSQL")
    P["rds_gb"] = price("AmazonRDS", SG, "APS1-RDS:GP3-Storage", like="PostgreSQL")
    P["vpce_hour"] = price("AmazonVPC", SG, "APS1-VpcEndpoint-Hours")
    P["vpce_gb"] = price("AmazonVPC", SG, "APS1-VpcEndpoint-Bytes", begin=0)
    P["textract"] = price("AmazonTextract", SG, "APS1-SyncTextPagesProcessed", begin=0)
    P["cohere_m"] = fm_price("Embed Multilingual", "Input tokens", "region")
    P["lam_req"] = price("AWSLambda", SG, "APS1-Request")
    P["lam_gbs"] = price("AWSLambda", SG, "APS1-Lambda-GB-Second-ARM")
    P["apigw"] = price("AmazonApiGateway", SG, "APS1-ApiGatewayHttpRequest")
    P["sqs"] = price("AWSQueueService", SG, "APS1-Requests-Tier1", like="standard")
    P["s3_gb"] = price("AmazonS3", SG, "APS1-TimedStorage-ByteHrs", begin=0)
    P["s3_put"] = price("AmazonS3", SG, "APS1-Requests-Tier1", like="PUT")
    P["s3_get"] = price("AmazonS3", SG, "APS1-Requests-Tier2", like="GET")
    P["waf_acl"] = price("awswaf", US, "USE1-WebACL")
    P["waf_rule"] = price("awswaf", US, "USE1-Rule")
    P["waf_req"] = price("awswaf", US, "USE1-Request")
    P["cw_ingest"] = price("AmazonCloudWatch", SG, "APS1-DataProcessing-Bytes", like="Standard log class")
    P["cw_store"] = price("AmazonCloudWatch", SG, "APS1-TimedStorage-ByteHrs", like="log storage")
    P["cw_alarm"] = price("AmazonCloudWatch", SG, "APS1-CW:AlarmMonitorUsage")
    P["kms_key"] = price("awskms", SG, "ap-southeast-1-KMS-Keys")
    P["kms_req"] = price("awskms", SG, "ap-southeast-1-KMS-Requests")
    P["secret"] = price("AWSSecretsManager", SG, "APS1-AWSSecretsManager-Secret")
    P["secret_req"] = price("AWSSecretsManager", SG, "APS1-AWSSecretsManagerAPIRequest")
    P["dns_q"] = price("AmazonRoute53", SG, "APS1-DNS-Queries", begin=0)
    in_m, out_m = llm_prices(llm)

    new_chunks = a["docs"] * a["chunks_per_doc"]
    embed_tokens = new_chunks * a["tokens_per_chunk"] + a["queries"] * a["q_embed_tokens"]
    scan_pages = a["docs"] * a["scan_share"] * a["pages_per_scan"]
    api_requests = a["queries"] + a["ingest_calls"]
    msgs = a["docs"]
    lam_gbs = a["docs"] * a["embedder_sec"] * a["embedder_gb"] + a["queries"] * a["query_sec"] * a["query_gb"] + a["ingest_calls"] * 0.1 * 0.128
    lam_reqs = api_requests + msgs
    sqs_reqs = a["sqs_poll_requests"] + msgs * 4
    waf_reqs = api_requests + a["ui_requests"]
    ei = a["endpoints"] * a["endpoint_azs"]
    rows = [
        ("RDS PostgreSQL", f"db.t4g.{rds}, single-AZ, {HOURS} h", HOURS * P["rds_hour"]),
        ("RDS PostgreSQL", f"{a['rds_gb']} GB gp3 storage", a["rds_gb"] * P["rds_gb"]),
        ("VPC endpoints", f"{a['endpoints']} interface endpoints x {a['endpoint_azs']} AZ, {HOURS} h", ei * HOURS * P["vpce_hour"]),
        ("VPC endpoints", f"{a['endpoint_gb']:g} GB processed", a["endpoint_gb"] * P["vpce_gb"]),
        ("WAF", f"1 web ACL + {a['waf_rules']} rules", P["waf_acl"] + a["waf_rules"] * P["waf_rule"]),
        ("WAF", f"{waf_reqs:,.0f} requests", waf_reqs * P["waf_req"]),
        ("Bedrock generation", f"{llm}: {a['queries'] * a['q_in_tokens'] / 1e6:.2f}M in, {a['queries'] * a['q_out_tokens'] / 1e6:.2f}M out tokens",
         a["queries"] * a["q_in_tokens"] / 1e6 * in_m + a["queries"] * a["q_out_tokens"] / 1e6 * out_m),
        ("Bedrock embeddings", f"Cohere Embed Multilingual v3, {embed_tokens / 1e6:.2f}M tokens", embed_tokens / 1e6 * P["cohere_m"]),
        ("Textract", f"{scan_pages:,.0f} pages text detection", scan_pages * P["textract"]),
        ("Lambda", f"arm64, {lam_gbs:,.0f} GB-s, {lam_reqs:,.0f} requests", lam_gbs * P["lam_gbs"] + lam_reqs * P["lam_req"]),
        ("API Gateway", f"HTTP API, {api_requests:,.0f} requests", api_requests * P["apigw"]),
        ("SQS", f"{sqs_reqs:,.0f} requests (mostly Lambda polling)", sqs_reqs * P["sqs"]),
        ("S3", f"{a['s3_gb']} GB Standard + requests", a["s3_gb"] * P["s3_gb"] + (a["ingest_calls"] + msgs) * P["s3_put"] + (msgs * 3 + a["ui_requests"] * 0.02) * P["s3_get"]),
        ("CloudWatch", f"{a['logs_gb']} GB logs ingested, {a['log_store_gb']} GB stored, {a['alarms']} alarms",
         a["logs_gb"] * P["cw_ingest"] + a["log_store_gb"] * P["cw_store"] + a["alarms"] * P["cw_alarm"]),
        ("KMS", f"1 key + {a['kms_requests']:,.0f} requests", P["kms_key"] + max(a["kms_requests"] - 20000, 0) * P["kms_req"]),
        ("Secrets Manager", f"1 secret + {a['secrets_requests']:,.0f} API calls", P["secret"] + a["secrets_requests"] * P["secret_req"]),
        ("Route 53", f"{(waf_reqs):,.0f} DNS queries (hosted zone not in Price List, excluded)", waf_reqs * P["dns_q"]),
    ]
    return rows, P, a


def totals(rows):
    return sum(r[2] for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = {}
    lines = []
    base_llm = "Claude Sonnet 5.5 (global)"
    for sname, over in SCENARIOS.items():
        row = {}
        for llm in LLMS:
            rows, P, a = estimate(over, llm)
            row[llm] = round(totals(rows), 2)
        out[sname] = row
    rows, P, a = estimate({}, base_llm)
    lines.append("### Scenario B in detail (monthly, USD)\n")
    lines.append("| Service | Item | USD |\n|---|---|---|")
    for svc, item, usd in rows:
        lines.append(f"| {svc} | {item} | {usd:,.2f} |")
    lines.append(f"| **Total** | with {base_llm} | **{totals(rows):,.2f}** |\n")
    lines.append("### Totals by scenario and generation model (monthly, USD)\n")
    lines.append("| Scenario | " + " | ".join(LLMS) + " |\n|---|" + "---|" * len(LLMS))
    for sname, row in out.items():
        lines.append(f"| {sname} | " + " | ".join(f"{row[l]:,.2f}" for l in LLMS) + " |")
    fixed = sum(r[2] for r in rows if r[0] in ("RDS PostgreSQL", "VPC endpoints", "WAF", "KMS", "Secrets Manager")) - rows[3][2]
    lines.append(f"\nFixed monthly cost that does not depend on use (RDS, endpoints, WAF, KMS, Secrets Manager): about {fixed:,.2f} USD.\n")
    nat_h = price("AmazonEC2", SG, "APS1-NatGateway-Hours")
    nat_gb = price("AmazonEC2", SG, "APS1-NatGateway-Bytes")
    v = P["vpce_hour"]
    lines.append("### Endpoints versus NAT gateway (monthly, USD, hourly charges only)\n")
    lines.append("| Option | USD |\n|---|---|")
    lines.append(f"| 4 interface endpoints incl. CloudWatch Logs, 2 AZ | {4 * 2 * HOURS * v:,.2f} |")
    lines.append(f"| 3 interface endpoints (Bedrock, Textract, Secrets Manager), 2 AZ | {3 * 2 * HOURS * v:,.2f} |")
    lines.append(f"| 3 interface endpoints, 1 AZ (this blueprint's base case) | {3 * HOURS * v:,.2f} |")
    lines.append(f"| 2 interface endpoints (Secrets Manager dropped via IAM database auth), 1 AZ | {2 * HOURS * v:,.2f} |")
    lines.append(f"| 1 NAT gateway, 1 AZ (plus {nat_gb:.3f} USD per GB processed) | {HOURS * nat_h:,.2f} |")
    lines.append(f"| 2 NAT gateways, 2 AZ | {2 * HOURS * nat_h:,.2f} |\n")
    rds_small = price("AmazonRDS", SG, "APS1-InstanceUsage:db.t4g.small", like="PostgreSQL")
    rds_micro = P["rds_hour"]
    maz = price("AmazonRDS", SG, "APS1-Multi-AZUsage:db.t4g.micro", like="PostgreSQL")
    maz_gb = price("AmazonRDS", SG, "APS1-RDS:Multi-AZ-GP3-Storage", like="PostgreSQL")
    lines.append("### Database options (monthly, USD, 20 GB gp3)\n")
    lines.append("| Option | USD |\n|---|---|")
    lines.append(f"| db.t4g.micro single-AZ (base case) | {HOURS * rds_micro + 20 * P['rds_gb']:,.2f} |")
    lines.append(f"| db.t4g.small single-AZ | {HOURS * rds_small + 20 * P['rds_gb']:,.2f} |")
    lines.append(f"| db.t4g.micro Multi-AZ (production shape) | {HOURS * maz + 20 * maz_gb:,.2f} |")
    cohere, titan = P["cohere_m"], price("AmazonBedrock", SG, "APS1-TitanEmbeddingV2-Text-input-tokens") * 1000
    corpus_tokens = 5686 * BASE["tokens_per_chunk"]
    lines.append("\n### One-time load of the existing corpus (5,686 chunks, about "
                 f"{corpus_tokens / 1e6:.2f}M tokens)\n")
    lines.append("| Embedding model | USD per 1M tokens | One-time USD |\n|---|---|---|")
    lines.append(f"| Cohere Embed Multilingual v3 | {cohere:g} | {corpus_tokens / 1e6 * cohere:,.2f} |")
    lines.append(f"| Titan Text Embeddings V2 | {titan:g} | {corpus_tokens / 1e6 * titan:,.2f} |")
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()
