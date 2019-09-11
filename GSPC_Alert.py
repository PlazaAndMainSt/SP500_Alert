import pandas as pd
import numpy as np
import yfinance as yf
import keyring
import datetime as dt
import smtplib

uname = 'your_username'
upass = keyring.get_password('Main', uname)
web_proxy = 'http://{u}:{p}@yourproxy.domain.com:80'.format(u=uname, p=upass)

start_date = dt.datetime.today().date() - dt.timedelta(365*10)
end_date = dt.datetime.today().date() - dt.timedelta(1)
threshold = 0.975

# Get the data from Yahoo Finance
#data = yf.download(tickers='^GSPC', start=start_date, end=end_date, proxy=web_proxy)
data = yf.download(tickers='^GSPC', period='10y', proxy=web_proxy)
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

send_frame = sp500_close.tail(1)
send_frame = send_frame.reset_index()
send_frame.columns = ['Date','S&P500', 'TTM Avg', 'Variance', 'Compare', 'Streak', 'Alert']
send_frame['Date'] = send_frame['Date'].dt.strftime('%m/%d/%Y')
send_frame = send_frame.T

email_conn = smtplib.SMTP(r'smtp address', 587)
email_conn.ehlo()
email_conn.starttls()
email_conn.login(uname, upass)
emailFROM = 'yourname@emaildomain.com'
emailTO =  ['yourname@emaildomain.com']
emailNOTE = '''\n\nNOTES:\nUsing 97.5% of TTM Avg as threshold
S&P500   --> S&P 500 Index (^GSPC)
TTM Avg  --> 12 month moving average
Variance --> Comparison to threshold
Compare  --> Above or Below threshold?
Streak   --> # of days currently in state
Alert    --> Buy or sell alert'''
emailtext = 'Subject: Automated S&P 500 Update\n\n'+ send_frame.to_string() + emailNOTE +'\n\nAutoEmail'
email_conn.sendmail(emailFROM, emailTO, emailtext)
print('Email sent')
