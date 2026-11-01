# Calculation conventions

## Classification

The taxonomy uses common investment-analysis categories: equity, fixed income, currency, commodities, listed alternative exposures, and derivatives/risk. Macroeconomic data, valuation and transaction disclosures are separate research layers. This is a configurable application taxonomy, not an official CFA Institute taxonomy or licensed sector-index product.

## Performance and risk

- 1D, 5-session and 21-session return = current chosen close / lagged chosen close - 1.
- YTD uses the last available close from the preceding calendar year, not the first January close. If that baseline is absent, the result is N/A.
- Displayed price is raw close; return history uses complete adjusted close when available, with the basis recorded.
- Realized volatility = sample standard deviation of the last 20 simple daily returns times sqrt(252), expressed as percent. It is not implied volatility or a forecast.
- Relative volume = latest volume / mean of the prior 20 observations, excluding latest volume. A full positive-volume baseline is required.
- Moving-average flags compare the current chosen close against its 50/200-observation average; short histories yield N/A.
- Cross-asset correlations align return dates with an inner join, require at least 20 common observations, and use up to the most recent 60. They do not imply causality.

Date lag counts NYSE sessions, with values greater than one session flagged as stale. FX/futures trading calendars differ, so lag is a report comparison measure rather than an assertion of each asset's official session schedule. Rankings and watchlist breadth in the summary require current US-session observations.

## Coverage and interpretation

Sector ETFs are public fund proxies, not exact sector indexes. A selected-stock watchlist is not exchange-wide breadth. Bond ETF price performance cannot be equated with yield changes, credit-spread changes, or actual duration attribution. Continuous commodity series can include contract-roll effects. Listed real-estate/BDC/bitcoin ETFs are not direct daily valuations of private assets.

Every return has its own observation date. Macro observations, disclosures, prices and calendars can have different publication lags. Missing inputs remain explicit. No news-based causality, forward return, consensus surprise, or institutional direction is synthesized from daily price or volume bars.
