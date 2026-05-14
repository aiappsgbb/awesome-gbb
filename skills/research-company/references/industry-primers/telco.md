# Industry Primer — Telco

> **Canon — see [AGENTS.md § 2.2](../../../../AGENTS.md#22--reference-data-files-are-canon--do-not-normalize).**
> Do not normalize the published shorthand documented here.

A starting-point cheat sheet for the `research-company` skill when
the target is a telecommunications operator (fixed-line, mobile,
wholesale, carrier, or data-centre / connectivity provider).

## Sub-segments

| Sub-segment | Examples | Notes |
|---|---|---|
| **Tier-1 incumbent** | (national-flag telcos, ex-monopolies) | Retail + wholesale + mobile + enterprise. Heavy regulator load. |
| **Mobile-led MNO** | (spectrum-licensed mobile-network operators) | Spectrum-heavy; tower/rAN angle prominent. |
| **B2B / wholesale** | (carrier-neutral fibre + colo + IP transit specialists) | Fibre + colo + IP transit. Less retail; capital-markets-grade SLAs. |
| **Cable / hybrid** | (coax + fibre + content operators) | Coax + fibre + content. |
| **Tower-co / infraco** | (passive-infrastructure landlord-model operators) | Passive infrastructure only; landlord model. |
| **MVNO / virtual** | (capacity-buying virtual operators) | Buys capacity wholesale, owns brand + BSS. |

Choose sub-segment first; it drives the entire org-chart shape.

## Canonical vertical entity kinds

Reference set for `vertical_entity_kinds[]`. Adapt to the target.

| Kind | Swaps for | Meaning |
|---|---|---|
| `Service` | `Brand` | Product SKU on the network (e.g. "Wave 100G", "IQ Ethernet 10G", "5G-FWA-50/10"). |
| `Circuit` | `Campaign` | Provisioned instance of a Service for one customer with two endpoints. |
| `Quote` | `Pitch` | Pre-sale priced bundle. |
| `CapacityPlan` | `MediaPlan` | Annual/quarterly capacity rollout. |
| `Site` | (new) | On-net building, MDU, customer premise. |
| `PointOfPresence` | (new) | PoP / DC / carrier-neutral location. |
| `Customer` | (new) | Enterprise account or wholesale partner. Subsumes Subsidiary's customer role. |
| `Incident` | (new) | Network incident (alarm-driven or customer-reported). |
| `Ticket` | (new) | A piece of work (incident, change, service request). |
| `NetworkElement` | (new) | A piece of equipment (router, OLT, BNG, transponder, cell site). |
| `IPPrefix` | (new) | An IPv4 or IPv6 prefix the operator advertises (RIR-allocated). |
| `BGPPeering` | (new) | A peering relationship with another ASN. |
| `CrossConnect` | (new) | A physical cable between two devices, often in a DC. |
| `Licence` | (new) | A telecom operating licence per regulator. |
| `Spectrum` | (new) | A spectrum allocation (band + MHz). Mobile-MNO only. |

## Canonical functions

| Function id | display_name | importance heuristic |
|---|---|---|
| `network-ops` | Network Operations | **hero** for any operator |
| `customer-success` | Customer Success | **hero** for B2B-led operators |
| `wholesale-sales` | Wholesale & Carrier Sales | core (often split from enterprise sales) |
| `enterprise-sales` | Enterprise Sales | core |
| `consumer-sales` | Consumer Sales | core (Tier-1 incumbents) — skip for B2B-only |
| `product` | Product | core |
| `tech` | Technology & Information (internal IT) | core |
| `security` | Cyber & Information Security | core (always, post-2024 norms) |
| `finance` | Finance | core |
| `hr` | People | core |
| `legal-and-regulatory` | Legal & Regulatory | core (regulatory load is heavier than other verticals) |
| `strategy` | Strategy & Transformation | support |
| `field-ops` | Field Operations | core (only if the operator owns field engineers; pure-wholesale plays don't) |

≤ 3 hero per brief.

## Canonical regulators (Europe + ANZ + Asia + Americas)

| id | name | country | domain |
|---|---|---|---|
| `ofcom` | Office of Communications | GB | telecom |
| `bnetza` | Bundesnetzagentur | DE | telecom |
| `arcep` | Autorité de régulation des communications électroniques, des postes et de la distribution de la presse | FR | telecom |
| `agcom` | Autorità per le garanzie nelle comunicazioni | IT | telecom |
| `cnmc` | Comisión Nacional de los Mercados y la Competencia | ES | telecom |
| `comreg` | Commission for Communications Regulation | IE | telecom |
| `acm-nl` | Autoriteit Consument & Markt | NL | telecom |
| `bipt` | Belgian Institute for Postal Services and Telecommunications | BE | telecom |
| `nkom` | Nasjonal kommunikasjonsmyndighet | NO | telecom |
| `pts` | Post- och telestyrelsen | SE | telecom |
| `traficom` | Liikenne- ja viestintävirasto | FI | telecom |
| `ttg` | Tilastokeskus (statistical telecom regulator) | FI | telecom |
| `urec` | Urząd Komunikacji Elektronicznej | PL | telecom |
| `anacom` | Autoridade Nacional de Comunicações | PT | telecom |
| `eett` | Εθνική Επιτροπή Τηλεπικοινωνιών και Ταχυδρομείων | GR | telecom |
| `rtr` | Rundfunk und Telekom Regulierungs-GmbH | AT | telecom |
| `bakom` | Bundesamt für Kommunikation | CH | telecom |
| `fcc` | Federal Communications Commission | US | telecom |
| `crtc` | Canadian Radio-television and Telecommunications Commission | CA | telecom |
| `mic-jp` | Ministry of Internal Affairs and Communications | JP | telecom |
| `imda` | Infocomm Media Development Authority | SG | telecom |
| `kcc` | Korea Communications Commission | KR | telecom |
| `acma` | Australian Communications and Media Authority | AU | telecom |
| `trai` | Telecom Regulatory Authority of India | IN | telecom |
| `anatel` | Agência Nacional de Telecomunicações | BR | telecom |
| `ift` | Instituto Federal de Telecomunicaciones | MX | telecom |

Horizontal regulators always applicable:

| id | name | country | domain |
|---|---|---|---|
| `ico` | Information Commissioner's Office | GB | data-protection |
| `cnil` | Commission nationale de l'informatique et des libertés | FR | data-protection |
| `bfdi` | Bundesbeauftragte für den Datenschutz und die Informationsfreiheit | DE | data-protection |

## Proposed-domains starter library

Pick 25–35 from this list (or extend) for `proposed_domains[]`.
**≤ 3 hero**; tag each with a realistic `cadence`.

### Customer / commercial (enterprise + wholesale)

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `quote-to-circuit` | Quote to Circuit | customer-success | ad-hoc | hero |
| `customer-onboarding-enterprise` | Enterprise Customer Onboarding | customer-success | ad-hoc | supporting |
| `customer-offboarding-decommission` | Customer Offboarding | customer-success | ad-hoc | supporting |
| `mrr-uplift-cross-sell` | MRR Uplift / Cross-sell | customer-success | monthly | supporting |
| `service-credit-claim` | Service Credit Claim | customer-success | ad-hoc | supporting |
| `sla-breach-rfo` | SLA-Breach RFO | customer-success | ad-hoc | supporting |
| `contract-renewal-circuit` | Circuit Contract Renewal | customer-success | quarterly | supporting |
| `wholesale-partner-onboarding` | Wholesale Partner Onboarding | wholesale-sales | ad-hoc | supporting |
| `interconnect-bgp-peering` | Interconnect & BGP Peering | wholesale-sales | ad-hoc | supporting |
| `carrier-dispute-credits` | Carrier Disputes & Credits | wholesale-sales | monthly | supporting |
| `mvno-enablement` | MVNO Enablement | wholesale-sales | ad-hoc | supporting |
| `hyperscaler-cloud-onramp` | Hyperscaler Cloud-Onramp Build | wholesale-sales | ad-hoc | supporting |

### Network operations

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `incident-to-restore` | Incident to Restore | network-ops | ad-hoc | hero |
| `capacity-augment` | Capacity Augment | network-ops | weekly | supporting |
| `planned-maintenance-window` | Planned Maintenance Window | network-ops | weekly | supporting |
| `fibre-cut-recovery` | Fibre-Cut Recovery | network-ops | ad-hoc | supporting |
| `noc-shift-handover` | NOC Shift Handover | network-ops | daily | supporting |
| `spectrum-allocation-renewal` | Spectrum Allocation Renewal | network-ops | annual | supporting |
| `network-element-firmware-roll` | Network Element Firmware Roll | network-ops | quarterly | supporting |
| `dns-change-cycle` | DNS Change Cycle | network-ops | weekly | supporting |

### Field operations & data-centre

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `field-engineer-dispatch` | Field Engineer Dispatch | field-ops | ad-hoc | supporting |
| `data-centre-customer-deploy` | Data-Centre Customer Deploy | field-ops | ad-hoc | supporting |
| `power-and-cooling-augment` | Power & Cooling Augment | field-ops | quarterly | supporting |
| `cross-connect-install` | Cross-Connect Install | field-ops | ad-hoc | supporting |
| `physical-security-audit` | Physical Security Audit | field-ops | semiannual | supporting |

### Security

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `cyber-incident-response` | Cyber Incident Response | security | ad-hoc | supporting (hero if the target has had a recent public breach) |
| `threat-intel-distribution` | Threat Intel Distribution | security | daily | supporting |
| `penetration-test-cycle` | Penetration Test Cycle | security | quarterly | supporting |
| `vulnerability-patch-cycle` | Vulnerability Patch Cycle | security | weekly | supporting |
| `third-party-risk-assessment` | Third-Party Risk Assessment | security | quarterly | supporting |

### Legal & regulatory

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `regulatory-licence-renewal` | Regulatory Licence Renewal | legal-and-regulatory | annual | supporting |
| `breach-notification-cycle` | Breach Notification Cycle | legal-and-regulatory | ad-hoc | supporting |
| `lawful-intercept-request` | Lawful Intercept Request | legal-and-regulatory | ad-hoc | supporting |
| `usage-data-retention-cycle` | Usage Data Retention Cycle | legal-and-regulatory | quarterly | supporting |
| `gdpr-dsar-handling` | GDPR DSAR Handling | legal-and-regulatory | weekly | supporting |
| `regulator-quarterly-filing` | Regulator Quarterly Filing | legal-and-regulatory | quarterly | supporting |

### Finance / billing

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `invoice-dispute-resolution` | Invoice Dispute Resolution | finance | weekly | supporting |
| `credit-risk-review` | Credit Risk Review | finance | monthly | supporting |
| `monthly-revenue-close` | Monthly Revenue Close | finance | monthly | supporting |
| `bad-debt-write-off` | Bad-Debt Write-Off | finance | quarterly | supporting |

### Cross-function meta-workflows

| workflow_type | display_name | function | cadence | importance hint |
|---|---|---|---|---|
| `<acquisition>-integration-cutover` | <Acquisition> Integration Cutover | tech | ad-hoc | supporting |
| `engineer-on-call-rotation` | Engineer On-Call Rotation | hr | weekly | supporting |
| `network-cert-renewal` | Network Certification Renewal | hr | annual | supporting |
| `training-and-skills-matrix` | Training & Skills Matrix | hr | quarterly | supporting |

## Canonical stack systems

Pick 12–20 for `stack.systems[]`. Always include at least one of each
role band below.

| role | typical vendors |
|---|---|
| `crm` | Salesforce, Microsoft Dynamics 365 |
| `itsm` | ServiceNow, BMC Helix |
| `erp` | SAP S/4HANA, Oracle Fusion |
| `hcm` | Workday, SAP SuccessFactors |
| `oss-bss` | **Amdocs, Netcracker, BluePlanet (Ciena), Cerillion, Comarch, NEC Netcracker, NetCracker**, Subex, Openet |
| `network-vendor` | Cisco, Juniper, Nokia, Ericsson, Huawei (where geopolitically permissible) |
| `identity` | Microsoft Entra ID, Okta, Ping Identity |
| `esign` | DocuSign, Adobe Sign |
| `observability` | App Insights / Azure Monitor, Datadog, Splunk, Dynatrace |
| `billing` | (often inside the OSS/BSS stack — Amdocs Convergent Charging, Cerillion Billing) |
| `dwh` / `lakehouse` | Microsoft Fabric / OneLake, Snowflake, Databricks |
| `cdn` | Akamai, Cloudflare, Fastly |

## Canonical cadenced rituals

| id | display_name | cadence | owner_function |
|---|---|---|---|
| `noc-shift-handover` | NOC Shift Handover | daily | network-ops |
| `weekly-capacity-review` | Weekly Capacity Review | weekly | network-ops |
| `change-advisory-board` | Change Advisory Board | weekly | tech |
| `weekly-pipeline-scrub` | Weekly Sales Pipeline Scrub | weekly | enterprise-sales |
| `monthly-rfo-close` | Monthly RFO Close | monthly | customer-success |
| `monthly-revenue-close` | Monthly Revenue Close | monthly | finance |
| `monthly-security-review` | Monthly Security Review | monthly | security |
| `quarterly-regulator-filing` | Quarterly Regulator Filing | quarterly | legal-and-regulatory |
| `quarterly-board-pack` | Quarterly Board Pack | quarterly | finance |
| `quarterly-product-review` | Quarterly Product Roadmap Review | quarterly | product |
| `annual-licence-renewal` | Annual Licence Renewal | annual | legal-and-regulatory |
| `annual-budget-cycle` | Annual Budget Cycle | annual | finance |
| `annual-perf-cycle` | Annual Performance Cycle | annual | hr |
| `annual-pen-test` | Annual Penetration Test | annual | security |

## Canonical KPI cinematics

Pick 6–12 for `kpi_cinematics[]`. The first six are non-negotiable
for any operator demo.

| id | display_name | unit | target_trend | owner_function |
|---|---|---|---|---|
| `mttr` | Mean Time To Restore | hours | down_is_good | network-ops |
| `otp_provisioning` | On-Time Provisioning % | percent | up_is_good | customer-success |
| `capacity_utilisation` | Capacity Utilisation | percent | stable | network-ops |
| `network_availability` | Network Availability | percent | up_is_good | network-ops |
| `churn_rate` | Customer Churn | percent | down_is_good | customer-success |
| `nps` | Net Promoter Score | count | up_is_good | customer-success |
| `cost_per_bit` | Cost per Bit | currency_usd | down_is_good | network-ops |
| `arpu` | Average Revenue Per User | currency_usd | up_is_good | finance |
| `dso` | Days Sales Outstanding | days | down_is_good | finance |
| `incident_volume` | Incident Volume (open) | count | down_is_good | network-ops |
| `mean_chargeable_install_days` | Mean Chargeable Install Days | days | down_is_good | customer-success |
| `wholesale_concentration` | Wholesale Revenue Concentration (top-10) | percent | down_is_good | wholesale-sales |

## Sources of record

When researching a telco for this primer's slots:

- **Annual report / capital-markets day PDF** on the company's own
  site → ownership, size, strategic themes, leadership.
- **National registry** for subsidiaries (Companies House / SEC /
  Handelsregister / Infogreffe).
- **Wikipedia** for history, acquisitions, ASN.
- **The company's own ASN page on `bgp.tools`** or `peeringdb.com` →
  ASN, peering policy, prefix count.
- **Vendor case-study pages** for stack signal — Amdocs / Netcracker /
  Cisco / Microsoft / Salesforce all publish logo walls.
- **Trade press** — Light Reading, TelecomTV, Capacity, Total Telecom,
  Fierce Telecom, Telecom Asia → leadership commentary, transformation
  programmes, recent narrative arcs.

## See also

- `references/brief-schema.md` for the output schema.
- The five other industry primers in this directory.
