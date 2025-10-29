import os
import pickle
from pathlib import Path

from activity_logger import log_event
from storage_helper import resolve_storage_paths


class Gerenciador:
    def __init__(self, palavraChave, root_directory):
        self.root_directory = root_directory
        (
            self.storage_label,
            self.storage_dir,
            authors_path,
            articles_path,
        ) = resolve_storage_paths(self.root_directory, palavraChave)
        self.diretorio_files = os.path.join(self.root_directory, 'Results')
        self.arquivo_autores = str(authors_path)
        self.arquivo_artigos = str(articles_path)
        self.inicializaPrograma()
        log_event(
            "STORAGE_READY",
            "Gestionnaire de stockage initialisé",
            search_label=self.storage_label,
            path=str(self.storage_dir),
        )

    def loadAutores(self):
        with open(self.arquivo_autores, 'rb') as file_input:
            lista_autores = pickle.load(file_input)
        return lista_autores

    def loadArtigos(self):
        with open(self.arquivo_artigos, 'rb') as file_input:
            lista_artigos = pickle.load(file_input)
        return lista_artigos

    def saveAutores(self, lista_autores):
        lista_autores.sort()
        with open(self.arquivo_autores, 'wb') as file_output:
            pickle.dump(lista_autores, file_output, -1)

    def saveArtigos(self, lista_artigos):
        lista_artigos.sort()
        with open(self.arquivo_artigos, 'wb') as file_output:
            pickle.dump(lista_artigos, file_output, -1)

    def inicializaAutores(self):
        lista_autores = []
        with open(self.arquivo_autores, 'wb') as file_output:
            pickle.dump(lista_autores, file_output, -1)

    def inicializaArtigos(self):
        lista_artigos = []
        with open(self.arquivo_artigos, 'wb') as file_output:
            pickle.dump(lista_artigos, file_output, -1)

    def inicializaPrograma(self):
        os.makedirs(self.diretorio_files, exist_ok=True)
        os.makedirs(self.storage_dir, exist_ok=True)
        caminho_autores = Path(self.arquivo_autores)
        caminho_artigos = Path(self.arquivo_artigos)
        if not caminho_artigos.is_file():
            self.inicializaArtigos()
        if not caminho_autores.is_file():
            self.inicializaAutores()