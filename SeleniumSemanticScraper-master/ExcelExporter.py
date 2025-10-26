import os
from typing import Iterable, List

import xlsxwriter

import Gerenciador


class ExcelExporter:
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
        if self.single_or_merge:
            self.articles_list = self.gui.merger.articles_list
            self.authors_list = self.gui.merger.authors_list

            if parameter == 'Importance Rate (RECOMMENDED)':
                self.merge_creator(1)
            elif parameter == "Number of Citations":
                self.merge_creator(2)
            elif parameter == "Newer Articles":
                self.merge_creator(3)
            elif parameter == "Alphabetically, by Article's Title":
                self.merge_creator(4)
        else:
            if parameter == 'Importance Rate (RECOMMENDED)':
                self.single_creator(1)
            elif parameter == "Number of Citations":
                self.single_creator(2)
            elif parameter == "Newer Articles":
                self.single_creator(3)
            elif parameter == "Alphabetically, by Article's Title":
                self.single_creator(4)

    def order_optimized(self, articles_list: Iterable):
        newer_date = 0

        for article in articles_list:
            if int(article.data) > newer_date:
                newer_date = int(article.data)

        ordered_list: List = []
        qualis_dict = {'A1': 1, 'A2': 2, 'A3': 3, 'A4': 4, 'B1': 5, 'B2': 6, 'B3': 7, 'B4': 8, 'B5': 9, 'C': 10, 'NF': 10, 'NP': 10}

        for article in articles_list:
            article.data_relativa = int(article.data) / (newer_date if newer_date > 0 else 1)

            # put a score based on number of citations
            if int(article.citacoes) > 100:
                article.citacoes_relativa = 1
            elif 20 < int(article.citacoes) <= 100:
                article.citacoes_relativa = 0.5
            else:
                article.citacoes_relativa = 0

            qualis_score = (10 - qualis_dict.get(article.qualis, 10)) / 9

            # put a score based on article's type
            # label = float(self.article_label(article))
            # article.cite_label = (4 - label)/3

            article.total_factor = 0.2 * article.data_relativa + 0.3 * article.citacoes_relativa + 0.5 * qualis_score
            ordered_list.append(article)

        self.ordered_optimized_list = sorted(ordered_list, key=lambda model: model.total_factor, reverse=True)

    def order_articles(self, articles_list, order_type):
        max_citations = 0
        newer_date = 0
        for article in articles_list:
            if int(article.data) > newer_date:
                newer_date = int(article.data)
            if int(article.citacoes) > max_citations:
                max_citations = int(article.citacoes)

        annotated_articles: List = []
        for article in articles_list:
            article.data_relativa = int(article.data) / (newer_date if newer_date > 0 else 1)
            article.citacoes_relativa = int(article.citacoes) / (max_citations if max_citations > 0 else 1)
            annotated_articles.append(article)

        self.ordered_date_articles_list = sorted(annotated_articles, key=lambda model: model.data_relativa, reverse=True)
        self.ordered_citations_articles_list = sorted(annotated_articles, key=lambda model: model.citacoes_relativa, reverse=True)

        if order_type == 1:
            return self.ordered_citations_articles_list
        elif order_type == 2:
            return self.ordered_date_articles_list
        return annotated_articles

    def _create_workbook(self, directory: str, filename: str):
        os.makedirs(directory, exist_ok=True)
        workbook = xlsxwriter.Workbook(os.path.join(directory, filename))

        worksheet_artigos = workbook.add_worksheet('ARTICLES')
        worksheet_autores = workbook.add_worksheet('AUTHORS')

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

        return (workbook, worksheet_artigos, worksheet_autores,
                primeiraLinha_format, one_line_format, autor_format, merge_format)

    @staticmethod
    def _write_article_headers(worksheet, header_format):
        headers = ['Index', 'Title', 'Authors', 'Publication Source', 'Publication Year', 'Citations',
                   'Qualis Score', 'Importance Rate', 'Article Link', 'BibTex', 'Synopsis']
        for idx, title in enumerate(headers):
            worksheet.write(0, idx, title, header_format)

    @staticmethod
    def _format_authors(authors):
        return ', '.join(autor.nome for autor in authors) if authors else ''

    @staticmethod
    def _write_author_headers(worksheet, header_format):
        headers = ['Author Name', 'Author Page', 'Related Published Articles']
        for idx, title in enumerate(headers):
            worksheet.write(0, idx, title, header_format)

    def merge_creator(self, search_type):
        diretorio_excel = os.path.join(self.root_directory, 'Results', 'Merged Search')
        articles = self._apply_article_order(self.articles_list, search_type)

        (workbook,
         worksheet_artigos,
         worksheet_autores,
         primeiraLinha_format,
         one_line_format,
         autor_format,
         merge_format) = self._create_workbook(diretorio_excel, 'Merged.xlsx')

        try:
            self._write_article_headers(worksheet_artigos, primeiraLinha_format)
            linha = 1
            numeroDoArtigo = 1

            for artigo in articles:
                worksheet_artigos.write(linha, 0, str(numeroDoArtigo), one_line_format)
                worksheet_artigos.write(linha, 1, artigo.titulo, one_line_format)
                worksheet_artigos.write(linha, 2, self._format_authors(artigo.autores), one_line_format)
                worksheet_artigos.write(linha, 3, artigo.publicado_em, one_line_format)
                worksheet_artigos.write(linha, 4, artigo.data, one_line_format)
                worksheet_artigos.write(linha, 5, artigo.citacoes, one_line_format)
                worksheet_artigos.write(linha, 6, artigo.qualis, one_line_format)
                worksheet_artigos.write(linha, 7, getattr(artigo, 'total_factor', ''), one_line_format)
                worksheet_artigos.write(linha, 8, artigo.link, one_line_format)
                worksheet_artigos.write(linha, 9, artigo.bibtex, one_line_format)
                worksheet_artigos.write(linha, 10, artigo.synopsis, one_line_format)
                numeroDoArtigo += 1
                linha += 1

            self._write_author_headers(worksheet_autores, primeiraLinha_format)
            self._write_authors(worksheet_autores, one_line_format, autor_format, merge_format, self.authors_list)
        finally:
            workbook.close()

        self.gui.show_saved_alert(diretorio_excel)

    def single_creator(self, search_type):
        diretorio_excel = os.path.join(self.root_directory, 'Results', self.search_parameter)

        gerenciador = Gerenciador.Gerenciador(self.search_parameter, self.root_directory)
        listaDeArtigos = gerenciador.loadArtigos()
        listaDeAutores = gerenciador.loadAutores()
        articles = self._apply_article_order(listaDeArtigos, search_type)

        (workbook,
         worksheet_artigos,
         worksheet_autores,
         primeiraLinha_format,
         one_line_format,
         autor_format,
         merge_format) = self._create_workbook(diretorio_excel, f'{self.search_parameter}.xlsx')

        try:
            self._write_article_headers(worksheet_artigos, primeiraLinha_format)
            linha = 1
            numeroDoArtigo = 1

            for artigo in articles:
                worksheet_artigos.write(linha, 0, str(numeroDoArtigo), one_line_format)
                worksheet_artigos.write(linha, 1, artigo.titulo, one_line_format)
                worksheet_artigos.write(linha, 2, self._format_authors(artigo.autores), one_line_format)
                worksheet_artigos.write(linha, 3, artigo.publicado_em, one_line_format)
                worksheet_artigos.write(linha, 4, artigo.data, one_line_format)
                worksheet_artigos.write(linha, 5, artigo.citacoes, one_line_format)
                worksheet_artigos.write(linha, 6, artigo.qualis, one_line_format)
                worksheet_artigos.write(linha, 7, getattr(artigo, 'total_factor', ''), one_line_format)
                worksheet_artigos.write(linha, 8, artigo.link, one_line_format)
                worksheet_artigos.write(linha, 9, artigo.bibtex, one_line_format)
                worksheet_artigos.write(linha, 10, artigo.synopsis, one_line_format)
                numeroDoArtigo += 1
                linha += 1

            self._write_author_headers(worksheet_autores, primeiraLinha_format)
            self._write_authors(worksheet_autores, one_line_format, autor_format, merge_format, listaDeAutores)
        finally:
            workbook.close()

        self.gui.show_saved_alert(diretorio_excel)

    def _apply_article_order(self, articles, search_type):
        if search_type == 1:
            self.order_optimized(articles)
            return self.ordered_optimized_list
        if search_type == 2:
            return self.order_articles(articles, 1)
        if search_type == 3:
            return self.order_articles(articles, 2)
        if search_type == 4:
            return sorted(articles, key=lambda artigo: getattr(artigo, 'titulo', '').lower())
        return list(articles)

    def _write_authors(self, worksheet_autores, one_line_format, autor_format, merge_format, autores_list):
        linha = 1
        nome_autor = 0
        link_autor = 1
        artigos_autor = 2

        for autor in autores_list:
            if autor.artigos:
                primeiraLinha = linha
                worksheet_autores.write(linha, nome_autor, autor.nome, one_line_format)
                worksheet_autores.write(linha, link_autor, autor.link, one_line_format)
                for artigos in autor.artigos:
                    artigo_link = getattr(artigos, 'link', '')
                    artigo_titulo = getattr(artigos, 'titulo', '')
                    if artigo_link:
                        worksheet_autores.write_url(linha, artigos_autor, artigo_link, autor_format, string=artigo_titulo)
                    else:
                        worksheet_autores.write(linha, artigos_autor, artigo_titulo, one_line_format)
                    linha += 1
                if primeiraLinha != linha - 1:
                    worksheet_autores.merge_range(primeiraLinha, nome_autor, linha - 1, nome_autor, autor.nome,
                                                  merge_format)
                    worksheet_autores.merge_range(primeiraLinha, link_autor, linha - 1, link_autor, autor.link,
                                                  merge_format)

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
