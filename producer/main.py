import asyncio
import logging
from typing import Type
from time import sleep

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
    while True:
        try:
            connection = await aio_pika.connect_robust(
                host="rabbitmq", port=5672, login="guest", password="guest"
            )
            break
        except Exception:
            logger.error("Unable to connect to rabbitmq.", exc_info=True)
            await asyncio.sleep(5)

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
        tasks = []
        for sitemap_url in sitemap_loader.sitemaps:
            # Scrape site maps
            url_statuses = sitemap_loader.load_sitemap(await get_webpage(sitemap_url))
            # TODO: Check to see if the URL last modified is before or after last scraped in DB
            # Rescrape out of date items
            for url_status in url_statuses:
                url = url_status.url
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
            logger.info(f"Adding {len(url_statuses)} to rabbitMQ.")
        await asyncio.gather(*tasks)
        logger.info("FINISHED PRODUCER")


if __name__ == "__main__":
    logger.info("STARTING.")
    asyncio.run(main())
    logger.info("CLOSING.")
