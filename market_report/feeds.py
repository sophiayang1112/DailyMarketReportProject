"""Explicit delayed/disclosed trade and event feeds; no volume-based block inference."""
import numpy as np
import pandas as pd


def block_trades(path,cutoff,target_session):
    if path is None:return [],{"status":"not_configured","note":"No trade-level feed configured; this does not mean no block trades occurred."}
    frame=pd.read_csv(path)
    required={"trade_id","symbol","trade_at","observed_at","shares","price","currency","venue","qualifier","status","source","source_url"}
    if not required<=set(frame):raise ValueError("Block CSV schema incomplete")
    for column in ["trade_at","observed_at"]:frame[column]=pd.to_datetime(frame[column],utc=True,errors="raise")
    if frame[list(required)].isna().any().any():raise ValueError("Missing trade fields")
    if (frame.observed_at<frame.trade_at).any():raise ValueError("Trade disclosure precedes trade time")
    for column in ["shares","price"]:
        frame[column]=pd.to_numeric(frame[column],errors="raise")
        if not np.isfinite(frame[column]).all() or (frame[column]<=0).any():raise ValueError("Trade size/price must be positive")
    if not frame.currency.eq("USD").all():raise ValueError("Block feed currently requires USD trades")
    if not frame.qualifier.isin(["reported_block","size_screen"]).all():raise ValueError("Unknown trade qualifier")
    if not frame.status.isin(["active","cancelled"]).all():raise ValueError("Unknown trade status")
    available=frame.loc[(frame.observed_at<=cutoff)&(frame.trade_at<=cutoff)].sort_values("observed_at")
    latest=available.drop_duplicates("trade_id",keep="last")
    selected=latest.loc[(latest.status=="active")&(latest.trade_at.dt.tz_convert("America/New_York").dt.date==target_session)].copy()
    selected["notional_usd"]=selected.shares*selected.price
    selected["disclosure_delay_minutes"]=(selected.observed_at-selected.trade_at).dt.total_seconds()/60
    selected=selected.sort_values("notional_usd",ascending=False)
    for column in ["trade_at","observed_at"]:selected[column]=selected[column].map(lambda x:x.isoformat())
    return selected.to_dict("records"),{"status":"available","note":"Provider-reported blocks and size-screened trades remain separate; no buy/sell institutional-flow inference is made."}


def events(path,cutoff):
    if path is None:return [],{"status":"not_configured","note":"No earnings/macro calendar feed configured. Dates have not been invented."}
    frame=pd.read_csv(path)
    required={"event_at","known_at","category","title","source","source_url","status"}
    if not required<=set(frame):raise ValueError("Event CSV schema incomplete")
    for column in ["event_at","known_at"]:frame[column]=pd.to_datetime(frame[column],utc=True,errors="raise")
    if frame[list(required)].isna().any().any():raise ValueError("Missing event fields")
    selected=frame.loc[(frame.known_at<=cutoff)&(frame.event_at>=cutoff)&(frame.event_at<=cutoff+pd.Timedelta(days=7))].sort_values("event_at").copy()
    if not selected.status.isin(["confirmed","estimated"]).all():raise ValueError("Event status must be confirmed or estimated")
    for column in ["event_at","known_at"]:selected[column]=selected[column].map(lambda x:x.isoformat())
    return selected.to_dict("records"),{"status":"available"}


def fundamentals(path,cutoff):
    if path is None:return [],{"status":"not_configured","note":"No valuation/estimates feed configured."}
    frame=pd.read_csv(path)
    required={"symbol","observed_at","period","pe_ttm","pe_forward","dividend_yield_percent","source","source_url"}
    if not required<=set(frame):raise ValueError("Fundamentals CSV schema incomplete")
    frame["observed_at"]=pd.to_datetime(frame.observed_at,utc=True,errors="raise")
    frame=frame.loc[frame.observed_at<=cutoff].sort_values("observed_at").drop_duplicates("symbol",keep="last").copy()
    for column in ["pe_ttm","pe_forward","dividend_yield_percent"]:
        frame[column]=pd.to_numeric(frame[column],errors="coerce")
        if np.isinf(frame[column]).any():raise ValueError("Infinite valuation metric")
    frame["observed_at"]=frame.observed_at.map(lambda x:x.isoformat())
    return frame.to_dict("records"),{"status":"available"}
