# Raw Material Purchase & Production Planner

Capstone project, AICA Level 2. A Streamlit application that turns a monthly sales plan (Excel) into a
raw-material purchase plan and a week-wise production plan.

It is a Python port of the offline dashboard `Purchase_Plan_Dashboard.html`, with one addition: on the
Production tab you enter the **monthly available days for each line**, and the weekly production plan is
rebuilt from those days.

## What it does

| Tab | Contents |
|---|---|
| Sales Plan | KPI cards, brand summary, sales plan by brand and pack size, possible production from opening stock, production required, blend requirement |
| Purchase Plan | Raw-material requirement, opening stock, required closing stock and **To Purchase**, with search and filters and CSV export |
| Production Plan | Available days per line (input), Week 1 to 4 plan by line and SKU, line-wise and brand-wise capacity analysis, production shortfall with reasons |

### Planning logic

1. Production Required = Sales + Closing FG - Opening FG.
2. The FG BOM (per 1,000 cases) is exploded into packing materials and blend demand.
3. Blend demand is netted against opening blend stock, then the Blend BOM (per 1,000 BL) is exploded into spirits and flavours.
4. To Purchase = Gross Requirement + Required Closing Stock - Opening Stock.
5. Production scheduling covers 4 weeks. Days per week for a line = monthly days / 4, capped at 6
   (one weekly holiday), so the maximum is 24 days a month. Week 1 is limited to what opening
   raw-material stock supports.

Lines, SKUs and daily rates are read from the `Line_Production` sheet of the workbook; nothing is hard-coded.

## Run it

Requires Python 3.10 or later.

```
pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows you can double-click `run_app.bat` instead. The app opens in the browser and loads
`Purchase_Plan_Standard_Revised.xlsx` by default; use the sidebar to load another month's file.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface |
| `planner_engine.py` | Calculation logic (MRP and production scheduling), no UI |
| `Purchase_Plan_Standard_Revised.xlsx` | Input template with sample data |
| `Purchase_Plan_Dashboard.html` | Original offline dashboard the app is based on |
| `.streamlit/config.toml` | Colour theme |
