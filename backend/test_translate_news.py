"""
Test: translate 3 latest news articles to Chinese via DeepSeek API.
Usage: uv run python test_translate_news.py
"""

import sqlite3
import json
import re
import urllib.request


DB_PATH = "dev.db"
DEEPSEEK_API_KEY = "sk-ed66526c39af46508a4a33c7e8bd95a2"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-v4-flash"


def strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_latest_news(n: int = 3) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT payload_json FROM news_articles_cache ORDER BY published_at DESC LIMIT ?",
        (n,),
    )
    rows = cur.fetchall()
    conn.close()
    return [json.loads(r[0]) for r in rows]


def translate(text: str) -> str:
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "你是专业的金融新闻翻译员。将用户输入的英文新闻内容翻译成简洁准确的中文，保留数字、公司名称和股票代码不变。只输出译文，不要解释。",
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        }
    ).encode()

    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"].strip()


def main():
    articles = fetch_latest_news(3)
    print(f"从数据库读取了 {len(articles)} 篇最新新闻\n{'=' * 60}\n")

    for i, article in enumerate(articles, 1):
        title = article.get("title", "")
        content = strip_html(article.get("content_html", ""))[:800]  # 限制长度
        published = article.get("published_at", "")

        print(f"[{i}] {published}")
        print(f"原文标题: {title}")
        print(f"原文摘要: {content[:200]}...")
        print()

        to_translate = f"标题：{title}\n\n内容：{content}"
        print("正在翻译...")
        translated = translate(to_translate)
        print(f"译文:\n{translated}")
        print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
