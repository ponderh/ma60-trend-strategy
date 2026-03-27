#!/usr/bin/env python3
"""
MA60信号检查工具 - 使用510310 ETF真实价格计算MA60
注意：策略使用510310 ETF的真实价格计算MA60，而不是沪深300指数点位
"""

import akshare as ak
import pandas as pd
from datetime import datetime

def check_signal():
    """检查当前信号"""
    print("=" * 70)
    print("MA60择时信号检查 (510310 ETF)")
    print("=" * 70)
    
    # 获取510310历史数据
    etf_df = ak.fund_etf_hist_em(
        symbol="510310", 
        period="daily", 
        start_date="20230101",  # 需要至少60天数据计算MA60
        end_date=datetime.now().strftime('%Y%m%d'), 
        adjust="qfq"
    )
    
    etf_df['日期'] = pd.to_datetime(etf_df['日期'])
    etf_df = etf_df.set_index('日期').sort_index()
    etf_df['收盘'] = etf_df['收盘'].astype(float)
    
    # 计算MA60 (基于ETF真实价格)
    etf_df['MA60'] = etf_df['收盘'].rolling(60).mean()
    
    # 获取最新数据
    latest = etf_df.iloc[-1]
    prev = etf_df.iloc[-2] if len(etf_df) > 1 else latest
    
    signal = 'BUY' if latest['收盘'] > latest['MA60'] else 'SELL'
    prev_signal = 'BUY' if prev['收盘'] > prev['MA60'] else 'SELL'
    
    print(f"\n检查日期: {latest.name.strftime('%Y-%m-%d')}")
    print(f"ETF代码: 510310 (沪深300ETF)")
    print(f"收盘价: {latest['收盘']:.3f}")
    print(f"MA60: {latest['MA60']:.3f}")
    print(f"信号: {signal}")
    
    # 信号变化提示
    if signal != prev_signal:
        if signal == 'BUY':
            print("\n🔔 信号变化: SELL → BUY")
        else:
            print("\n🔔 信号变化: BUY → SELL")
    
    # 显示近期数据
    print("\n" + "-" * 70)
    print("近期数据 (最近10个交易日):")
    print("-" * 70)
    print(f"{'日期':<12} {'收盘':>8} {'MA60':>8} {'信号':>6}")
    print("-" * 70)
    
    for _, row in etf_df.tail(10).iterrows():
        ma = row['MA60'] if pd.notna(row['MA60']) else 0
        sig = 'BUY' if row['收盘'] > ma else 'SELL'
        print(f"{row.name.strftime('%Y-%m-%d'):<12} {row['收盘']:>8.3f} {ma:>8.3f} {sig:>6}")
    
    # 建议
    print()
    print("=" * 70)
    if signal == 'BUY':
        print("✅ 建议: 持有510310（沪深300ETF）")
        print("   收盘价 > MA60，ETF处于多头趋势")
    else:
        print("⚠️ 建议: 持有货币基金，等待买入时机")
        print("   收盘价 < MA60，ETF处于空头趋势")
    print("=" * 70)
    
    return signal


if __name__ == '__main__':
    check_signal()
