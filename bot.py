import os
import atoma
import pickle
import hashlib
import requests
import asyncio
import telegram
import traceback
from flask import Flask, Response
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
app = Flask(__name__)


@app.route("/")
def index():
    """web trigger"""
    try:
        asyncio.run(send_messages())
        return Response("Messages sent successfully", status=200)
    except Exception as ex:
        exception_text = "".join(
            traceback.TracebackException.from_exception(ex).format()
        )
        return Response("=== Exception === \n" + exception_text, status=500)


async def send_messages():
    pickle_file = "sent_message_urls.pickle"
    try:
        sent_message_urls = pickle.load(open(pickle_file, "rb"))
    except (OSError, IOError) as e:
        sent_message_urls = set()
        pickle.dump(sent_message_urls, open(pickle_file, "wb"))

    messages = []

    # HackerOne Hacktivity feed.
    r = requests.get(
        "https://api.hackerone.com/v1/hackers/hacktivity",
        auth=(os.environ["HACKERONE_API_USERNAME"], os.environ["HACKERONE_API_KEY"]),
        headers={"Accept": "application/json"},
    )
    for item in r.json()["data"]:
        if item["attributes"]["url"] == None:
            continue

        messages.append(
            {
                "text": item["attributes"]["title"]
                + "\n"
                + item["relationships"]["program"]["data"]["attributes"]["name"]
                + " disclosed a bug submitted by "
                + item["relationships"]["reporter"]["data"]["attributes"]["username"]
                + ": "
                + item["attributes"]["url"],
                "url": item["attributes"]["url"],
            }
        )

    # Reddit RSS Feed for Netsec subreddit
    try:
        feed_text = requests.get("https://www.reddit.com/r/netsec/top/.rss")
        feed = atoma.parse_atom_bytes(feed_text.content)
        for entry in feed.entries:
            messages.append(
                {
                    "text": entry.title.value + " - " + entry.links[0].href,
                    "url": entry.links[0].href,
                }
            )
    except atoma.exceptions.FeedXMLError as ex:
        # Probably rate limited by Reddit, so we just ignore it blissfully.
        pass

    # send messages and save sent url to pickle file
    bot = telegram.Bot(os.environ["TELEGRAM_BOT_TOKEN"])
    for message in messages:
        text, url = message["text"], message["url"]
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

        if url_hash in sent_message_urls:
            continue

        await bot.send_message(
            text=text,
            chat_id=os.environ["TELEGRAM_CHAT_ID"],
            disable_notification=True,
        )

        sent_message_urls.add(url_hash)
        pickle.dump(sent_message_urls, open(pickle_file, "wb"))


if __name__ == "__main__":
    """CLI trigger"""
    asyncio.run(send_messages())
