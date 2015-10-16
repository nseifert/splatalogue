__author__ = 'nseifert'
import urllib2
from bs4 import BeautifulSoup
import time
import re

def pretty_print(comp):
    form = "{:5}\t{:45}\t{:15}\t{:40} {:40}"
    output = form.format(*('Tag', 'Molecule', 'Date','Cat Link', 'Metadata Link'))+'\n'
    for row in comp:
        output += form.format(*(row[0], row[1], time.strftime("%B %Y", row[2]), row[3], row[4]))+'\n'
    return output



if __name__ == "__main__":
    unidrop = lambda x: re.sub(r'[^\x00-\x7F]+',' ', x) # Gets rid of any non-ASCII unicode symbols in a string

    BASE_URL = "http://www.astro.uni-koeln.de"
    page = urllib2.urlopen(BASE_URL+"/cdms/entries")
    soup = BeautifulSoup(page.read(), "lxml")

    urls = [] # URLs to CAT and Documentation (metadata) files
    des = [] # Text from table entries
    for tr in soup.find_all('tr')[1:]:
        des.append([col.text for col in tr.find_all('td')])
        urls.append([a['href'] for a in tr.find_all('a')])

    compiled = [] # 0 --> tag, 1 --> Molecule, 2 --> struct_time obj, 4 --> cat file, 5 --> metadata
    for i, entry in enumerate(urls):
        date = des[i][6].strip()

        try:  # Because Holger isn't consistent with his date formatting
            formatted_date = time.strptime(date, "%b. %Y")
        except ValueError:
            try:
                formatted_date = time.strptime(date, "%B %Y")
            except ValueError:
                formatted_date = time.strptime(date, "%b %Y")

        compiled.append([unidrop(des[i][0]).encode('utf-8'), unidrop(des[i][1]).encode('utf-8'),
                         formatted_date, urls[i][1], urls[i][2]])

    compiled.sort(key=lambda x: x[2], reverse=True)

    print pretty_print(compiled)
