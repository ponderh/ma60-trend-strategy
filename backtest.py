#!/usr/bin/env python3
"""
MA60择时策略 - 回测引擎
验证策略在历史数据上的表现
"""

import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime
import json

def run_backtest(start_date='2015-01-01', end_date=None, initial_cash=1000000):
    """运行回测"""
    
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    print("=" * 70)
    print("MA60择时策略 - 历史回测")
    print("=" * 70)
    print(f"\n回测区间: {start_date} ~ {end_date}")
    print(f"初始资金: {initial_cash:,.0f}元")
    
    # 获取数据
    print("\n[1] 获取沪深300数据...")
    bs.login()
    
    rs = bs.query_history_k_data_plus(
        "sh.000300",
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
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
    
    print(f"  数据量: {len(df)}条")
    
    # 计算MA60
    print("\n[2] 计算MA60...")
    df['MA60'] = df['close'].rolling(60).mean()
    df['signal'] = (df['close'] > df['MA60']).astype(int)
    df['return'] = df['close'].pct_change()
    df = df.dropna().reset_index(drop=True)
    print(f"  有效数据: {len(df)}条")
    
    # 计算收益
    print("\n[3] 计算回测收益...")
    df['strategy_return'] = df['return'] * df['signal']
    
    # 成本
    TRANSACTION_COST = 0.0014
    DAILY_COST = 0.00007
    df['strategy_return_net'] = df['strategy_return'] - DAILY_COST
    
    # 累计净值
    df['benchmark_value'] = (1 + df['return']).cumprod() * initial_cash
    df['strategy_value'] = (1 + df['strategy_return_net']).cumprod() * initial_cash
    
    # 计算指标
    print("\n[4] 计算绩效指标...")
    
    final_value = df['strategy_value'].iloc[-1]
    final_benchmark = df['benchmark_value'].iloc[-1]
    
    years = (df['date'].iloc[-1] - df['date'].iloc[0]).days / 365.25
    total_return = (final_value / initial_cash - 1) * 100
    annual_return = ((final_value / initial_cash) ** (1/years) - 1) * 100
    benchmark_annual = ((final_benchmark / initial_cash) ** (1/years) - 1) * 100
    
    # 最大回撤
    peak = df['strategy_value'].cummax()
    drawdown = (df['strategy_value'] - peak) / peak
    max_drawdown = drawdown.min() * 100
    
    # 夏普比率
    daily_returns = df['strategy_value'].pct_change().dropna()
    excess_return = daily_returns.mean() * 252 - 0.03
    volatility = daily_returns.std() * np.sqrt(252)
    sharpe = excess_return / volatility if volatility > 0 else 0
    
    # 交易次数
    trades = (df['signal'].diff() != 0).sum()
    
    # 输出结果
    print("\n" + "=" * 70)
    print("回测结果")
    print("=" * 70)
    
    print(f"\n{'指标':<20} {'策略':>15} {'买入持有':>15}")
    print("-" * 70)
    print(f"{'最终市值':<20} {final_value:>14,.0f} {final_benchmark:>14,.0f}")
    print(f"{'总收益率':<20} {total_return:>14.1f}% {((final_benchmark/initial_cash-1)*100):>14.1f}%")
    print(f"{'年化收益率':<20} {annual_return:>14.1f}% {benchmark_annual:>14.1f}%")
    print(f"{'超额收益(Alpha)':<20} {annual_return-benchmark_annual:>14.1f}% {'-':>15}")
    print(f"{'最大回撤':<20} {max_drawdown:>14.1f}% {((df['benchmark_value']/df['benchmark_value'].cummax()-1).min()*100):>14.1f}%")
    print(f"{'夏普比率':<20} {sharpe:>15.2f} {'-':>15}")
    print(f"{'持仓时间比例':<20} {df['signal'].mean()*100:>14.0f}% {'100':>14.0f}%")
    print(f"{'交易次数':<20} {trades:>15}次 {'0':>14}次")
    print("-" * 70)
    
    # 年度分析
    print("\n" + "=" * 70)
    print("年度收益对比")
    print("=" * 70)
    
    df['year'] = df['date'].dt.year
    yearly_benchmark = df.groupby('year').apply(
        lambda x: (x['benchmark_value'].iloc[-1] / x['benchmark_value'].iloc[0] - 1) * 100
    )
    yearly_strategy = df.groupby('year').apply(
        lambda x: (x['strategy_value'].iloc[-1] / x['strategy_value'].iloc[0] - 1) * 100
    )
    
    print(f"\n{'年份':<8} {'MA60择时':>12} {'买入持有':>12} {'超额':>10} {'状态'}")
    print("-" * 60)
    
    win_count = 0
    for year in sorted(yearly_strategy.index):
        excess = yearly_strategy[year] - yearly_benchmark[year]
        win = "✅" if excess > 0 else "❌"
        if excess > 0:
            win_count += 1
        status = "持仓" if df[df['year']==year]['signal'].mean() > 0.5 else "空仓"
        print(f"{year:<8} {yearly_strategy[year]:>10.1f}% {yearly_benchmark[year]:>10.1f}% {excess:>+8.1f}% {win} {status}")
    
    print("-" * 60)
    print(f"年度胜率: {win_count}/{len(yearly_strategy)} ({win_count/len(yearly_strategy)*100:.0f}%)")
    
    # 目标达成
    print("\n" + "=" * 70)
    print("目标达成情况")
    print("=" * 70)
    
    target_return = 20
    target_drawdown = 20
    
    return_ok = "✅" if annual_return >= target_return else "❌"
    dd_ok = "✅" if abs(max_drawdown) <= target_drawdown else "❌"
    sharpe_ok = "✅" if sharpe >= 1 else "⚠️"
    
    print(f"\n  年化收益 {annual_return:.1f}% (目标>{target_return}%) {return_ok}")
    print(f"  最大回撤 {max_drawdown:.1f}% (目标<{target_drawdown}%) {dd_ok}")
    print(f"  夏普比率 {sharpe:.2f} {sharpe_ok}")
    
    if annual_return >= target_return and abs(max_drawdown) <= target_drawdown:
        print("\n🎉 策略达标!")
    
    # 保存结果
    result = {
        'strategy': 'MA60择时',
        'start_date': start_date,
        'end_date': end_date,
        'initial_cash': initial_cash,
        'final_value': float(final_value),
        'total_return': float(total_return),
        'annual_return': float(annual_return),
        'benchmark_annual': float(benchmark_annual),
        'alpha': float(annual_return - benchmark_annual),
        'max_drawdown': float(max_drawdown),
        'sharpe': float(sharpe),
        'total_trades': int(trades),
        'holding_ratio': float(df['signal'].mean() * 100),
        'win_rate': float(win_count / len(yearly_strategy) * 100)
    }
    
    with open('backtest_result.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n结果已保存: backtest_result.json")
    print("=" * 70)
    
    return result


if __name__ == '__main__':
    run_backtest()
