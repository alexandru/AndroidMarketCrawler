import eventlet
eventlet.monkey_patch()

import os
import re
import urllib
import json
import sys

from pyquery import pyquery as pq


class AndroidMarketCrawler(object):
    def __init__(self, concurrency=10):
        self.pool = eventlet.GreenPool(concurrency)
        self.queue = eventlet.Queue()
        self.queue.put("https://market.android.com/")
        self.results = eventlet.Queue()
        self.seen_app_ids = set()
        self.seen = set()
        self.failed = 0

    def fetch_content(self, url):
        resp = urllib.urlopen(url)            
        if resp.getcode() == 404:
            return
        elif resp.getcode() != 200:
            self.failed += 1
            return

        try:
            content = resp.read()
            doc = pq.PyQuery(content)
            if not self.is_page_valid(url, doc):
                return         

            sys.stderr.write(url + "\n")

            all_links = [
                a.attrib['href']
                for a in doc('a') 
                if re.search(r'\/(details|developer)[?]', a.attrib.get('href', '')) \
                and not re.search('reviewId', a.attrib.get('href', '')) \
                and not re.search('accounts\/ServiceLogin', a.attrib.get('href', ''))
            ]

            for link in all_links:
                if not link: continue
                self.queue.put(self.absolute_url(link))

            app_info = self.fetch_app_info(url, doc)
            if app_info: 
                self.seen_app_ids.add(app_info['uid'])
                self.results.put(app_info)

        except:
            pass

    def next(self):
        if not self.results.empty():
            return self.results.get()

        while not self.queue.empty() or self.pool.running() != 0:
            url = eventlet.with_timeout(0.1, self.queue.get, timeout_value='')

            if url:
                if url in self.seen: continue
                uid = self.get_id(url)
                if uid in self.seen_app_ids: continue
                self.seen.add(url)
                self.pool.spawn_n(self.fetch_content, url)

            if not self.results.empty():
                return self.results.get()

        raise StopIteration

    def is_page_valid(self, url, doc):
        if url == "https://market.android.com/":
            return True
        if url.startswith("https://market.android.com/details?id=apps_topselling_paid"):
            return True
        if url.startswith("https://market.android.com/details?id=apps_topselling_free"):
            return True
        if not re.search(r'details|developer', url):
            return False
        if re.search('reviewId', url):
            return False
        params = self.query_vars(url)
        if not params.get('id') and not params.get('pub'): 
            return False
        if re.search(r'developer', url):
            if not (doc('h1.page-banner-text').text() or '').lower().startswith('apps by'):
                return False
            return True
        if not doc('div.apps.details-page'): 
            return False
        if 'Apps' not in [a.text for a in doc('.page-content .breadcrumbs a')]:
            return False
        return True

    def fetch_app_info(self, url, doc):
        params = self.query_vars(url)
        if not params.get('id'): return None
        if not doc('div.apps.details-page'): return None
        if 'Apps' not in [a.text for a in doc('.page-content .breadcrumbs a')]:
            return None

        app_info = {
            'uid': params['id'],
            'name': doc('h1.doc-banner-title').text(),
            'app_link': self.absolute_url('/details?id=' + params['id']),
            'dev_name': doc('a.doc-header-link').text(),
            'dev_link': self.absolute_url(doc('a.doc-header-link').attr['href']),
            'dev_web_links': list(set([
                self.query_vars(a.attrib['href'])['q'] 
                for a in doc('.doc-overview a') 
                if a.text and "Visit Developer's Website" in a.text
            ])),
            'dev_emails': list(set([
                a.attrib['href'][len('mailto:'):] 
                for a in doc('.doc-overview a') 
                if a.attrib.get('href', '').startswith('mailto:')
            ])),
            'rating_count': int(re.sub(r'\D+', '', doc('[itemprop=ratingCount]').text() or '0')),
            'rating_value': doc('[itemprop=ratingValue]').attr['content'],
            'description_html': doc('#doc-original-text').html(),
            'users_also_installed': [
                self.query_vars(a.attrib['href'])['id'] 
                for a in doc('[data-analyticsid=users-also-installed] a.common-snippet-title')
            ],
            'users_also_viewed': [
                self.query_vars(a.attrib['href'])['id'] 
                for a in doc('[data-analyticsid=related] a.common-snippet-title')
            ],
        }

        match = re.findall(r'.*[\d\.]+', doc('.buy-button-price').text())
        if match:
            app_info['is_free'] = False
            app_info['price'] = match[0]
        else:
            app_info['is_free'] = True
            app_info['price'] = 0

        match = [a.text for a in doc('.doc-metadata-list dd a') if 'category' in a.attrib.get('href')]
        if match: app_info['category'] = match[0]
        
        match = re.findall('([\d,]+)\s*-\s*([\d,]+)', doc('[itemprop=numDownloads]').text() or '')
        if match:
            imin, imax = [re.sub(r'\D+', '', m) for m in match[0]]
            app_info['installs_min'] = int(imin)
            app_info['installs_max'] = int(imax)

        return app_info

    def get_id(self, url):
        params = self.query_vars(url)
        return params.get('id')

    def query_vars(self, url):
        v = {}
        match = re.findall('[^?]+[?](.*)$', url)

        if match:
            query = match[0]
            parts = query.split('&')
            for part in parts:
                keyval = [urllib.unquote_plus(i) for i in part.split('=', 1)]
                key, val = keyval if len(keyval) == 2 else (keyval[0], '')
                v[key] = val

        return v

    def absolute_url(self, url):
        if url and url.startswith('/'):
            return "https://market.android.com" + url
        return url or ''

    def __iter__(self):
        return self

        
fh = open(os.path.join(os.path.dirname(__file__), 'stats.json'), 'w')
fh.write("[\n")
for app in AndroidMarketCrawler(concurrency=10):
    fh.write(json.dumps(app) + ", \n")
fh.write("{}]")

    
