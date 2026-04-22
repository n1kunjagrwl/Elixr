# External Integrations

All external API clients live in `platform/clients/`. Domains never import these directly — they receive them via FastAPI dependency injection. Temporal activities call them through the same client instances.

---

## Twilio — OTP SMS

**Purpose**: Deliver one-time passwords to users during login and registration.

**Owning domain**: `identity`  
**Called by**: `OTPDeliveryWorkflow` (Temporal activity)  
**Client file**: `platform/clients/twilio.py`

**Integration details**:
- Uses Twilio Verify API (not raw SMS) — handles carrier routing, rate limiting, and delivery receipts natively
- Message: `"Your Elixir OTP is {code}. Valid for 60 seconds."`
- Indian numbers require E.164 format (`+91XXXXXXXXXX`)

**Rate limits / cost**:
- Twilio Verify: ~₹6–8 per OTP (varies by carrier and country)
- Built-in rate limiting in Twilio Verify prevents abuse at the provider level
- App-level: max 3 OTP requests per phone per 15 minutes (enforced in `identity` service)

**Fallback**: If Twilio fails, the Temporal workflow retries up to 3 times with exponential backoff (2s, 4s, 8s). If all retries fail, the user sees an error and can request a new OTP after 60 seconds.

---

## AMFI — Mutual Fund NAVs

**Purpose**: Fetch daily Net Asset Values (NAVs) for all Indian mutual fund schemes.

**Owning domain**: `investments`  
**Called by**: `MarketPriceFetchWorkflow` (Temporal activity)  
**Client file**: `platform/clients/amfi.py`

**Integration details**:
- AMFI publishes a flat text file daily at `https://www.amfiindia.com/spages/NAVAll.txt`
- Format: pipe-delimited rows, one per scheme, including ISIN, scheme code, scheme name, NAV, and NAV date
- Parse the full file once per day; update all MF holdings in one pass
- Match holdings to schemes by ISIN or by AMFI scheme code stored in `instruments.ticker`

**Rate limits / cost**: Free, no API key required. Single file download once per day is sufficient.

**Fallback**: If the AMFI file is unavailable, log a warning and retain the previous NAV. Do not mark holdings as stale until 48 hours have passed without an update.

---

## Eodhd — NSE/BSE Stock and ETF Prices

**Purpose**: Fetch real-time and end-of-day prices for Indian stocks and ETFs listed on NSE and BSE.

**Owning domain**: `investments`  
**Called by**: `MarketPriceFetchWorkflow` (Temporal activity)  
**Client file**: `platform/clients/eodhd.py`

**Integration details**:
- REST API: `GET https://eodhd.com/api/real-time/{ticker}.NSE?api_token={key}&fmt=json`
- Returns: `open`, `high`, `low`, `close`, `previousClose`, `timestamp`
- Batch endpoint available: up to 50 tickers per request (`?s=INFY.NSE,TCS.NSE,...`)
- Use the batch endpoint to minimise API calls per workflow run

**Rate limits / cost**:
- Free tier: 20 API calls/day — insufficient for production
- All-World plan: ~$20/month — covers NSE, BSE, US markets
- Cache prices in `valuation_snapshots`; only re-fetch during scheduled workflow runs (every 15 min during market hours, every 6 hours otherwise)

**Fallback**: Retain last known price. Mark `holdings.last_valued_at` so the UI can show "price as of {timestamp}" and warn if stale beyond 1 trading day.

---

## CoinGecko — Cryptocurrency Prices

**Purpose**: Fetch current prices for crypto holdings in INR and USD.

**Owning domain**: `investments`  
**Called by**: `MarketPriceFetchWorkflow` (Temporal activity)  
**Client file**: `platform/clients/coingecko.py`

**Integration details**:
- REST API: `GET https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=inr,usd`
- `ids` is the CoinGecko coin ID (e.g. `bitcoin`, `ethereum`, `matic-network`)
- Store CoinGecko ID in `instruments.ticker` for crypto instruments
- Up to 250 coin IDs per request

**Rate limits / cost**:
- Free tier (Demo): 30 calls/minute, 10k calls/month — sufficient for moderate user base
- Pro: $129/month for higher limits

**Fallback**: Retain last known price. Crypto prices can move significantly; show "last updated {timestamp}" prominently in the UI when price is stale.

---

## Twelve Data — US Stock Prices

**Purpose**: Fetch prices for US-listed stocks and ETFs (NYSE, NASDAQ).

**Owning domain**: `investments`  
**Called by**: `MarketPriceFetchWorkflow` (Temporal activity)  
**Client file**: `platform/clients/twelve_data.py`

**Integration details**:
- REST API: `GET https://api.twelvedata.com/price?symbol={symbol}&apikey={key}`
- Batch: `GET /price?symbol=AAPL,MSFT,GOOGL&apikey={key}`
- US markets trade 9:30 AM–4:00 PM ET (7:00 PM–1:30 AM IST) — schedule workflow accordingly
- For Indian users, convert USD price to INR using the latest FX rate from the `fx` domain

**Rate limits / cost**:
- Free tier: 800 API credits/day (1 credit per price request, 8 per time-series)
- Basic: $12/month for 55k credits/day

**Fallback**: Retain last known price. Show "market closed" or "price as of {date}" in portfolio view.

---

## metals-api — Gold Price

**Purpose**: Fetch current gold spot price (XAU) to value physical gold holdings and Sovereign Gold Bonds.

**Owning domain**: `investments`  
**Called by**: `MarketPriceFetchWorkflow` (Temporal activity)  
**Client file**: `platform/clients/metals_api.py`

**Integration details**:
- REST API: `GET https://metals-api.com/api/latest?access_key={key}&base=INR&symbols=XAU`
- Returns price per troy ounce; convert to per gram: `price_per_gram = price_per_oz / 31.1035`
- For SGBs, use RBI issue price (stored at instrument creation) + accrued interest; market price is used for current valuation

**Rate limits / cost**:
- Free: 100 requests/month — sufficient if fetched once per `MarketPriceFetchWorkflow` run
- Basic: €9.99/month for 10k requests

**Fallback**: MCX gold price can be scraped as an alternative if metals-api is unavailable. Last known price retained otherwise.

---

## exchangerate-api — Foreign Exchange Rates

**Purpose**: Cache exchange rates for multi-currency transaction display and investment portfolio conversion to INR.

**Owning domain**: `fx`  
**Called by**: `FXRateRefreshWorkflow` (Temporal activity, scheduled every 6 hours)  
**Client file**: `platform/clients/exchangerate.py`

**Integration details**:
- REST API: `GET https://v6.exchangerate-api.com/v6/{key}/latest/INR`
- Returns rates for all currencies relative to INR as base
- Rates are upserted into `fx_rates` table; `fx` domain exposes `convert()` service method
- Historical rates endpoint available for displaying transactions in their original currency at the time of transaction

**Rate limits / cost**:
- Free tier: 1,500 requests/month — sufficient at 4 refreshes/day
- Pro: $10/month for 1M requests/month

**Fallback**: If the API is unavailable, use the last cached rate. Stale rates (>24 hours old) trigger a warning in the portfolio view but do not block display. FX rates are informational — financial decisions should not depend on real-time precision.

---

## Summary Table

| Client | Purpose | Domain | Workflow | Cost tier needed |
|---|---|---|---|---|
| Twilio Verify | OTP SMS | `identity` | `OTPDeliveryWorkflow` | Pay-per-use |
| AMFI | MF NAVs | `investments` | `MarketPriceFetchWorkflow` | Free |
| Eodhd | NSE/BSE stocks | `investments` | `MarketPriceFetchWorkflow` | ~$20/month |
| CoinGecko | Crypto | `investments` | `MarketPriceFetchWorkflow` | Free tier OK |
| Twelve Data | US stocks | `investments` | `MarketPriceFetchWorkflow` | Free tier OK |
| metals-api | Gold | `investments` | `MarketPriceFetchWorkflow` | Free tier OK |
| exchangerate-api | FX rates | `fx` | `FXRateRefreshWorkflow` | Free tier OK |

---

## Adding a New Integration

1. Create `platform/clients/{name}.py` with a class whose constructor receives the config values it needs (API key, base URL, etc.) as plain arguments — injected by `runtime/dependencies.py`. Do not import `Settings` or `shared/config.py` directly from a client class.
2. Register it in `runtime/lifespan.py` (instantiate on startup, close on shutdown)
3. Add it as a FastAPI dependency in `runtime/app.py`
4. Document it in this file with: purpose, rate limits, owning domain, fallback behaviour
5. Write a unit test using `respx` or `httpretty` to mock the HTTP responses
