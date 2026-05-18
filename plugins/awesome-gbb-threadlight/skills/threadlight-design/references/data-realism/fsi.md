# FSI demo-data realism rules

> **Audience.** Use this file when generating mock data for any FSI process
> demo (KYC/AML, fraud monitoring, credit, claims, payments, capital
> markets). Every rule has a citation — if you change a value, follow the
> citation, don't guess.

## Vocabulary every FSI SME expects to see

If a generated SPEC, agent prompt, or sample data omits these terms when
they apply, an industry SME will conclude we don't know banking. Cross-
check before declaring a SPEC ready:

**Compliance / AML / KYC**: CIP (Customer Identification Program) · CDD
(Customer Due Diligence) · EDD (Enhanced Due Diligence — applies to PEPs,
high-risk jurisdictions, complex ownership) · UBO (Ultimate Beneficial
Owner — FinCEN BOI threshold **25%** under the Corporate Transparency Act)
· SAR (Suspicious Activity Report — FinCEN form 111, 30-day filing window
from initial detection, 60-day extension on continuing activity) · CTR
(Currency Transaction Report — FinCEN form 112, **>\ cash aggregate
per business day per customer**) · structuring / smurfing · PEP (Politically
Exposed Person) · adverse media · 314(a) / 314(b) USA PATRIOT Act
information sharing · MRA (Matter Requiring Attention — bank-regulator
finding) · MRIA (Matter Requiring Immediate Attention) · lookback (when a
regulator orders a retroactive review)

**Sanctions lists**: OFAC SDN · OFAC Consolidated · OFAC Sectoral (SSI) ·
EU Consolidated Financial Sanctions List · UN Security Council Consolidated
List (1267 / 1988) · HMT OFSI Consolidated List (UK) · DFAT Consolidated
List (Australia) · SECO (Switzerland) · Hong Kong UNATM list

**Regs**: BSA · USA PATRIOT Act · Bank Secrecy Act · FATCA · CRS · FATF 40
Recommendations · FFIEC BSA/AML Manual · OCC Bulletins · FRB SR letters ·
Reg E (EFT) · Reg Z (TILA) · Reg B (ECOA / fair lending) · Reg DD
(truth-in-savings) · MiFID II · CRD V/VI · CRR · BCBS 239 (risk data
aggregation) · IFRS 9 / CECL (credit loss) · GDPR (EU) · CCPA (CA) ·
GLBA · NYDFS Part 500 (cyber)

**Capital markets**: Dodd-Frank Title VII · EMIR · CFTC Part 43/45 · MAR
(Market Abuse Reg) · best-execution · MNPI (material non-public info)

**Insurance**: NAIC · ORSA · IFRS 17 · Solvency II · ICS · LIMRA · ACORD

**Vendor systems** (name them when describing customer integrations):
- **Core banking**: FIS Profile / IBS · Fiserv DNA · Jack Henry SilverLake
  · Temenos T24 · Finastra Fusion · Mambu · Thought Machine Vault
- **AML / sanctions / fraud**: NICE Actimize · SAS AML · Quantexa · Oracle
  Financial Services Analytical Apps (OFSAA) · LexisNexis Bridger · Refinitiv
  World-Check · Dow Jones Risk Center · Featurespace ARIC · Feedzai
- **KYC / onboarding**: Fenergo · nCino · Salesforce Financial Services
  Cloud · ComplyAdvantage · Trulioo · Onfido · Persona · Socure
- **Trading / treasury**: Murex · Calypso · Bloomberg AIM / TOMS / SSEOMS
  · MarkitWire · Charles River IMS · BlackRock Aladdin
- **Payments**: TCH RTP · FedNow · SWIFT gpi · ISO 20022 (CBPR+, HVPS+) ·
  EBA STEP2 · CHAPS · ACH

**Roles** (use real titles in personas, not "compliance person"):
- Branch: Branch Manager · Personal Banker · Relationship Manager (RM) ·
  Premier Banker · Private Banker
- Compliance: BSA Officer · MLRO (UK) · CCO (Chief Compliance Officer) ·
  Sanctions Officer · L1/L2/L3 AML Analyst · QC Reviewer
- Risk: CRO · Credit Officer · Model Risk Manager · Underwriter
- Ops: KYC Analyst · Onboarding Ops · Loan Processor · Wire Investigator

## Identifiers (citation-backed, never-resolving)

| Type | Rule + citation | Example |
|------|-----------------|---------|
| **US SSN** | SSA-published documentation set: 987-65-4320 through 987-65-4329. **Do NOT** use 900–999 with middle digits 70–88/90–92/94–99 — that's the **REAL** ITIN range issued by the IRS (per IRS Pub. 1635). | 987-65-4321 |
| **US ITIN** | If you specifically need ITIN-formatted, use SSA documentation set values that are formatted ITIN-shaped but are explicitly published as test (very rare — usually use SSN doc set above). | (avoid unless required) |
| **US EIN** | EIN test set: prefixes 0, 7–9, 17–19, 28–29, 49, 69, 70, 78–79, 89 are not issued by IRS (IRS Pub. 1635 list of valid prefixes). | 0-1234567 |
| **EU IBAN** | ECB IBAN registry includes published examples per country. Use those exactly with the citation in a comment. Do NOT generate IBANs that pass mod-97 against arbitrary BBANs — they may resolve to real accounts. | GB82 WEST 1234 5698 7654 32 (UK ECB example) · DE89 3704 0044 0532 0130 00 (Germany ECB example — Commerzbank Köln BLZ; cite as ECB-published demo, never as `test'') |
| **UK sort code** | UK Payments Association documented test sort codes: NatWest test 7-00-93, HSBC test 60-16-13. **0-00-XX is NOT a documented reserved range**. | 7-00-93 |
| **SWIFT/BIC** | XXX suffix = head-office branch (not "test"). Use SWIFT-reference test pattern or a clearly-fictional 4-letter institution: TESTBIC0XXX. **DEUTDEFFXXX is the real primary BIC for Deutsche Bank AG** — never use as a "test" example. | TESTGB22XXX |
| **CUSIP / ISIN / SEDOL** | CUSIP fictional test prefixes per CUSIP Global Services. ISIN: use country prefix + valid Luhn check. **Do not use the SPDR / iShares / Vanguard prefixes that map to real ETFs.** | BBG000B9XRY4 (Bloomberg test FIGI shape — for fictional securities only) |
| **LEI** | GLEIF publishes a sandbox at lei-test.gleif.org with documented sandbox LEIs. Use those. | (cite GLEIF sandbox) |
| **Customer ID** | Internal — prefix with your bank's two-token shifted name + dash, e.g. CFB-CUST-00042 for "Cardinal Federal Bank". | CFB-CUST-00042 |
| **Account number** | Synthetic 8–12 digits prefixed 9 (rarely real account leading digit at most US institutions); cite the bank's documented account-number format. | 987654321 |
| **Phone (US/CA)** | NANPA fictional reservation: +1-NPA-555-01XX where NPA is any valid area code and 1XX is the central-office line range 100–199. **555 is the central-office code, not the area code** — +1-555-01XX-XXXX is malformed. | +1-202-555-0173 |

## Names

| Field | Rule |
|-------|------|
| **Person names** | Faker locale matching geography (n_US, n_GB, de_DE, r_FR, pt_BR, ja_JP). Never names of public figures, sanctioned persons, or recognizable celebrities. |
| **Company names** | **Two-token-shift pattern**: <Distinctive adjective + Industry noun> — Cardinal Federal Bank, Northwind Financial Holdings, Pinnacle Trust & Capital, Solstice Wealth Management. **Banned**: any verbatim real bank name (Wells Fargo, JPMorgan, Citi, HSBC…), and the cartoon names from the universal README (Acme, FooCorp, Contoso, Fabrikam, Northwind Traders verbatim). |
| **Branch names** | Real city + fictional street: Manhattan – Hawthorne Street Branch. |

## Sanctions / watchlist

- **Always include a sanctioned-entity case** in demo data, but the entity
  must be **fictional** AND modeled on the **shape of a real high-risk
  pattern** an AML SME will recognize. Acceptable patterns (May 2026
  high-risk concentrations per FATF Public Statement and OFAC enforcement
  data):
  - **DPRK shell-company structure**: nominally a Hong Kong or Singapore
    trading entity with Pyongyang-linked beneficial ownership through 2–3
    layers; commodity profile (coal, seafood, textiles, IT services).
  - **Iran / IRGC-front**: nominally a UAE or Türkiye intermediary trading
    petrochemicals or dual-use electronics with concealed Iranian principals.
  - **Russia post-2022 evasion**: nominally a Central Asia or Caucasus
    trader sourcing Western goods (EAR-controlled microelectronics, ball
    bearings, optics) for re-export to Russian consignees.
  - **Drug-trafficking organization (DTO)**: cash-intensive front-business
    pattern (car wash, restaurant chain, used-car lot) with structured
    deposits and outbound wires to high-risk source-country corridors.

  Each fictional entity should have: incorporation date, two named
  beneficial owners (synthetic names per § Names), registered agent
  address in a documented FATF "jurisdictions under increased monitoring"
  country (current grey-list per FATF June 2024; **do NOT** stigmatize
  legitimate Caribbean financial centers like Cayman, Bahamas, Barbados —
  those are **not** on the FATF grey list).
- The agent's hit on this entity is the named golden case for the
  experience walkthrough — preserve it.

## Transactions

- **Amount distribution**: log-normal, mean ~\,200, p99 ~\,000 for retail
  consumer; for SMB / commercial, log-normal mean ~\,000, p99 ~\.5M.
- **Velocity**: retail consumers 5–15 txns/month; high-velocity flag fires
  at ≥40/month. Commercial customers 200–2,000 txns/month.
- **Geographies**: 80% home country, 15% common cross-border (UK→EU,
  US→Canada, US→Mexico, EU→UK), 5% high-risk corridors (named documented
  FATF grey-list jurisdictions; never invented "Crimson Caribbean").
- **Suspicious patterns** seeded for the demo: **structuring** (10× \,800
  to stay under CTR threshold), **round-amount + offshore destination**,
  **dormant-then-active** accounts, **pass-through** (immediate
  wire-out matching wire-in), **BIN attack** card patterns, **APP scams**
  (authorised push payment fraud — UK CRM Code).

## Production-realism volume + SLA defaults

For demos where the customer asks "how does this look at our volume?",
target these scales — anything smaller is a sandbox, not a credible PoC:

| Process | Realistic record volume | Realistic SLA |
|---------|--------------------------|----------------|
| KYC onboarding (retail) | 50K–200K customers, 5–15K new/month | Same-day for low-risk; **2–5 business days for EDD** |
| KYC onboarding (corporate / commercial) | 10K–50K entities, 200–500 new/month | **5–15 business days for complex EDD** with UBO chain |
| AML transaction monitoring (Tier-1 bank) | **5K–50K alerts/day** with **>95% historical false-positive rate** | L1 disposition <24h; L2 escalation <72h; SAR filing within FinCEN 30-day window |
| Fraud detection (card / payments) | 1M–10M txn/day, alert volume 0.5–2% | Real-time block <2s; case review <4h |
| Sanctions screening | 100–500 alerts/day per US\ AUM | <1 business day disposition |
| Credit underwriting (consumer) | 1K–10K applications/day | Decisioning <30s automated; manual review <24h |
| Fraud-investigation queue (retail bank) | 500–5K open cases at steady-state | 5–10 business day cycle time |

Demos with 5–10 records read as toys. Default to **≥50 records per primary
entity** for any seller-led narrative; **≥10K records** for an executive
walkthrough where the customer asks scale questions.

## Credit data

- **FICO scores**: bimodal mixture — 30% sub-prime cluster N(580, 50),
  70% prime cluster N(740, 45), clipped [300, 850]. (US Experian / FRB
  Survey of Consumer Finances 2024 distribution.)
- **DTI ratios**: mean 28%, std 12%, clip [0%, 80%]. CFPB ATR/QM 43% DTI
  ceiling for QM; >43% triggers manual review.
- **Income**: log-normal, geography-adjusted, with a long tail.

## Voice / document samples (for KYC, FNOL)

- **ID document images**: use the templates from the Microsoft Document
  Intelligence sample gallery (passport, driver's license). Replace name,
  DOB, photo with synthetic. **Never** reuse a real ID image, even partially.
- **Selfie / biometric photos**: AI-generated faces (this-person-does-not-exist
  pattern) — never real photos.
- **Voice samples** (FNOL): TTS-generated from synthetic scripts. If using
  voice acting, get explicit talent release. Never real claim recordings.

## Document corpora (for Foundry IQ Knowledge Bases)

- **Policies / regulations**: prefer **publicly published** primary sources
  (Federal Register, EUR-Lex, FCA Handbook, FFIEC BSA/AML manual, OCC
  Bulletins, BIS / BCBS papers, FATF Recommendations). Always safe to ship.
  Do NOT use a customer's internal policy doc even if shared in workshop.
- **Brand guidelines / product docs**: synthesize a fictional bank's
  policy (e.g. `Cardinal Federal Bank KYC Manual v3.2'') with realistic
  structure. Citation pattern is what matters; content is plausible fiction.

## FSI-native KPIs (for SPEC § 9 + foundry-evals)

When designing KPIs for an FSI process, prefer these over generic
`auto_decline_rate'' style metrics. SMEs will recognize them:

| Process | KPI | Plausible target |
|---------|-----|-------------------|
| AML monitoring | **Alert-to-case conversion rate** | 3–8% (rest are L1 false positives) |
| AML monitoring | **L1 false-positive rate** | 92–97% baseline; agent should reduce by 15–30% |
| AML monitoring | **SAR filing cycle time** | Median <15 days from initial detection (regulator window 30) |
| AML monitoring | **Lookback coverage rate** | 100% of in-scope accounts within regulator-imposed window |
| KYC | **EDD case throughput** (cases/analyst/day) | 2–6 for complex corporate, 8–15 for retail high-risk |
| KYC | **First-touch resolution** | 60–75% |
| Sanctions | **Same-day disposition rate** | >85% |
| Sanctions | **Hit-rate by list** (volume per list as denominator) | OFAC <1%, EU <0.5%, internal PEP 2–5% |
| Fraud | **Detection-rate at fixed FP budget** (e.g. recall@5% FPR) | 60–85% depending on segment |
| Fraud | **False-decline rate** (good txns blocked) | <0.5% |
| Credit | **Auto-decision rate** | 70–85% for retail; 30–50% for SMB |
| Credit | **Override rate** (manual reverses model) | <8% baseline |

## Golden cases for the FSI experience walkthrough

| Case ID | Persona | Story beat |
|---------|---------|------------|
| kyc-cardinal-aerospace-holdings | Premium corporate onboarding, 4-layer UBO chain crossing 3 jurisdictions | Hero approval flow with citations |
| kyc-pyongyang-trade-shell-hk | DPRK-shell-pattern hit (modeled per § Sanctions) | Hard-stop sanctions block with regulator-grade audit trail |
| kyc-quietstream-consulting-llc | Adverse-media match (PEP false positive — same name as a recently-published Bloomberg article subject) | HITL escalation with rationale capture |
| kyc-meridian-import-export | Structuring pattern in funding source (10× \,800 deposits in 8 days) | Detect-and-flag with SAR-ready package |
| kyc-evergreen-hospitality-group | Clean baseline — happy-path approval, low-risk SMB | Comparison anchor / SLA baseline |

> Naming follows two-token-shift rule (no `Acme'').

## Reset semantics

- idempotent — reset wipes Cosmos containers and re-seeds from JSON
  files. Reset must complete in <30s for live demo recovery.
- See `threadlight-demo-data-factory` for the exact reset script pattern
  (upsert-then-delete, partition-key from container metadata, capped
  concurrency).

---

## Card disputes & chargebacks (Reg E / Reg Z)

> **Anchor pattern.** This subsection is anchored against reusable
> dispute and chargeback realism rules. Every rule below should have a
> corresponding seed record in your process repo's `specs/sample-data/`.
> When a value drifts, bring the seed and canon back into sync together.

### Card identifiers (PCI-DSS v4.0 — strict)

PCI-DSS v4.0 § 3.4 mandates: cardholder PAN must be masked anywhere it
is rendered. Last 4 digits are the **only** segment that may appear in
demo data. Anything else (BIN-only, first-6-last-4 form, or
clear-text "for visualization") fails an auditor's first-pass scan.

| Field | Rule + citation | Example |
|-------|-----------------|---------|
| **PAN — display** | PCI-DSS v4.0 § 3.4.1 — last 4 digits ONLY when rendered to a user. **Never** first-6-last-4 in customer-facing UI even though the standard permits it for some operational uses; in a demo it reads as careless. | `4471` (in JSON: `"card_number_masked": "4471"`) |
| **PAN — storage** | Demo data MUST never include a clear-text 16-digit PAN. If a Faker call generates one, treat it as a deny-list violation and regenerate. The canon stores ONLY the 4-digit suffix end-to-end (Cosmos → MCP → workspace). | (4-digit string only) |
| **Card network** | Enum: `VISA` · `MASTERCARD` · `AMEX` · `DISCOVER` · `DINERS`. Demo distribution: 60% VISA / 30% MC / 8% AMEX / 2% DISC matches US issuance share (Federal Reserve Payments Study 2023). | `VISA` |
| **Card type** | `DEBIT` (Reg E governs) · `CREDIT` (Reg Z governs) · `PREPAID` (Reg E with carve-outs). The reg framework MUST be derived from card type, not asked of the cardholder — that's a frequent demo bug. | `DEBIT` → `regulatory_framework: REG_E` |
| **Card BIN range (test)** | Visa BIN test ranges per Visa Acceptance Solutions sandbox: 4111 11XX (test card numbers); MC test 5454 54XX. **Do NOT generate plausible BINs** that could resolve to a real issuer (e.g. 4147 20XX is Chase Visa). | (use 4111-suffix or pure last-4 form) |
| **Authorization code** | 6-digit alphanumeric per Visa Auth Spec; pattern `AUTH-NNNNNN` for synthetic clarity. Real auth codes are issuer-assigned and may collide — synthetic prefix prevents that. | `AUTH-449218` |

### MCC (Merchant Category Code) anchors

MCC is ISO 18245-defined. SMEs check that demo merchants line up with
real MCCs for their stated industry — e.g. a "coffee shop" mocked at
MCC 5732 (Electronics) breaks credibility. Anchor your
`merchants.json` to these MCCs:

| MCC | Category | Example merchant pattern |
|-----|----------|--------------------------|
| **5411** | Grocery stores, supermarkets | regional grocery — high-volume legit |
| **5541** | Service stations | regional gas — legit, occasional skim-attack target |
| **5732** | Electronics stores | High-risk MCC for online fraud; foreign processors common |
| **5734** | Computer software stores | Digital download fraud, BIN-attack target |
| **5712** | Furniture | Delayed-fulfillment dispute pattern |
| **5251** | Hardware stores | Premium goods → CNP velocity fraud target |
| **5814** | Eating places, restaurants | Coffee/quick-serve — common BILLING_ERROR (duplicate tap) |
| **5912** | Drug stores, pharmacies | High-volume legit, low chargeback rate |
| **5999** | Misc retail (online retail catch-all) | online marketplace shape |
| **4899** | Cable / streaming services | Recurring billing, FRICTIONLESS_RECURRING dispute pattern |

> **Distribution.** A realistic merchant set for a card-dispute demo
> has ~70% legit-low-risk MCCs (5411, 5541, 5912), ~20% mid-risk
> (5712, 5814, 5999, 4899), and ~10% high-risk fraud-trigger MCCs
> (5732, 5734, 5251 with elevated risk_score). Skew further toward
> high-risk and the demo reads as fraud-by-design (no nuance);
> skew lower and the agent has nothing to detect.

### Network reason codes (the ones SMEs check first)

| Network | Reason code | Description | When to use as golden case |
|---------|-------------|-------------|----------------------------|
| **VISA** | `10.4` | Other Fraud — Card-Not-Present | Hero CNP fraud case (e.g. odd-hour foreign-IP txn). Visa Core Rules § 5.7.1 / Dispute Condition 10.4. |
| **VISA** | `10.5` | Visa Fraud Monitoring Program | Merchant-velocity-driven fraud — when the merchant's chargeback ratio crossed the VFMP threshold. |
| **VISA** | `12.5` | Incorrect Amount / Duplicate Processing | Duplicate-tap at restaurant (BILLING_ERROR), partial refund mismatch. |
| **VISA** | `13.1` | Merchandise / Services Not Received | Furniture / online-order non-delivery (MERCHANDISE_SERVICE category). |
| **MASTERCARD** | `4837` | No Cardholder Authorization | MC equivalent of Visa 10.4. CNP fraud canonical. |
| **MASTERCARD** | `4853` | Cardholder Dispute Defective Merchandise | Damaged-goods category. |
| **MASTERCARD** | `4859` | Services Not Rendered | MC equivalent of Visa 13.1. |

> Visa Core Rules + Mastercard Chargeback Guide are paid documents
> shipped to issuers under NDA. **Never** quote verbatim text in
> demo corpora — paraphrase the rule semantically and cite by
> rule number only. A reference `network_rules.json`
> should follow this pattern (rules paraphrased, rule_section cited
> explicitly).

### Reg E / Reg Z timer math (the trap that kills credibility)

This is the single area where a demo most often goes off the rails —
the timers are non-trivial and the wrong number is immediately spotted
by any compliance SME.

| Rule | Citation | Detail |
|------|----------|--------|
| **Reg E provisional credit (POS / online)** | 12 CFR 1005.11(c)(2) | Issuer must investigate and provisionally credit within **10 business days** of notice of error if investigation will exceed 10 BD. |
| **Reg E provisional credit (ATM / new account / foreign)** | 12 CFR 1005.11(c)(3) | Extended to **45 business days** when txn at electronic terminal, in foreign country, or on account <30 days old. |
| **Reg E investigation deadline (with provisional credit)** | 12 CFR 1005.11(c)(1) + (c)(2) | **45 calendar days** from notice of error to complete investigation (extends to 90 if (c)(3) conditions met). |
| **Reg E notice of error window** | 12 CFR 1005.11(b)(1)(i) | Cardholder has **60 days from the periodic statement** that first reflected the error to give notice. Past 60 days → consumer-protection liability shifts. |
| **Reg Z billing-error window** | 12 CFR 1026.13(b)(1) | Cardholder has **60 days from statement date** (NOT transaction date — common mistake) to assert a billing error. |
| **Reg Z investigation deadline** | 12 CFR 1026.13(c)(2) | Issuer must complete investigation within **2 complete billing cycles** (max 90 days) of receipt of billing-error notice. |
| **Reg Z written acknowledgment** | 12 CFR 1026.13(c)(1) | Issuer must mail written acknowledgment within **30 days** of receipt unless investigation already complete. |

### Federal Reserve holidays (canonical 11-holiday list)

The Reg E "business day" definition (12 CFR 1005.2(d)) excludes
weekends + Federal Reserve holidays. **The list below is the canonical
11-holiday set** — mirror `_FED_HOLIDAYS` in the agent and any
`src/jobs/deadline-watcher/main.py` implementation. Promote this list
to any FSI demo doing business-day arithmetic:

```
1.  New Year's Day                  Jan 1
2.  Martin Luther King Jr. Day      3rd Monday in Jan
3.  Presidents' Day                 3rd Monday in Feb
4.  Memorial Day                    Last Monday in May
5.  Juneteenth                      Jun 19  (federal since 2021)
6.  Independence Day                Jul 4
7.  Labor Day                       1st Monday in Sep
8.  Columbus Day                    2nd Monday in Oct
9.  Veterans Day                    Nov 11
10. Thanksgiving                    4th Thursday in Nov
11. Christmas Day                   Dec 25
```

> Saturdays + Sundays are also non-business-days under Reg E.
> "Observed" rule: when the holiday falls on Saturday → Friday is the
> federal observed day; on Sunday → Monday is the observed day.
> **Both the holiday calendar date AND the observed date are non-
> business days for Reg E purposes** — when in doubt, exclude both.

### Card-not-present (CNP) fraud signals

For golden fraud cases, these signals are what an SME expects to see
on the dispute case file. Golden cases should exhibit several of
these signals together (for example: 3:42 AM time + foreign IP +
non-browser UA + high-risk MCC + foreign-incorporated merchant):

| Signal | Where it lives in the data | Example value |
|--------|----------------------------|---------------|
| Anomalous transaction time | `transaction_date` (look at hour-of-day) | `2026-05-04T03:42:00Z` (3:42 AM cardholder local) |
| IP geo mismatch | `device_fingerprint` includes IP | `DFP-IP-103.45.12.88-...` (APAC IP on US account) |
| Non-browser user-agent | `device_fingerprint` includes UA | `...UA-curl` or `...UA-python-requests` |
| Merchant in high-risk jurisdiction | `merchant.country` + `risk_flags` | `country: PH`, `risk_flags: [FOREIGN_PROCESSOR]` |
| High-risk MCC + new merchant | `merchant.mcc` + `incorporation_year` | MCC 5732 + `incorporation_year: 2024` |
| Velocity (duplicate twin charges) | Two txns same merchant ±5 min, same amount | `TXN-DC005-A` $3250 at 20:15 + `TXN-DC005-B` $3250 at 20:18 |
| Out-of-pattern amount | Amount ≥ p99 of cardholder's 90-day history | $1247.83 vs context $34–$87 |

### Identifier formats

| Entity | Pattern | Example | Notes |
|--------|---------|---------|-------|
| Account | `ACCT-{NNNN}` (4-digit zero-padded) | `ACCT-0042` | 4-digit cap is fine for demos; real account #s vary by bank |
| Customer | `CFB-CUST-{NNNNN}` (5-digit per § Names two-token bank shift) | `CFB-CUST-00042` | "CFB" = Cardinal Federal Bank synthetic |
| Dispute case | `CASE-{NNN}` | `CASE-001` | Display-friendly; keep consistent across data and UI |
| Reg E claim | `RE-{YYYY}{WW}-{NNN}` | `RE-202619-001` | YYYY+ISO-week+seq; matches FFIEC reporting cadence |
| Transaction (disputed) | `TXN-DC{NNN}-{LETTER}` | `TXN-DC001-A` | Letter suffix when one dispute spans multiple txns |
| Transaction (context) | `TXN-CTX-{ACCT}-{NNN}` | `TXN-CTX-0042-001` | Surrounding history for the disputed account |
| Merchant | `MER-{NAME-TOKEN}-{NNN}` | `MER-EXOTECH-001` | Name token shortens long names; collision-avoidance via NNN |
| Authorization code | `AUTH-{NNNNNN}` (6-digit) | `AUTH-449218` | Per Visa Auth Spec |

### Dispute amount distributions (canonical examples)

| Category | Distribution | p50 / p99 | Example |
|----------|--------------|-----------|---------------|
| FRAUD (CNP / debit) | log-normal, peak ~$200, fat tail | $250 / $5,000 | `CASE-001`: $1,247.83 |
| FRAUD (CNP / luxury duplicate) | bimodal — single-txn ~$200 OR twin-charge ~$3,000+ | $3,000+ for twins | `CASE-005`: 2 × $3,250 |
| FRAUD (small-test then escalate) | low-amount probe ($10–$100), then high-amount cleanout | $50 probe + $1,500+ | `CASE-007`: $55.40 probe |
| BILLING_ERROR (duplicate tap) | low-amount ×2 same minute | $20–$80 each | `CASE-002`: 2 × $23.50 |
| MERCHANDISE_SERVICE (non-delivery) | catalog-shape mid-amount | $200–$800 | `CASE-003`: $419.99 |
| FRICTIONLESS_RECURRING (subscription rage) | 1× recurring × 6–12 cycles | $20–$50/mo | `CASE-006`: $218.00 (12-cycle aggregate) |

### Traps (what NOT to do — even if legacy internal seeds did it)

> **Honesty note.** Some internal demo seeds mix synthetic high-risk
> merchants with **real-world merchant names** as legit-low-risk anchors.
> That may work for internal validation, but for any customer-facing demo
> it crosses two lines: trademark (using a real chain's name in a demo
> without consent) AND customer confusion ("wait, do you have that
> integration?"). The canon REJECTS this pattern. Use these synthetic
> anchors instead:

| Don't (legacy internal seed) | Do (canon) |
|------------------------|------------|
| `Amazon Marketplace` | `Northstar Online Marketplace` |
| `Whole Foods Market` | `Greenway Organic Markets` |
| `Shell Gas Station` | `Coastal Petroleum Stop` |
| `CVS Pharmacy` | `MedPoint Pharmacy` |
| `Netflix Subscription` | `Streamfront Subscription` |

Other never-do traps for card disputes:
- **Real CFPB enforcement-action case numbers** — they're public; if
  an SME recognizes one, the entire seed loses credibility. Use
  fictional `RE-{YYYY}{WW}-{NNN}` per identifier table.
- **Real Visa/MC arbitration case numbers** — same risk; arbitration
  records are confidential under network rules. Don't seed any.
- **Real OFAC SDN list entries as positive matches** — the SDN list
  is publicly searchable; using a real entry as a "positive hit" both
  embarrasses the demo (SME spots it instantly) and is an unforced
  ethical issue (real OFAC entries are real people). Use the
  fictional shell-company patterns from § Sanctions / watchlist above.
- **Real victim names from public CFPB / OCC dispute filings** —
  don't lift a victim narrative from a real complaint. Synthesize.

### Anchor-pattern worked example

A reference implementation should exercise the canon as follows. Use
these as copy-paste patterns when seeding an FSI dispute / fraud demo:

| Canon section | Reference artifact (file · key field) | Worked value |
|---------------|------------------------------------|--------------|
| PAN masking | `disputes.json` · `card_number_masked` | `"4471"` (last-4 only, string) |
| Network reason code | `disputes.json` · `reason_code` | `"10.4"` (Visa CNP fraud) |
| Reg E framework binding | `disputes.json` · `regulatory_framework` derived from `card_type=DEBIT` | `"REG_E"` |
| Reg E timer math | `src/mcp/server.py` · `compute_regulatory_timers` tool | 10 BD provisional credit; 45 BD investigation |
| Fed holiday list | `src/agent/container.py` · `_FED_HOLIDAYS` constant | 11-holiday canonical list (above) |
| Network rule citation | `network_rules.json` · `entries[].rule_section` | `"Visa Core Rules § 5.7.1 / Dispute Condition 10.4"` (rule # cited; text paraphrased) |
| MCC anchors | `merchants.json` · `mcc` | 5732 (high-risk) · 5411 (legit) · 5814 (BILLING) — full set above |
| CNP fraud signals | `transactions.json` · `device_fingerprint` + `transaction_date` hour | `"DFP-IP-103.45.12.88-UA-curl"` at 3:42 AM |
| Twin-charge velocity | `transactions.json` · `TXN-DC005-A` + `TXN-DC005-B` | 2 × $3,250 at 20:15 + 20:18 |
| Cardholder name (synthetic) | `disputes.json` · `cardholder_name` + `cardholder_address` | `"<example-cardholder>"` / `"<example-address>"` |
| Real merchant names (legacy / DO NOT use) | `merchants.json` · `MER-AMZN-001`, `MER-NETFLIX-018`, etc. | Mark for replacement at v4 — see Traps section above |