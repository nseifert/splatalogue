__author__ = 'nseifert'
import urllib2
from bs4 import BeautifulSoup


if __name__ == "__main__":
    BASE_URL = "http://www.astro.uni-koeln.de"
    page = urllib2.urlopen(BASE_URL+"/cdms/entries")
    soup = BeautifulSoup(page.read(), "lxml")

    urls = []
    des = [] # Text from table entries
    for tr in soup.find_all('tr')[1:]:

        tds = tr.find_all('td')
        des.append([col.text for col in tds])

        links = tr.find_all('a')
        urls.append([a['href'] for a in links])

    compiled = []
    for i, entry in enumerate(urls):
        pass # Put together descriptors and URLs here 

        #compiled.append([descriptors])
