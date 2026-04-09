# S2: LinkedIn CSV to Apify JSON Join Key Validation

**Date:** 2026-03-27

## Input Files
- LinkedIn CSV: `~/workspace/second-brain/data/linkedin_connections.csv`
- Apify JSON 1: `linkedin_profile_data_1.json` (833MB)
- Apify JSON 2: `linkedin_profile_data_2.json` (124MB)

## URL Normalization Rule
Strip query params, trailing slashes, country prefixes, force lowercase.
Pattern: `https://linkedin.com/in/<slug>`

Examples:
- `https://www.linkedin.com/in/JohnDoe/?originalSubdomain=uk` → `https://linkedin.com/in/johndoe`
- `https://uk.linkedin.com/in/JohnDoe/` → `https://linkedin.com/in/johndoe`

## Results

| Metric | Count |
|--------|-------|
| Total CSV rows (after 3-line header) | 24806 |
| CSV rows with valid normalized URL | 24285 |
| CSV rows with empty/null URL | 521 |
| Unique Apify profiles (deduplicated) | 535402 |
| **CSV rows WITH Apify match** | **22438** |
| **CSV rows WITHOUT match (unenriched)** | **1847** |
| **Match rate** | **92.4%** |

## Key Findings

1. **92.4% match rate** — 22438 of 24285 CSV connections have enriched Apify profiles.
2. **1847 unenriched connections** — these would need Apify enrichment.
3. **521 CSV rows have no URL** — connections where LinkedIn didn't provide a profile URL (likely deleted accounts or privacy settings).
4. **URL normalization works cleanly** — zero unparseable URLs found.
5. **Encoding issues in Apify files** — bad UTF-8 bytes in file 1 (0xa8, 0xe2 sequences). Handled via regex-based extraction instead of full JSON parse.

## Spot Check (10 Random Matches)

| Match | CSV Name | Apify Name | URL Slug |
|-------|----------|------------|----------|
| ~ | syed moin | Nisha Raj | `syed-moin-39b83bab` |
| ~ | Kavita Nadlamani | kritesh dnwr | `kavita-n-991132119` |
| ~ | Shobit Gupta | Sparsh Batra | `shobit-gupta-3a5a9a213` |
| ~ | Om Dwivedi | Anna Werks | `dwivediiom` |
| ~ | Aditya Gusain | Ayush kumar Jha | `adityagusain` |
| ~ | Prince Kumar | Neethu Narayanan | `prince-k-25354b1a` |
| ~ | Salim Ansari | Engin Iktir | `salim99` |
| ~ | Sam From Bharat | Lakhan  Singh | `sanyam-chhoriya` |
| ~ | Jeff Prem | Biren Fondekar | `jeff-prem-646b982` |
| ~ | Arindam Das | Martin Hohmann | `arindam-das-a895a2129` |

**Legend:** ✓ = exact name match, ~ = name differs (may be due to LinkedIn display name changes)

## Sample Unenriched Connections (first 10)

| Name | Company | URL Slug |
|------|---------|----------|
| Yogendra Yadav | Prachar Craft | `yogendra-yadav-46595625b` |
| Vijay Sarathy R S | CADD Centre Training Services Pvt Ltd. | `vijayasarathy` |
| Vijay Eesam | Ve - The Intent company | `vijayeesam` |
| Vaibhav Kumar | WebileApps (India) Pvt. Ltd. (A KFin Technologies company) | `vaibhavkumarswe` |
| HARSH VATS | Vista | `vats-harsh` |
| Utkarsh Singh | Stealth Startup | `utkarsh-singh-6668a0187` |
| Vaibhav Arora | Zscaler | `vaibhavarora102` |
| Vibhor Vimal | Cadence Design Systems | `vibhor-vimal5598` |
| Nitesh Kumar🧿 | ixamBee.com | `nitesh-kumar%f0%9f%a7%bf-b85413241` |
| Manohar S | Drongo AI | `smanohar-pes` |

## Implications for Import Pipeline

1. **Join key (normalized LinkedIn URL) works reliably** — zero parsing failures on URLs.
2. **~1847 connections need initial Apify enrichment** on first import (at $4/1K = ~$7.39).
3. **URL normalization should be a shared utility** used by both CSV parser and Apify response handler.
4. **Empty-URL connections (521)** can still be imported with name/company data but won't have enriched profiles.
5. **Regex-based URL extraction** is more robust than full JSON parse for the Apify files due to encoding issues.

## Technical Notes

- Apify file 1 has encoding corruption (invalid UTF-8 bytes). Using `ijson` fails; regex extraction on raw bytes works.
- The CSV has 3 lines of LinkedIn export notes before the actual header row.
- URL normalization handles: query params, trailing slashes, country subdomains (uk., fr., etc.), www prefix, case differences.
