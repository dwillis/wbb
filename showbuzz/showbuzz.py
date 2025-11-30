import requests
import lxml.html as lh
import pandas as pd
from datetime import date
from dateutil.rrule import rrule, DAILY
import calendar


def rows_from_page(url):
    page = requests.get(url)
    doc = lh.fromstring(page.content)
    tr_elements = doc.xpath('//tr')
    tr_elements = tr_elements[1:]  # Remove row above headers
    return tr_elements


def sbd_df(date):
    # Scrape webpage
    date_str = '{d.month}-{d.day}-{d.year}'.format(d = date)
    day_of_week = calendar.day_name[date.weekday()]
    url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-' + date_str + '.html'
    tr_elements = rows_from_page(url)

    # Non-standard pages
    if len(tr_elements) == 0:
        if date_str == '3-5-2018':
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-monday-cable-originals-network-finals-3-d-2018.html'
            tr_elements = rows_from_page(url)
        if date_str == '5-22-2019':
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-wednesday-cable-originals-network-finals-5-23-2019.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-update-' + date_str +'.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-a-network-finals-' + date_str + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-to-come-' + date_str + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-coming-soon-' + date_str + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-coming-soon-network-finals-' + date_str + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/preliminary-showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-' + date_str + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-' + date_str + '-broadcast-finals-available-friday' + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-' + date_str + '-broadcast-finals-available-monday' + '.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-coming-monday-' + date_str +'.html'
            tr_elements = rows_from_page(url)
        if len(tr_elements) == 0:
            url = 'http://www.showbuzzdaily.com/articles/showbuzzdailys-top-150-' + day_of_week + '-cable-originals-network-finals-final-charts-to-follow-' + date_str +'.html'
            tr_elements = rows_from_page(url)

    # Create columns list
    col = []
    i = 0
    for t in tr_elements[0]:
        i += 1
        name = t.text_content()
        col.append((name, []))

    # Scrape rows
    for j in range(len(tr_elements) - 150, len(tr_elements)):
        T = tr_elements[j]
        # if len(T) != 7:
        #     break
        i = 0
        for t in T.iterchildren():
            data = t.text_content()
            if i > 0:
                try:
                    data = int(data)
                except:
                    pass
            col[i][1].append(data)
            i += 1

    # Create DataFrame
    if len(col) == 17: # Fix for 2020-08-06 having detailed ratings
        col = col[0:6] + [('(000s)', col[16][1])]

    Dict = {title: column for (title, column) in col}
    df = pd.DataFrame(Dict)
    df.columns = ['rank', 'program', 'network', 'time', 'duration', 'rating', 'viewers']
    df['date'] = date.strftime("%Y-%m-%d")
    return df


# Code Entry
start_date = date(2019, 3, 22)
end_date = date(2019, 4, 7)
for dt in rrule(DAILY, dtstart = start_date, until = end_date):
    try:
        df = sbd_df(dt)
        df.to_csv(dt.strftime("%Y-%m-%d") + '.csv', index = False)
    except:
        raise
        print('Error on: ' + dt.strftime("%Y-%m-%d"))
