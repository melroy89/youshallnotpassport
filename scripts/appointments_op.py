"""
Module to obtain free slots for premium passport appointments.

Provides the functions:

*func*: `get_appointment_data` (main entry point)
*func*: `clean_df`
*func*: `get_token`
*func*: `form_data`
"""
from datetime import date as dt
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import pandas as pd
from IPython.display import display
from tabulate import tabulate

# For local testing - to delete
# import chromedriver_autoinstaller
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.chrome.options import Options
# from selenium.common.exceptions import NoSuchElementException
# chromedriver_autoinstaller.install()

__author__ = ['Dr. Usman Kayani']

MAIN_URL = 'https://www.passport.service.gov.uk/urgent/'
MAIN_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:103.0) Gecko/20100101 Firefox/103.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
}

session = requests.Session()


def form_data(data: dict) -> str:
    """Form the data for a POST request.

    Args:
        data: dict
            The data to form.
    """
    return '&'.join(['{}={}'.format(k, v) for k, v in data.items()])


def get_token(data: str) -> str:
    """Get the token from the data.

    Args:
        data: str
            The data to get the token from.

    Returns:
        str
            The token.
    """
    soup = BeautifulSoup(data.text, 'html.parser')
    token_data = soup.find('input', {'name': 'x-csrf-token'})
    if token_data:
        csrf_token = token_data.get('value')
        return csrf_token
    else:
        return None


def get_appointment_data(MAIN_URL) -> pd.DataFrame:
    """Get the appointment data.

    Args:
        MAIN_URL: str
            The main URL to get the data from.

    Returns:
        pd.DataFrame
            The dataframe with the appointment data.
    """
    # session.headers = MAIN_HEADERS
    form_datas = [
        {'is-uk-application': 'true'},
        {
            'date-of-birth-day': '01',
            'date-of-birth-month': '01',
            'date-of-birth-year': '1990',
        },
        {'previous-passport': 'true'},
        {'passport-lost': 'false'},
        {'name-changed': 'false'},
        {
            'passport-issue-day': '01',
            'passport-issue-month': '01',
            'passport-issue-year': '2010',
        },
        {'damaged': 'false'},
        {'other-passports': 'false'},
        {},
        {},
    ]

    start_urls = [
        MAIN_URL,
        'https://www.passport.service.gov.uk/filter/start/urgent'
    ]

    # For local testing - to delete
    # options = Options()
    # options.add_argument('--disable-gpu')
    # options.add_argument('--no-sandbox')
    # options.add_argument('--window-size=1920,1080')
    # the_driver = webdriver.Chrome(options=options)

    for url in start_urls:
        data = session.get(url)
        # the_driver.get(url) # For local testing - to delete

    # For local testing - to delete
    # session = requests.Session()
    # # Set correct user agent
    # selenium_user_agent = the_driver.execute_script("return navigator.userAgent;")
    # session.headers.update({"user-agent": selenium_user_agent})
    #
    # for cookie in the_driver.get_cookies():
    #     session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
    #
    # data = session.get(url)

    no_appt_text = 'Sorry, there are no available appointments'
    if no_appt_text in data.text:
        return no_appt_text

    csrf_token = get_token(data)
    curr_url = data.url

    form_headers = {
        'Referer': 'https://www.passport.service.gov.uk/filter/overseas',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': 'https://www.passport.service.gov.uk'
    }

    list_of_urls = []

    session.headers.update(form_headers)

    for form in form_datas:
        data = session.post(
            curr_url,
            data=form_data({**form, 'x-csrf-token': csrf_token}),
            allow_redirects=True
        )
        curr_url = data.url
        csrf_token = get_token(data)

    session.headers = MAIN_HEADERS
    curr_year = dt.today().year

    first_page = f'https://www.passport.service.gov.uk/booking/choose-date-and-place/{curr_year}-01-01/previous'
    data = session.get(first_page)

    df = pd.read_html(data.text)[0]
    first_date = datetime.strptime(df.columns[0], '%A  %d %B').replace(year=curr_year) + timedelta(days=5)

    list_of_urls = update_list_of_urls(data, list_of_urls)

    start_dates = [
        (first_date + timedelta(days=6 * i)).strftime(f'%Y-%m-%d')
        for i in range(4)
    ]

    data_list = []
    data_list.append(df)
    for date in start_dates:
        first_page = f'https://www.passport.service.gov.uk/booking/choose-date-and-place/{date}/next'
        data = session.get(first_page)
        list_of_urls = update_list_of_urls(data, list_of_urls)
        try:
            curr_df = pd.read_html(data.text)[0]
            data_list.append(curr_df)
        except:
            pass

    cleaned_df = clean_df(pd.concat(data_list, axis=1))
    print(f"Checking actual number of appointments.")

    for url in list_of_urls:
        data_table_data = session.get("https://www.passport.service.gov.uk" + url)
        df_table = pd.read_html(data_table_data.text)[0]
        date_is = datetime.strptime(url.split("/")[-1], '%Y-%m-%d').strftime('%a %-e %b')
        location_is = url.split("/")[-2].capitalize()
        count_is = df_table.iloc[:, 0].to_string().count("Available")
        cleaned_df.at[location_is, date_is] = count_is

    return cleaned_df


def update_list_of_urls(session_data, list_of_urls_to_update) -> list:
    """
    Gathers a list of urls to get the appointments data from

    Args:
        session_data:
            requests session data
        list_of_urls_to_update: list
            A list of already gathered urls

    Returns:
        list_of_urls_to_update: list
            The updated list
    """
    soup = BeautifulSoup(session_data.text, 'html.parser')
    table = soup.find('table', {'class': "govuk-table booking-table"})

    if table is not None:
        for a in table.findAll('a'):
            url = a.get("href")
            list_of_urls_to_update.append(url)

    return list_of_urls_to_update


def clean_df(df) -> pd.DataFrame:
    """
    Clean the dataframe.

    Args:
        df: pd.DataFrame
            The dataframe to clean.

    Returns:
        pd.DataFrame
            The cleaned dataframe.
    """
    if "Birmingham" not in df:
        df.loc[len(df)] = "Birmingham  Unavailable"

    locations = [
        "London",
        "Peterborough",
        "Newport",
        "Liverpool",
        "Durham",
        "Glasgow",
        "Belfast",
        "Birmingham"
    ]
    df.index = locations

    for x in locations:
        df = df.replace(x, '', regex=True)

    df = (
        df
        .replace(' Unavailable', 0, regex=True)
        .replace(' Available', 1, regex=True)
    )

    base = datetime.today()
    date_list = [(base + timedelta(days=x)).strftime("%A %-d %B") for x in range(28)]
    better_date_list = [(base + timedelta(days=x)).strftime("%a %-d %b") for x in range(28)]

    nice_df = pd.DataFrame(columns=date_list,
                           index=locations)

    df.columns = df.columns.str.replace("  ", " ")
    df = df.loc[:, ~df.columns.duplicated()]

    col_dates = list(df.columns)

    df = df.reset_index()
    for col in col_dates:
        for idx in df.index:
            location = df.iloc[idx]["index"]

            number_of_appts = df.iloc[idx][col]
            nice_df.at[location, col] = number_of_appts

    nice_df.columns = better_date_list
    nice_df = nice_df.fillna(0)
    nice_df = nice_df.astype(float)

    return nice_df


if __name__ == '__main__':
    data = get_appointment_data(MAIN_URL)
    if isinstance(data, pd.DataFrame):
        display(tabulate(data, headers='keys', tablefmt='psql'))
    else:
        print(data)
