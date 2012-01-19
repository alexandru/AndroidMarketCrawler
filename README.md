# Simple script for crawling the Android Marketplace.

See this article for details:

[Crawling the Android Marketplace: 155,200 Apps](http://bionicspirit.com/blog/2011/12/15/crawling-the-android-marketplace-155200-apps.html)

Installing dependencies:

```bash
easy_install pyquery
easy_install eventlet
```

Of if you're using pip:

```bash
pip install -r reqs.txt
```

Usage:

```
python crawler.py path/to/destination.json_lines
```
