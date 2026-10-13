#!/usr/bin/env python3
"""Local AWS prices: download the official AWS Price List once, keep it, query it from SQLite.

    python tools/pricing/pricing.py update [--region ap-southeast-1] [--raw-dir DIR] [--only AmazonRDS,AWSLambda]
    python tools/pricing/pricing.py digest --out DIR [--region R] [--offer AmazonRDS]
    python tools/pricing/pricing.py find <word> [<word> ...] [--offer AmazonRDS] [--limit 20]
    python tools/pricing/pricing.py info

Source: https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws (public, no credentials).
`update` keeps every raw file as <raw-dir>/<region>/<offer>.json.gz (byte-exact content, gzipped) plus a
MANIFEST.csv, and loads all on-demand prices into SQLite at $AWS_PRICING_DIR or ~/aws-pricing/prices.db.
`digest` writes compact markdown per offer for a knowledge base. Prices are list prices, not a bill.
"""
import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"
DEFAULT_REGION = "ap-southeast-1"
DROP_ATTRS = {"servicecode", "location", "locationType", "regionCode"}
MAX_LINES = 20000  # digest lines per markdown file


def data_dir():
    return Path(os.environ.get("AWS_PRICING_DIR") or Path.home() / "aws-pricing")


def open_text(path):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def fetch(url, dest=None):
    req = urllib.request.Request(url, headers={"User-Agent": "aws-blueprint-pricing/1"})
    with urllib.request.urlopen(req, timeout=180) as r:
        if dest is None:
            return r.read()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        return dest


def download(region, offers, raw_dir, workers=6):
    """Fetch each offer, gzip it next to the others, return {offer: info dict or None}."""
    out_dir = raw_dir / region
    out_dir.mkdir(parents=True, exist_ok=True)

    def one(offer):
        url = f"{BASE}/{offer}/current/{region}/index.json"
        tmp = out_dir / f"{offer}.json.part"
        final = out_dir / f"{offer}.json.gz"
        try:
            fetch(url, tmp)
        except urllib.error.HTTPError as err:
            if err.code in (403, 404):
                return offer, None
            raise
        raw_bytes = tmp.stat().st_size
        with open(tmp, "rb") as src, gzip.open(final, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst, 1 << 20)
        with open(tmp, "rb") as f:
            head = f.read(800).decode("utf-8", "replace")
        tmp.unlink()
        sha = hashlib.sha256(final.read_bytes()).hexdigest()
        return offer, dict(offer=offer, published=_find(head, "publicationDate"), version=_find(head, "version"),
                           bytes_raw=raw_bytes, bytes_gz=final.stat().st_size, sha256_gz=sha, url=url,
                           fetched=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), path=final)

    with ThreadPoolExecutor(workers) as pool:
        return dict(pool.map(one, offers))


def _find(text, key):
    m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def pack(product):
    a = product.get("attributes", {})
    return {"productFamily": product.get("productFamily") or "",
            "attributes": {k: v for k, v in a.items() if k not in DROP_ATTRS}}


def term_rows(offer, region, sku, product, terms):
    a = product["attributes"]
    attrs = json.dumps(a, separators=(",", ":"))
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            usd = dim.get("pricePerUnit", {}).get("USD")
            if usd is None:
                continue
            yield (offer, region, sku, product["productFamily"], a.get("usagetype", ""), a.get("operation", ""),
                   dim.get("description", ""), dim.get("unit", ""), float(usd),
                   dim.get("beginRange", ""), dim.get("endRange", ""), attrs)


def json_rows(offer, region, path):
    with open_text(path) as f:
        data = json.load(f)
    products = data.get("products", {})
    for sku, terms in data.get("terms", {}).get("OnDemand", {}).items():
        if sku in products:
            yield from term_rows(offer, region, sku, pack(products[sku]), terms)


def stream_rows(offer, region, path):
    """Pretty-printed price list read line by line (AmazonEC2 is too big to json.load)."""
    wanted, section, sub, block = {}, None, None, None
    sku4 = re.compile(r'^    "([A-Za-z0-9]+)" : \{\s*$')
    sku6 = re.compile(r'^      "([A-Za-z0-9]+)" : \{\s*$')
    with open_text(path) as f:
        for line in f:
            if line.startswith('  "products"'):
                section = "products"
                continue
            if line.startswith('  "terms"'):
                section = "terms"
                continue
            if section == "products":
                if block is None:
                    if sku4.match(line):
                        block = [line]
                else:
                    block.append(line)
                    if line.startswith("    }"):
                        text = "".join(block).rstrip().rstrip(",")
                        (sku, prod), = json.loads("{" + text + "}").items()
                        wanted[sku] = pack(prod)
                        block = None
            elif section == "terms":
                if block is None and line.startswith('    "'):
                    sub = "OnDemand" if line.startswith('    "OnDemand"') else None
                    continue
                if sub != "OnDemand":
                    continue
                if block is None:
                    m = sku6.match(line)
                    if m and m.group(1) in wanted:
                        block = [line]
                else:
                    block.append(line)
                    if line.startswith("      }"):
                        text = "".join(block).rstrip().rstrip(",")
                        (sku, terms), = json.loads("{" + text + "}").items()
                        yield from term_rows(offer, region, sku, wanted[sku], terms)
                        block = None


def open_db():
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(d / "prices.db")
    cols = [r[1] for r in db.execute("PRAGMA table_info(meta)")]
    if cols and "version" not in cols:  # older schema: the tables are derived data, rebuild them
        db.executescript("DROP TABLE IF EXISTS prices; DROP TABLE IF EXISTS meta;")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS prices (offer TEXT, region TEXT, sku TEXT, family TEXT, usagetype TEXT,
      operation TEXT, description TEXT, unit TEXT, usd REAL, begin_range TEXT, end_range TEXT, attrs TEXT);
    CREATE INDEX IF NOT EXISTS prices_offer ON prices(offer, region);
    CREATE TABLE IF NOT EXISTS meta (offer TEXT, region TEXT, published TEXT, version TEXT, fetched TEXT,
      PRIMARY KEY (offer, region));
    """)
    return db


def load_offer(db, offer, region, path):
    rows = stream_rows(offer, region, path) if offer == "AmazonEC2" else json_rows(offer, region, path)
    db.execute("DELETE FROM prices WHERE offer=? AND region=?", (offer, region))
    batch, n = [], 0
    for row in rows:
        batch.append(row)
        if len(batch) >= 5000:
            db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
            n, batch = n + len(batch), []
    if batch:
        db.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", batch)
        n += len(batch)
    return n


def cmd_update(args):
    region = args.region
    offers = sorted(json.loads(fetch(f"{BASE}/index.json"))["offers"])
    if args.only:
        offers = [o for o in args.only.split(",") if o in offers]
    raw_dir = Path(args.raw_dir) if args.raw_dir else data_dir() / "raw"
    print(f"downloading up to {len(offers)} offers for {region} into {raw_dir / region} ...", flush=True)
    got = download(region, offers, raw_dir)
    present = {o: i for o, i in got.items() if i}
    raw_mb = sum(i["bytes_raw"] for i in present.values()) / 1e6
    gz_mb = sum(i["bytes_gz"] for i in present.values()) / 1e6
    print(f"downloaded {len(present)} files, {raw_mb:.0f} MB raw, {gz_mb:.0f} MB gzipped; "
          f"{len(got) - len(present)} offers have no file for {region}", flush=True)
    manifest = raw_dir / region / "MANIFEST.csv"
    with open(manifest, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["offer", "published", "version", "bytes_raw", "bytes_gz", "sha256_gz", "fetched", "url"])
        for o in sorted(present):
            i = present[o]
            w.writerow([o, i["published"], i["version"], i["bytes_raw"], i["bytes_gz"], i["sha256_gz"], i["fetched"], i["url"]])
    db = open_db()
    total = 0
    for o in sorted(present):
        n = load_offer(db, o, region, present[o]["path"])
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?,?,?,datetime('now'))",
                   (o, region, present[o]["published"], present[o]["version"]))
        db.commit()
        total += n
    dbp = data_dir() / "prices.db"
    print(f"database {dbp} ({dbp.stat().st_size / 1e6:.0f} MB), {total} price rows; manifest {manifest}")


def cmd_load(args):
    """Rebuild the database from raw files already on disk (no download)."""
    region = args.region
    raw = (Path(args.raw_dir) if args.raw_dir else data_dir() / "raw") / region
    db = open_db()
    total = 0
    for path in sorted(raw.glob("*.json.gz")):
        offer = path.name[: -len(".json.gz")]
        with gzip.open(path, "rt", encoding="utf-8") as f:
            head = f.read(800)
        n = load_offer(db, offer, region, path)
        db.execute("INSERT OR REPLACE INTO meta VALUES (?,?,?,?,datetime('now'))",
                   (offer, region, _find(head, "publicationDate"), _find(head, "version")))
        db.commit()
        total += n
        print(f"{offer}: {n} rows", flush=True)
    dbp = data_dir() / "prices.db"
    print(f"database {dbp} ({dbp.stat().st_size / 1e6:.0f} MB), {total} price rows")


def fmt_line(usage, desc, unit, usd, b, e):
    tier = f" [tier {b} to {e}]" if b not in ("", "0") or e not in ("", "Inf") else ""
    price = f"{usd:.10f}".rstrip("0").rstrip(".") or "0"
    return f"- {usage} | {desc} | {price} USD per {unit}{tier}"


def cmd_digest(args):
    db = open_db()
    out = Path(args.out) / args.region
    out.mkdir(parents=True, exist_ok=True)
    q = "SELECT offer, published, version, fetched FROM meta WHERE region=?" + (" AND offer=?" if args.offer else "") + " ORDER BY offer"
    metas = db.execute(q, (args.region, args.offer) if args.offer else (args.region,)).fetchall()
    files = lines_total = 0
    for offer, published, version, fetched in metas:
        rows = db.execute("SELECT family, usagetype, description, unit, usd, begin_range, end_range FROM prices "
                          "WHERE offer=? AND region=? ORDER BY family, usagetype, description, CAST(begin_range AS REAL)",
                          (offer, args.region)).fetchall()
        seen, fam_lines = set(), []
        for fam, usage, desc, unit, usd, b, e in rows:
            key = (fam, usage, desc, unit, usd, b, e)
            if key in seen:
                continue
            seen.add(key)
            fam_lines.append((fam or "Other", fmt_line(usage, desc, unit, usd, b, e)))
        parts = [fam_lines[i:i + MAX_LINES] for i in range(0, len(fam_lines), MAX_LINES)] or [[]]
        for pi, part in enumerate(parts, 1):
            name = f"{offer}.md" if len(parts) == 1 else f"{offer}--part{pi:02d}.md"
            head = [f"# AWS price list: {offer}, {args.region}", "",
                    f"Source: {BASE}/{offer}/current/{args.region}/index.json",
                    f"Published: {published} (version {version}). Fetched: {fetched} (database load time, UTC).",
                    "On-demand list prices in USD, not a bill. Each line: usage type | description | price per unit.",
                    ""]
            if len(parts) > 1:
                head += [f"Part {pi} of {len(parts)}.", ""]
            body, cur = [], None
            for fam, line in part:
                if fam != cur:
                    body += ["", f"## {offer} / {fam}", ""]
                    cur = fam
                body.append(line)
            (out / name).write_text("\n".join(head + body) + "\n", encoding="utf-8")
            files += 1
            lines_total += len(part)
    size = sum(p.stat().st_size for p in out.glob("*.md"))
    print(f"digest: {files} files, {lines_total} lines, {size / 1e6:.1f} MB in {out} (about {size / 3.5 / 1e6:.1f}M tokens at 3.5 bytes per token)")


def cmd_find(args):
    db = open_db()
    words = [w.lower() for w in args.word]
    where = " AND ".join("lower(offer || ' ' || family || ' ' || usagetype || ' ' || operation || ' ' || description || ' ' || attrs) LIKE ?"
                         for _ in words)
    params = [f"%{w}%" for w in words]
    if args.offer:
        where += " AND offer = ?"
        params.append(args.offer)
    if args.region:
        where += " AND region = ?"
        params.append(args.region)
    rows = db.execute(f"SELECT offer, region, usagetype, description, unit, usd, begin_range, end_range "
                      f"FROM prices WHERE {where} ORDER BY offer, usagetype, CAST(begin_range AS REAL) LIMIT ?",
                      params + [args.limit]).fetchall()
    for offer, region, usage, desc, unit, usd, b, e in rows:
        print(f"{offer} | {region} | {fmt_line(usage, desc, unit, usd, b, e)[2:]}")
    print(f"{len(rows)} row(s)" + (" (limit reached, add words or --offer)" if len(rows) == args.limit else ""))


def cmd_info(_):
    db = open_db()
    rows = db.execute("SELECT region, count(*), min(published), max(published), min(fetched) FROM meta GROUP BY region").fetchall()
    if not rows:
        print("empty: run `update` first")
    for region, n, pmin, pmax, fetched in rows:
        count = db.execute("SELECT count(*) FROM prices WHERE region=?", (region,)).fetchone()[0]
        print(f"{region}: {n} offers, {count} rows, published {pmin[:10]} to {pmax[:10]}, loaded {fetched}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update")
    u.add_argument("--region", default=DEFAULT_REGION)
    u.add_argument("--only")
    u.add_argument("--raw-dir")
    ld = sub.add_parser("load")
    ld.add_argument("--region", default=DEFAULT_REGION)
    ld.add_argument("--raw-dir")
    d = sub.add_parser("digest")
    d.add_argument("--out", required=True)
    d.add_argument("--region", default=DEFAULT_REGION)
    d.add_argument("--offer")
    f = sub.add_parser("find")
    f.add_argument("word", nargs="+")
    f.add_argument("--offer")
    f.add_argument("--region")
    f.add_argument("--limit", type=int, default=20)
    sub.add_parser("info")
    args = ap.parse_args()
    {"update": cmd_update, "load": cmd_load, "digest": cmd_digest, "find": cmd_find, "info": cmd_info}[args.cmd](args)


if __name__ == "__main__":
    main()
