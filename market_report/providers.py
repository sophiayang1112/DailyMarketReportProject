"""Public daily market history and optional official-series adapters."""
import io
import json
from urllib.parse import quote,urlencode
from urllib.request import Request,urlopen
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from .calendar import calendar,completed_us_bar

FRED_SERIES={"DGS2":"2Y Treasury yield","DGS5":"5Y Treasury yield","DGS10":"10Y Treasury yield",
             "DGS30":"30Y Treasury yield","DFII10":"10Y real Treasury yield",
             "T10YIE":"10Y breakeven inflation","BAMLC0A0CM":"Investment-grade option-adjusted spread",
             "BAMLH0A0HYM2":"High-yield option-adjusted spread"}


MACRO_SERIES={"CPIAUCSL":("US consumer price index","index"),"UNRATE":("US unemployment rate","%"),"FEDFUNDS":("Effective federal funds rate","%"),"PAYEMS":("US nonfarm payroll employment","thousand jobs")}


def fetch_json(url,timeout=12):
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=timeout) as response:return json.load(response)


def yahoo_history(asset,cutoff):
    symbol=asset["symbol"]
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe='')}?range=2y&interval=1d"
    payload=fetch_json(url)
    if payload.get("chart",{}).get("error"):raise ValueError("Provider returned chart error")
    result=payload["chart"]["result"][0];meta=result["meta"]
    currency=meta.get("currency")
    if asset["kind"] in {"stock","etf"} and currency!="USD":raise ValueError("Unexpected quote currency")
    points=result.get("timestamp",[]);quotes=result["indicators"]["quote"][0]
    adjusted=result["indicators"].get("adjclose",[{}])[0].get("adjclose",[None]*len(points))
    rows=[]
    timezone_name=meta.get("exchangeTimezoneName","America/New_York")
    for index,epoch in enumerate(points):
        when=pd.Timestamp(epoch,unit="s",tz="UTC");day=when.tz_convert(timezone_name).date()
        close=quotes.get("close",[])[index]
        if close is None or not np.isfinite(close) or close<=0:continue
        if asset["kind"] in {"stock","etf","index"}:
            if not completed_us_bar(day,cutoff):continue
        else:
            # Conservative completion for non-US-session daily bars: never take an open bar.
            if when+pd.Timedelta(hours=24)>cutoff:continue
        rows.append({"symbol":symbol,"date":str(day),"close":float(close),
            "adjusted_close":adjusted[index],"volume":quotes.get("volume",[None]*len(points))[index]})
    if not rows:raise ValueError("No completed bars available before cutoff")
    frame=pd.DataFrame(rows).drop_duplicates("date",keep="last").sort_values("date")
    return frame,{"provider":"Yahoo Finance chart (unofficial)","source_url":url,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),"quote_currency":currency,
        "completion_rule":"NYSE close" if asset["kind"] in {"stock","etf","index"} else "bar timestamp + 24 hours (conservative)"}


def live_prices(assets,cutoff,workers=4):
    frames=[];sources={};errors=[]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures={executor.submit(yahoo_history,asset,cutoff):asset for asset in assets}
        for future in as_completed(futures):
            asset=futures[future]
            try:
                frame,source=future.result();frames.append(frame);sources[asset["symbol"]]=source
            except Exception as exc:errors.append({"section":"market_data","symbol":asset["symbol"],"error":str(exc)[:240]})
    columns=["symbol","date","close","adjusted_close","volume"]
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=columns),sources,errors


def read_prices(path,assets,cutoff):
    frame=pd.read_csv(path)
    required={"symbol","date","close"}
    if not required<=set(frame):raise ValueError("Price CSV requires symbol,date,close")
    if frame.duplicated(["symbol","date"]).any():raise ValueError("Duplicate symbol/date prices")
    frame["date"]=pd.to_datetime(frame.date,errors="raise").dt.date
    if "adjusted_close" not in frame:frame["adjusted_close"]=np.nan
    if "volume" not in frame:frame["volume"]=np.nan
    lookup={asset["symbol"]:asset for asset in assets};keep=[]
    for row in frame.itertuples():
        if row.symbol not in lookup:keep.append(False);continue
        kind=lookup[row.symbol]["kind"]
        allowed=completed_us_bar(row.date,cutoff) if kind in {"stock","etf","index"} else row.date<cutoff.tz_convert("America/New_York").date()
        keep.append(allowed)
    frame=frame.loc[keep].copy();frame["date"]=frame.date.map(str)
    frame["close"]=pd.to_numeric(frame.close,errors="raise")
    if not np.isfinite(frame.close).all() or (frame.close<=0).any():raise ValueError("Prices must be finite and positive")
    return frame,{symbol:{"provider":"User-provided price CSV","source_url":"local file","retrieved_at":datetime.now(timezone.utc).isoformat()} for symbol in frame.symbol.unique()},[]


def fred_rates(cutoff,path=None,live=False):
    source="User-provided FRED-format CSV"
    if path:frame=pd.read_csv(path)
    elif live:
        url="https://fred.stlouisfed.org/graph/graph.csv?"+urlencode({"id":",".join(list(FRED_SERIES)+list(MACRO_SERIES)),"cosd":str((cutoff-pd.Timedelta(days=740)).date()),"coed":str(cutoff.date())})
        with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=12) as response:
            frame=pd.read_csv(io.BytesIO(response.read()))
        source=url
    else:return [],{"status":"not_configured","source":"FRED CSV or --fred-live"}
    treasury_format="Date" in frame and any(column in frame for column in ["2 Yr","5 Yr","10 Yr","30 Yr"])
    if treasury_format:
        frame=frame.rename(columns={"Date":"observation_date","2 Yr":"DGS2","5 Yr":"DGS5","10 Yr":"DGS10","30 Yr":"DGS30"})
        source="User-provided US Treasury yield CSV"
    date_column="observation_date" if "observation_date" in frame else "DATE"
    if date_column not in frame:raise ValueError("Rates CSV needs observation_date or DATE")
    frame[date_column]=pd.to_datetime(frame[date_column],errors="raise")
    frame=frame.loc[frame[date_column].dt.date<=cutoff.tz_convert("America/New_York").date()].sort_values(date_column)
    output=[]
    for series,name in FRED_SERIES.items():
        if series not in frame:continue
        subset=frame[[date_column,series]].copy();subset[series]=pd.to_numeric(subset[series],errors="coerce");subset=subset.dropna()
        if subset.empty:continue
        latest=subset.iloc[-1];previous=subset.iloc[-2] if len(subset)>1 else None
        output.append({"series":series,"name":name,"value_percent":float(latest[series]),
            "change_bps":None if previous is None else float(latest[series]-previous[series])*100,
            "date":latest[date_column].date().isoformat(),"source_url":"https://home.treasury.gov/resource-center-data-chart-center/interest-rates" if treasury_format else "https://fred.stlouisfed.org/series/"+series})
    # A curve slope requires same-date observations, not unrelated latest points.
    if {"DGS2","DGS10"}<=set(frame):
        paired=frame[[date_column,"DGS2","DGS10"]].copy()
        for column in ["DGS2","DGS10"]:paired[column]=pd.to_numeric(paired[column],errors="coerce")
        paired=paired.dropna()
        if len(paired):
            last=paired.iloc[-1];previous=paired.iloc[-2] if len(paired)>1 else None
            spread=float(last.DGS10-last.DGS2)
            output.append({"series":"10Y_MINUS_2Y","name":"10Y - 2Y Treasury curve slope","value_percent":spread,
                "change_bps":None if previous is None else (spread-float(previous.DGS10-previous.DGS2))*100,
                "date":last[date_column].date().isoformat(),"source_url":"https://home.treasury.gov/resource-center-data-chart-center/interest-rates" if treasury_format else "https://fred.stlouisfed.org/series/T10Y2Y"})
    for series,(name,unit) in MACRO_SERIES.items():
        if series not in frame:continue
        subset=frame[[date_column,series]].copy();subset[series]=pd.to_numeric(subset[series],errors="coerce");subset=subset.dropna()
        if subset.empty:continue
        latest=subset.iloc[-1]
        output.append({"category":"macro","series":series,"name":name,"value":float(latest[series]),
            "unit":unit,"change":None if len(subset)<2 else float(latest[series]-subset.iloc[-2][series]),
            "yoy_percent":None if len(subset)<13 or subset.iloc[-13][series]==0 else float((latest[series]/subset.iloc[-13][series]-1)*100),
            "date":str(latest[date_column].date()),"source_url":"https://home.treasury.gov/resource-center-data-chart-center/interest-rates" if treasury_format else "https://fred.stlouisfed.org/series/"+series})
    return output,{"status":"available" if output else "empty","source":source}
