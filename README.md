# Belle Listing AI

Streamlit application for generating separate Myntra and Flipkart listing workbooks from marketplace-specific trackers and templates.

## Setup

1. Create a virtual environment.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and set secure local values.
4. Place the Google service-account JSON at the path in `GOOGLE_APPLICATION_CREDENTIALS`.
5. Set the `WORKBOOK_*_ID` values and share those sheets with the service-account email.

Never commit credentials, tracker exports, generated workbooks, tokens, or the device database.

## Run

Frontend:

```powershell
python -m streamlit run frontend/app_streamlit.py
```

Optional device-management backend:

```powershell
python -m uvicorn backend.server:app --host 127.0.0.1 --port 5001
```

## Marketplace Outputs

- Myntra uses `scripts/run_generator_myntra.py`, the Myntra template, and writes `Myntra_Sku_Ready_*.xlsx` under `data/output/<brand>/`.
- Flipkart uses `scripts/run_generator_flipkart.py`, the Flipkart template, and writes `Flipkart_Sku_Ready_*.xlsx` under `data/output/flipkart/<brand>/`.

The UI selects the dedicated generator and output path for each marketplace.

## Tests

```powershell
python -m pytest
```

The repository includes the blank marketplace templates required to preserve their distinct column layouts. Operational tracker data remains local or in Google Sheets.
