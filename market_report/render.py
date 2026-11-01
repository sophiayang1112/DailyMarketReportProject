import base64
import html
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SECTIONS=[("equity_benchmarks","Equity benchmarks | 全球股票基准"),
 ("equity_sectors","US equity sectors | 美股行业板块"),("equity_watchlist","Selected stocks | 行业个股观察"),
 ("fixed_income","Fixed-income exposures | 固定收益资产"),("currencies","Currencies | 外汇"),
 ("commodities","Commodities | 大宗商品"),("listed_alternatives","Listed alternatives | 上市另类资产"),
 ("risk_indicators","Derivatives & risk | 衍生品与风险指标")]


def fmt(value,digits=2,suffix=""):
    if value is None:return "N/A"
    if isinstance(value,(int,float)):
        if not np.isfinite(value):return "N/A"
        return f"{value:,.{digits}f}{suffix}"
    return str(value)


def asset_table(rows):
    return [[row["name"]+(" · "+row["sector"] if row["asset_class"]=="equity_watchlist" else ""),row["symbol"],fmt(row["close"],4),row["unit"],
        fmt(row["return_1d"],2,"%"),fmt(row["return_5d"],2,"%"),fmt(row["return_21d"],2,"%"),
        fmt(row["return_ytd"],2,"%"),row["date"]+(" [STALE]" if row["stale"] else "")] for row in rows]


def table(headers,rows):
    content="<thead><tr>"+"".join("<th>"+html.escape(str(h))+"</th>" for h in headers)+"</tr></thead><tbody>"
    for row in rows:content+="<tr>"+"".join("<td>"+html.escape(str(cell))+"</td>" for cell in row)+"</tr>"
    return '<div class="table-wrap"><table>'+content+"</tbody></table></div>"


def md_table(headers,rows):
    def cell(value):return str(value).replace("|","/").replace("\n"," ")
    return "| "+" | ".join(map(cell,headers))+" |\n| "+" | ".join(["---"]*len(headers))+" |\n"+"\n".join("| "+" | ".join(map(cell,row))+" |" for row in rows)+"\n"


def charts(report,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);output=[]
    rows=[r for r in report["assets"] if r["asset_class"]=="equity_sectors" and r["return_1d"] is not None]
    if rows:
        rows=sorted(rows,key=lambda r:r["return_1d"])
        fig,ax=plt.subplots(figsize=(9,4.7));values=[r["return_1d"] for r in rows]
        ax.barh([r["sector"] for r in rows],values,color=["#cf755b" if v<0 else "#278c85" for v in values])
        ax.axvline(0,color="gray",linewidth=.7);ax.set_xlabel("1 completed session return (%)")
        ax.set_title("US sector ETF performance | observation dates in report")
        fig.tight_layout();path=directory/"sector_performance.png";fig.savefig(path,dpi=150);plt.close(fig);output.append(path)
    corr=report["correlations"]
    if corr["status"]=="available":
        fig,ax=plt.subplots(figsize=(7,5));image=ax.imshow(corr["matrix"],vmin=-1,vmax=1,cmap="RdBu_r")
        ax.set_xticks(range(len(corr["symbols"])),corr["symbols"],rotation=35,ha="right")
        ax.set_yticks(range(len(corr["symbols"])),corr["symbols"])
        for i,row in enumerate(corr["matrix"]):
            for j,value in enumerate(row):ax.text(j,i,f"{value:.2f}",ha="center",va="center",fontsize=8)
        ax.set_title(f"Cross-asset return correlation | {corr['observations']} common observations")
        fig.colorbar(image,ax=ax);fig.tight_layout();path=directory/"cross_asset_correlation.png";fig.savefig(path,dpi=150);plt.close(fig);output.append(path)
    tenor={"DGS2":2,"DGS5":5,"DGS10":10,"DGS30":30}
    curve=[r for r in report["rates"] if r.get("series") in tenor]
    if len(curve)>1 and len({r["date"] for r in curve})==1:
        curve=sorted(curve,key=lambda r:tenor[r["series"]]);fig,ax=plt.subplots(figsize=(7,4))
        ax.plot([tenor[r["series"]] for r in curve],[r["value_percent"] for r in curve],"o-",color="#278c85")
        ax.set(xlabel="Maturity (years)",ylabel="Yield (%)",title="US Treasury curve | "+curve[0]["date"])
        fig.tight_layout();path=directory/"treasury_curve.png";fig.savefig(path,dpi=150);plt.close(fig);output.append(path)
    return output


def render(report,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    image_paths=charts(report,output/"charts")
    metadata=report["metadata"];sample=metadata["data_mode"]=="sample"
    title="Daily Cross-Asset Market Brief"
    fragments=[];markdown=["# "+title,"",f"US session: {metadata['session']} | As of: {metadata['cutoff_utc']}",""]
    if sample:
        fragments.append('<div class="notice sample">SYNTHETIC DATA EXAMPLE · 合成数据示例，不是实际市场行情</div>')
        markdown += ["**SYNTHETIC DATA EXAMPLE — not live market data.**",""]
    if report["gaps"]:
        fragments.append('<div class="notice">Data coverage / 数据覆盖：'+html.escape("；".join(report["gaps"]))+'</div>')
        markdown += ["Data coverage: "+"; ".join(report["gaps"]),""]
    facts="".join('<li>'+html.escape(row["text"])+"</li>" for row in report["summary"])
    fragments.append('<section><h2>Market pulse | 市场摘要</h2><ul>'+facts+'</ul></section>')
    markdown += ["## Market pulse",""]+["- "+row["text"] for row in report["summary"]]+[""]
    def section(heading,headers,rows,note=""):
        fragments.append('<section><h2>'+html.escape(heading)+'</h2>'+('<p class="note">'+html.escape(note)+'</p>' if note else '')+(table(headers,rows) if rows else '<p class="note">No data configured or available for this section.</p>')+'</section>')
        markdown.extend(["## "+heading,"",note,"",md_table(headers,rows) if rows else "Not configured / unavailable.",""])
    macro=[r for r in report["rates"] if r.get("category")=="macro"]
    section("Macro & policy | 宏观与政策",["Indicator","Value","Unit","Change","YoY","Observation period"],
        [[r["name"],fmt(r["value"]),r["unit"],fmt(r["change"]),fmt(r["yoy_percent"],2,"%"),r["date"]] for r in macro],
        "FRED dates are observation periods, not economic-release timestamps. Changes use previous available observations; missing series are not estimated.")
    for category,heading in SECTIONS:
        rows=[r for r in report["assets"] if r["asset_class"]==category]
        if category=="equity_sectors":rows=sorted(rows,key=lambda r:r["return_1d"] if r["return_1d"] is not None else -999,reverse=True)
        if category=="equity_watchlist":rows=sorted(rows,key=lambda r:(r["sector"],r["symbol"]))
        note={"equity_watchlist":"A selected large-cap watchlist, not the full US equity universe. Sector labels are maintained in configuration.",
            "fixed_income":"ETF price/total-return exposures are separate from bond yields and credit spreads shown below.",
            "commodities":"Continuous/front-contract futures quotes. Contract rolls and conservative daily-bar completion can affect returns and observation dates; no spot-price or futures-curve claim.",
            "currencies":"Quote direction is explicit in the unit column. Non-US-session bars use a conservative completion rule.",
            "listed_alternatives":"Publicly traded proxies only. Private equity, private debt and direct property do not have reliable daily observable marks.",
            "risk_indicators":"VIX is an implied-volatility index. Options skew, Greeks and positioning require separate datasets."}.get(category,"")
        section(heading,["Instrument","Symbol","Last","Unit","1D","5 sessions","21 sessions","YTD","Observed"],asset_table(rows),note)
    rates=[r for r in report["rates"] if r.get("category")!="macro"]
    section("Rates & credit | 利率曲线与信用利差",["Series","Latest","Unit","Change (bp)","Observed"],
        [[r["name"],fmt(r["value_percent"]*(100 if r["series"].startswith("BAML") or r["series"]=="10Y_MINUS_2Y" else 1)),
          "bp" if r["series"].startswith("BAML") or r["series"]=="10Y_MINUS_2Y" else "%",fmt(r["change_bps"]),r["date"]] for r in rates],
        "Yield and spread changes are basis points. 10Y-2Y uses same-date paired observations. FRED published data are not a historical vintage database.")
    section("Stock valuation | 个股估值",["Symbol","TTM P/E","Forward P/E","Dividend yield %","Period","Observed","Source"],
        [[r["symbol"],fmt(r["pe_ttm"]),fmt(r["pe_forward"]),fmt(r["dividend_yield_percent"]),r["period"],r["observed_at"],r["source"]] for r in report["fundamentals"]],
        "Provider-defined multiples; forward estimates and accounting bases require source review. Missing estimates are left blank.")
    alerts=report["volume_alerts"]
    section("Volume & technical screens | 成交量与技术观察",["Stock","1D","Volume / prior 20-session avg","20-session volatility","Above 50DMA","Above 200DMA"],
        [[r["symbol"],fmt(r["return_1d"],2,"%"),fmt(r["relative_volume_20d"],2,"x"),fmt(r["realized_vol_20d"],1,"%"),r["above_50dma"],r["above_200dma"]] for r in alerts],
        "Stocks at or above 2x prior 20-session average volume. This screen is not evidence of a block trade or institutional buying.")
    trades=report["block_trades"]
    section("Disclosed block & large trades | 披露大宗及大额成交",["Symbol","Shares","Price USD","Notional USD","Qualifier","Venue","Trade time","Disclosure delay min","Source"],
        [[r["symbol"],fmt(r["shares"],0),fmt(r["price"]),fmt(r["notional_usd"],0),r["qualifier"],r["venue"],r["trade_at"],fmt(r["disclosure_delay_minutes"]),r["source"]] for r in trades],report["feed_status"]["blocks"]["note"])
    section("Next seven days | 未来七天事件",["Time UTC","Category","Event","Status","Source"],
        [[r["event_at"],r["category"],r["title"],r["status"],r["source"]] for r in report["events"]],
        "Only events known by the report cutoff are included. Confirmed and estimated times remain distinct.")
    for path in image_paths:
        encoded=base64.b64encode(path.read_bytes()).decode()
        fragments.append('<section class="chart"><img alt="'+html.escape(path.stem)+'" src="data:image/png;base64,'+encoded+'"></section>')
        markdown += [f"![{path.stem}](charts/{path.name})",""]
    coverage=[[row["symbol"],row["date"],row["lag_us_sessions"],row["return_basis"],report["sources"][row["symbol"]]["provider"]] for row in report["assets"]]
    section("Source & freshness audit | 来源与时效",["Symbol","Observed","US-session lag","Return basis","Source"],coverage,
        "Dates and lag are explicit. Historical price history may be restated for corporate actions; this report is not a point-in-time backtest. Correlations are descriptive, not causal.")
    source_links=[]
    for symbol,source in report["sources"].items():
        url=source["source_url"]
        if url.startswith(("https://","http://")):source_links.append('<a href="'+html.escape(url,quote=True)+'">'+html.escape(symbol)+'</a>')
    extra_rows=report["rates"]+report["block_trades"]+report["events"]+report["fundamentals"]
    extra_urls=sorted({r.get("source_url","") for r in extra_rows if r.get("source_url","").startswith(("https://","http://"))})
    source_links += ['<a href="'+html.escape(url,quote=True)+'">'+html.escape(url)+'</a>' for url in extra_urls]
    fragments.append('<section><h2>Source links</h2><div class="sources">'+" · ".join(source_links)+'</div></section>')
    markdown.extend(["## Source links", ""])
    for symbol,source in report["sources"].items():
        if source["source_url"].startswith(("https://","http://")):markdown.append(f"- [{symbol}]({source['source_url']})")
    markdown.extend(["- "+url for url in extra_urls])

    css="""*{box-sizing:border-box}body{margin:0;background:#eef2f6;color:#182a3a;font-family:Segoe UI,Microsoft YaHei,Arial,sans-serif}main{max-width:1240px;margin:28px auto;padding:0 22px 40px}header{background:#112b40;color:white;padding:36px;border-radius:18px}header small{color:#91d7d1;text-transform:uppercase;letter-spacing:2px}h1{font-size:32px;margin:12px 0}h2{font-size:21px;margin:0 0 16px}section{background:white;padding:25px;margin:18px 0;border:1px solid #dce5ec;border-radius:14px}p,li{line-height:1.7}.note{font-size:13px;color:#536879}.notice{margin:20px 0;padding:18px;border-radius:10px;background:#fff4d7;border:1px solid #ebce82;line-height:1.7}.sample{background:#fee9d8;font-weight:700}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;background:#eaf3f4;color:#214954}th,td{padding:10px 8px;border-bottom:1px solid #e1e8ed;vertical-align:top}td{white-space:nowrap}td:first-child{white-space:normal;min-width:145px}tr:hover{background:#f6fafc}.chart img{width:100%;max-width:1000px;display:block;margin:auto}.sources{font-size:12px;line-height:2;overflow-wrap:anywhere}a{color:#116d78}.meta{color:#bfd1df;font-size:13px}@media print{body{background:white}main{max-width:none;margin:0}header,section{break-inside:avoid}.table-wrap{overflow:visible}table{font-size:9px}.notice{font-size:11px}}"""
    header='<header><small>DailyMarketReportProject · Investment Research</small><h1>'+title+'</h1><p>US trading session '+metadata["session"]+'</p><div class="meta">As of '+html.escape(metadata["cutoff_utc"])+"<br>New York: "+html.escape(metadata["cutoff_new_york"])+" · Chicago: "+html.escape(metadata["cutoff_chicago"])+"<br>Market data coverage: "+str(metadata["covered_assets"])+" / "+str(metadata["configured_assets"])+" instruments</div></header>"
    document='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+'</title><style>'+css+'</style></head><body><main>'+header+"".join(fragments)+'</main></body></html>'
    (output/"report.html").write_text(document,encoding="utf-8")
    (output/"report.md").write_text("\n".join(markdown),encoding="utf-8")
