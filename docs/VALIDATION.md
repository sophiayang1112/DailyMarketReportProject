# Validation record

## Executed checks

- Fourteen automated tests passed: completed-session calendar, NYSE holiday and early close, timezone requirement, prior-year-end YTD, split-adjusted returns, prior-only volume baseline, incomplete-bar exclusion, rate basis-point conversion, synchronized 10Y-2Y slope, Treasury CSV compatibility, delayed disclosures and cancellations, future-known events, HTML escaping and finite JSON serialization.
- Editable installation and the installed report-generation command succeeded.
- A complete synthetic fixture report generated HTML, Markdown, JSON and three charts. The HTML's synthetic label was verified, and embedded chart images were present.
- Chromium rendering was inspected for bilingual text, wide tables, trade fields, chart layout and the source audit.

## Live-source check

Report cutoff: 2026-11-01 18:00 UTC. The latest completed US session was 2026-10-30. All 49 configured market instruments returned usable history, and strict-mode SPY freshness validation passed.

FRED access timed out in this environment. The report explicitly recorded unavailable rate/credit/macro data. No trade-level feed, event calendar or valuation-estimates feed was configured; those gaps were disclosed. File imports for those sections are implemented and tested. No unavailable field was replaced with fictional live data.

The repository publishes a synthetic layout fixture, not raw third-party market histories. Live reports remain under ignored output directories. Provider access and scheduled runner outcomes can change and are not guaranteed by this local check.

## Reproduce

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
market-report --mode sample --as-of 2026-11-01T18:00:00Z --strict --output output/sample
market-report --mode live --fred-live --strict --output output/live
```
