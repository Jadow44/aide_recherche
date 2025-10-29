import pickle
from pathlib import Path

import xlsxwriter

import Gerenciador
from activity_logger import log_event


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class ExcelExporter:
    _OPTION_MAPPING = {
        'Importance Rate (RECOMMENDED)': 'optimized',
        "Indice d'importance (RECOMMANDÉ)": 'optimized',
        'Indice d’importance (RECOMMANDÉ)': 'optimized',
        'Number of Citations': 'citations',
        'Nombre de citations': 'citations',
        'Newer Articles': 'newest',
        'Articles les plus récents': 'newest',
        "Alphabetically, by Article's Title": 'alphabetical',
        'Ordre alphabétique du titre': 'alphabetical',
    }
    def __init__(self, search, single_or_merge, root_directory):
        self.root_directory = root_directory
        self.articles_list = []
        self.authors_list = []
        self.search_parameter = search
        self.ordered_date_articles_list = []
        self.ordered_citations_articles_list = []
        self.ordered_optimized_list = []
        self.gui = None
        self.single_or_merge = single_or_merge

    def set_list(self, articles_list, authors_list):
        self.articles_list = articles_list
        self.authors_list = authors_list

    def order_type(self, parameter):
        order_key = self._OPTION_MAPPING.get(parameter)

        if order_key is None and isinstance(parameter, str):
            normalized = parameter.strip().lower()
            for option, mapped_key in self._OPTION_MAPPING.items():
                if option.lower() == normalized:
                    order_key = mapped_key
                    break

        if order_key is None:
            print(f"Option de tri « {parameter} » inconnue. Utilisation de l’indice d’importance recommandé.")
            order_key = 'optimized'

        if self.single_or_merge:
            merger = getattr(self.gui, 'merger', None)
            if merger is None:
                self.gui.show_export_empty_alert(merge=True)
                return False

            self.articles_list = list(merger.articles_list)
            self.authors_list = list(merger.authors_list)

            if not self.articles_list:
                self.gui.show_export_empty_alert(merge=True)
                return False

            return self.merge_creator(order_key)

        return self.single_creator(order_key)

    def order_optimized(self, articles_list):
        ordered = list(articles_list)
        newer_date = max((_safe_int(article.data) for article in ordered), default=0)

        for article in ordered:
            article.data_relativa = _safe_int(article.data) / (newer_date if newer_date > 0 else 1)

            citations = _safe_int(article.citacoes)
            if citations > 100:
                article.citacoes_relativa = 1
            elif 20 < citations <= 100:
                article.citacoes_relativa = 0.5
            elif citations > 0:
                article.citacoes_relativa = 0.2
            else:
                article.citacoes_relativa = 0

            qualis_dict = {'A1': 1, 'A2': 2, 'A3': 3, 'A4': 4, 'B1': 5, 'B2': 6, 'B3': 7, 'B4': 8, 'B5': 9, 'C': 10, 'NF': 10, 'NP': 10}
            qualis_score = (10 - qualis_dict.get(article.qualis, 10)) / 9

            relevance_value = getattr(article, 'relevance_score', 0.0)
            relevance_ratio = max(0.0, min(relevance_value, 100.0)) / 100
            article.relevance_relativa = relevance_ratio

            article.total_factor = round(
                0.35 * relevance_ratio
                + 0.2 * article.data_relativa
                + 0.25 * article.citacoes_relativa
                + 0.2 * qualis_score,
                4,
            )

        ordered.sort(key=lambda model: model.total_factor, reverse=True)
        self.ordered_optimized_list = ordered
        return ordered

    def order_articles(self, articles_list, order_type):
        ordered = list(articles_list)

        max_citations = max((_safe_int(article.citacoes) for article in ordered), default=0)
        newer_date = max((_safe_int(article.data) for article in ordered), default=0)
        qualis_dict = {'A1': 1, 'A2': 2, 'A3': 3, 'A4': 4, 'B1': 5, 'B2': 6, 'B3': 7, 'B4': 8, 'B5': 9, 'C': 10, 'NF': 10, 'NP': 10}

        for article in ordered:
            article.data_relativa = _safe_int(article.data) / (newer_date if newer_date > 0 else 1)
            article.citacoes_relativa = _safe_int(article.citacoes) / (max_citations if max_citations > 0 else 1)
            qualis_score = (10 - qualis_dict.get(article.qualis, 10)) / 9
            relevance_value = getattr(article, 'relevance_score', 0.0)
            relevance_ratio = max(0.0, min(relevance_value, 100.0)) / 100
            article.relevance_relativa = relevance_ratio
            article.total_factor = round(
                0.35 * relevance_ratio
                + 0.2 * article.data_relativa
                + 0.25 * article.citacoes_relativa
                + 0.2 * qualis_score,
                4,
            )

        if order_type == 'citations':
            ordered.sort(key=lambda model: model.citacoes_relativa, reverse=True)
            self.ordered_citations_articles_list = ordered
        elif order_type == 'newest':
            ordered.sort(key=lambda model: model.data_relativa, reverse=True)
            self.ordered_date_articles_list = ordered
        elif order_type == 'alphabetical':
            ordered.sort(key=lambda model: (model.titulo or '').lower())

        return ordered

    def _apply_order(self, articles_list, order_key):
        if order_key == 'optimized':
            return self.order_optimized(articles_list)
        if order_key in {'citations', 'newest', 'alphabetical'}:
            return self.order_articles(articles_list, order_key)
        return list(articles_list)

    def merge_creator(self, order_key):
        diretorio_excel = Path(self.root_directory) / 'Results' / 'Merged Search'
        diretorio_excel.mkdir(parents=True, exist_ok=True)

        workbook_path = diretorio_excel / 'Merged.xlsx'
        log_event(
            "EXPORT_XLSX_START",
            "Création d’un export Excel fusionné",
            path=str(workbook_path),
            order=order_key,
            merge=True,
        )

        workbook = xlsxwriter.Workbook(str(workbook_path))

        worksheet_artigos = workbook.add_worksheet('ARTICLES')
        worksheet_autores = workbook.add_worksheet('AUTEURS')

        if not self.articles_list:
            workbook.close()
            log_event(
                "EXPORT_XLSX_ABORTED",
                "Export Excel fusionné annulé : aucune donnée",
                path=str(workbook_path),
                merge=True,
            )
            self.gui.show_export_empty_alert(merge=True)
            return False

        indice = 0
        titulo = 1
        autores = 2
        publicado = 3
        data = 4
        pertinence = 5
        citacoes = 6
        qualis = 7
        optimized = 8
        link = 9
        bibtex = 10
        synopsis = 11
        concepts_col = 12
        linha = 0

        """label_comment = 'Label NUMBER: 1 -> article\n' \
                        'Label NUMBER: 2 -> conference, inproceedings, proceedings or phdthesis\n' \
                        'Label NUMBER: 3 -> mastersthesis, book, inbook, Incollection or techreport\n' \
                        'Label NUMBER: 4 -> manual, misc or unpublished'
        """

        primeiraLinha_format = workbook.add_format({'bold': True,
                                                    'font_size': '16',
                                                    'align': 'center',
                                                    'bg_color': '#757A79',
                                                    'font_color': 'white',
                                                    'border': 1})

        one_line_format = workbook.add_format({'bg_color': "#B5E9FF",
                                               'align': 'center',
                                               'border': 1})

        autor_format = workbook.add_format({'bg_color': "#B5E9FF",
                                            'align': 'center',
                                            'border': 1,
                                            'underline': True,
                                            'font_color': 'blue'})

        merge_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': "#B5E9FF",
            'border': 1
        })

        worksheet_artigos.write(linha, indice, 'Indice', primeiraLinha_format)
        worksheet_artigos.write(linha, titulo, 'Titre', primeiraLinha_format)
        worksheet_artigos.write(linha, autores, 'Auteur(s)', primeiraLinha_format)
        worksheet_artigos.write(linha, publicado, 'Source de publication', primeiraLinha_format)
        worksheet_artigos.write(linha, data, 'Année de publication', primeiraLinha_format)
        worksheet_artigos.write(linha, pertinence, 'Score de pertinence', primeiraLinha_format)
        worksheet_artigos.write(linha, citacoes, 'Citations', primeiraLinha_format)
        worksheet_artigos.write(linha, qualis, 'Indice Qualis', primeiraLinha_format)
        worksheet_artigos.write(linha, optimized, 'Indice d’importance', primeiraLinha_format)
        worksheet_artigos.write(linha, link, 'Lien vers l’article', primeiraLinha_format)
        worksheet_artigos.write(linha, bibtex, 'BibTeX', primeiraLinha_format)
        worksheet_artigos.write(linha, synopsis, 'Résumé', primeiraLinha_format)
        worksheet_artigos.write(linha, concepts_col, 'Concepts détectés', primeiraLinha_format)
        linha += 1

        ordered_articles = self._apply_order(self.articles_list, order_key)

        numeroDoArtigo = 1

        for artigo in ordered_articles:
            primeiraLinha = linha
            worksheet_artigos.write(linha, indice, str(numeroDoArtigo), one_line_format)

            #articleLabel = self.article_label(artigo)

            #worksheet_artigos.write(linha, type, articleLabel, one_line_format)
            worksheet_artigos.write(linha, titulo, artigo.titulo, one_line_format)
            worksheet_artigos.write(linha, publicado, artigo.publicado_em, one_line_format)
            worksheet_artigos.write(linha, data, artigo.data, one_line_format)
            worksheet_artigos.write(linha, pertinence, f"{getattr(artigo, 'relevance_score', 0.0):.2f}", one_line_format)
            worksheet_artigos.write(linha, citacoes, artigo.citacoes, one_line_format)
            worksheet_artigos.write(linha, qualis, artigo.qualis, one_line_format)
            worksheet_artigos.write(linha, optimized, artigo.total_factor, one_line_format)
            worksheet_artigos.write(linha, link, artigo.link, one_line_format)
            worksheet_artigos.write(linha, bibtex, artigo.bibtex, one_line_format)
            worksheet_artigos.write(linha, synopsis, artigo.synopsis, one_line_format)
            concepts_text = ', '.join(getattr(artigo, 'concepts', [])) or '-'
            worksheet_artigos.write(linha, concepts_col, concepts_text, one_line_format)
            authors = ''

            for autor in artigo.autores:
                authors += autor.nome + ', '
            authors = authors[:-2]
            worksheet_artigos.write(linha, autores, authors, one_line_format)

            numeroDoArtigo += 1
            linha += 1

        nome_autor = 0
        link_autor = 1
        artigos_autor = 2
        linha = 0

        worksheet_autores.write(linha, nome_autor, 'Nom de l’auteur', primeiraLinha_format)
        worksheet_autores.write(linha, link_autor, 'Page de l’auteur', primeiraLinha_format)
        worksheet_autores.write(linha, artigos_autor, 'Articles associés', primeiraLinha_format)
        linha += 1

        for autor in self.authors_list:
            primeiraLinha = linha
            worksheet_autores.write(linha, nome_autor, autor.nome, one_line_format)
            author_link = autor.link if autor.link else '-'
            worksheet_autores.write(linha, link_autor, author_link, one_line_format)
            for artigos in autor.artigos:
                try:
                    worksheet_autores.write_url(linha, artigos_autor, artigos.link, autor_format, string=artigos.titulo)
                except:
                    worksheet_autores.write(linha, artigos_autor, artigos.titulo, one_line_format)
                finally:
                    linha += 1
            if primeiraLinha != linha - 1:
                worksheet_autores.merge_range(primeiraLinha, nome_autor, linha - 1, nome_autor, autor.nome,
                                              merge_format)
                worksheet_autores.merge_range(primeiraLinha, link_autor, linha - 1, link_autor, author_link,
                                              merge_format)

        workbook.close()

        log_event(
            "EXPORT_XLSX_DONE",
            "Export Excel fusionné terminé",
            path=str(workbook_path),
            merge=True,
            articles=len(self.articles_list),
            authors=len(self.authors_list),
        )

        self.gui.show_saved_alert(str(diretorio_excel))
        return True

    def single_creator(self, order_key):
        gerenciador = Gerenciador.Gerenciador(self.search_parameter, self.root_directory)
        diretorio_excel = Path(gerenciador.storage_dir)
        diretorio_excel.mkdir(parents=True, exist_ok=True)

        workbook_path = diretorio_excel / f"{gerenciador.storage_label}.xlsx"
        log_event(
            "EXPORT_XLSX_START",
            "Création d’un export Excel",
            path=str(workbook_path),
            order=order_key,
            merge=False,
        )

        workbook = xlsxwriter.Workbook(str(workbook_path))

        worksheet_artigos = workbook.add_worksheet('ARTICLES')
        worksheet_autores = workbook.add_worksheet('AUTEURS')

        indice = 0
        titulo = 1
        autores = 2
        publicado = 3
        data = 4
        pertinence = 5
        citacoes = 6
        qualis = 7
        optimized = 8
        link = 9
        bibtex = 10
        synopsis = 11
        concepts_col = 12
        linha = 0

        """label_comment = 'Label NUMBER: 1 -> Journal Article\n' \
                        'Label NUMBER: 2 -> Conference, CaseReport\n' \
                        'Label NUMBER: 3 -> Book, BookSection, News, Study\n' \
                        'Label NUMBER: 4 -> Others'
        """

        primeiraLinha_format = workbook.add_format({'bold': True,
                                                    'font_size': '16',
                                                    'align': 'center',
                                                    'bg_color': '#757A79',
                                                    'font_color': 'white',
                                                    'border': 1})

        one_line_format = workbook.add_format({'bg_color': "#B5E9FF",
                                               'align': 'center',
                                               'border': 1})

        autor_format = workbook.add_format({'bg_color': "#B5E9FF",
                                            'align': 'center',
                                            'border': 1,
                                            'underline': True,
                                            'font_color': 'blue'})

        merge_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': "#B5E9FF",
            'border': 1
        })

        worksheet_artigos.write(linha, indice, 'Indice', primeiraLinha_format)
        worksheet_artigos.write(linha, titulo, 'Titre', primeiraLinha_format)
        worksheet_artigos.write(linha, autores, 'Auteur(s)', primeiraLinha_format)
        worksheet_artigos.write(linha, publicado, 'Source de publication', primeiraLinha_format)
        worksheet_artigos.write(linha, data, 'Année de publication', primeiraLinha_format)
        worksheet_artigos.write(linha, pertinence, 'Score de pertinence', primeiraLinha_format)
        worksheet_artigos.write(linha, citacoes, 'Citations', primeiraLinha_format)
        worksheet_artigos.write(linha, qualis, 'Indice Qualis', primeiraLinha_format)
        worksheet_artigos.write(linha, optimized, 'Indice d’importance', primeiraLinha_format)
        worksheet_artigos.write(linha, link, 'Lien vers l’article', primeiraLinha_format)
        worksheet_artigos.write(linha, bibtex, 'BibTeX', primeiraLinha_format)
        worksheet_artigos.write(linha, synopsis, 'Résumé', primeiraLinha_format)
        worksheet_artigos.write(linha, concepts_col, 'Concepts détectés', primeiraLinha_format)
        linha += 1

        try:
            listaDeArtigos = gerenciador.loadArtigos()
        except (FileNotFoundError, EOFError, pickle.UnpicklingError):
            listaDeArtigos = []

        try:
            listaDeAutores = gerenciador.loadAutores()
        except (FileNotFoundError, EOFError, pickle.UnpicklingError):
            listaDeAutores = []

        if not listaDeArtigos:
            workbook.close()
            log_event(
                "EXPORT_XLSX_ABORTED",
                "Export Excel annulé : aucune donnée",
                path=str(workbook_path),
                merge=False,
            )
            self.gui.show_export_empty_alert(merge=False, search=self.search_parameter)
            return False

        self.articles_list = list(listaDeArtigos)
        self.authors_list = list(listaDeAutores)

        ordered_articles = self._apply_order(self.articles_list, order_key)

        numeroDoArtigo = 1

        for artigo in ordered_articles:
            primeiraLinha = linha
            worksheet_artigos.write(linha, indice, str(numeroDoArtigo), one_line_format)

            #articleLabel = self.article_label(artigo)

            #worksheet_artigos.write(linha, type, articleLabel, one_line_format)
            worksheet_artigos.write(linha, titulo, artigo.titulo, one_line_format)
            worksheet_artigos.write(linha, publicado, artigo.publicado_em, one_line_format)
            worksheet_artigos.write(linha, data, artigo.data, one_line_format)
            worksheet_artigos.write(linha, pertinence, f"{getattr(artigo, 'relevance_score', 0.0):.2f}", one_line_format)
            worksheet_artigos.write(linha, citacoes, artigo.citacoes, one_line_format)
            worksheet_artigos.write(linha, qualis, artigo.qualis, one_line_format)
            worksheet_artigos.write(linha, optimized, artigo.total_factor, one_line_format)
            worksheet_artigos.write(linha, link, artigo.link, one_line_format)
            worksheet_artigos.write(linha, bibtex, artigo.bibtex, one_line_format)
            worksheet_artigos.write(linha, synopsis, artigo.synopsis, one_line_format)
            concepts_text = ', '.join(getattr(artigo, 'concepts', [])) or '-'
            worksheet_artigos.write(linha, concepts_col, concepts_text, one_line_format)
            authors = ''

            for autor in artigo.autores:
                authors += autor.nome + ', '
            authors = authors[:-2]
            worksheet_artigos.write(linha, autores, authors, one_line_format)

            numeroDoArtigo += 1
            linha += 1

        nome_autor = 0
        link_autor = 1
        artigos_autor = 2
        linha = 0

        worksheet_autores.write(linha, nome_autor, 'Nom de l’auteur', primeiraLinha_format)
        worksheet_autores.write(linha, link_autor, 'Page de l’auteur', primeiraLinha_format)
        worksheet_autores.write(linha, artigos_autor, 'Articles associés', primeiraLinha_format)
        linha += 1

        for autor in self.authors_list:
            if len(autor.artigos) > 0:
                primeiraLinha = linha
                worksheet_autores.write(linha, nome_autor, autor.nome, one_line_format)
                author_link = autor.link if autor.link else '-'
                worksheet_autores.write(linha, link_autor, author_link, one_line_format)
                for artigos in autor.artigos:
                    try:
                        worksheet_autores.write_url(linha, artigos_autor, artigos.link, autor_format, string=artigos.titulo)
                    except:
                        worksheet_autores.write(linha, artigos_autor, artigos.titulo, one_line_format)
                    finally:
                        linha += 1
                if primeiraLinha != linha - 1:
                    worksheet_autores.merge_range(primeiraLinha, nome_autor, linha - 1, nome_autor, autor.nome,
                                                  merge_format)
                    worksheet_autores.merge_range(primeiraLinha, link_autor, linha - 1, link_autor, author_link,
                                                  merge_format)

        workbook.close()

        log_event(
            "EXPORT_XLSX_DONE",
            "Export Excel terminé",
            path=str(workbook_path),
            merge=False,
            articles=len(ordered_articles),
            authors=len(self.authors_list),
        )

        self.gui.show_saved_alert(str(diretorio_excel))
        return True

    def article_label(self, artigo):
        if 'Conference' in artigo.cite or 'CaseReport' in artigo.cite:
            article_label = '2'
        elif 'JournalArticle' in artigo.cite or 'Review' in artigo.cite:
            article_label = '1'
        elif 'Book' in artigo.cite or 'BookSection' in artigo.cite or 'News' in artigo.cite or 'Study' in artigo.cite:
            article_label = '3'
        else:
            article_label = '4'

        return article_label
