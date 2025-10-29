import os
import re
import sys
import datetime
import time
from contextlib import closing
from typing import List, Dict, Optional

import requests

from Artigo import Artigo
from Autor import Autor
from ExcelExporter import ExcelExporter
from Gerenciador import Gerenciador
from RelevanceEngine import QueryRelevanceEngine
import Timer
from TranslationHelper import build_text_variants
from findQualis import find_similar_journal
from NetworkHelper import configure_session_for_tor
from KeyLoader import (
    load_semantic_scholar_api_key,
    load_tor_proxy,
    load_tor_browser_path,
    load_tor_control_settings,
)
from TorIntegration import ensure_local_tor_proxy, request_new_tor_identity
from activity_logger import log_event, log_exception

class Crawler:
    def __init__(self, root_directory):
        # saves current directory in a string
        self.root_directory = root_directory

        self.start_time = Timer.timeNow()
        self.end_time = Timer.timeNow()

        self.manager = None
        self.list_authors: List[Autor] = []
        self.list_articles: List[Artigo] = []

        self.input_search = ''
        self.input_pages = 0
        self.year_filter_choice: Optional[int] = None
        self.keyword_rules: List[Dict[str, str]] = []

        self.gui = None
        self.relevance_engine = None

        self.index_progress_bar = 1
        self._session = requests.Session()
        self.using_tor = False
        self._tor_proxy = None
        self._tor_manager = None
        self._tor_control_port = None
        self._tor_control_password = None
        self.api_key_active = False

        api_key = load_semantic_scholar_api_key()
        if api_key:
            self._session.headers.update({"x-api-key": api_key})
            self.api_key_active = True
            print("Clé API Semantic Scholar détectée et appliquée.")
            log_event("CONFIG", "Clé API Semantic Scholar détectée")
        else:
            print(
                "Aucune clé API Semantic Scholar détectée. Configurez keys.py ou la variable",
                "d’environnement correspondante pour augmenter les quotas.",
            )
            log_event("CONFIG", "Aucune clé API Semantic Scholar configurée")

        tor_browser_path = load_tor_browser_path()
        if tor_browser_path:
            log_event("TOR_CONFIG", "Chemin Tor Browser fourni", path=tor_browser_path)
        tor_proxy_hint = load_tor_proxy()
        control_port, control_password = load_tor_control_settings()
        if control_port:
            self._tor_control_port = control_port
        if control_password:
            self._tor_control_password = control_password
        if not tor_proxy_hint:
            proxy_candidate, manager = ensure_local_tor_proxy(tor_browser_path)
            if proxy_candidate:
                tor_proxy_hint = proxy_candidate
                log_event("TOR_CONFIG", "Proxy Tor local disponible", proxy=tor_proxy_hint)
            if manager:
                self._tor_manager = manager
        using_tor, proxy_label = configure_session_for_tor(
            self._session,
            explicit_proxy=tor_proxy_hint,
        )
        if using_tor:
            print("Utilisation du proxy Tor pour Semantic Scholar.")
            self.using_tor = True
            self._tor_proxy = proxy_label
            log_event("TOR_USAGE", "Session configurée pour utiliser Tor", proxy=proxy_label)
            if self._tor_control_port is not None:
                if request_new_tor_identity(self._tor_control_port, self._tor_control_password):
                    log_event(
                        "TOR_USAGE",
                        "Identité Tor renouvelée avant la collecte",
                        port=self._tor_control_port,
                    )
                else:
                    log_event(
                        "TOR_USAGE",
                        "Impossible de renouveler l’identité Tor",
                        port=self._tor_control_port,
                    )
        elif tor_proxy_hint:
            print(
                "Un proxy Tor a été configuré dans keys.py mais n’a pas pu être appliqué.",
                "Vérifiez que le service Tor est démarré et accessible.",
            )
            log_event("TOR_USAGE", "Échec de l’application du proxy Tor", proxy=tor_proxy_hint)
        else:
            print(
                "Aucun proxy Tor détecté. Pour activer la protection, définissez TOR_SOCKS_PROXY",
                "dans keys.py ou dans votre environnement.",
            )
            log_event("TOR_USAGE", "Aucun proxy Tor détecté")

    def update_search_parameters(self, input_search, input_pages, year_filter, keyword_rules):
        normalized_search = self._normalize_search_phrase(input_search)
        if normalized_search != (input_search or ""):
            log_event(
                "SEARCH_PIPELINE",
                "Requête normalisée pour le crawler",
                original=input_search,
                sanitized=normalized_search,
            )
        self.input_search = normalized_search
        self.input_pages = input_pages
        self.year_filter_choice = self._map_year_filter(year_filter)
        self.keyword_rules = keyword_rules or []
        log_event(
            "CRAWLER_CONFIG",
            "Paramètres de recherche mis à jour",
            query=self.input_search,
            pages=self.input_pages,
            year_filter=self.year_filter_choice,
            keywords=self.keyword_rules,
        )

    def _map_year_filter(self, year_filter) -> Optional[int]:
        if year_filter is None:
            return None

        if isinstance(year_filter, int):
            return max(0, year_filter) or None

        normalized = str(year_filter).strip().lower()
        if not normalized:
            return None

        if '5' in normalized:
            return 5
        if '10' in normalized:
            return 10
        if '20' in normalized:
            return 20

        if 'pas' in normalized or 'toute' in normalized:
            return None

        return None

    def _build_year_param(self, years: Optional[int]) -> Optional[str]:
        if not years:
            return None
        current_year = datetime.date.today().year
        start_year = max(1900, current_year - years + 1)
        return f"{start_year}-"

    def _normalize_search_phrase(self, value: Optional[str]) -> str:
        return re.sub(r"\s+", " ", (value or "").strip())

    def _dedupe_tokens(self, text: str) -> str:
        tokens = [token for token in re.split(r"\s+", text.strip()) if token]
        deduped: List[str] = []
        for token in tokens:
            if deduped and token.lower() == deduped[-1].lower():
                continue
            deduped.append(token)
        return " ".join(deduped)

    def _describe_standard_strategy(self) -> str:
        if not self.year_filter_choice:
            return "Recherche standard"

        if self.year_filter_choice == 5:
            suffix = "(≤ 5 ans)"
        elif self.year_filter_choice == 10:
            suffix = "(≤ 10 ans)"
        elif self.year_filter_choice == 20:
            suffix = "(≤ 20 ans)"
        else:
            suffix = ""

        if suffix:
            return f"Recherche standard {suffix}"
        return "Recherche standard"

    def _should_add_recent_strategy(self, years: int) -> bool:
        if years <= 0:
            return False
        if self.year_filter_choice is None:
            return True
        return self.year_filter_choice > years

    def _build_translated_query(self, text: str) -> str:
        variants = list(build_text_variants(text or ""))
        if not variants:
            return ""
        joined = " ".join(variants)
        cleaned = self._dedupe_tokens(joined)
        log_event(
            "QUERY_VARIANTS",
            "Requête enrichie avec variantes",
            original=text,
            variants=variants,
            normalized=cleaned,
        )
        return cleaned

    def _prepare_keyword_constraints(self):
        mandatory = []
        optional = []

        for keyword in self.keyword_rules:
            term = (keyword.get('term') or '').strip()
            if not term:
                continue

            variants = list(build_text_variants(term))
            if not variants:
                continue

            entry = {
                'label': term,
                'forms': variants,
                'display_terms': set(variants),
            }
            log_event(
                "KEYWORD_VARIANTS",
                "Critère enrichi",
                original=term,
                variants=variants,
                importance=keyword.get('importance'),
            )

            if keyword.get('importance') == 'required':
                mandatory.append(entry)
            else:
                optional.append(entry)

        log_event(
            "KEYWORD_SUMMARY",
            "Résumé des contraintes de mots-clés",
            mandatory=len(mandatory),
            optional=len(optional),
        )
        return mandatory, optional

    # extract the type of the article from the BibText cite text and returns it as a single word string
    # TODO: extract it from "publicationTypes" attribute
    def return_type_cite(self, string_cite):
        list_cite = string_cite.split('{')
        type_cite = list_cite[0][1:]
        return type_cite

    def start_search(self):
        self.start_time = Timer.timeNow()
        log_event(
            "CRAWLER_RUN",
            "Début de la recherche",
            query=self.input_search,
            article_limit=self.input_pages,
            year_filter=self.year_filter_choice,
            tor_enabled=self.using_tor,
            tor_proxy=self._tor_proxy,
        )

        # loads files for the inputted search if they exist, otherwise, the files are created
        self.manager = Gerenciador(self.input_search, self.root_directory)
        self.list_authors = set(self.manager.loadAutores())
        self.list_articles = set(self.manager.loadArtigos())

        existing_articles = len(self.list_articles)
        existing_keys = {
            (
                (article.titulo or "").strip().lower(),
                (article.link or "").strip().lower(),
            )
            for article in self.list_articles
        }
        author_lookup = {
            (author.nome, author.link): author for author in self.list_authors
        }

        _search_query = self._build_translated_query(self.input_search)
        if _search_query != self.input_search:
            log_event(
                "QUERY_NORMALIZED",
                "Requête finale transmise à Semantic Scholar",
                original=self.input_search,
                query=_search_query,
            )
        article_limit = max(1, int(self.input_pages))
        desired_results = article_limit
        _articles_endpoint = 'https://api.semanticscholar.org/graph/v1/paper/search'

        base_query_params = {
            "query": _search_query,
            "fields": "abstract,authors,citationCount,citationStyles,title,url,venue,year",
            "offset": 0,
            "limit": article_limit,
        }
        log_event(
            "CRAWLER_QUERY",
            "Paramètres de requête Semantic Scholar",
            base_query=base_query_params,
        )

        year_param = self._build_year_param(self.year_filter_choice)
        if year_param:
            base_query_params["year"] = year_param

        mandatory_keywords, optional_keywords = self._prepare_keyword_constraints()

        self.relevance_engine = QueryRelevanceEngine(
            _search_query,
            mandatory_keywords=mandatory_keywords,
            optional_keywords=optional_keywords,
        )
        targeted_queries = self.relevance_engine.build_targeted_queries()
        log_event(
            "CRAWLER_TARGETS",
            "Requêtes ciblées construites",
            total=len(targeted_queries),
        )

        search_strategies = [
            (self._describe_standard_strategy(), {}),
        ]

        if targeted_queries:
            for position, query_override in enumerate(targeted_queries, start=1):
                description = "Requête ciblée" if len(targeted_queries) == 1 else f"Requête ciblée {position}"
                search_strategies.append(
                    (
                        description,
                        {
                            "query_override": query_override,
                        },
                    )
                )

        if self._should_add_recent_strategy(5):
            search_strategies.append(
                (
                    "Articles récents (5 dernières années)",
                    {"year": self._build_year_param(5)},
                )
            )

        if self._should_add_recent_strategy(10):
            search_strategies.append(
                (
                    "Articles publiés depuis 10 ans",
                    {"year": self._build_year_param(10)},
                )
            )

        search_strategies.append(("Requête orientée revue de littérature", {"query_suffix": "review"}))
        accepted_candidates = {}
        fallback_candidates = {}

        responses_received = 0

        def normalize_key(article: Artigo) -> tuple[str, str]:
            return (
                (article.titulo or "").strip().lower(),
                (article.link or "").strip().lower(),
            )

        log_event(
            "CRAWLER_STRATEGIES",
            "Liste des stratégies de recherche",
            strategies=[description for description, _ in search_strategies],
        )

        for index, (description, extra) in enumerate(search_strategies, start=1):
            if self.gui is not None:
                self.gui.notify_strategy_started(description, index, len(search_strategies))

            query_params = dict(base_query_params)
            if "query_override" in extra:
                query_params["query"] = extra["query_override"]
                extra_params = {k: v for k, v in extra.items() if k not in {"query_override"}}
            elif "query_suffix" in extra:
                query_params["query"] = re.sub(
                    r"\s+",
                    " ",
                    f"{query_params['query']} {extra['query_suffix']}".strip(),
                )
                extra_params = {k: v for k, v in extra.items() if k != "query_suffix"}
            else:
                extra_params = extra
            query_params.update(extra_params)
            if query_params.get("query"):
                query_params["query"] = self._dedupe_tokens(str(query_params["query"]))

            try:
                articles_res = self._perform_semantic_scholar_request(
                    _articles_endpoint,
                    query_params,
                    request_details={
                        "description": description,
                        "params": dict(query_params),
                        "strategy_index": index,
                    },
                )
            except requests.RequestException as exc:
                error_message = self._format_request_error(exc)
                print(
                    "Failed to reach Semantic Scholar API:",
                    exc,
                    file=sys.stderr,
                )
                log_exception(
                    "CRAWLER_REQUEST_ERROR",
                    "Erreur lors de l’interrogation de Semantic Scholar",
                    exc,
                    description=description,
                    params=query_params,
                )
                self.gui.show_search_failed_alert(error_message)
                return

            responses_received += 1

            data = articles_res.get("data")
            if not isinstance(data, list):
                print("From Semantic Scholar API:", file=sys.stderr)
                for key in articles_res.keys():
                    print(key, ": ", articles_res[key], sep="", file=sys.stderr)
                data = []
                log_event(
                    "CRAWLER_RESPONSE",
                    "Réponse inattendue du service",
                    description=description,
                    keys=list(articles_res.keys()),
                )

            previous_total = len(accepted_candidates)

            for item in data:
                title = item["title"]
                _paper_authors = item["authors"]

                list_authors_in_article: List[Autor] = []
                seen_authors = set()

                for temp in _paper_authors:
                    name = temp["name"]
                    link = None
                    author_key = (name, link)
                    author = author_lookup.get(author_key)
                    if author is None:
                        author = Autor(name, link)
                        author_lookup[author_key] = author
                    if author not in seen_authors:
                        list_authors_in_article.append(author)
                        seen_authors.add(author)

                list_authors_in_article.sort()

                _venue = item["venue"]
                origin = _venue if _venue else "-"

                _year = item["year"]
                date = str(_year) if _year else "0"

                _citationCount = item["citationCount"]
                citationCount = str(int(_citationCount if _citationCount else "0"))

                _url = item["url"]
                link = _url if _url else "-"

                _citationStyles = item["citationStyles"]
                _bibtex = _citationStyles["bibtex"] if _citationStyles else _citationStyles
                bibtex = '-'
                cite = '-'
                if _bibtex:
                    bibtex = _bibtex
                    cite = self.return_type_cite(bibtex)

                _abstract = item["abstract"]
                synopsis = _abstract.replace(" Expand", "") if _abstract else "Aucun résumé"
                synopsis = synopsis.replace("TLDR\n", "")

                qualis_score = find_similar_journal(target_text=origin)

                new_article = Artigo(
                    title,
                    list_authors_in_article,
                    origin,
                    date,
                    citationCount,
                    link,
                    cite,
                    bibtex,
                    synopsis,
                    qualis_score,
                )

                relevance_result = self.relevance_engine.evaluate(title, synopsis)
                new_article.relevance_score = relevance_result.score
                concepts_to_store = relevance_result.matched_concepts or relevance_result.matched_terms
                new_article.concepts = sorted(concepts_to_store)

                key = normalize_key(new_article)
                if key in existing_keys:
                    continue

                if key in accepted_candidates:
                    if accepted_candidates[key][0].relevance_score >= new_article.relevance_score:
                        continue

                if key in fallback_candidates:
                    if fallback_candidates[key][0].relevance_score >= new_article.relevance_score:
                        continue

                current_count = len(accepted_candidates)
                if self.relevance_engine.should_keep(relevance_result, current_count, desired_results):
                    accepted_candidates[key] = (new_article, list_authors_in_article, relevance_result)
                    log_event(
                        "CRAWLER_ACCEPTED",
                        "Article retenu selon les critères",
                        title=title,
                        link=link,
                        score=relevance_result.score,
                        mandatory_hits=sorted(relevance_result.mandatory_hits),
                        optional_hits=sorted(relevance_result.optional_hits),
                        optional_count=len(relevance_result.optional_hits),
                        title_only_groups=relevance_result.title_only_groups,
                    )
                else:
                    if relevance_result.mandatory_missing:
                        log_event(
                            "CRAWLER_REJECTED",
                            "Article rejeté : critères obligatoires manquants",
                            title=title,
                            link=link,
                            score=relevance_result.score,
                            missing=sorted(relevance_result.mandatory_missing),
                        )
                        continue
                    fallback_candidates[key] = (new_article, list_authors_in_article, relevance_result)
                    log_event(
                        "CRAWLER_FALLBACK",
                        "Article conservé pour analyse ultérieure",
                        title=title,
                        link=link,
                        score=relevance_result.score,
                        mandatory_hits=sorted(relevance_result.mandatory_hits),
                        optional_hits=sorted(relevance_result.optional_hits),
                        optional_count=len(relevance_result.optional_hits),
                        title_only_groups=relevance_result.title_only_groups,
                    )

            new_items = len(accepted_candidates) - previous_total
            total_items = articles_res.get("total", len(data)) or len(data)

            if self.gui is not None:
                self.gui.notify_strategy_results(description, new_items, total_items)
            log_event(
                "CRAWLER_RESPONSE",
                "Résultats reçus pour une stratégie",
                description=description,
                new_items=new_items,
                total_items=total_items,
                accepted=len(accepted_candidates),
            )

            if len(accepted_candidates) >= desired_results:
                break

        selected_candidates = sorted(
            accepted_candidates.values(),
            key=lambda candidate: candidate[0].relevance_score,
            reverse=True,
        )

        if len(selected_candidates) < desired_results and fallback_candidates:
            remaining = desired_results - len(selected_candidates)
            fallback_sorted = sorted(
                fallback_candidates.values(),
                key=lambda candidate: candidate[0].relevance_score,
                reverse=True,
            )
            selected_candidates.extend(fallback_sorted[:remaining])
            log_event(
                "CRAWLER_SELECTION",
                "Ajout de candidats de secours",
                remaining=remaining,
            )

        selected_candidates = selected_candidates[:desired_results]

        self.list_authors = set(self.list_authors)

        for article, authors, _ in selected_candidates:
            key = normalize_key(article)
            if key in existing_keys:
                continue

            before = len(self.list_articles)
            self.list_articles.add(article)
            if len(self.list_articles) != before:
                existing_keys.add(key)
                for author in authors:
                    if author not in self.list_authors:
                        self.list_authors.add(author)
                    author.addArtigo(article)

        self.end_time = Timer.timeNow()

        total_added = len(self.list_articles) - existing_articles
        if responses_received == 0 or total_added <= 0:
            self.gui.show_search_failed_alert(
                f"Aucun nouvel article n’a été trouvé pour « {self.input_search} ». Modifiez la requête ou réessayez ultérieurement."
            )
            log_event(
                "CRAWLER_EMPTY",
                "Aucun nouvel article trouvé",
                query=self.input_search,
                responses=responses_received,
            )
            return

        self.list_articles = list(self.list_articles)
        self.list_authors = list(self.list_authors)

        self.manager.saveArtigos(self.list_articles)
        self.manager.saveAutores(self.list_authors)
        log_event(
            "CRAWLER_STORAGE",
            "Résultats sauvegardés",
            articles_path=self.manager.arquivo_artigos,
            authors_path=self.manager.arquivo_autores,
            total_articles=len(self.list_articles),
            total_authors=len(self.list_authors),
        )

        self.gui.show_search_done_alert(
            Timer.totalTime(self.start_time, self.end_time),
            str(total_added),
        )
        log_event(
            "CRAWLER_COMPLETE",
            "Recherche terminée",
            total_articles=len(self.list_articles),
            added=total_added,
            duration_seconds=Timer.totalTime(self.start_time, self.end_time).seconds,
        )

    def _perform_semantic_scholar_request(self, endpoint, params, *, request_details=None):
        """Issue a request with retry logic for rate limiting and transient failures."""
        max_attempts = 6
        backoff = 5
        request_logged = False
        for attempt in range(1, max_attempts + 1):
            if not request_logged:
                metadata = {}
                if isinstance(request_details, dict):
                    metadata.update(request_details)
                metadata.setdefault("params", dict(params))
                log_event(
                    "CRAWLER_REQUEST",
                    "Envoi d’une requête Semantic Scholar",
                    **metadata,
                )
                request_logged = True
            log_event(
                "CRAWLER_HTTP",
                "Tentative d’appel Semantic Scholar",
                attempt=attempt,
                max_attempts=max_attempts,
            )
            try:
                with closing(
                    self._session.get(
                        endpoint,
                        params=params,
                        timeout=60,
                    )
                ) as response:
                    response.raise_for_status()
                    payload = response.json()
                    log_event(
                        "CRAWLER_HTTP",
                        "Réponse reçue",
                        attempt=attempt,
                        status=response.status_code,
                        remaining=response.headers.get("X-RateLimit-Remaining"),
                    )
                    return payload
            except requests.HTTPError as exc:
                response = exc.response
                if response is None:
                    raise

                status_code = response.status_code
                if status_code == 429 or status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            wait_time = int(float(retry_after))
                        except ValueError:
                            wait_time = backoff
                    else:
                        wait_time = backoff

                    if self.gui is not None:
                        if status_code == 429:
                            self.gui.notify_rate_limit(wait_time, attempt, max_attempts)
                        else:
                            self.gui.notify_transient_error(wait_time, attempt, max_attempts)
                    log_event(
                        "CRAWLER_HTTP_WAIT",
                        "Réponse HTTP invite à patienter",
                        status=status_code,
                        wait_seconds=wait_time,
                        attempt=attempt,
                    )

                    if attempt == max_attempts:
                        raise

                    time.sleep(wait_time)
                    backoff = min(backoff * 2, 60)
                    continue

                raise
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == max_attempts:
                    raise

                if self.gui is not None:
                    self.gui.notify_transient_error(backoff, attempt, max_attempts)
                log_exception(
                    "CRAWLER_HTTP_WAIT",
                    "Nouvelle tentative après erreur réseau",
                    exc,
                    wait_seconds=backoff,
                    attempt=attempt,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
            except requests.RequestException:
                raise

        raise requests.RequestException("Exceeded retry attempts")

    def _format_request_error(self, exc: requests.RequestException) -> str:
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            status_code = exc.response.status_code
            if status_code == 429:
                return (
                    "La limite de requêtes Semantic Scholar est atteinte. Les tentatives ont échoué malgré plusieurs essais. Patientez quelques minutes ou configurez une clé API pour augmenter les limites."
                )
            if status_code >= 500:
                return "Le service Semantic Scholar est momentanément indisponible. Veuillez réessayer plus tard."
            return f"La requête Semantic Scholar a échoué avec le statut {status_code}."

        if isinstance(exc, requests.Timeout):
            return "La requête vers Semantic Scholar a expiré. Vérifiez votre connexion puis réessayez."

        return "Une erreur inattendue est survenue lors de la communication avec Semantic Scholar."

    def saves_excel(self, parameter):
        # creates the excel file
        os.chdir(self.root_directory)
        excelExporter = ExcelExporter(self.input_search, self.gui.single_or_merge, self.root_directory)
        excelExporter.gui = self.gui
        excelExporter.order_type(parameter)

    def connection_status_message(self):
        if self.using_tor:
            if self._tor_proxy:
                base_message = f"Protection active : les requêtes passent par Tor ({self._tor_proxy})."
            else:
                base_message = "Protection active : les requêtes passent par Tor."
        else:
            base_message = "Connexion directe : aucun proxy Tor détecté."

        if self.api_key_active:
            return base_message + " Clé API Semantic Scholar chargée."
        return base_message + " Pas de clé API détectée."
