import datetime
from io import StringIO
from typing import Dict, TextIO

import talib
from numpy import ndarray
from qtf.indicators import KDJ, MACD

from .datafeed import load_data_msd
from .symbols import symbol_with_name


async def load_raw_data(symbol: str, end_date=None) -> Dict[str, ndarray]:
  if end_date is None:
    end_date = datetime.datetime.now() + datetime.timedelta(days=1)
  if type(end_date) == str:
    end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")

  start_date = end_date - datetime.timedelta(days=365 * 2)

  return await load_data_msd(
    symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")
  )


def build_stock_data(symbol: str, raw_data: Dict[str, ndarray]) -> str:
  md = StringIO()
  build_basic_data(md, symbol, raw_data)
  build_trading_data(md, symbol, raw_data)
  build_technical_data(md, symbol, raw_data)
  build_financial_data(md, symbol, raw_data)

  return md.getvalue()


def filter_sector(sectors: list[str]) -> list[str]:
  keywords = ["MSCI", "标普", "同花顺", "融资融券", "沪股通"]
  # return sectors not including keywords
  return [s for s in sectors if not any(k in s for k in keywords)]


def est_fin_ratio(last_fin_date: datetime.datetime) -> float:
  if last_fin_date.month == 12:
    return 1
  elif last_fin_date.month == 9:
    return 0.75
  elif last_fin_date.month == 6:
    return 0.5
  elif last_fin_date.month == 3:
    return 0.25
  else:
    return 0


def build_basic_data(fp: TextIO, symbol: str, data: Dict[str, ndarray]) -> str:
  print("# 基本数据", file=fp)
  print("", file=fp)
  symbol, name = list(symbol_with_name([symbol]))[0]
  sector = " ".join(filter_sector(data["SECTOR"]))
  data_date = datetime.datetime.fromtimestamp(data["DATE"][-1] / 1e9)
  fin, _ = data["_DS_FINANCE"]
  last_fin_date = datetime.datetime.fromtimestamp(fin["DATE"][-1] / 1e9)
  fin_ratio = est_fin_ratio(last_fin_date)

  print(f"- 股票代码: {symbol}", file=fp)
  print(f"- 股票名称: {name}", file=fp)
  print(f"- 数据日期: {data_date.strftime('%Y-%m-%d')}", file=fp)
  print(f"- 行业概念: {sector}", file=fp)
  print(f"- 市盈率: {(data['CLOSE2'][-1] / data['EPS'][-1]) * fin_ratio:.2f}", file=fp)
  print(f"- 市净率: {data['CLOSE2'][-1] / data['EPSU'][-1] * fin_ratio:.2f}", file=fp)
  print(f"- 净资产收益率: {data['ROE'][-1]:.2f}", file=fp)
  print("", file=fp)


def build_trading_data(fp: TextIO, symbol: str, data: Dict[str, ndarray]) -> str:
  close = data["CLOSE"]
  tcap = data["TCAP"]
  volume = data["VOLUME"]
  high = data["HIGH"]
  low = data["LOW"]

  periods = list(filter(lambda n: n <= len(close), [5, 20, 60, 120, 240]))

  print("# 交易数据", file=fp)
  print("", file=fp)

  print("## 价格", file=fp)
  print(f"- 当日: {close[-1]:.3f} 最高: {high[-1]:.3f} 最低: {low[-1]:.3f}", file=fp)
  for p in periods:
    print(
      f"- {p}日均价: {close[-p:].mean():.3f} 最高: {high[-p:].max():.3f} 最低: {low[-p:].min():.3f}",
      file=fp,
    )
  print("", file=fp)

  print("## 振幅", file=fp)
  print(f"- 当日: {(high[-1] / low[-2] - 1):.2%}", file=fp)
  for p in periods:
    print(f"- {p}日振幅: {(high[-p:].max() / low[-p:].min() - 1):.2%}", file=fp)
  print("", file=fp)

  print("## 涨跌幅", file=fp)
  print(f"- 当日: {(close[-1] / close[-2] - 1):.2%}", file=fp)
  for p in periods:
    print(f"- {p}日累计: {(close[-1] / close[-p] - 1) * 100:.2f}%", file=fp)
  print("", file=fp)

  print("## 成交量(万手)", file=fp)
  print(f"- 当日: {volume[-1] / 1e6:.2f}", file=fp)
  for p in periods:
    print(f"- {p}日均量(万手): {volume[-p:].mean() / 1e6:.2f}", file=fp)
  print("", file=fp)

  print("## 换手率", file=fp)
  print(f"- 当日: {volume[-1] / tcap[-1]:.2%}", file=fp)
  for p in periods:
    print(f"- {p}日均换手: {volume[-p:].mean() / tcap[-1]:.2%}", file=fp)
    print(f"- {p}日总换手: {volume[-p:].sum() / tcap[-1]:.2%}", file=fp)
  print("", file=fp)


def build_technical_data(fp: TextIO, symbol: str, data: Dict[str, ndarray]) -> str:
  close = data["CLOSE"]
  high = data["HIGH"]
  low = data["LOW"]

  if len(close) < 30:
    return

  print("# 技术指标(最近30日)", file=fp)
  print("", file=fp)

  kdj_k, kdj_d, kdj_j = KDJ(close, high, low, 9, 3)

  macd_diff, macd_dea = MACD(close, 12, 26, 9)

  rsi_6 = talib.RSI(close, timeperiod=6)
  rsi_12 = talib.RSI(close, timeperiod=12)
  rsi_24 = talib.RSI(close, timeperiod=24)

  bb_upper, bb_middle, bb_lower = talib.BBANDS(close, matype=talib.MA_Type.T3)

  date = [
    datetime.datetime.fromtimestamp(d / 1e9).strftime("%Y-%m-%d") for d in data["DATE"]
  ]
  columns = [
    ("日期", date),
    ("KDJ.K", kdj_k),
    ("KDJ.D", kdj_d),
    ("KDJ.J", kdj_j),
    ("MACD DIF", macd_diff),
    ("MACD DEA", macd_dea),
    ("RSI(6)", rsi_6),
    ("RSI(12)", rsi_12),
    ("RSI(24)", rsi_24),
    ("BBands Upper", bb_upper),
    ("BBands Middle", bb_middle),
    ("BBands Lower", bb_lower),
  ]
  print("| " + " | ".join([c[0] for c in columns]) + " |", file=fp)
  print("| --- " * len(columns) + "|", file=fp)
  for i in range(-1, max(-len(date), -31), -1):
    print(
      "| " + date[i] + "|" + " | ".join([f"{c[1][i]:.2f}" for c in columns[1:]]) + " |",
      file=fp,
    )
  print("", file=fp)


def build_financial_data(fp: TextIO, symbol: str, data: Dict[str, ndarray]) -> str:
  fin, _ = data["_DS_FINANCE"]
  dates = fin["DATE"]
  max_years = 5
  print("# 财务数据", file=fp)
  print("", file=fp)
  years = 0
  fields = [
    ("主营收入(亿元)", "MR", 10000),
    ("净利润(亿元)", "NP", 10000),
    ("每股收益", "EPS", 1),
    ("每股净资产", "NAVPS", 1),
    ("净资产收益率", "ROE", 1),
  ]

  rows = []
  for i in range(len(dates) - 1, 0, -1):
    date = datetime.datetime.fromtimestamp(dates[i] / 1e9)
    if date.month != 12 or years >= max_years:
      continue
    row = [date.strftime("%Y年度")]
    for _, field, div in fields:
      row.append(fin[field][i] / div)
    rows.append(row)
    years += 1

  print("| 指标 | " + " ".join([f"{r[0]} |" for r in rows]), file=fp)
  print("| --- " * (len(rows) + 1) + "|", file=fp)
  for i in range(1, len(rows[0])):
    print(
      f"| {fields[i - 1][0]} | " + " ".join([f"{r[i]:.2f} |" for r in rows]), file=fp
    )

  print("", file=fp)
