import asyncio
import anyio
import logging

import core
import aio_pika
from constants import SCRAPE_SLEEP
from scraper import get_webpage, load_sitemap, scrape_recipe
from utils import map_recipe_for_db, upsert_to_db

logger = logging.getLogger(__name__)


async def scrape_url(url: str):
    try:
        recipe = await scrape_recipe(url)
    except Exception as e:
        logger.exception(f"Unable to scrape url: {url}.")
        raise e
    db_recipe = map_recipe_for_db(recipe)
    try:
        upsert_to_db(db_recipe)
    except Exception as e:
        logger.exception(f"Unable to save to db url: {url}.")
        raise e
    logger.debug("Saved to db.")
    # Sleep between scrapes to prevent overloading their server and not get detected as a bot
    await anyio.sleep(SCRAPE_SLEEP)


async def on_message(message: aio_pika.abc.AbstractIncomingMessage):
    async with message.process(requeue=False):
        url = message.body.decode()
        await scrape_url(url)
        await anyio.sleep(SCRAPE_SLEEP)


async def main():
    logger.info(f"APP VERSION: {core.config.version}")
    # 2. Establish a robust connection (auto-reconnects)
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

    queues = [
        "all_recipes",
        "budget_bytes",
        "hello_fresh",
        "serious_eats",
        "blue_apron",
    ]
    async with connection:
        async with anyio.create_task_group() as tg:
            for queue_name in queues:
                # 3. Create a channel
                channel = await connection.channel()

                # 4. Set Prefetch (QoS)
                # Limits the consumer to only 10 unacknowledged messages at a time
                await channel.set_qos(prefetch_count=1)

                dlx = await channel.declare_exchange(
                    f"{queue_name}.dlx",
                    aio_pika.ExchangeType.DIRECT,
                    durable=True,
                )

                dlq = await channel.declare_queue(
                    f"{queue_name}.dlq",
                    durable=True,
                )

                await dlq.bind(dlx, routing_key=f"{queue_name}.dlq")

                # 5. Declare the queue (must match the producer's durable=True)
                declared_queue = await channel.declare_queue(
                    f"{queue_name}",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": f"{queue_name}.dlx",
                        "x-dead-letter-routing-key": f"{queue_name}.dlq",
                    },
                )

                # 6. Start consuming using the callback
                tg.start_soon(declared_queue.consume, on_message)

                print(f" [{queue_name}] Waiting for messages.")

        # Wait until the connection is closed or process is interrupted
        await anyio.sleep_forever()


if __name__ == "__main__":
    anyio.run(main)
