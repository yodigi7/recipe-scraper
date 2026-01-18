import asyncio
import logging
from datetime import datetime

import httpx
from lxml import etree
from recipe_scrapers import scrape_html
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from domain_models import Recipe, UrlStatus
from errors import NotOKHttpResponse

logger = logging.getLogger(__name__)


async def scrape_recipe(url) -> Recipe:
    webpage_txt = await get_webpage(url)
    scraped_data = scrape_html(webpage_txt, url)
    return Recipe(url, scraped_data.to_json(), datetime.now())


@retry(
    retry=retry_if_exception_type(NotOKHttpResponse),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=3, exp_base=3, jitter=3),
)
async def get_webpage(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    if response.status_code != httpx.codes.OK:
        logger.warning(
            f"Error retrieving webpage from url: {url}, status code: {response.status_code}, response text: {response.text}"
        )
        raise NotOKHttpResponse("Error retrieving webpage")
    logger.debug(f"Successfully retrieved webpage from URL: {url}")
    return response.text


def load_sitemap(sitemap_data: str) -> list[UrlStatus]:
    root = etree.fromstring(sitemap_data.encode("utf-8"))
    ns_map = {"ns": root.nsmap[None]} if None in root.nsmap else root.nsmap
    url_items = root.findall(".//ns:url", namespaces=ns_map)
    url_statuses = []
    for url_item in url_items:
        url = url_item.findtext("ns:loc", namespaces=ns_map)
        lastmod = datetime.fromisoformat(url_item.findtext("ns:lastmod", namespaces=ns_map))
        url_statuses.append(UrlStatus(url, lastmod))
    return url_statuses


async def main():
    sitemap_url = "https://www.allrecipes.com/sitemap_1.xml"
    sitemap_data = await get_webpage(sitemap_url)
    url_statuses = load_sitemap(sitemap_data)
    logger.info(url_statuses)


if __name__ == "__main__":
    asyncio.run(main())
