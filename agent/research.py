"""Fetch dated summaries from a fixed source list. Story text is untrusted data."""
import concurrent.futures
import re
from datetime import timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlsplit
from xml.etree import ElementTree

# Sections from one newsroom share a publisher identity during corroboration.
FEEDS = [
    ('The Hindu', 'https://www.thehindu.com/news/national/feeder/default.rss', 'thehindu.com'),
    ('BBC', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'bbc.co.uk'),
    ('BBC', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'bbc.co.uk'),
    ('BBC', 'https://feeds.bbci.co.uk/news/technology/rss.xml', 'bbc.co.uk'),
    ('The Guardian', 'https://www.theguardian.com/world/rss', 'theguardian.com'),
    ('The Guardian', 'https://www.theguardian.com/culture/rss', 'theguardian.com'),
    ('Indian Express', 'https://indianexpress.com/feed/', 'indianexpress.com'),
    ('Indian Express', 'https://indianexpress.com/section/business/feed/', 'indianexpress.com'),
    ('ScienceDaily', 'https://www.sciencedaily.com/rss/top/science.xml', 'sciencedaily.com'),
]


def clean(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', ' ', unescape(value or ''))).strip()


def parse_feed(body, publisher, domain, now):
    if len(body)>1_000_000 or b'<!ENTITY' in body.upper() or b'<!DOCTYPE' in body.upper():
        return []
    items = []
    for item in ElementTree.fromstring(body).findall('.//item'):
        link = item.findtext('link','')
        host = urlsplit(link).hostname or ''
        allowed = {domain,'bbc.com'} if publisher=='BBC' else {domain}
        if urlsplit(link).scheme!='https' or not any(host==d or host.endswith('.'+d) for d in allowed):
            continue
        try:
            dt = parsedate_to_datetime(item.findtext('pubDate'))
            if not timedelta(0)<=now-dt<=timedelta(days=4):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        items.append(dict(source=publisher,url=link,date=dt.isoformat(),headline=clean(item.findtext('title'))[:240],
                          summary=clean(item.findtext('description'))[:1000],
                          background=clean(item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded'))[:1800]))
        if len(items)==6:
            break
    return items


def discover(now):
    import requests
    def fetch(entry):
        publisher,url,domain=entry
        try:
            with requests.get(url,timeout=(4,8),stream=True,headers={'User-Agent':'PersonalEditorialAgent/1.0'}) as response:
                response.raise_for_status()
                body=bytearray()
                for chunk in response.iter_content(32768):
                    body.extend(chunk)
                    if len(body)>1_000_000:
                        return []
                return parse_feed(bytes(body), publisher,domain,now)
        except (requests.RequestException,ElementTree.ParseError,ValueError):
            return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        items = (item for group in pool.map(fetch, FEEDS) for item in group)
        return list({item['url']: item for item in items}.values())
