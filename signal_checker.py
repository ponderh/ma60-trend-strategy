#!/usr/bin/env python3
"""
MA60趋势择时策略 - 当前信号检查

数据来源：baostock（免费，无需API Key）
逻辑：
  - 获取沪深300（sh.000300）最近90个交易日数据
  - 计算MA60
  - 判断收盘价与MA60的关系
  - 输出信号和建议操作
"""

import baostock as bs
import pandas as pd
from datetime import datetime, timedelta


def get_current_signal(code='sh.000300', days=90):
    """
    获取当前MA60择时信号

    参数：
        code: 指数代码（默认沪深300）
        days: 获取最近多少个交易日的数据（默认90，确保有足够计算MA60的数据）

    返回：
        dict: 信号信息
    """
    bs.login()

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days + 30)).strftime('%Y-%m-%d')

    rs = bs.query_history_k_data_plus(
        code,
        "date,code,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="2"
    )

    data = []
    while (rs.error_code == '0') & rs.next():
        data.append(rs.get_row_data())

    bs.logout()

    if not data:
        return {'error': '无法获取数据，请检查网络连接'}

    df = pd.DataFrame(data, columns=rs.fields)
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = df['close'].astype(float)
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df = df.dropna(subset=['close']).sort_values('date').reset_index(drop=True)

    # 计算MA60
    df['ma60'] = df['close'].rolling(60).mean()

    if len(df) < 60:
        return {'error': f'数据不足，仅有{len(df)}个交易日，需要至少60个'}

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    if pd.isna(latest['ma60']):
        return {'error': 'MA60计算结果为空，数据不足'}

    signal = 'BUY' if latest['close'] > latest['ma60'] else 'SELL'

    # 判断趋势
    ma60_trend = '上升' if latest['ma60'] > prev['ma60'] else '下降'
    diff_pct = (latest['close'] - latest['ma60']) / latest['ma60'] * 100

    return {
        'date': latest['date'].strftime('%Y-%m-%d'),
        'prev_date': prev['date'].strftime('%Y-%m-%d'),
        'code': code,
        'close': latest['close'],
        'prev_close': prev['close'],
        'open': latest['open'],
        'high': latest['high'],
        'low': latest['low'],
        'ma60': latest['ma60'],
        'prev_ma60': prev['ma60'],
        'ma60_trend': ma60_trend,
        'diff_pct': diff_pct,
        'signal': signal,
        'prev_signal': 'BUY' if prev['close'] > prev['ma60'] else 'SELL',
        'data_count': len(df),
    }


def print_signal(info):
    """打印信号"""
    if 'error' in info:
        print(f"\n❌ 错误: {info['error']}\n")
        return

    print()
    print("=" * 58)
    print("  MA60大盘择时信号检查")
    print("=" * 58)
    print(f"  检查日期:  {info['date']}（前一交易日: {info['prev_date']}）")
    print("-" * 58)
    print(f"  指数代码:  {info['code']}（沪深300）")
    print(f"  收盘价:    {info['close']:.2f}")
    print(f"  MA60:      {info['ma60']:.2f}  ({info['ma60_trend']})")
    print(f"  偏离度:    {info['diff_pct']:+.2f}%")
    print("-" * 58)
    print(f"  当前信号:  【{info['signal']}】")
    print(f"  前日信号:  【{info['prev_signal']}】")
    print("=" * 58)

    if info['signal'] == 'BUY':
        print(f"  ✅ 建议: 持有510310（沪深300ETF）")
        print(f"     收盘价 {info['close']:.2f} > MA60 {info['ma60']:.2f}")
        if info['prev_signal'] == 'SELL':
            print(f"     ⚡ 昨日发生金叉！次日在开盘价买入510310")
    else:
        print(f"  ⚠️  建议: 持有货币基金，等待买入时机")
        print(f"     收盘价 {info['close']:.2f} < MA60 {info['ma60']:.2f}")
        if info['prev_signal'] == 'BUY':
            print(f"     ⚡ 昨日发生死叉！次日在开盘价卖出510310")
    print("=" * 58)
    print()


def main():
    print("正在获取MA60择时信号...")
    info = get_current_signal()
    print_signal(info)
    return info


if __name__ == '__main__':
    main()
