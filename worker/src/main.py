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
    while True:
        try:
            connection = await aio_pika.connect_robust(
                host="rabbitmq", port=5672, login="guest", password="guest"
            )
            break
        except Exception:
            logger.error("Unable to connect to rabbitmq.", exc_info=True)

    queues = [
        "all_recipes",
        "budget_bytes",
        "hello_fresh",
        "serious_eats",
        "blue_apron",
    ]
    async with connection:
        async with anyio.create_task_group() as tg:
            for queue in queues:
                # 3. Create a channel
                channel = await connection.channel()

                # 4. Set Prefetch (QoS)
                # Limits the consumer to only 10 unacknowledged messages at a time
                await channel.set_qos(prefetch_count=1)

                dlx = await channel.declare_exchange(
                    f"{queue}.dlx",
                    aio_pika.ExchangeType.DIRECT,
                    durable=True,
                )

                dlq = await channel.declare_queue(
                    f"{queue}.dlq",
                    durable=True,
                )

                await dlq.bind(dlx, routing_key=f"{queue}.dlq")

                # 5. Declare the queue (must match the producer's durable=True)
                queue = await channel.declare_queue(
                    f"{queue}",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": f"{queue}.dlx",
                        "x-dead-letter-routing-key": f"{queue}.dlq",
                    },
                )

                # 6. Start consuming using the callback
                tg.start_soon(queue.consume, on_message)

                print(f" [{queue}] Waiting for messages.")

        # Wait until the connection is closed or process is interrupted
        await anyio.sleep_forever()


if __name__ == "__main__":
    anyio.run(main)
