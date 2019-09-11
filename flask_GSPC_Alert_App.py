

from flask import Flask
import pandas as pd
import numpy as np
import yfinance as yf
import datetime as dt
import pytz
import matplotlib.pyplot as plt
pd.plotting.register_matplotlib_converters()

est = pytz.timezone('US/Eastern')

app = Flask(__name__)

@app.route('/')

def print_GSPC_Alert():
    start_date = dt.datetime.today().date() - dt.timedelta(365*21 + 21/4)
    end_date = dt.datetime.today().date() - dt.timedelta(1)
    threshold = 0.975

    # Get the data from Yahoo Finance
    #data = yf.download(tickers='^GSPC', start=start_date, end=end_date)
    data = yf.download(tickers='^GSPC', period='21y')

    # Clean up the data and add the triggers
    sp500_close = data[['Close']].copy(deep=True)
    idx = pd.date_range(start_date, end_date)
    sp500_close = sp500_close.reindex(idx, fill_value=np.nan)
    sp500_close.fillna(method='ffill', inplace=True)
    sp500_close.loc[:,'T12M_Close'] = sp500_close['Close'].rolling(365).mean()
    sp500_close.loc[:,'T12M_Compare'] = sp500_close['Close']/(sp500_close['T12M_Close'] * threshold) - 1
    sp500_close.loc[:,'Compare_Cat'] = np.where(sp500_close.loc[:,'T12M_Compare']>=0,'Above', 'Below')

    sp500_close = sp500_close[365:].copy(deep=True)
    sign = np.sign(sp500_close['T12M_Compare'][1:])
    s = sign.groupby((sign!=sign.shift()).cumsum()).cumsum()
    sp500_close.loc[:,'above_streak']=s.where(s>0, 0.0)
    sp500_close.loc[:,'below_streak']=s.where(s<0, 0.0).abs()
    sp500_close.loc[:,'Current_Streak'] = sp500_close['above_streak'] + sp500_close['below_streak']

    #sp500_close.loc[:,'Alert'] = np.where(sp500_close.loc[:,'Current_Streak']>=14,np.where(sp500_close.loc[:,'Compare_Cat']=='Below','***** SELL *****', '***** BUY *****'), '***** BUY *****')
    sp500_close.loc[:,'Alert'] = np.where(sp500_close.loc[:,'Current_Streak']>=14,np.where(sp500_close.loc[:,'Compare_Cat']=='Below','***** SELL *****', '***** HOLD *****'), np.where(sp500_close.loc[:,'Compare_Cat']=='Above','***** BUY *****', '***** WATCH FOR SELL *****'))
    sp500_close = sp500_close.drop(['above_streak', 'below_streak'], axis=1)

    # Do What if analysis on investing 20 years ago
    sp500_close.loc[:,'SELL_TRIGGER'] = np.where(sp500_close.loc[:,'Alert']=='***** SELL *****',5000, 0)
    sp500_close['BUY_HOLD'] = sp500_close['Close']
    sp500_close['INV_SHARES'] = 0
    sp500_close['INV_VALUE'] = 0
    sp500_close['INV_CASH'] = 0
    sp500_close['INV_TOTAL'] = 0
    sp500_close.iloc[0,8] = 1

    for row in range(1,len(sp500_close)):
        if sp500_close.iloc[row, 5] == '***** SELL *****':
            # Sell shares to cash, set shares to zero
            sp500_close.iloc[row, 10] = sp500_close.iloc[row-1, 8]*sp500_close.iloc[row, 0] + sp500_close.iloc[row-1, 10]
            sp500_close.iloc[row, 8] = 0
        elif sp500_close.iloc[row, 5] == '***** BUY *****':
            # Use cash to buy shares, set cash to zero
            sp500_close.iloc[row, 8] = sp500_close.iloc[row-1, 10]/sp500_close.iloc[row, 0] + sp500_close.iloc[row-1, 8]
            sp500_close.iloc[row, 10] = 0
        else:
            sp500_close.iloc[row, 8] = sp500_close.iloc[row-1, 8]
            sp500_close.iloc[row, 10] = sp500_close.iloc[row-1, 10] * (1 + (0.01/365))  # Cash earns 1% APY while waiting

    sp500_close.loc[:, 'INV_VALUE'] = sp500_close.loc[:, 'Close']*sp500_close.loc[:, 'INV_SHARES']
    sp500_close.loc[:, 'INV_TOTAL'] = sp500_close.loc[:, 'INV_VALUE'] + sp500_close.loc[:, 'INV_CASH']

    plt.figure()
    fig, ax1 = plt.subplots(figsize=(12,8), sharey=True)
    x = sp500_close.index
    y1 = sp500_close['BUY_HOLD']
    y2 = sp500_close['INV_TOTAL']
    y3 = sp500_close['SELL_TRIGGER']

    ax1.bar(x, y3, alpha=0.5, width = 0.99, color='r', label='Sell Alert')

    #ax2 = ax1.twinx(sharey=True)
    ax1.plot(x, y1, color='b', label='Buy & Hold')
    ax1.plot(x, y2, color='k', label='Invested')

    plt.annotate('${:,.0f}'.format(y1[0]), (x[0],y1[0]), bbox=dict(boxstyle="round", fc="none", ec="green"), xytext=(0, 40), textcoords='offset points', ha='center', arrowprops=dict(arrowstyle="->", color='green', linestyle='dashed'))
    plt.annotate('${:,.0f}'.format(y1[-1]), (x[-1],y1[-1]*0.95), bbox=dict(boxstyle="round", fc="none", ec="green"), xytext=(0, -40), textcoords='offset points', ha='center', arrowprops=dict(arrowstyle="->", color='green', linestyle='dashed'))
    plt.annotate('${:,.0f}'.format(y2[-1]), (x[-1],y2[-1]*1.01), bbox=dict(boxstyle="round", fc="none", ec="green"), xytext=(0, 40), textcoords='offset points', ha='center', arrowprops=dict(arrowstyle="->", color='green', linestyle='dashed'))

    plt.title('Buying 1 Share of S&P 500 Index 20 Years Ago: Method Comparison')
    plt.ylabel('Investment Value')
    plt.xlabel('Year')
    plt.legend(loc=2)
    fig.savefig('Invest_WhatIf_20Yr.png')

    send_frame = pd.DataFrame(sp500_close.iloc[-1, 0:6]).T
    send_frame = send_frame.reset_index()
    send_frame.columns = ['Date','S&P500', 'TTM Avg', 'Variance', 'Compare', 'Streak', 'Alert']
    send_frame['Date'] = send_frame['Date'].dt.strftime('%m/%d/%Y')
    send_frame = send_frame.T
    send_frame.columns = [""]

    return '''<html>
            <h1>Automated S&P 500 Update</h1>
            <body>

                <p>{txt}</p>
                <p> </p>
                <h3>NOTES: </h3>
                <ul>
                    <li>S&P500   --> S&P 500 Index (^GSPC)</li>
                    <li>TTM Avg  --> 12 month moving average</li>
                    <li>Threshold --> Using 97.5% of TTM Avg as threshold
                    <li>Variance --> Comparison to threshold</li>
                    <li>Compare  --> Above or Below threshold?</li>
                    <li>Streak   --> # of days currently in state</li>
                    <li>Alert    --> Buy or sell alert</li>
                </ul>
                <h3>CONCEPT </h3>
                <p>Today's S&P 500 Index price is compared against the trailing 12-month average close price.
                                If that ratio is above 97.5%, you should either buy or hold the stock (given your current situation).
                                If that ratio is below 97.5% for more than 14 days in a row, you should sell the stock and hold the cash in a savings account.
                                Once the alert shows BUY again, you should repurchase the stock with the cash on hand, having hopefully skipped the extended downturn.
                                DISCLAIMER: this is for entertainment purposes only and does not constitute investment advice in any capacity.
                <p> Last Run: {eff_dt} EST</p>
                <p> <img src="Invest_WhatIf_20Yr.png" width="800" height="600" alt="graph"> </p>
            </body>
        </html>
        '''.format(txt=send_frame.to_html(), eff_dt=(dt.datetime.now().astimezone(est)).strftime('%m/%d/%Y %I:%M%p'))


