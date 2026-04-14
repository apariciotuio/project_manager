---
description: Tuio insurance domain knowledge — terminology, regulations, edge cases
applyTo: "**/domain/**/*.py,**/insurance/**/*.py,**/policies/**/*.py,**/claims/**/*.py,**/quotes/**/*.py,**/underwriting/**/*.py,**/domain/**/*.ts,**/insurance/**/*.ts,**/policies/**/*.ts,**/claims/**/*.ts,**/quotes/**/*.ts,**/underwriting/**/*.ts,**/services/**/*.py,**/services/**/*.ts"
---

# Insurance Domain — Tuio

Digital-first insurtech. Products: Home, Life, Auto. Up to 40% savings, 100% digital. Website: https://www.tuio.com

## Core Terminology

| Spanish | English | Definition |
|---------|---------|------------|
| Póliza | Policy | Insurance contract |
| Prima | Premium | Amount paid for coverage |
| Siniestro | Claim/Loss | Event triggering coverage |
| Franquicia | Deductible | Amount insured pays first |
| Tomador | Policyholder | Person who pays |
| Asegurado | Insured | Person/property covered |
| Cotización | Quote | Price estimate |
| Contratación | Underwriting | Purchase process |
| Renovación | Renewal | Continuation at term end |
| Anulación | Cancellation | Policy termination |
| Perito | Claims adjuster | Damage assessor |
| Indemnización | Settlement | Claim payment |
| Capital asegurado | Sum insured | Maximum payable |
| Carencia | Waiting period | Time before coverage activates |
| Subrogación | Subrogation | Insurer's recovery right |

## Regulations

- **DGSFP** (Spanish regulator), **Solvencia II** (EU capital requirements), **IDD** (distribution directive)
- **GDPR/RGPD + LOPD-GDD**: consent, data minimization, right to erasure. Health data = explicit consent
- **14-day cooling-off** for online contracts. IPID mandatory. Plain language required
- **KYC/AML**: identity verification, suspicious activity reporting

## Edge Cases (Always Consider)

**Policy**: mid-term cancellation (pro-rata), payment failure at renewal (grace period), address/vehicle change (re-underwriting), insured item no longer exists

**Claims**: exceeds sum insured (cap), during waiting period (reject), multiple in short period (fraud flags), incomplete docs (deadlines), third party involved (subrogation)

**Pricing/Underwriting**: risk profile change (mid-term adjustment), prior claims (loading), incorrect information (void/proportional settlement)

**Technical**: expired quote (re-quote), payment processor down (fallback/retry), doc generation failure (async retry)
