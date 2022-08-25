from datetime import date as dt
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
from IPython.display import display
from tabulate import tabulate

__author__ = ['Dr. Usman Kayani']

MAIN_URL = 'https://www.passport.service.gov.uk/urgent/'
session = requests.Session()
session.headers = {    
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
}

def form_data(data: dict) -> str:
    """Form the data for a POST request.

    Args:
        data: dict
            The data to form.
    """
    return '&'.join(['{}={}'.format(k, v) for k, v in data.items()])

def get_token(data: str) -> dict:
    soup = BeautifulSoup(data.text, 'html.parser')
    token_data = soup.find('input', {'name': 'x-csrf-token'})
    if token_data:
        csrf_token = token_data.get('value')
        return csrf_token
    else:
        return None

def get_appointment_data(MAIN_URL) -> pd.DataFrame:
    form_datas = [
        {'is-uk-application' : 'true'},
        {
            'date-of-birth-day' : '01',
            'date-of-birth-month' : '01',
            'date-of-birth-year' : '1990',
        },
        {'previous-passport' : 'true'},
        {'passport-lost': 'false'},
        {'name-changed' : 'false'},
        {
            'passport-issue-day' : '01',
            'passport-issue-month' : '01',
            'passport-issue-year' : '2010',
        },
        {'damaged' : 'false'},
        {'other-passports' : 'false'},
        {},
        {},
    ]

    start_urls = [
        MAIN_URL, 
        'https://www.passport.service.gov.uk/filter/start/urgent'
    ]

    for url in start_urls:
        data = session.get(url)

    no_appt_text = 'Sorry, there are no available appointments'
    if no_appt_text in data.text:
        return no_appt_text

    csrf_token = get_token(data)
    curr_url = data.url

    form_headers = {
        'Referer': 'https://www.passport.service.gov.uk/filter/overseas',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': '72',
        'Origin': 'https://www.passport.service.gov.uk'
    }
    session.headers.update(form_headers)

    for form in form_datas:
        data = session.post(
            curr_url, 
            data=form_data({**form, 'x-csrf-token': csrf_token}), 
            allow_redirects=True
        )
        curr_url = data.url
        csrf_token = get_token(data)

    session.headers = dict(set(session.headers.items()) - set(form_headers.items()))
    curr_year = dt.today().year

    first_page = f'https://www.passport.service.gov.uk/booking/choose-date-and-place/{curr_year}-01-01/previous'
    data = session.get(first_page)

    df = pd.read_html(data.text)[0]
    last_date = datetime.strptime(df.columns[-1], '%A  %d %B') + timedelta(days=1)
    start_dates = [
        (last_date + timedelta(days=7*i)).strftime(f'{curr_year}-%m-%d')
        for i in range(3)
    ]

    for date in start_dates:
        first_page = f'https://www.passport.service.gov.uk/booking/choose-date-and-place/{date}/next'
        data = session.get(first_page)
        try:
            curr_df = pd.read_html(data.text)[0]
        except:
            pass

    return clean_df(pd.concat([df, curr_df], axis=1))

def clean_df(df) -> pd.DataFrame:
    locations = [
        "London", 
        "Peterborough", 
        "Newport", 
        "Liverpool", 
        "Durham", 
        "Glasgow", 
        "Belfast", 
    ]
    df.index = locations

    for x in locations:
        df = df.replace(x, '', regex=True)

    df = df.replace(' Unavailable', 0, regex=True)
    df = df.replace(' Available', 1, regex=True)
        
    return df.loc[:, ~df.columns.duplicated()]

if __name__ == '__main__':
    data = get_appointment_data(MAIN_URL)
    if isinstance(data, pd.DataFrame):
        display(tabulate(data, headers='keys', tablefmt='psql'))
    else:
        print(data)
