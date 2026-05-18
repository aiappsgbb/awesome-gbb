# Domain Primer: Financial Services — KYC / AML

> Use this primer when the user mentions: KYC, AML, customer onboarding (banking/FSI),
> due diligence, sanctions screening, PEP, SAR, compliance onboarding, anti-money laundering,
> know your customer, customer identification program (CIP).

## Regulatory Landscape

| Regulation | Jurisdiction | Key Requirements |
|------------|-------------|------------------|
| **Bank Secrecy Act (BSA)** | US | Customer Identification Program (CIP), SAR filing, CTR reporting |
| **USA PATRIOT Act** | US | Enhanced due diligence for higher-risk customers, Section 314 information sharing |
| **EU Anti-Money Laundering Directives (AMLD 4/5/6)** | EU | Risk-based approach, beneficial ownership registers, PEP screening |
| **FATF Recommendations** | Global | 40 Recommendations on AML/CFT, risk-based approach, customer due diligence |
| **FinCEN regulations** | US | SAR/CTR filing thresholds, recordkeeping requirements |
| **GDPR** | EU | Data minimization for KYC data, right to erasure vs retention obligations |
| **MiFID II / PSD2** | EU | Client categorization, payment service provider due diligence |

**Key tension:** AML retention requirements (5-7 years) vs GDPR data minimization — the spec must address this.

## Typical Business Rules

These are **suggestions** — confirm with the user and adapt to their specific institution.

| Rule | Condition | Action | Notes |
|------|-----------|--------|-------|
| **CDD Tier Assignment** | All new customers | Assign risk tier: Simplified (SDD), Standard (CDD), Enhanced (EDD) based on risk factors | Risk factors: geography, product type, transaction patterns, PEP status |
| **PEP Screening** | All customers | Screen against PEP lists (domestic + foreign) | Must include family members and close associates |
| **Sanctions Screening** | All customers + all transactions | Screen against OFAC SDN, EU sanctions, UN sanctions | Real-time for transactions, periodic refresh for customers |
| **Beneficial Ownership** | Entity customers (non-individual) | Identify all beneficial owners with ≥25% ownership | Threshold varies by jurisdiction (10% in some EU states) |
| **EDD Trigger** | High-risk country, PEP, complex ownership, unusual activity | Escalate to Enhanced Due Diligence | Requires senior approval, additional documentation |
| **Periodic Review** | All active customers | Re-verify KYC at intervals: High=1yr, Medium=3yr, Low=5yr | Triggered also by material change events |
| **SAR Filing** | Suspicious activity detected | File Suspicious Activity Report within 30 days | Cannot notify the customer (tipping off prohibition) |
| **CTR Filing** | Cash transaction ≥ $10,000 | File Currency Transaction Report | Structuring detection for split transactions |
| **Document Expiry** | ID document expiration date passed | Flag for re-verification, block high-risk transactions | Grace period varies by risk tier |

## Common Data Models

### Customer
| Field | Type | Notes |
|-------|------|-------|
| customer_id | string | Unique identifier |
| customer_type | enum: individual / entity | Drives different verification flows |
| legal_name | string | Full legal name or registered entity name |
| date_of_birth | date | Individuals only |
| nationality | string | ISO country code |
| country_of_residence | string | ISO country code |
| tax_id | string | SSN, TIN, or equivalent |
| risk_tier | enum: low / medium / high | Assigned by CDD process |
| pep_status | enum: none / domestic_pep / foreign_pep / associate | From PEP screening |
| onboarding_date | datetime | When KYC was first completed |
| last_review_date | datetime | Last periodic review |
| next_review_due | date | Based on risk tier interval |
| status | enum: pending / active / blocked / closed | Account status |

### RiskAssessment
| Field | Type | Notes |
|-------|------|-------|
| assessment_id | string | Unique identifier |
| customer_id | string | FK to Customer |
| assessment_date | datetime | When performed |
| risk_score | float | 0-100 composite score |
| risk_tier | enum: low / medium / high | Derived from score + rules |
| risk_factors | list[string] | Contributing factors |
| assessor | enum: automated / analyst_name | Who performed it |
| edd_required | bool | Whether Enhanced DD is needed |
| approval_status | enum: pending / approved / rejected | For EDD cases |

### SanctionsScreeningResult
| Field | Type | Notes |
|-------|------|-------|
| screening_id | string | Unique identifier |
| customer_id | string | FK to Customer |
| screening_date | datetime | When performed |
| lists_checked | list[string] | e.g., ["OFAC_SDN", "EU_SANCTIONS", "UN_CONSOLIDATED"] |
| match_found | bool | Whether any potential matches |
| matches | list[object] | Potential matches with confidence scores |
| disposition | enum: cleared / true_match / pending_review | Analyst disposition |

### SuspiciousActivityReport
| Field | Type | Notes |
|-------|------|-------|
| sar_id | string | Unique identifier |
| customer_id | string | FK to Customer |
| activity_description | string | Narrative of suspicious activity |
| amount_involved | float | Total amount if applicable |
| filing_date | date | When SAR was filed |
| status | enum: draft / filed / acknowledged | Filing status |

## Common System Integrations

| System | Direction | Purpose | Typical Provider |
|--------|-----------|---------|-----------------|
| **Sanctions list provider** | Read | OFAC SDN, EU, UN screening | Dow Jones, Refinitiv World-Check, ComplyAdvantage |
| **PEP database** | Read | Politically exposed persons screening | Same providers as sanctions |
| **Credit bureau** | Read | Identity verification, credit history | Experian, Equifax, TransUnion |
| **ID verification service** | Read | Document verification, biometric matching | Jumio, Onfido, Veriff |
| **Core banking system** | Read-Write | Customer master, account status | SAP, Temenos, FIS, Finastra |
| **Transaction monitoring** | Read | Suspicious transaction detection | Actimize, Norkom, Mantas |
| **Case management** | Read-Write | Investigation workflow, audit trail | Pega, Appian, ServiceNow |
| **Regulatory filing system** | Write | SAR/CTR electronic filing | FinCEN BSA E-Filing |
| **Document management** | Read-Write | KYC document storage, retrieval | SharePoint, OpenText, Box |

> Most of these will be **mock** in development. Define data models + sample data first,
> replace with real integrations when available.

## Typical Process Patterns

### New Customer Onboarding (CDD Flow)
```
Application intake → Identity verification → PEP screening → Sanctions screening
    → Risk scoring → Tier assignment → [If EDD needed → Enhanced review → Approval]
    → Account activation → Schedule periodic review
```

### Periodic Review
```
Review trigger (timer or event) → Refresh customer data → Re-screen sanctions/PEP
    → Recalculate risk → [If risk increased → Trigger EDD]
    → Update review date → Schedule next review
```

### Suspicious Activity Investigation
```
Alert received → Gather transaction history → Analyze patterns
    → [If suspicious → Draft SAR → Compliance review → File SAR]
    → [If cleared → Document rationale → Close alert]
```

## Domain Vocabulary

| Term | Meaning |
|------|---------|
| **CDD** | Customer Due Diligence — standard identity verification and risk assessment |
| **EDD** | Enhanced Due Diligence — deeper investigation for higher-risk customers |
| **SDD** | Simplified Due Diligence — lighter checks for lowest-risk customers |
| **PEP** | Politically Exposed Person — government officials, their family, close associates |
| **SAR** | Suspicious Activity Report — mandatory filing when suspicious activity detected |
| **CTR** | Currency Transaction Report — mandatory filing for cash transactions ≥$10K |
| **CIP** | Customer Identification Program — minimum identity verification requirements |
| **Beneficial Owner** | Individual who ultimately owns or controls ≥25% of an entity |
| **OFAC SDN** | Office of Foreign Assets Control Specially Designated Nationals list |
| **Tipping off** | Prohibited act of informing a customer about a SAR filing |
| **Structuring** | Splitting transactions to avoid reporting thresholds (illegal) |
| **RBA** | Risk-Based Approach — calibrating controls to the level of risk |
