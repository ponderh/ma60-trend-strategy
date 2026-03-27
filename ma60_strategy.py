#!/usr/bin/env python3
"""
MA60趋势择时策略 - 核心模块
"""

import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class MA60Strategy:
    """MA60择时策略"""
    
    def __init__(self, initial_cash=1000000):
        self.initial_cash = initial_cash
        self.position = 0  # 0=空仓, 1=持仓
        self.cash = initial_cash
        self.shares = 0
        
    def login(self):
        """登录baostock"""
        bs.login()
        
    def logout(self):
        """登出baostock"""
        bs.logout()
    
    def get_index_data(self, code='sh.000300', start_date=None, end_date=None):
        """获取指数数据"""
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        rs = bs.query_history_k_data_plus(
            code,
            "date,close",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2"
        )
        
        data = []
        while (rs.error_code == '0') & rs.next():
            data.append(rs.get_row_data())
        
        df = pd.DataFrame(data, columns=rs.fields)
        df['date'] = pd.to_datetime(df['date'])
        df['close'] = df['close'].astype(float)
        
        return df
    
    def calculate_ma60(self, df):
        """计算MA60"""
        df['MA60'] = df['close'].rolling(60).mean()
        return df
    
    def generate_signal(self, df):
        """生成交易信号"""
        latest = df.iloc[-1]
        signal = 1 if latest['close'] > latest['MA60'] else 0
        return signal, latest
    
    def get_current_signal(self, code='sh.000300'):
        """获取当前信号"""
        self.login()
        
        # 获取最近60个交易日的数据
        df = self.get_index_data(code)
        df = self.calculate_ma60(df)
        df = df.dropna()
        
        signal, latest = self.generate_signal(df)
        
        self.logout()
        
        return {
            'code': code,
            'date': latest['date'].strftime('%Y-%m-%d'),
            'close': latest['close'],
            'MA60': latest['MA60'],
            'signal': 'BUY' if signal == 1 else 'SELL',
            'action': '持有510310' if signal == 1 else '持有货币基金'
        }
    
    def run_backtest(self, start_date='2015-01-01', end_date=None):
        """运行回测"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            
        self.login()
        df = self.get_index_data('sh.000300', start_date, end_date)
        self.logout()
        
        df = self.calculate_ma60(df)
        df = df.dropna().reset_index(drop=True)
        
        # 生成信号
        df['signal'] = (df['close'] > df['MA60']).astype(int)
        df['return'] = df['close'].pct_change()
        
        # 策略收益
        df['strategy_return'] = df['return'] * df['signal']
        
        # 扣除成本
        TRANSACTION_COST = 0.0014
        DAILY_COST = 0.00007
        df['strategy_return_net'] = df['strategy_return'] - DAILY_COST
        
        # 累计净值
        df['benchmark_value'] = (1 + df['return']).cumprod() * self.initial_cash
        df['strategy_value'] = (1 + df['strategy_return_net']).cumprod() * self.initial_cash
        
        return df
    
    def get_metrics(self, df):
        """计算绩效指标"""
        final_value = df['strategy_value'].iloc[-1]
        final_benchmark = df['benchmark_value'].iloc[-1]
        
        years = (df['date'].iloc[-1] - df['date'].iloc[0]).days / 365.25
        total_return = (final_value / self.initial_cash - 1) * 100
        annual_return = ((final_value / self.initial_cash) ** (1/years) - 1) * 100
        benchmark_annual = ((final_benchmark / self.initial_cash) ** (1/years) - 1) * 100
        
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
        
        return {
            'initial_cash': self.initial_cash,
            'final_value': final_value,
            'total_return': total_return,
            'annual_return': annual_return,
            'benchmark_annual': benchmark_annual,
            'alpha': annual_return - benchmark_annual,
            'max_drawdown': max_drawdown,
            'sharpe': sharpe,
            'total_trades': trades,
            'holding_days': df['signal'].sum(),
            'holding_ratio': df['signal'].mean() * 100,
            'years': years
        }


def main():
    """主函数"""
    strategy = MA60Strategy()
    
    # 获取当前信号
    print("=" * 60)
    print("MA60趋势择时策略 - 当前信号")
    print("=" * 60)
    
    signal_info = strategy.get_current_signal()
    
    print(f"\n指数代码: {signal_info['code']}")
    print(f"日期: {signal_info['date']}")
    print(f"收盘价: {signal_info['close']:.2f}")
    print(f"MA60: {signal_info['MA60']:.2f}")
    print(f"\n信号: {signal_info['signal']}")
    print(f"操作: {signal_info['action']}")
    
    if signal_info['signal'] == 'BUY':
        print("\n✅ 建议持有510310（沪深300ETF）")
    else:
        print("\n⚠️ 建议持有货币基金，等待买入时机")


if __name__ == '__main__':
    main()
