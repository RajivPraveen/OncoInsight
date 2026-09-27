# CMS Reference Price Sources

Seed file: `dbt/oncoinsight/seeds/ref_cms_reference_prices.csv` (35 rows)  
Retrieved: 2026-09-25. Every value was parsed programmatically from the files below. None were typed in by hand or estimated.

## 1. Medicare Physician Fee Schedule (PFS): surgery_professional, radiation, chemo_admin

- **File:** RVU26D, the CY2026 PFS Relative Value File, October 2026 release (released 08/26/2026). Table used: `PPRRVU2026_Oct_nonQPP.csv`
- **URL:** https://www.cms.gov/files/zip/rvu26d-updated-08-26-2026.zip
  (landing page: https://www.cms.gov/medicare/payment/fee-schedules/physician/pfs-relative-value-files/rvu26d)
- **Conversion factor:** **33.4009** (the non-qualifying-APM-participant CF, from the `CONV FACTOR` column of the nonQPP file). For CY2026 CMS publishes two CFs. The QP (qualifying APM participant) CF is 33.5675, from `PPRRVU2026_Oct_QPP.csv`. The table uses the non-QP CF because it applies to most clinicians.
- **How values were computed:** national payment = total RVU x CF, rounded to cents. GPCIs are all 1.0 (national).
  - Surgery (19301, 19303, 19307, 38525, 38900): **FACILITY TOTAL** RVU. This is the surgeon's fee when the operation is done in a hospital or ASC. 19301, 19303, 19307 and 38525 have a 090-day global period. 38900 is a ZZZ add-on code.
  - Radiation (77412, 77301, 77263, 77427) and chemo administration (96413, 96415, 96409): **NON-FACILITY TOTAL** RVU. This is the freestanding center / physician office global payment.
  - The table does not apply multiple-procedure, bilateral, assistant-surgeon or sequestration adjustments. The payment amount is the full Medicare allowed amount, which includes beneficiary coinsurance.
  - The exact RVU used for each row is recorded in the `price_basis` column.

## 2. ASP Drug Pricing File: drug_infusion, plus J8522 (drug_oral)

- **File:** October 2026 Medicare Part B Payment Limit File, version 091626 (section 508 CSV). Effective 2026-10-01 to 2026-12-31. Based on 2Q26 ASP data.
- **URL:** https://www.cms.gov/files/zip/october-2026-medicare-part-b-payment-limit-files-final.zip
  (landing page: https://www.cms.gov/medicare/payment/part-b-drugs/asp-pricing-files)
- **Value used:** the "Payment Limit" column (ASP + 6%) per HCPCS billing unit. The billing unit is taken from the "HCPCS Code Dosage" column. Values are kept to the file's 3 decimal places.

## 3. NADAC: drug_oral (pharmacy)

- **Dataset:** NADAC (National Average Drug Acquisition Cost) 2026, data.medicaid.gov dataset `fbb83258-11c7-47f5-8b18-5f8e79f7e704`, as_of_date **2026-09-23**
- **URL:** https://download.medicaid.gov/data/nadac-national-average-drug-acquisition-cost-09-23-2026.csv
  (queried through https://data.medicaid.gov/api/1/datastore/query/fbb83258-11c7-47f5-8b18-5f8e79f7e704/0)
- **How values were computed:** filtered on as_of_date = 2026-09-23 and an exact `ndc_description` match: TAMOXIFEN 20 MG TABLET, ANASTROZOLE 1 MG TABLET, LETROZOLE 2.5 MG TABLET, EXEMESTANE 25 MG TABLET, CAPECITABINE 500 MG TABLET. Within each product, every NDC had the same NADAC (pricing_unit = EA, generic classification), so that single per-tablet value is used.
- NADAC is a pharmacy acquisition-cost benchmark (Medicaid). It is not a Medicare payment amount.

## Substitutions (successor codes used)

| Standard code | Code used | Reason |
|---|---|---|
| J9070 cyclophosphamide | **J9075** (Inj, cyclophosphamide, NOS, 5 mg) | J9070 is not in the Oct 2026 or Jul 2026 ASP files. J9071 to J9076 are the current product-specific and NOS codes. |
| J9190 fluorouracil 500 mg | **J9192** (Inj, fluorouracil, 10 mg) | The Oct 2026 file shows J9192 as "Added October 2026" and J9190 is gone. The last J9190 payment limit was $2.024 per 500 mg (July 2026 file). That value is not in the seed. |
| J9250 methotrexate | **J9260** (methotrexate sodium, 50 mg) | J9250 is absent from the ASP file. |
| Capecitabine J8520/J8521 | **J8522** (capecitabine, oral, 50 mg) | This is the only capecitabine code in the ASP file. Its limit is also recorded, along with the NADAC for the 500 mg tablet. |
| 77385/77386 IMRT delivery | **77412** (radiation tx delivery level 3) | 77385 and 77386 (and the G6015 IMRT G-code) are not in the CY2026 RVU26D file. |

## Gaps (codes not found, left out of the CSV)

1. **All OPPS facility rows (`surgery_facility`: 19301, 19303, 19307, 38525/38900 APC payment rates).** The OPPS Addendum B download (latest is July 2026, updated 2026-07-21: `https://www.cms.gov/apps/ama/license.asp?file=/files/zip/july-2026-opps-addendum-b.zip`) is behind an AMA CPT license click-through ("Accept" / "Don't Accept"). No October 2026 Addendum B is posted yet. Hospital facility fees are therefore excluded from the cost model. To add them, accept the AMA license at that URL, download the zip, and parse the APC payment rates for these CPT codes into the seed with the same columns.
2. **J9202 goserelin (Zoladex).** It is not in the payment limit file. It is listed in the October 2026 "Drugs Not Payable Under Part B" file because the manufacturer (TerSera) has no Medicaid National Drug Rebate Agreement, so there is no Part B payment amount.
