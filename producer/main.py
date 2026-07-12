import asyncio
import logging
from typing import Type

import aio_pika
from aio_pika.abc import AbstractRobustConnection

from scraper import (
    AllRecipesSitemapLoader,
    BlueApronSitemapLoader,
    BudgetBytesSitemapLoader,
    HelloFreshSitemapLoader,
    SeriousEatsSitemapLoader,
    get_webpage,
    SitemapLoader,
)

logger = logging.getLogger(__name__)


async def main():
    await asyncio.sleep(5)
    max_retries = 30
    for attempt in range(max_retries):
        try:
            connection = await aio_pika.connect_robust(
                host="rabbitmq", port=5672, login="guest", password="guest"
            )
            break
        except Exception:
            logger.error("Unable to connect to rabbitmq. Attempt %d/%d.", attempt + 1, max_retries, exc_info=True)
            await asyncio.sleep(5)
    else:
        logger.critical("Failed to connect to rabbitmq after %d attempts. Exiting.", max_retries)
        return

    # await load_recipes(connection, AllRecipesSitemapLoader())
    # await load_recipes(connection, BudgetBytesSitemapLoader)
    # await load_recipes(connection, HelloFreshSitemapLoader)
    # await load_recipes(connection, SeriousEatsSitemapLoader)
    await load_recipes(connection, BlueApronSitemapLoader)


async def load_recipes(
    rabbitmq_conn: AbstractRobustConnection, sitemap_loader: Type[SitemapLoader]
):
    # 2. Establish Connection & Channel
    async with rabbitmq_conn:
        channel = await rabbitmq_conn.channel()

        dlx = await channel.declare_exchange(
            f"{sitemap_loader.queue_name}.dlx",
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        dlq = await channel.declare_queue(
            f"{sitemap_loader.queue_name}.dlq",
            durable=True,
        )

        await dlq.bind(dlx, routing_key=f"{sitemap_loader.queue_name}.dlq")

        await channel.declare_queue(
            f"{sitemap_loader.queue_name}",
            durable=True,
            arguments={
                "x-dead-letter-exchange": f"{sitemap_loader.queue_name}.dlx",
                "x-dead-letter-routing-key": f"{sitemap_loader.queue_name}.dlq",
            },
        )
        from db import get_session
        from models import Recipe

        tasks = []
        for sitemap_url in sitemap_loader.sitemaps:
            # Scrape site maps
            url_statuses = sitemap_loader.load_sitemap(await get_webpage(sitemap_url))
            
            urls_to_check = [u.url for u in url_statuses]
            with get_session() as session:
                # Get the canonical_url and last_scraped from DB for all scraped urls
                db_results = session.query(Recipe.canonical_url, Recipe.last_scraped).filter(Recipe.canonical_url.in_(urls_to_check)).all()
                db_lookup = {r.canonical_url: r.last_scraped for r in db_results}

            to_queue = 0
            skipped = 0
            
            for url_status in url_statuses:
                url = url_status.url
                last_modified = url_status.last_modified
                
                # Check DB status
                db_last_scraped = db_lookup.get(url)
                
                # Should queue if:
                # 1. Not in DB at all (db_last_scraped is None and url not in db_lookup)
                # 2. In DB but never scraped (db_last_scraped is None and url in db_lookup)
                # 3. Last modified is newer than last scraped
                should_queue = False
                if url not in db_lookup:
                    should_queue = True
                elif db_last_scraped is None:
                    should_queue = True
                elif last_modified and last_modified > db_last_scraped:
                    should_queue = True
                    
                if should_queue:
                    to_queue += 1
                    message = aio_pika.Message(
                        body=url.encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    )
                    tasks.append(
                        channel.default_exchange.publish(
                            message,
                            routing_key=f"{sitemap_loader.queue_name}",
                        )
                    )
                else:
                    skipped += 1
                    
            logger.info(f"Adding {to_queue} to rabbitMQ. Skipped {skipped} as they are up to date.")
        await asyncio.gather(*tasks)
        logger.info("FINISHED PRODUCER")


if __name__ == "__main__":
    logger.info("STARTING.")
    asyncio.run(main())
    logger.info("CLOSING.")
