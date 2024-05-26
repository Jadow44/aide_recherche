import json
import os
import time
from datetime import datetime
from random import randint
from typing import Optional

from scholarly import scholarly
import pandas as pd

from src.logger import Logger

SEARCH_TERMS = [
    ('"locomotor rehabilitation"', '"non-ambulant"'),
    ('"locomotor rehabilitation"', 'non-ambulant')
]
MAX_LIMIT_PER_SEARCH_TERM =  150

class ScholarScraper:
    def __init__(self):
        self._df: Optional[pd.DataFrame] = None
        self._logger = Logger()
        self._now = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        os.mkdir(f"../outputs/{self._now}")

    def get_articles(self):
        for search_term in SEARCH_TERMS:
            final_search_term = f'{search_term[0]} {search_term[1]}'
            self._logger.info(f"searching for: {final_search_term}")
            data = self._search_for_title(final_search_term)
            len_data = (len(data))
            self._logger.info(f"got data of length: {len_data}")

            if (len(data)) == 0:
                self._logger.info(f"skipping as no data available for {final_search_term}")
                break
            self._add_to_df(data, final_search_term)
            # save to file
            self._logger.info(f"saving to csv...")
            self._save_to_csv(final_search_term, len_data)
            self._logger.info(f"saving to csv completed")
            time.sleep(randint(1, 5))

    def _save_to_csv(self, final_search_term, len_data):
        self._rename_columns()
        name = f"{len_data}_articles_for_{final_search_term}".replace(" ", "_")
        self._df.to_csv(f"../outputs/{self._now}/{name}.csv")

    def _add_to_df(self, data: json, search_term: str) -> None:
        self._df = pd.json_normalize(data)
        self._df["search_term"] = search_term
        self._logger.info(f"created new df")

    def _search_for_title(self, search_term):
        scholarly.set_timeout(randint(1, 5))
        search_query = scholarly.search_pubs(search_term)
        try:
            out = list(search_query)
        except Exception:
            self._logger.error("failed to get articles")
        return out

    def _rename_columns(self):
        self._df["Journal Title"] = None
        self._df["ISSN"] = None
        self._df["ISBN"] = None
        self._df["Volume"] = None
        self._df["Issue"] = None
        self._df["First Page"] = None
        self._df["Page Count"] = None
        self._df["Accession Number"] = None
        self._df["DOI"] = None
        self._df["First Page"] = None
        self._df["Publisher"] = None
        self._df["Doctype"] = None
        self._df["Subjects"] = None
        self._df["Keywords"] = None
        self._df[">>>other_fields>>>"] = None
        self._df = self._df.rename(
            columns={
                'bib.title': 'Article Title',
                'bib.author': 'Author',
                'bib.pub_year': 'Publication Date',
                'bib.abstract': 'Abstract',
                'pub_url': 'PLink',
            }
        )[
            [
                "Article Title",
                "Author",
                "Journal Title",
                "ISSN",
                "ISBN",
                "Publication Date",
                "Volume",
                "Issue",
                "First Page",
                "Page Count",
                "Accession Number",
                "DOI",
                "Publisher",
                "Doctype",
                "Subjects",
                "Keywords",
                "Abstract",
                "PLink",
                ">>>other_fields>>>",
                "eprint_url",
                "num_citations",
                "url_scholarbib",
                "url_add_sclib",
                "author_id",
                "bib.venue",
                "search_term"
            ]
        ]

