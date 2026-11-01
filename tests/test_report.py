import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from market_report.calendar import cutoff_timestamp,last_completed_session
from market_report.analytics import performance
from market_report.providers import fred_rates,yahoo_history
from market_report.feeds import block_trades,events
from market_report.render import table
from market_report.cli import json_safe

ASSET={"symbol":"SPY","name":"S&P 500 ETF","asset_class":"equity_benchmarks","kind":"etf","sector":"","unit":"USD"}


class CalendarTests(unittest.TestCase):
    def test_weekend_uses_last_completed_session(self):
        self.assertEqual(str(last_completed_session(cutoff_timestamp("2026-11-01T18:00:00Z"))),"2026-10-30")

    def test_holiday_and_early_close(self):
        before=cutoff_timestamp("2026-11-27T17:59:00Z");after=cutoff_timestamp("2026-11-27T18:00:00Z")
        self.assertEqual(str(last_completed_session(before)),"2026-11-25")
        self.assertEqual(str(last_completed_session(after)),"2026-11-27")

    def test_timezone_required(self):
        with self.assertRaises(ValueError):cutoff_timestamp("2026-11-01")


class AnalyticsTests(unittest.TestCase):
    def test_ytd_uses_previous_year_end(self):
        frame=pd.DataFrame({"date":["2025-12-30","2025-12-31","2026-01-02","2026-01-05"],
            "close":[100,110,121,133.1],"adjusted_close":[100,110,121,133.1],"volume":[100]*4})
        row=performance(frame,ASSET,pd.Timestamp("2026-01-05").date())
        self.assertAlmostEqual(row["return_ytd"],21.)

    def test_split_adjusted_returns(self):
        frame=pd.DataFrame({"date":["2026-01-02","2026-01-05"],"close":[100,50],"adjusted_close":[50,50],"volume":[100,200]})
        row=performance(frame,ASSET,pd.Timestamp("2026-01-05").date())
        self.assertEqual(row["return_1d"],0)
        self.assertEqual(row["close"],50)

    def test_relative_volume_excludes_current_day(self):
        days=pd.bdate_range("2026-01-01",periods=21)
        frame=pd.DataFrame({"date":days.strftime("%Y-%m-%d"),"close":[100]*21,"adjusted_close":[100]*21,"volume":[100]*20+[1000]})
        self.assertEqual(performance(frame,ASSET,days[-1].date())["relative_volume_20d"],10)

    def test_incomplete_us_bar_excluded(self):
        timestamps=[int(pd.Timestamp(day,tz="UTC").timestamp()) for day in ["2026-10-29 13:30","2026-10-30 13:30"]]
        payload={"chart":{"result":[{"meta":{"currency":"USD","exchangeTimezoneName":"America/New_York"},
            "timestamp":timestamps,"indicators":{"quote":[{"close":[100,110],"volume":[100,100]}],"adjclose":[{"adjclose":[100,110]}]}}]}}
        with patch("market_report.providers.fetch_json",return_value=payload):
            frame,_=yahoo_history(ASSET,cutoff_timestamp("2026-10-30T15:00:00Z"))
        self.assertEqual(frame.date.tolist(),["2026-10-29"])


class ImportedFeedTests(unittest.TestCase):
    def test_rate_basis_points_and_synchronized_curve(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"rates.csv"
            path.write_text("observation_date,DGS2,DGS10\n2026-10-29,4.0,4.2\n2026-10-30,4.1,.\n")
            rows,_=fred_rates(cutoff_timestamp("2026-11-01T18:00:00Z"),str(path))
        by_id={row["series"]:row for row in rows}
        self.assertAlmostEqual(by_id["DGS2"]["change_bps"],10)
        self.assertAlmostEqual(by_id["10Y_MINUS_2Y"]["value_percent"],.2)
        self.assertEqual(by_id["10Y_MINUS_2Y"]["date"],"2026-10-29")

    def test_official_treasury_csv_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"treasury.csv"
            path.write_text("Date,2 Yr,5 Yr,10 Yr,30 Yr\n10/29/2026,4.0,4.1,4.2,4.5\n10/30/2026,4.1,4.2,4.3,4.6\n")
            rows,status=fred_rates(cutoff_timestamp("2026-11-01T18:00:00Z"),str(path))
        self.assertIn("Treasury",status["source"])
        self.assertEqual(next(row for row in rows if row["series"]=="DGS10")["value_percent"],4.3)

    def test_missing_trade_feed_not_zero_activity(self):
        rows,status=block_trades(None,cutoff_timestamp("2026-11-01T18:00:00Z"),pd.Timestamp("2026-10-30").date())
        self.assertEqual(rows,[]);self.assertEqual(status["status"],"not_configured")
        self.assertIn("does not mean",status["note"])

    def test_trade_cancellations_and_disclosure_cutoff(self):
        base={"trade_id":"T1","symbol":"SPY","trade_at":"2026-10-30T15:00:00Z","observed_at":"2026-10-30T15:05:00Z",
            "shares":10000,"price":100,"currency":"USD","venue":"X","qualifier":"reported_block","status":"active","source":"test","source_url":"https://example.com"}
        cancelled={**base,"observed_at":"2026-10-30T17:00:00Z","status":"cancelled"}
        late={**base,"trade_id":"T2","observed_at":"2026-11-02T17:00:00Z"}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"trades.csv";pd.DataFrame([base,cancelled,late]).to_csv(path,index=False)
            early,_=block_trades(str(path),cutoff_timestamp("2026-10-30T16:00:00Z"),pd.Timestamp("2026-10-30").date())
            final,_=block_trades(str(path),cutoff_timestamp("2026-11-01T18:00:00Z"),pd.Timestamp("2026-10-30").date())
        self.assertEqual(len(early),1);self.assertEqual(early[0]["notional_usd"],1000000)
        self.assertEqual(final,[])

    def test_future_known_events_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"events.csv"
            pd.DataFrame([dict(event_at="2026-11-03T14:00:00Z",known_at="2026-11-02T14:00:00Z",category="macro",title="Test",source="test",source_url="https://example.com",status="confirmed")]).to_csv(path,index=False)
            rows,_=events(str(path),cutoff_timestamp("2026-11-01T18:00:00Z"))
        self.assertEqual(rows,[])


class OutputTests(unittest.TestCase):
    def test_html_escapes_provider_content(self):
        output=table(["name"],[["<script>alert(1)</script>"]])
        self.assertNotIn("<script>",output);self.assertIn("&lt;script&gt;",output)

    def test_json_nonfinite_is_null(self):
        encoded=json.dumps(json_safe({"missing":np.nan,"infinite":np.inf}),allow_nan=False)
        self.assertEqual(json.loads(encoded),{"missing":None,"infinite":None})


if __name__=="__main__":unittest.main()
