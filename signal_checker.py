#!/usr/bin/env python3
"""
MA60信号检查工具
检查当前沪深300指数的MA60择时信号
"""

import baostock as bs
import pandas as pd
from datetime import datetime

def check_signal():
    """检查当前信号"""
    print("=" * 70)
    print("MA60择时信号检查")
    print("=" * 70)
    
    # 登录
    bs.login()
    
    # 获取最近60个交易日数据
    rs = bs.query_history_k_data_plus(
        "sh.000300",
        "date,open,high,low,close,volume",
        start_date=(datetime.now() - pd.Timedelta(days=100)).strftime('%Y-%m-%d'),
        end_date=datetime.now().strftime('%Y-%m-%d'),
        frequency="d",
        adjustflag="2"
    )
    
    data = []
    while (rs.error_code == '0') & rs.next():
        data.append(rs.get_row_data())
    
    df = pd.DataFrame(data, columns=rs.fields)
    bs.logout()
    
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = df['close'].astype(float)
    df['MA60'] = df['close'].rolling(60).mean()
    
    # 获取最新数据
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    # 计算信号
    signal = 'BUY' if latest['close'] > latest['MA60'] else 'SELL'
    
    print(f"\n检查日期: {latest['date'].strftime('%Y-%m-%d')}")
    print(f"沪深300收盘: {latest['close']:.2f}")
    print(f"MA60: {latest['MA60']:.2f}")
    print(f"信号: {signal}")
    print()
    
    # 显示近期数据
    print("-" * 70)
    print("近期数据 (最近10个交易日):")
    print("-" * 70)
    print(f"{'日期':<12} {'收盘':>10} {'MA60':>10} {'信号':>6}")
    print("-" * 70)
    
    for _, row in df.tail(10).iterrows():
        ma60_val = row['MA60'] if pd.notna(row['MA60']) else 0
        sig = 'BUY' if row['close'] > ma60_val else 'SELL'
        print(f"{row['date'].strftime('%Y-%m-%d'):<12} {row['close']:>10.2f} {ma60_val:>10.2f} {sig:>6}")
    
    # 建议
    print()
    print("=" * 70)
    if signal == 'BUY':
        print("✅ 建议: 持有510310（沪深300ETF）")
        print("   收盘价 > MA60，市场处于多头趋势")
    else:
        print("⚠️ 建议: 持有货币基金，等待买入时机")
        print("   收盘价 < MA60，市场处于空头趋势")
    print("=" * 70)
    
    return signal


if __name__ == '__main__':
    check_signal()
