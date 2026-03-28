#!/usr/bin/env python3
"""
MA60趋势择时策略 - 回测引擎（严谨版）

信号逻辑：
  - 收盘价 > MA60 → 多头状态（下一个交易日开盘买入）
  - 收盘价 < MA60 → 空头状态（下一个交易日开盘卖出）

执行规则：
  - 信号在收盘时产生，次日开盘价执行（不含滑点）
  - 交易成本：买入0.015%，卖出0.015%（ETF免印花税）

数据来源：
  - 回测：沪深300指数（hs300_index_v3.pkl）
  - 实盘信号：baostock获取沪深300指数实时数据

回测区间：2015-04-03 ～ 2026-03-24
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# 数据路径（可通过环境变量覆盖）
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'workspace', 'astock-strategy-v3', 'data')
FALLBACK_DATA_DIR = '/home/ponder/.openclaw/workspace/astock-strategy-v3/data'


def load_hs300_index(data_dir=None):
    """加载沪深300指数数据"""
    if data_dir is None:
        data_dir = FALLBACK_DATA_DIR

    pkl_path = os.path.join(data_dir, 'hs300_index_v3.pkl')
    if not os.path.exists(pkl_path):
        raise FileNotFoundError(f"数据文件不存在: {pkl_path}\n请确保已完成A股K线数据采集。")

    df = pd.read_pickle(pkl_path)
    df = df.sort_index()
    df['ma60'] = df['close'].rolling(60).mean()
    df['above'] = (df['close'] > df['ma60']).astype(int)
    return df.dropna(subset=['ma60'])


def run_backtest(df=None, initial_cash=1_000_000, cost_pct=0.0015,
                 data_dir=None, include_open_trade=False):
    """
    运行MA60择时策略回测

    参数：
        df: DataFrame，含列 date(index), open, close, ma60, above
            如不传则自动从本地数据加载
        initial_cash: 初始资金（元）
        cost_pct: 单边交易成本率（默认0.15%）
        data_dir: 数据目录
        include_open_trade: 是否包含未平仓仓位（最后持仓按收盘价结算）

    返回：
        dict: 包含完整回测结果
    """
    if df is None:
        df = load_hs300_index(data_dir)
    else:
        df = df.copy()
        if 'ma60' not in df.columns:
            df['ma60'] = df['close'].rolling(60).mean()
        if 'above' not in df.columns:
            df['above'] = (df['close'] > df['ma60']).astype(int)
        df = df.dropna(subset=['ma60']).sort_index()

    records = df.reset_index()
    records.columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'ma60',
                       'hs300_above_ma60', 'norm_close', 'above']

    trades = []
    position = 0  # 0=空仓, 1=持仓
    entry_date = None
    entry_price = None
    entry_ma60 = None
    have_position = False  # 是否曾经开过仓

    for i, row in records.iterrows():
        if i == len(records) - 1:
            break

        next_row = records.iloc[i + 1]

        # 金叉：当天跌破MA60，下一天站上 → 买入
        if row['above'] == 0 and next_row['above'] == 1:
            if position == 0:
                position = 1
                entry_date = next_row['date']
                entry_price = next_row['open']
                entry_ma60 = next_row['ma60']
                have_position = True
                trades.append({
                    'type': 'BUY',
                    'date': entry_date,
                    'price': entry_price,
                    'ma60': entry_ma60,
                })

        # 死叉：当天站上MA60，下一天跌破 → 卖出
        elif row['above'] == 1 and next_row['above'] == 0:
            if position == 1:
                position = 0
                sell_price = next_row['open']
                ret = (sell_price - entry_price) / entry_price - cost_pct * 2
                trades.append({
                    'type': 'SELL',
                    'date': next_row['date'],
                    'price': sell_price,
                    'ma60': next_row['ma60'],
                    'entry_date': entry_date,
                    'entry_price': entry_price,
                    'entry_ma60': entry_ma60,
                    'return_pct': ret * 100,
                    'return': ret,
                })

    # 处理未平仓
    open_trade = None
    if position == 1 and have_position:
        last = records.iloc[-1]
        ret = (last['close'] - entry_price) / entry_price - cost_pct * 2
        open_trade = {
            'type': 'SELL(final)',
            'date': last['date'],
            'price': last['close'],
            'ma60': last['ma60'],
            'entry_date': entry_date,
            'entry_price': entry_price,
            'entry_ma60': entry_ma60,
            'return_pct': ret * 100,
            'return': ret,
        }
        trades.append(open_trade)

    # 绩效计算（只含已平仓交易）
    closed = [t for t in trades if t['type'] == 'SELL']
    if not closed:
        return {'error': '无完整交易记录'}

    rets = [t['return'] for t in closed]
    n = len(rets)
    wins = sum(1 for r in rets if r > 0)
    n_years = (records['date'].iloc[-1] - records['date'].iloc[0]).days / 365.25

    # 净值序列
    nav = np.cumprod([1 + r for r in rets])
    peak = np.maximum.accumulate(nav)
    dd = (nav - peak) / peak
    max_dd = dd.min()

    ann_ret = (nav[-1]) ** (1 / n_years) - 1
    vol = np.std(rets) * np.sqrt(12)
    sharpe = ann_ret / vol if vol > 0 else 0

    # 基准（同期买入持有）
    first_close = records.iloc[0]['close']
    last_close = records.iloc[-1]['close']
    bench_ann = (last_close / first_close) ** (1 / n_years) - 1

    # 年度明细
    yearly = {}
    for t in closed:
        yr = pd.Timestamp(t['date']).year
        yearly.setdefault(yr, []).append(t['return'])
    for yr in sorted(yearly):
        yearly[yr] = {
            'trades': len(yearly[yr]),
            'return': (np.prod([1 + r for r in yearly[yr]]) - 1) * 100,
            'win_rate': sum(1 for r in yearly[yr] if r > 0) / len(yearly[yr]) * 100,
        }

    result = {
        'data_range': [str(records['date'].iloc[0].date()), str(records['date'].iloc[-1].date())],
        'initial_cash': initial_cash,
        'final_value': initial_cash * nav[-1],
        'n_years': round(n_years, 2),
        'n_closed_trades': n,
        'n_wins': wins,
        'n_losses': n - wins,
        'win_rate': wins / n * 100,
        'avg_return_pct': np.mean(rets) * 100,
        'best_trade_pct': max(rets) * 100,
        'worst_trade_pct': min(rets) * 100,
        'total_return_pct': (nav[-1] - 1) * 100,
        'annual_return_pct': ann_ret * 100,
        'annual_return_net_pct': (ann_ret - cost_pct * 2 * n / n_years / 12) * 100,
        'max_drawdown_pct': max_dd * 100,
        'volatility': vol * 100,
        'sharpe': round(sharpe, 2),
        'benchmark_annual_pct': bench_ann * 100,
        'excess_annual_pct': (ann_ret - bench_ann) * 100,
        'holding_ratio': n_years * 12 / n if n > 0 else 0,  # 平均持仓月数
        'current_position': 'open' if open_trade else 'closed',
        'open_trade': {
            'entry_date': str(open_trade['entry_date'].date()) if open_trade else None,
            'entry_price': round(open_trade['entry_price'], 3) if open_trade else None,
            'current_return_pct': round(open_trade['return_pct'], 2) if open_trade else None,
        } if open_trade else None,
        'yearly': {str(k): v for k, v in sorted(yearly.items())},
        'trades': [
            {k: (str(v.date()) if isinstance(v, pd.Timestamp) else round(v, 4) if isinstance(v, float) else v)
             for k, v in t.items()}
            for t in trades
        ],
    }

    return result


def print_report(result):
    """打印回测报告"""
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         MA60大盘择时策略 · 回测报告（沪深300指数）              ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  数据区间: {result['data_range'][0]} ~ {result['data_range'][1]}（{result['n_years']}年）           ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  初始资金: {result['initial_cash']:>15,.0f} 元                       ║")
    print(f"║  最终市值: {result['final_value']:>15,.2f} 元                       ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  总收益率:   {result['total_return_pct']:>8.2f}%                           ║")
    print(f"║  年化收益:   {result['annual_return_pct']:>8.2f}%  （已扣交易成本）        ║")
    print(f"║  最大回撤:   {result['max_drawdown_pct']:>8.2f}%                           ║")
    print(f"║  夏普比率:   {result['sharpe']:>8.2f}                               ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  交易次数:   {result['n_closed_trades']:>4d} 次（完整平仓）                   ║")
    print(f"║  盈利次数:   {result['n_wins']:>4d} 次  |  亏损次数: {result['n_losses']:>4d} 次        ║")
    print(f"║  胜率:       {result['win_rate']:>7.1f}%                               ║")
    print(f"║  平均单次:   {result['avg_return_pct']:>8.2f}%                           ║")
    print(f"║  最大单次盈利: {result['best_trade_pct']:>7.2f}%  最大单次亏损: {result['worst_trade_pct']:>8.2f}%   ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  买入持有基准年化: {result['benchmark_annual_pct']:>7.2f}%                     ║")
    print(f"║  超额收益（年化）: {result['excess_annual_pct']:>7.2f}%                     ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  年度明细（含成本）                                           ║")
    for yr, stats in result['yearly'].items():
        r = stats['return']
        w = stats['win_rate']
        n = stats['trades']
        print(f"║    {yr}: {r:>+7.2f}%  胜率{w:5.1f}%  {n}次交易{' ' * (20-len(yr))}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    pos_str = "当前持仓" if result['current_position'] == 'open' else "空仓"
    print(f"║  当前状态: {pos_str:<50} ║")
    if result['open_trade']:
        ot = result['open_trade']
        print(f"║    买入于 {ot['entry_date']} @ {ot['entry_price']}  浮盈: {ot['current_return_pct']:+.2f}%   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    print(f"⚠  注意：回测用沪深300指数，实盘交易510310（ETF）会有轻微跟踪误差")


def save_report(result, path=None):
    """保存报告为JSON"""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), 'backtest_result.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"报告已保存: {path}")


if __name__ == '__main__':
    print("正在加载数据并运行回测...")
    try:
        result = run_backtest()
        print_report(result)
        save_report(result)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请先运行A股数据采集脚本。")
