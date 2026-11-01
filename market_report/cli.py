import argparse
import json
import math
from datetime import datetime,timezone
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from .calendar import cutoff_timestamp,last_completed_session,calendar
from .providers import live_prices,read_prices,fred_rates
from .analytics import performance,correlations,build_summary
from .feeds import block_trades,events,fundamentals
from .render import render
from . import sample


def json_safe(value):
    if isinstance(value,dict):return {str(key):json_safe(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(item) for item in value]
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(np.bool_,)):return bool(value)
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    return value


def generate(args):
    cutoff=cutoff_timestamp(args.as_of);session=last_completed_session(cutoff)
    if args.skip_closed_day and not calendar().is_session(pd.Timestamp(cutoff.tz_convert("America/New_York").date())):
        print("No NYSE session scheduled on the local report date; daily generation skipped.")
        return 0
    universe_path=Path(args.universe) if args.universe else Path(__file__).with_name("universe.json")
    assets=json.loads(universe_path.read_text(encoding="utf-8"))
    if len({asset["symbol"] for asset in assets})!=len(assets):raise ValueError("Duplicate universe symbols")
    if args.mode=="sample":prices,sources,errors=sample.prices(assets,session)
    elif args.mode=="csv":
        if not args.prices_csv:raise ValueError("CSV mode requires --prices-csv")
        prices,sources,errors=read_prices(args.prices_csv,assets,cutoff)
    else:prices,sources,errors=live_prices(assets,cutoff,args.workers)
    prices=prices.loc[pd.to_datetime(prices.date).dt.date<=session].copy()
    rows=[]
    for asset in assets:
        frame=prices.loc[prices.symbol==asset["symbol"]]
        if frame.empty:continue
        try:rows.append(performance(frame,asset,session))
        except Exception as exc:errors.append({"section":"analytics","symbol":asset["symbol"],"error":str(exc)})
    if args.mode=="sample":
        rates,rate_status=sample.rates(session)
        trade_time=calendar().session_close(pd.Timestamp(session))-pd.Timedelta(hours=1)
        trades=[{"trade_id":"synthetic-1","symbol":"MSFT","shares":25000,"price":250.,"currency":"USD",
            "notional_usd":6250000.,"qualifier":"reported_block","venue":"Synthetic venue",
            "trade_at":trade_time.isoformat(),"observed_at":(trade_time+pd.Timedelta(minutes=15)).isoformat(),
            "disclosure_delay_minutes":15.,"source":"Synthetic fixture","source_url":"synthetic fixture","status":"active"}]
        trade_status={"status":"synthetic","note":"Synthetic trade fixture, not an actual market disclosure."}
        calendar_events=[{"event_at":(cutoff+pd.Timedelta(days=2)).isoformat(),"known_at":cutoff.isoformat(),
            "category":"macro","title":"Synthetic scheduled economic release","status":"confirmed","source":"Synthetic fixture","source_url":"synthetic fixture"}]
        event_status={"status":"synthetic"}
        valuation=[{"symbol":"MSFT","pe_ttm":25.,"pe_forward":23.,"dividend_yield_percent":1.,
            "period":"synthetic fixture","observed_at":cutoff.isoformat(),"source":"Synthetic fixture","source_url":"synthetic fixture"}]
        valuation_status={"status":"synthetic"}
    else:
        try:rates,rate_status=fred_rates(cutoff,args.fred_csv,args.fred_live)
        except Exception as exc:
            rates=[];rate_status={"status":"unavailable","source":"FRED","error":str(exc)}
            errors.append({"section":"rates_macro","error":str(exc)})
        trades,trade_status=block_trades(args.blocks_csv,cutoff,session)
        calendar_events,event_status=events(args.events_csv,cutoff)
        valuation,valuation_status=fundamentals(args.fundamentals_csv,cutoff)
    missing=[asset["symbol"] for asset in assets if asset["symbol"] not in {row["symbol"] for row in rows}]
    gaps=[]
    if missing:gaps.append("Missing market histories: "+", ".join(missing))
    stale=[row["symbol"] for row in rows if row["stale"]]
    if stale:gaps.append("Stale market observations: "+", ".join(stale))
    if rate_status["status"] in {"not_configured","unavailable","empty"}:gaps.append("Rates, credit spreads and macro releases unavailable / not configured")
    if trade_status["status"]=="not_configured":gaps.append("Trade-level block / off-exchange feed not configured")
    if event_status["status"]=="not_configured":gaps.append("Earnings and economic-event calendar not configured")
    if valuation_status["status"]=="not_configured":gaps.append("Valuation / forward estimates feed not configured")
    alerts=[row for row in rows if row["asset_class"]=="equity_watchlist" and row["lag_us_sessions"]==0
            and row["relative_volume_20d"] is not None and row["relative_volume_20d"]>=2]
    alerts.sort(key=lambda row:row["relative_volume_20d"],reverse=True)
    report={"metadata":{"project":"DailyMarketReportProject","data_mode":args.mode,"session":str(session),
        "cutoff_utc":cutoff.isoformat(),"cutoff_chicago":cutoff.tz_convert("America/Chicago").isoformat(),
        "cutoff_new_york":cutoff.tz_convert("America/New_York").isoformat(),
        "generated_at":datetime.now(timezone.utc).isoformat(),"configured_assets":len(assets),"covered_assets":len(rows)},
        "assets":rows,"rates":rates,"block_trades":trades,"events":calendar_events,"fundamentals":valuation,
        "volume_alerts":alerts,"summary":build_summary(rows),"correlations":correlations(prices),
        "sources":sources,"feed_status":{"rates":rate_status,"blocks":trade_status,"events":event_status,"fundamentals":valuation_status},
        "gaps":gaps,"errors":errors,
        "coverage_notes":["Sector ETF returns are not proprietary sector-index or full-constituent returns.",
            "Watchlist screens do not represent the full US equity market.","Bond ETF returns are not yield or credit-spread changes.",
            "Large trading volume is not proof of a block trade or institutional inflow.",
            "No complete US consolidated off-exchange or trade-condition feed is bundled.",
            "Private-market assets do not have daily observable public prices."]}
    report=json_safe(report)
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    (output/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    render(report,output)
    print(json.dumps({"session":str(session),"mode":args.mode,"coverage":f"{len(rows)}/{len(assets)}",
        "gaps":gaps,"html":str(output/"report.html")},ensure_ascii=True,indent=2))
    spy=next((row for row in rows if row["symbol"]=="SPY"),None)
    if args.strict and (spy is None or spy["lag_us_sessions"]!=0):return 2
    return 0


def main():
    parser=argparse.ArgumentParser(description="Daily cross-asset investment research report")
    parser.add_argument("--mode",choices=["live","csv","sample"],default="live")
    parser.add_argument("--as-of",help="Timezone-aware cutoff, e.g. 2026-11-01T18:00:00Z")
    parser.add_argument("--output",default="output/latest");parser.add_argument("--universe")
    for name in ["prices-csv","blocks-csv","events-csv","fundamentals-csv"]:parser.add_argument('--'+name)
    parser.add_argument("--fred-csv","--rates-csv",dest="fred_csv")
    parser.add_argument("--fred-live",action="store_true");parser.add_argument("--strict",action="store_true")
    parser.add_argument("--skip-closed-day",action="store_true");parser.add_argument("--workers",type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.workers<=6:parser.error("Use 1-6 market-data workers")
    if args.mode=="sample" and any([args.prices_csv,args.fred_csv,args.blocks_csv,args.events_csv,args.fundamentals_csv,args.fred_live]):
        parser.error("Sample mode does not combine with external feeds")
    sys.exit(generate(args))


if __name__=="__main__":main()
