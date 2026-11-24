# CashSense in Power BI - build guide (about 15 minutes)

Power BI Desktop (free) is installed. CashSense exports the data as a star schema in
`data/phase4/powerbi/` (run `python -m cashsense.cli phase4` to refresh it). All data is SAMPLE data.

## 1. Load the tables
1. Open **Power BI Desktop** > **Blank report**.
2. **Home > Get data > Text/CSV**, pick `data/phase4/powerbi/dim_account.csv` > **Load**.
3. Repeat for: `dim_party.csv`, `dim_date.csv`, `fact_bank_line.csv`, `fact_forecast_week.csv`,
   `fact_forecast_flow.csv`, `fact_recon_item.csv`, `fact_risk.csv`.
   (Faster: **Get data > Folder**, choose the `powerbi` folder, **Combine & Transform** is NOT needed - use
   Text/CSV per file so each becomes its own table.)
4. In **Transform data**, make sure `cc_utilisation` is a Decimal number and the date columns are Date. Close & Apply.

## 2. Relationships (Model view)
| From (many) | To (one) |
|---|---|
| fact_bank_line[account_id] | dim_account[account_id] |
| fact_bank_line[party_id] | dim_party[party_id] |
| fact_bank_line[date] | dim_date[date] |
| fact_forecast_flow[party_id] | dim_party[party_id] |
| fact_forecast_flow[date] | dim_date[date] |
| fact_recon_item[account_id] | dim_account[account_id] |
| fact_risk[party_id] | dim_party[party_id] |

## 3. Measures
**Modeling > New measure**, one per line from `data/phase4/powerbi/measures.dax`
(Inflow, Outflow, Net Flow, CC Drawn, CC Limit, CC Utilisation, Peak CC Utilisation, Weeks Above 85%,
Bank Lines, Lines For Review, Open Risks, High Risks, Unreconciled Amount). Format CC Utilisation as Percentage.

## 4. Report page "Treasury" (suggested visuals)
1. **Slicer**: fact_forecast_week[scenario_label] (single select, default "Base case").
2. **Line chart**: X = fact_forecast_week[week], Y = CC Utilisation; add a constant line at 0.85
   (Analytics pane > Constant line) labelled "85% alert" and one at 1.0 "CC limit".
3. **Clustered column chart**: X = week, Y = Inflow and Outflow.
4. **Cards**: Peak CC Utilisation, Weeks Above 85%, Open Risks, High Risks.
5. **Table**: fact_risk (type, severity, status, amount, explanation).
6. **Donut**: fact_bank_line amount_inr by category (filter month = Mar 2026, amount_inr < 0) - where the money went.

## 5. Phone layout and mobile app
1. **View > Mobile layout**, drag the cards, the slicer and the line chart onto the phone canvas.
2. **Save** as `CashSense.pbix` in `cashsense/powerbi/`.
3. To view on the phone: **Home > Publish** to *My workspace* (needs a Power BI sign-in with a work or school
   account), then open the **Power BI mobile app** with the same account. Note: sharing reports with other people
   needs a Pro / Premium-per-user licence; viewing your own report in My workspace is expected to work on the free
   licence - confirm with your tenant's settings.

## Refreshing
Re-run `python -m cashsense.cli phase4`, then **Home > Refresh** in Power BI Desktop.
