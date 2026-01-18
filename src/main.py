import asyncio
import logging

import core
from constants import SCRAPE_SLEEP
from scraper import get_webpage, load_sitemap, scrape_recipe
from utils import map_recipe_for_db, upsert_to_db

logger = logging.getLogger(__name__)


async def main():
    logger.info(f"APP VERSION: {core.config.version}")
    # TODO: extract this out
    sitemaps = [
        # "https://www.allrecipes.com/sitemap_1.xml",
        # "https://www.allrecipes.com/sitemap_2.xml",
        "https://www.allrecipes.com/sitemap_3.xml",
        "https://www.allrecipes.com/sitemap_4.xml",
    ]
    for sitemap_url in sitemaps:
        # Scrape site maps
        url_statuses = load_sitemap(await get_webpage(sitemap_url))
        # TODO: Check to see if the URL last modified is before or after last scraped in DB
        # Rescrape out of date items
        for url_status in url_statuses:
            url = url_status.url
            try:
                recipe = await scrape_recipe(url)
            except:
                logger.exception(f"Unable to scrape url: {url}.")
                continue
            db_recipe = map_recipe_for_db(recipe)
            try:
                upsert_to_db(db_recipe)
            except:
                logger.exception(f"Unable to save to db url: {url}.")
                continue
            logger.debug("Saved to db.")
            # Sleep between scrapes to prevent overloading their server and not get detected as a bot
            await asyncio.sleep(SCRAPE_SLEEP)


if __name__ == "__main__":
    asyncio.run(main())
