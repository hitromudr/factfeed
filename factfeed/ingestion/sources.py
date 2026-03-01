"""Source definitions for all target RSS feeds."""

# Each source is stored in the database via seed_sources() on startup.
# The feed_url values here are the initial seeds; they can be updated in the
# database without a code change.

SOURCES = [
    {"name": "BBC News", "feed_url": "http://feeds.bbci.co.uk/news/rss.xml"},
    # NOTE: Reuters' RSS feed URL has historically been unstable.  Using the
    # sitemap-based feed as a fallback; the URL is stored in the sources DB
    # table so it can be updated without code changes.
    {
        "name": "Reuters",
        "feed_url": "https://www.reuters.com/arc/outboundfeeds/news-sitemap-index/?outputType=xml",
    },
    # NOTE: AP News has no obvious stable first-party RSS feed.  Using the
    # RSSHub proxy as recommended by research.
    {"name": "AP News", "feed_url": "https://rsshub.app/apnews/topics/apf-topnews"},
    {"name": "NPR", "feed_url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "Al Jazeera", "feed_url": "https://www.aljazeera.com/xml/rss/all.xml"},
    # Europe
    {"name": "The Guardian", "feed_url": "https://www.theguardian.com/world/rss"},
    {"name": "Deutsche Welle", "feed_url": "https://rss.dw.com/rdf/rss-en-all"},
    {"name": "France 24", "feed_url": "https://www.france24.com/en/rss"},
    {
        "name": "El País",
        "feed_url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    },
    # Asia & Middle East
    {
        "name": "NHK World",
        "feed_url": "https://www3.nhk.or.jp/nhkworld/upld/medias/en/news/news.xml",
    },
    {
        "name": "The Hindu",
        "feed_url": "https://www.thehindu.com/news/national/feeder/default.rss",
    },
    {"name": "SCMP", "feed_url": "https://www.scmp.com/rss/91/feed"},
    {
        "name": "Al Jazeera Arabic",
        "feed_url": "https://www.aljazeera.net/aljazeerarss/a7c186be-1baa-4bd4-9d80-a84db769f779/73d0e1b4-532f-45ef-b135-bfdff8b8cab9",
    },
    # Latin America & Africa
    {"name": "MercoPress", "feed_url": "https://en.mercopress.com/rss/"},
    {
        "name": "AllAfrica",
        "feed_url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
    },
    # CIS
    {"name": "Meduza", "feed_url": "https://meduza.io/rss/all"},
    {"name": "TASS", "feed_url": "https://tass.ru/rss/v2.xml"},
]
