"""Deterministic, explicitly synthetic fixtures for tests and report previews."""
import numpy as np
import pandas as pd
from .calendar import calendar
from .providers import FRED_SERIES


def prices(assets,target_session,seed=42):
    rng=np.random.default_rng(seed)
    days=calendar().sessions_in_range(pd.Timestamp(target_session)-pd.Timedelta(days=730),pd.Timestamp(target_session))
    base={"EURUSD=X":1.08,"JPY=X":150,"CNY=X":7.1,"DX-Y.NYB":103,"GC=F":2600,"SI=F":30,"CL=F":75,"NG=F":3,"HG=F":4.2,"^VIX":18}
    rows=[]
    market=rng.normal(.00025,.009,len(days))
    for asset in assets:
        daily=.4*market+rng.normal(.0001,.006,len(days))
        if asset["asset_class"]=="fixed_income":daily=rng.normal(.00005,.002,len(days))
        values=base.get(asset["symbol"],100)*np.exp(np.cumsum(daily))
        for day,value in zip(days,values):rows.append({"symbol":asset["symbol"],"date":str(day.date()),"close":float(value),"adjusted_close":float(value),"volume":int(rng.integers(100000,5000000))})
    frame=pd.DataFrame(rows)
    sources={asset["symbol"]:{"provider":"Synthetic deterministic fixture","source_url":"synthetic fixture","retrieved_at":str(target_session)} for asset in assets}
    return frame,sources,[]


def rates(target_session):
    anchors={"DGS2":4.1,"DGS5":4.,"DGS10":4.2,"DGS30":4.5,"DFII10":1.9,"T10YIE":2.3,"BAMLC0A0CM":.9,"BAMLH0A0HYM2":3.2}
    rows=[{"series":key,"name":name,"value_percent":anchors[key],"change_bps":float(index-3),"date":str(target_session),"source_url":"synthetic fixture"} for index,(key,name) in enumerate(FRED_SERIES.items())]
    rows.append({"series":"10Y_MINUS_2Y","name":"10Y - 2Y Treasury curve slope","value_percent":.1,"change_bps":2.,"date":str(target_session),"source_url":"synthetic fixture"})
    rows.extend([{"category":"macro","series":"UNRATE","name":"US unemployment rate","value":4.2,"unit":"%","change":.1,"yoy_percent":None,"date":str(target_session),"source_url":"synthetic fixture"},
        {"category":"macro","series":"CPIAUCSL","name":"US consumer price index","value":320.,"unit":"index","change":.6,"yoy_percent":2.6,"date":str(target_session),"source_url":"synthetic fixture"}])
    return rows,{"status":"synthetic","source":"Synthetic deterministic fixture"}
