# Contact Source Format Mapping

Spike S5 analysis: exact column layouts of all 4 contact source files mapped to LinkedOut ParsedContact fields.

Date: 2026-03-27

---

## 1. Summary Table

| Source Type | File Name | Data Rows | Key Columns | ParsedContact Coverage |
|---|---|---|---|---|
| LinkedIn CSV | `linkedin_connections.csv` | 24,806 | First Name, Last Name, URL, Email Address, Company, Position, Connected On | first/last name, company, title, linkedin_url, connected_at; email sparse (3.6%) |
| Google Contacts (job) | `contacts_from_google_job.csv` | 177 | Given Name, Family Name, E-mail 1 - Value, Website 1 - Value | first/last name, full_name, email (100%); no phone, no company/title |
| Contacts with phone | `contacts_with_phone.csv` | 1,540 | First Name, Middle Name, Last Name, Mobile Phone, E-mail Address, Company, Job Title | phone (87% mobile), first_name; email sparse (10%), company sparse (4%) |
| Email-only contacts | `gmail_contacts_email_id_only.csv` | 2,186 | First Name, Last Name, E-mail 1 - Value, Organization Name | email (100%); names unreliable, no phone, no company |

---

## 2. Per-Source Sections

### 2.1 LinkedIn CSV (`linkedin_connections.csv`)

**Format note:** File begins with a 3-line header note (lines 1-3) before the actual CSV header on line 4. The parser MUST skip lines 1-3 or detect the CSV header row dynamically.

```
Line 1: Notes:
Line 2: "When exporting your connection data, you may notice..."
Line 3: (blank)
Line 4: First Name,Last Name,URL,Email Address,Company,Position,Connected On  <-- actual header
```

**Columns (7):**

| # | Column | Example |
|---|--------|---------|
| 1 | First Name | `R.K.` |
| 2 | Last Name | `K.` |
| 3 | URL | `https://www.linkedin.com/in/rlrahulkanojia` |
| 4 | Email Address | `s.n@gmail.com` (mostly empty) |
| 5 | Company | `Wolters Kluwer` |
| 6 | Position | `Senior Machine Learning Engineer` |
| 7 | Connected On | `22 Feb 2026` |

**Sample rows (redacted):**

| First Name | Last Name | URL | Email Address | Company | Position | Connected On |
|---|---|---|---|---|---|---|
| R.K. | K. | https://www.linkedin.com/in/xxx | | Wolters Kluwer | Sr ML Engineer | 22 Feb 2026 |
| M.C. | | https://www.linkedin.com/in/yyy | | | | 07 Feb 2026 |
| U. | (UT) | https://www.linkedin.com/in/zzz | | xmplify.tech | Founder, CTA | 22 Jan 2026 |

**Column to ParsedContact mapping:**

| Source Column | ParsedContact Field | Notes |
|---|---|---|
| First Name | `first_name` | Direct |
| Last Name | `last_name` | May contain parenthetical nicknames, e.g. "(UT)" |
| First Name + Last Name | `full_name` | Concatenate with space |
| Email Address | `email` | Only 883/24,806 (3.6%) populated; LinkedIn privacy setting |
| Company | `company` | 96% populated |
| Position | `title` | 96% populated |
| URL | `linkedin_url` | Always present; already normalized LinkedIn profile URL |
| Connected On | `connected_at` | Format: `DD Mon YYYY` (e.g. `22 Feb 2026`). Parse with `%d %b %Y` |
| (entire row) | `raw_record` | Store as dict |

**Edge cases:**
- **3-line header note:** Must skip before parsing CSV
- **Email mostly missing:** Only 3.6% of rows have email; cannot rely on email as identifier
- **Last name quirks:** Some have nicknames in parens: `(UT)`. Some single-letter last names: `S`, `M`, `N`
- **Missing company/position:** ~4% of rows have empty Company and Position (e.g. students, between jobs)
- **Date format:** `DD Mon YYYY` -- no zero-padding (e.g. `7 Feb` not `07 Feb` in some rows). Use flexible parsing
- **Comma in Position:** Quoted fields, e.g. `"Founder, Chief Technology Advisor"` -- standard CSV quoting, handled by csv.reader

---

### 2.2 Google Contacts - Job (`contacts_from_google_job.csv`)

**Format:** Standard Google Contacts CSV export. 31 columns, most empty. No header preamble.

**Columns (31, key ones bolded):**

| # | Column | Populated |
|---|--------|-----------|
| 1 | **Name** | 176/177 |
| 2 | **Given Name** | 176/177 |
| 3 | Additional Name | rare |
| 4 | **Family Name** | 170/177 |
| 5-8 | Yomi Name variants | empty |
| 9-10 | Name Prefix/Suffix | empty |
| 11-14 | Initials, Nickname, Short Name, Maiden Name | empty |
| 15 | Birthday | empty |
| 16 | Gender | empty |
| 17-25 | Location through Subject | empty |
| 26 | Notes | empty |
| 27 | **Group Membership** | always present: `* My Contacts ::: Exit` or `Exit` |
| 28 | **E-mail 1 - Type** | `*` or `* Work` |
| 29 | **E-mail 1 - Value** | 177/177 (100%) |
| 30 | Website 1 - Type | `Profile` when present |
| 31 | **Website 1 - Value** | 122/177 -- Google profile URLs |

**Sample rows (redacted):**

| Name | Given Name | Family Name | E-mail 1 - Value | Group Membership |
|---|---|---|---|---|
| A.B. | A. | B. | ab@google.com | * My Contacts ::: Exit |
| A.P. | A. | P. | ap@google.com | Exit |

**Column to ParsedContact mapping:**

| Source Column | ParsedContact Field | Notes |
|---|---|---|
| Given Name | `first_name` | Direct |
| Family Name | `last_name` | Direct; 7 rows have empty family name |
| Name | `full_name` | Pre-formatted full name |
| E-mail 1 - Value | `email` | 100% populated |
| (none) | `phone` | Not available in this export |
| (none) | `company` | Not available; these are all from one employer context |
| (none) | `title` | Not available |
| (none) | `linkedin_url` | Not available |
| (none) | `connected_at` | Not available |
| (entire row) | `raw_record` | Store as dict |

**Edge cases:**
- **Group Membership separator:** Uses ` ::: ` as multi-value delimiter (not comma)
- **Website is Google Profile, not LinkedIn:** `http://www.google.com/profiles/NNNNN` -- not useful for `linkedin_url`
- **All contacts from same company context:** This is a job-era export; company can be inferred but is not explicit
- **Email type field:** `*` or `* Work` -- can be used to tag email type but not needed for ParsedContact
- **Different column layout from file 4:** Both are Google Contacts exports but have completely different schemas (see Section 3)

---

### 2.3 Contacts with Phone (`contacts_with_phone.csv`)

**Format:** Outlook-style CSV export (Google Contacts exported in Outlook format). 67 columns, most empty. No header preamble.

**Columns (67, key ones listed):**

| # | Column | Fill Rate |
|---|--------|-----------|
| 1 | **First Name** | ~100% |
| 2 | **Middle Name** | ~25% |
| 3 | **Last Name** | 953/1540 (62%) |
| 4 | Title | ~0% |
| 5 | Suffix | rare |
| 10 | E-mail Address | 160/1540 (10%) |
| 11 | E-mail 2 Address | rare |
| 13 | Primary Phone | 18/1540 |
| 16 | **Mobile Phone** | 1332/1540 (87%) |
| 38 | **Company** | 64/1540 (4%) |
| 39 | **Job Title** | 3/1540 (<1%) |
| 67 | Categories | always: `myContacts` or `Imported MM/DD/YYYY;myContacts` |

**Sample rows (redacted):**

| First Name | Middle Name | Last Name | Mobile Phone | E-mail Address | Company |
|---|---|---|---|---|---|
| A. | | | +91 79943 34501 | | |
| A.T. | | | +1 404-661-6234 | | |
| A. | | A. | +1 (408) 881-4767 | | |
| A. | (A. | F.) | +919715426276 | | |

**Column to ParsedContact mapping:**

| Source Column | ParsedContact Field | Notes |
|---|---|---|
| First Name | `first_name` | Needs cleaning -- see edge cases |
| Last Name | `last_name` | 62% populated; may contain context keywords |
| First Name + Last Name | `full_name` | Concatenate; Middle Name often has annotations, not real middle names |
| E-mail Address | `email` | Only 10% populated |
| Mobile Phone (primary), then Primary Phone, Home Phone | `phone` | Coalesce: Mobile > Primary > Home. Multiple formats |
| Company | `company` | Only 4% populated |
| Job Title | `title` | Essentially empty (<1%) |
| (none) | `linkedin_url` | Not available |
| (none) | `connected_at` | Not available |
| (entire row) | `raw_record` | Store as dict |

**Edge cases (significant):**
- **Name pollution:** Names contain contextual annotations:
  - Parenthetical context: `Abbas,(Anish,Friend)` -- middle name is `(Anish`, last name is `Friend)`
  - Company in last name: `Abhilash,,Python` -- "Python" is context, not a surname
  - Location in name: `Aarthi Beevi (District,Urban,Bangalore)` -- CSV quoting breaks across fields
  - Multi-word first name: `Aarjav Trivedi` in First Name column, Last Name empty
  - Comma in name causes field shift: `"Aastha,Crio.Do"` -- quoted but still problematic
- **Phone format inconsistency:** Multiple formats observed:
  - `+91 79943 34501` (Indian with spaces)
  - `+919715426276` (Indian, no spaces)
  - `+1 (408) 881-4767` (US with parens)
  - `+1 404-661-6234` (US with dashes)
  - `8053416962` (bare 10-digit)
  - `(408) 816-0070` (US local)
  - `93413 21918` (Indian, no country code)
  - Phone normalization is essential (E.164 recommended)
- **38% missing last names:** Many contacts are first-name-only phone contacts
- **Outlook export format:** 67 columns vs Google Contacts' 27/31 -- completely different schema despite both originating from Google account data

---

### 2.4 Email-Only Contacts (`gmail_contacts_email_id_only.csv`)

**Format:** Google Contacts CSV export (newer format). 27 columns. No header preamble.

**Columns (27, key ones listed):**

| # | Column | Fill Rate |
|---|--------|-----------|
| 1 | **First Name** | 1268/2186 (58%) -- BUT see edge cases |
| 2 | Middle Name | rare |
| 3 | **Last Name** | 1028/2186 (47%) |
| 4-6 | Phonetic Name variants | empty |
| 7-8 | Name Prefix/Suffix | empty |
| 9-10 | Nickname, File As | empty |
| 11 | Organization Name | 0/2186 |
| 12 | Organization Title | 0/2186 |
| 17 | **Labels** | always: `* Other Contacts` |
| 18 | E-mail 1 - Label | `* ` (asterisk + space) |
| 19 | **E-mail 1 - Value** | 2186/2186 (100%) |
| 24-25 | Phone 1 - Label/Value | 3/2186 |

**Sample rows (redacted):**

| First Name | Last Name | E-mail 1 - Value | Labels |
|---|---|---|---|
| (email as name) | | a***@gmail.com | * Other Contacts |
| (email as name) | | b***@gmail.com | * Other Contacts |
| 3966 | SBI | Sbi.03966@sbi.co.in | * Other Contacts |
| 91springboard | Boosters | boosters@91springboard.com | * Other Contacts |

**Column to ParsedContact mapping:**

| Source Column | ParsedContact Field | Notes |
|---|---|---|
| First Name | `first_name` | Unreliable -- see edge cases. Only use if not an email address |
| Last Name | `last_name` | Unreliable -- often organization fragments |
| First Name + Last Name | `full_name` | Only if names are real (not emails/numbers) |
| E-mail 1 - Value | `email` | 100% populated -- the only reliable field |
| Phone 1 - Value | `phone` | Essentially empty (3 rows) |
| Organization Name | `company` | Always empty |
| Organization Title | `title` | Always empty |
| (none) | `linkedin_url` | Not available |
| (none) | `connected_at` | Not available |
| (entire row) | `raw_record` | Store as dict |

**Edge cases (significant):**
- **Email address stored as First Name:** 53 rows have the email address duplicated in the First Name field. Detect with `@` check
- **Non-person entities as "names":** Organization names split across First/Last: `91springboard / Boosters`, `3966 / SBI`. These are not human contacts
- **918 rows with completely empty names:** Only email is available. `full_name` must be null
- **"* Other Contacts" label:** All entries are from Gmail's auto-collected contacts (people you emailed), not manually curated. Lower quality than "My Contacts"
- **Overlap with file 2:** Both are Google Contacts exports but different schemas:
  - File 2: 31 columns, uses `Name`/`Given Name`/`Family Name`/`Group Membership`/`E-mail 1 - Type`
  - File 4: 27 columns, uses `First Name`/`Last Name`/`Labels`/`E-mail 1 - Label`

---

## 3. Cross-Source Comparison

### ParsedContact Field Availability

| ParsedContact Field | LinkedIn | Google Job | Contacts w/ Phone | Email-Only |
|---|---|---|---|---|
| `first_name` | 100% | 99% | ~100% (noisy) | 58% (very noisy) |
| `last_name` | ~99% | 96% | 62% | 47% (noisy) |
| `full_name` | derived | 99% (Name col) | derived | unreliable |
| `email` | 3.6% | 100% | 10% | 100% |
| `phone` | -- | -- | 87% | <1% |
| `company` | 96% | -- | 4% | -- |
| `title` | 96% | -- | <1% | -- |
| `linkedin_url` | 100% | -- | -- | -- |
| `connected_at` | 100% | -- | -- | -- |

### Source Strengths

| Source | Primary Value |
|---|---|
| LinkedIn | Professional identity (name, company, title, linkedin_url, connected_at) |
| Google Job | Verified email for known professional contacts |
| Contacts w/ Phone | Phone numbers for personal/professional contacts |
| Email-Only | Email addresses from correspondence (lowest quality, highest volume) |

---

## 4. Converter Implementation Notes

### 4.1 LinkedInContactConverter

- **Header skip:** Must detect/skip the 3-line preamble. Strategy: scan for the line starting with `First Name,Last Name,URL` or skip first N non-CSV lines.
- **Date parsing:** `connected_at` format is `DD Mon YYYY`. Use `datetime.strptime(val, "%d %b %Y").date()`.
- **Email:** Treat empty string as None. Do not default to any value.
- **linkedin_url:** Use as-is; already in `https://www.linkedin.com/in/slug` format. Normalize trailing slashes.
- **Deduplication key:** `linkedin_url` (unique per connection).

### 4.2 GoogleJobContactConverter

- **Column layout:** 31-column Google Contacts export. Use `Given Name`/`Family Name` for first/last, `Name` for full_name.
- **No phone/company/title:** These fields will always be None from this source.
- **Website field:** Google profile URL, not LinkedIn -- do not map to `linkedin_url`.
- **Group Membership parsing:** Split on ` ::: ` if needed for filtering.

### 4.3 PhoneContactConverter

- **Phone normalization:** Multiple formats must be normalized to E.164 (`+XXXXXXXXXXX`). Use a library like `phonenumbers`.
  - Default country: India (+91) for bare numbers without country code.
  - Phone coalescing order: Mobile Phone > Primary Phone > Home Phone > Business Phone.
- **Name cleaning:** Strip parenthetical annotations from First Name and Middle Name. Do not use Middle Name as-is -- it often contains context, not a real middle name.
- **Last Name reliability:** 38% missing. Company names or context words sometimes appear in Last Name field. Consider heuristic validation.
- **67-column format:** Most columns empty. Only read the ~6 relevant columns; store full row in `raw_record`.

### 4.4 EmailOnlyContactConverter

- **Name validation:** Before using First Name / Last Name:
  1. Reject if contains `@` (email stored as name)
  2. Reject if purely numeric
  3. Consider rejecting if it matches a known organization pattern
- **Primary identifier:** Email is the only reliable field. All other fields are best-effort.
- **Quality flag:** Consider marking these contacts with a lower confidence score or source quality indicator since they come from Gmail's auto-collected "Other Contacts."
- **Deduplication:** Email is the natural dedup key, but may overlap with emails from other sources.

### 4.5 Cross-Source Decisions

1. **File 2 vs File 4 schema difference:** Despite both being Google exports, they have different column schemas (31 vs 27 columns, different column names). Each needs its own converter. Flag: `contacts_from_google_job.csv` uses `Given Name`/`Family Name`/`Name` while `gmail_contacts_email_id_only.csv` uses `First Name`/`Last Name` (no composite `Name` column).

2. **Deduplication across sources:** When the same person appears in multiple sources, merge strategy:
   - LinkedIn + Google Job: match on email (when LinkedIn has it) or name similarity
   - LinkedIn + Phone: match on name similarity (no shared unique key)
   - Google Job + Email-Only: match on email

3. **Source priority for field conflicts:** LinkedIn > Google Job > Phone Contacts > Email-Only (based on data quality and professional relevance).
