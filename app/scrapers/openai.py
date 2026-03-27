from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import markdownify
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel


class OpenAINewsArticle(BaseModel):
    title: str
    url: str
    published_at: datetime
    description: str
    content_markdown: Optional[str] = None


class OpenAIScraper:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.feed_urls = [
            "https://openai.com/news/rss.xml",
            "https://openai.com/blog/rss.xml",
        ]
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )

    def _parse_feed(self):
        for url in self.feed_urls:
            feed = feedparser.parse(url)
            if feed.entries:
                return feed
        return feedparser.parse(self.feed_urls[0])

    def _extract_content_markdown(self, article_url: str) -> Optional[str]:
        try:
            response = requests.get(
                article_url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            container = soup.find("article") or soup.find("main") or soup.body
            if container is None:
                return None
            return markdownify.markdownify(str(container), heading_style="ATX").strip()
        except Exception:
            return None

    def get_latest_articles(self, hours: int = 24) -> list[OpenAINewsArticle]:
        feed = self._parse_feed()
        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles: list[OpenAINewsArticle] = []
        for entry in feed.entries:
            if not getattr(entry, "published_parsed", None):
                continue
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_time < cutoff_time:
                continue
            articles.append(
                OpenAINewsArticle(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    published_at=published_time,
                    description=entry.get("summary", ""),
                )
            )
        return articles

    def scrape(self, hours: int = 150) -> list[OpenAINewsArticle]:
        articles = self.get_latest_articles(hours=hours)
        result: list[OpenAINewsArticle] = []
        for article in articles:
            content_md = self._extract_content_markdown(article.url)
            result.append(article.model_copy(update={"content_markdown": content_md}))
        return result


if __name__ == "__main__":
    scraper = OpenAIScraper()
    data = scraper.scrape(hours=200)
    print(f"Fetched {len(data)} OpenAI articles")
