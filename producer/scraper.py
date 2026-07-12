import logging
from datetime import datetime, timezone
from typing import Protocol, List, ClassVar


import httpx
from lxml import etree
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from errors import NotOKHttpResponse
from models import UrlStatus


logger = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type(NotOKHttpResponse),
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=3, exp_base=3, jitter=3),
)
async def get_webpage(url: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url)
    if response.status_code != httpx.codes.OK:
        logger.warning(
            f"Error retrieving webpage from url: {url}, status code: {response.status_code}, response text: {response.text}"
        )
        raise NotOKHttpResponse("Error retrieving webpage")
    logger.debug(f"Successfully retrieved webpage from URL: {url}")
    return response.text

def basic_load_sitemap(sitemap_data: str) -> List[UrlStatus]:
    tree = etree.fromstring(sitemap_data.encode("utf-8"))

    ns_map = {"s": tree.nsmap[None]} if None in tree.nsmap else tree.nsmap

    urls = tree.xpath("//s:url", namespaces=ns_map)

    url_statuses = []

    for url_node in urls:
        loc = url_node.xpath("./s:loc/text()", namespaces=ns_map)
        lastmod_text = url_node.xpath("./s:lastmod/text()", namespaces=ns_map)

        if loc and lastmod_text:
            clean_date = lastmod_text[0].strip()
            # Parse the datetime string
            lastmod = datetime.fromisoformat(clean_date)
            # Ensure it is timezone-aware. If naive, assume UTC.
            if lastmod.tzinfo is None:
                lastmod = lastmod.replace(tzinfo=timezone.utc)

            url_statuses.append(UrlStatus(loc[0], lastmod))

    return url_statuses


def basic_load_sitemap_no_lastmod(sitemap_data: str) -> List[UrlStatus]:
    tree = etree.fromstring(sitemap_data.encode("utf-8"))

    ns_map = {"s": tree.nsmap[None]} if None in tree.nsmap else tree.nsmap

    urls = tree.xpath("//s:url", namespaces=ns_map)

    url_statuses = []

    for url_node in urls:
        loc = url_node.xpath("./s:loc/text()", namespaces=ns_map)

        if loc:
            url_statuses.append(UrlStatus(loc[0], datetime.now(timezone.utc)))

    return url_statuses


class SitemapLoader(Protocol):
    queue_name: ClassVar[str]
    sitemaps: ClassVar[list[str]]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> List[UrlStatus]:
        """Extracts a flat list of recipe URLs from the source."""
        ...


class AllRecipesSitemapLoader(SitemapLoader):
    queue_name = "all_recipes"
    sitemaps = [
        "https://www.allrecipes.com/sitemap_1.xml",
        "https://www.allrecipes.com/sitemap_2.xml",
        "https://www.allrecipes.com/sitemap_3.xml",
        "https://www.allrecipes.com/sitemap_4.xml",
    ]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> list[UrlStatus]:
        root = etree.fromstring(sitemap_data.encode("utf-8"))
        ns_map = {"ns": root.nsmap[None]} if None in root.nsmap else root.nsmap
        url_items = root.findall(".//ns:url", namespaces=ns_map)
        url_statuses = []
        for url_item in url_items:
            url = url_item.findtext("ns:loc", namespaces=ns_map)
            lastmod = datetime.fromisoformat(
                url_item.findtext("ns:lastmod", namespaces=ns_map)
            )
            if lastmod.tzinfo is None:
                lastmod = lastmod.replace(tzinfo=timezone.utc)
            url_statuses.append(UrlStatus(url, lastmod))
        return url_statuses


class BudgetBytesSitemapLoader(SitemapLoader):
    queue_name = "budget_bytes"
    sitemaps = [
        "https://www.budgetbytes.com/post-sitemap.xml",
        "https://www.budgetbytes.com/post-sitemap2.xml",
    ]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> List[UrlStatus]:
        return basic_load_sitemap(sitemap_data)


class HelloFreshSitemapLoader(SitemapLoader):
    queue_name = "hello_fresh"
    sitemaps = ["https://www.hellofresh.com/sitemap_recipe_pages.xml"]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> List[UrlStatus]:
        return basic_load_sitemap(sitemap_data)


class SeriousEatsSitemapLoader(SitemapLoader):
    queue_name = "serious_eats"
    sitemaps = ["https://www.seriouseats.com/sitemap_1.xml"]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> List[UrlStatus]:
        return basic_load_sitemap(sitemap_data)


class BlueApronSitemapLoader(SitemapLoader):
    queue_name = "blue_apron"
    sitemaps = ["https://www.blueapron.com/recipes/sitemap.xml"]

    @staticmethod
    def load_sitemap(sitemap_data: str) -> List[UrlStatus]:
        return basic_load_sitemap_no_lastmod(sitemap_data)
