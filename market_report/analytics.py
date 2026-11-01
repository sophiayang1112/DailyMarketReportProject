import numpy as np
import pandas as pd
from .calendar import calendar


def performance(frame,asset,target_session):
    frame=frame.sort_values("date").copy()
    close=pd.to_numeric(frame.close,errors="coerce")
    adjusted=pd.to_numeric(frame.adjusted_close,errors="coerce")
    use_adjusted=adjusted.notna().all() and (adjusted>0).all()
    series=adjusted if use_adjusted else close
    if not np.isfinite(series).all() or (series<=0).any():raise ValueError("Invalid prices in return series")
    current=float(series.iloc[-1]);observed=pd.to_datetime(frame.date)
    def change(lag):return None if len(series)<=lag else float((current/series.iloc[-lag-1]-1)*100)
    previous_year=np.flatnonzero(observed.dt.year.to_numpy()<observed.iloc[-1].year)
    ytd=None if not len(previous_year) else float((current/series.iloc[previous_year[-1]]-1)*100)
    volume=pd.to_numeric(frame.volume,errors="coerce")
    previous_volume=volume.iloc[-21:-1]
    rel_volume=None
    if len(previous_volume)==20 and previous_volume.notna().all() and previous_volume.mean()>0 and pd.notna(volume.iloc[-1]):
        rel_volume=float(volume.iloc[-1]/previous_volume.mean())
    daily=series.pct_change().dropna()
    vol=None if len(daily)<20 else float(daily.tail(20).std(ddof=1)*np.sqrt(252)*100)
    effective=observed.iloc[-1].date()
    session_lag=max(0,len(calendar().sessions_in_range(pd.Timestamp(effective),pd.Timestamp(target_session)))-1) if effective<=target_session else 0
    return {**asset,"date":str(effective),"close":float(close.iloc[-1]),"return_1d":change(1),
        "return_5d":change(5),"return_21d":change(21),"return_ytd":ytd,
        "volume":None if pd.isna(volume.iloc[-1]) else float(volume.iloc[-1]),
        "relative_volume_20d":rel_volume,"realized_vol_20d":vol,
        "above_50dma":None if len(series)<50 else bool(current>series.tail(50).mean()),
        "above_200dma":None if len(series)<200 else bool(current>series.tail(200).mean()),
        "return_basis":"adjusted close" if use_adjusted else "close (unadjusted)",
        "lag_us_sessions":session_lag,"stale":session_lag>1,"observations":len(series)}


def correlations(prices,symbols=None):
    symbols=symbols or ["SPY","TLT","LQD","HYG","GC=F","DX-Y.NYB"]
    panel={}
    for symbol in symbols:
        frame=prices.loc[prices.symbol==symbol].sort_values("date")
        if frame.empty:continue
        adjusted=pd.to_numeric(frame.adjusted_close,errors="coerce")
        values=adjusted if adjusted.notna().all() and (adjusted>0).all() else pd.to_numeric(frame.close)
        series=pd.Series(values.to_numpy(),index=pd.to_datetime(frame.date)).pct_change().dropna()
        panel[symbol]=series
    if len(panel)<2:return {"status":"insufficient_data","symbols":[],"matrix":[],"observations":0}
    aligned=pd.concat(panel,axis=1,join="inner").dropna().tail(60)
    if len(aligned)<20:return {"status":"insufficient_data","symbols":list(panel),"matrix":[],"observations":len(aligned)}
    return {"status":"available","symbols":list(aligned.columns),"matrix":aligned.corr().to_numpy().tolist(),
        "observations":len(aligned),"start":str(aligned.index[0].date()),"end":str(aligned.index[-1].date())}


def build_summary(rows):
    by_symbol={row["symbol"]:row for row in rows};facts=[]
    spy=by_symbol.get("SPY")
    if spy and spy["return_1d"] is not None:facts.append({"kind":"fact","text":f"SPY {spy['return_1d']:+.2f}% on {spy['date']}; 20-session realized volatility {spy['realized_vol_20d']:.1f}% annualized." if spy["realized_vol_20d"] is not None else f"SPY {spy['return_1d']:+.2f}% on {spy['date']}.","symbols":["SPY"]})
    sectors=sorted([row for row in rows if row["asset_class"]=="equity_sectors" and row["return_1d"] is not None and row["lag_us_sessions"]==0],key=lambda r:r["return_1d"],reverse=True)
    if sectors:facts.append({"kind":"fact","text":f"Sector ETF leader: {sectors[0]['sector']} {sectors[0]['return_1d']:+.2f}%; laggard: {sectors[-1]['sector']} {sectors[-1]['return_1d']:+.2f}%. Dates are shown in the sector table.","symbols":[sectors[0]["symbol"],sectors[-1]["symbol"]]})
    vix=by_symbol.get("^VIX")
    if vix:facts.append({"kind":"fact","text":f"VIX: {vix['close']:.2f} volatility points, observed {vix['date']}; this is an implied-volatility index, not a traded asset return.","symbols":["^VIX"]})
    watch=[row for row in rows if row["asset_class"]=="equity_watchlist" and row["return_1d"] is not None and row["lag_us_sessions"]==0]
    if watch:
        facts.append({"kind":"fact","text":f"Selected-stock breadth: {sum(r['return_1d']>0 for r in watch)} rising / {sum(r['return_1d']<0 for r in watch)} falling out of {len(watch)} covered stocks. This is watchlist breadth, not exchange-wide breadth.","symbols":[r["symbol"] for r in watch]})
    return facts
