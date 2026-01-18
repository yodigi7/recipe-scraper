import logging

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

import domain_models
import models
from db import get_session

logger = logging.getLogger(__name__)


def map_recipe_for_db(recipe: domain_models.Recipe) -> models.Recipe:
    return models.Recipe(canonical_url=recipe.canonical_url, json=recipe.json, last_scraped=recipe.last_scraped)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=3, exp_base=3, jitter=3),
)
def upsert_to_db(recipe: models.Recipe):
    with get_session() as session:
        try:
            session.add(recipe)
            session.commit()
        except IntegrityError:
            logger.info(f"Error with inserting, likely need to update instead.")
            session.rollback()  # undo failed INSERT tx
            session.execute(
                update(models.Recipe)
                .where(models.Recipe.canonical_url == recipe.canonical_url)
                .values(
                    json=recipe.json,
                    version=recipe.version,
                )
            )
            session.commit()  # commit the UPDATE
