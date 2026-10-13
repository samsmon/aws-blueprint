# pricing

Downloads the official AWS Price List once, keeps the raw files, and answers price questions from a local SQLite database. Cost docs cite this, so figures can be traced and refreshed.

```bash
python tools/pricing/pricing.py update --region ap-southeast-1 --raw-dir <folder for raw files>
python tools/pricing/pricing.py find nat gateway hour --offer AmazonEC2
python tools/pricing/pricing.py info
python tools/pricing/pricing.py digest --out <folder>     # markdown per service, for a knowledge base
python tools/pricing/pricing.py load --raw-dir <folder>   # rebuild the database from raw files, no download
```

## What it does
- Source: `https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws`. Public, no credentials. Prices are list prices, on-demand terms, in USD. They are estimates inputs, never a bill.
- `update` fetches every service that has a file for the region (189 of 272 for `ap-southeast-1`), keeps each as `<raw-dir>/<region>/<offer>.json.gz` (content unchanged, gzipped), writes `MANIFEST.csv` (publication date, version, sizes, sha256, URL), and loads all on-demand prices into SQLite.
- `AmazonEC2` alone is about 357 MB, so it is read line by line, never loaded whole.
- The database is `$AWS_PRICING_DIR/prices.db`, default `~/aws-pricing/prices.db`. It sits outside the repo and can be rebuilt from the raw files.
- `find` takes any number of words and matches them against service, family, usage type, description and attributes. Add `--offer` to narrow, `--limit` to see more.

## Where the data for this repo lives
Raw files and digests are kept in the `cloud-ops` repo under `projects/aws-pricing/` (git-ignored there, because of size; the manifest is tracked). Nothing under `~/aws-pricing` or those folders is committed here.

## Limits
- Only the region you pass is downloaded. Another region (for example the fallback in `rag-aws` decision D8) is the same command with `--region`.
- Free tiers, reserved terms and savings plans are not applied. Cost estimates say so.
- A price file that AWS republishes changes the numbers; the manifest records which version was used.
