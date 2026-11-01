# Sources and input schemas

## Market history

The public adapter reads completed daily chart bars from Yahoo Finance. Each asset declares symbol, name, asset class, instrument kind, sector, and price unit. ETF/stock quotes must use USD. Currency direction and futures price unit are defined in the universe configuration, not inferred from the size of the price.

US stocks/ETFs/index observations are accepted only after the corresponding NYSE close. Non-US-session observations require the daily bar timestamp plus 24 hours to have elapsed, a conservative approximation that can lag actual local closes. Observation dates and provider completion rules remain visible. The adapter is not a consolidated tape or exchange-certified official close.

Price CSV columns: `symbol,date,close,adjusted_close,volume`. The last two fields are optional. Symbol/date pairs must be unique, closes finite and positive, and future/incomplete observations are excluded. CSV non-US-session observations conservatively require a prior local calendar day.

The report calculates returns from adjusted close only when the history is complete and positive; otherwise it uses unadjusted close and labels that basis. It does not splice adjusted and raw prices into one return series. Corporate-action adjustments can be revised after the fact.

## Rates and macro

US Treasury CSV exports with `Date`, `2 Yr`, `5 Yr`, `10 Yr`, and `30 Yr` are accepted using `--rates-csv`; they are mapped to the same yield fields and attributed to the Treasury source.

FRED CSV accepts `observation_date` or `DATE`, plus any supported series columns. Missing values such as `.` are ignored rather than replaced with zero.

Rates: DGS2, DGS5, DGS10, DGS30, DFII10, T10YIE. Credit: BAMLC0A0CM and BAMLH0A0HYM2. Macro: CPIAUCSL, UNRATE, FEDFUNDS and PAYEMS. FRED source links accompany each series. Some underlying series, including credit indexes, can have third-party licensing conditions.

Rates and credit inputs are percent units. A change of 0.10 percentage points is 10 basis points. Credit OAS and 10Y-2Y display in basis points; Treasury yields and breakevens display in percent. A Treasury slope is calculated only from paired same-date values. A yield-curve chart requires same-date tenors.

CPI and payroll inputs are monthly observations. Changes compare the previous nonmissing observation, and YoY compares the observation 12 records earlier. This assumes a complete monthly series; gap-filled, irregular or daily macro exports need preparation before use. Observation periods do not prove when a release became known. No historical-vintage/release-time claim is made.

## Block and large trades

Required CSV fields:

`trade_id,symbol,trade_at,observed_at,shares,price,currency,venue,qualifier,status,source,source_url`

Timestamps require the provider's true trade/disclosure times, normalized to UTC. Price and shares must be positive; this adapter supports USD equity trades. `qualifier` is either `reported_block` (explicit provider condition) or `size_screen` (a separately labeled large-trade screen). A provider's block definition must be reviewed independently; there is no universal size threshold in this project.

`status` is `active` or `cancelled`. Corrections repeat the trade ID with a later observed_at and the corrected fields. At the report cutoff, latest-known records win, then cancellations are excluded. Cancellations should carry the original positive size/price metadata. Records disclosed after the cutoff cannot appear, even when the underlying trade occurred earlier.

The report filters trade dates to the selected US session, shows notional and disclosure delay, and does not infer buyer identity, investor intent or aggressor side. FINRA off-exchange/ATS aggregate publications are not equivalent to a complete contemporaneous block-trade tape. To use a vendor feed, map its actual conditions and timestamps to this schema and follow its terms.

## Event calendar

`event_at,known_at,category,title,source,source_url,status`

Only events already known by the cutoff and occurring in the next seven days are included. Status is `confirmed` or `estimated`. Category can distinguish earnings, economic releases, central banks, auctions, expiries, or corporate actions. The adapter does not generate event dates.

## Valuation and estimates

`symbol,observed_at,period,pe_ttm,pe_forward,dividend_yield_percent,source,source_url`

Keep accounting and estimate conventions in `period`/source metadata. Data after the cutoff are excluded; the latest available symbol record is used. Missing numeric values are preserved. No claim is made that provider estimates or multiples are directly comparable across all issuers.

## Secrets and publication

No paid provider, cloud account, email address or API key is required for the public-price path. Keep private exports outside the repository or use ignored CSV paths. Live outputs under `output/` are ignored by Git. The public example uses synthetic fixtures and is prominently labeled.
