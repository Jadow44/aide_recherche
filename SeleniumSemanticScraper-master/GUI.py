from appJar import gui
from UniteArticles import Merger
from SemanticScholarMetaCrawler import Crawler
from PDFDownloader import PDFDownloader
from tkinter import filedialog
import os
import re
import sys

from activity_logger import log_event


def restart_program():
    """Restarts the current program."""
    python = sys.executable
    log_event("APP_RESTART", "Redémarrage demandé par l’utilisateur")
    os.execl(python, python, * sys.argv)


class GUI:
    def __init__(self, root_directory):
        self.root_directory = root_directory
        self.app = gui('Collecteur Semantic Scholar', '800x400')
        self.app.setGuiPadding(20, 20)
        self.app.setLocation('CENTER')
        self.app.setFont(16)
        self.search_phrase = ''
        self.input_pages = 0
        self.crawler = Crawler(self.root_directory)
        self.folders_text = ''
        self.folders_list = []
        self.drag_and_drop_supported = True
        self.single_or_merge = False
        self.merger = None
        self.connection_status_text = self.crawler.connection_status_message()
        self.year_filter_choice = 'Toutes les parutions'
        self.keyword_criteria = []
        self.keyword_fields = []

        self.crawler.gui = self

    def menus_pressed(self, menu):
        log_event("MENU_ACTION", "Sélection d’un élément de menu", menu=menu)
        if menu == 'Nouvelle recherche':
            restart_program()
        if menu == "Fermer":
            self.app.stop()
        if menu == "Aide":
            self.app.startSubWindow('Help', 'Aide', True, )
            self.app.showSubWindow('Help')
            self.help_screen()
            self.app.stopSubWindow()
        if menu == "À propos":
            self.app.startSubWindow('About', 'À propos du programme', True, )
            self.app.showSubWindow('About')
            self.about_screen()
            self.app.stopSubWindow()

    def menus(self):
        file_menus = ["Nouvelle recherche", "-", "Fermer"]
        about_menus = ["Aide", "À propos"]
        self.app.addMenuList("Fichier", file_menus, self.menus_pressed)
        self.app.addMenuList("Assistance", about_menus, self.menus_pressed)

    def main_search(self):
        self.app.setStretch('column')
        self.app.setSticky('we')
        self.app.addLabel('Label_Search', 'Saisissez votre requête :', row=0)
        self.app.addEntry('Entry_Search', row=1)
        self.app.addLabel('Connection_Status', self.connection_status_text, row=2)
        self.app.setLabelAlign('Connection_Status', 'left')
        self.app.addLabel('label_space', '', row=3)
        self.app.addLabel('Label_Year_Filter', 'Filtrer par date de parution :', row=4)
        self.app.addOptionBox(
            'Year_Filter_Option',
            [
                'Toutes les parutions',
                'Moins de 5 ans',
                'Moins de 10 ans',
                'Moins de 20 ans',
            ],
            row=5,
        )
        self.app.setOptionBox('Year_Filter_Option', 'Toutes les parutions')
        self.app.addLabel('Label_Pages_Quantity', 'Choisissez le nombre d’articles à récupérer :', row=6)
        self.app.addScale('Quantity_scale', row=7)
        self.app.setScaleRange('Quantity_scale', 0, 100, 100)
        self.app.showScaleIntervals('Quantity_scale', 5)
        self.app.showScaleValue('Quantity_scale', True)
        self.app.addLabel('Label_Keyword_Title',
                          'Affinez la sélection des résumés avec vos mots-clés :', row=8)
        self.app.addMessage(
            'Keywords_Explanation',
            "Ajoutez jusqu’à cinq termes. Les mots marqués « Indispensable » devront apparaître dans le résumé. "
            "Les mots « Souhaitable » renforcent la pertinence sans être obligatoires.",
            row=9,
        )
        self.app.setMessageWidth('Keywords_Explanation', 500)
        self.app.startLabelFrame('Critères de résumé', row=10, colspan=2)
        self.app.setLabelFramePadding('Critères de résumé', 10, 10)
        self.app.addLabel('Keyword_Header_Term', 'Mot-clé', row=0, column=0)
        self.app.addLabel('Keyword_Header_Type', 'Importance', row=0, column=1)
        self.keyword_fields = []
        for index in range(5):
            entry_id = f'Keyword_entry_{index + 1}'
            option_id = f'Keyword_status_{index + 1}'
            self.app.addEntry(entry_id, row=index + 1, column=0)
            self.app.addOptionBox(option_id, ['Indispensable', 'Souhaitable'], row=index + 1, column=1)
            self.app.setOptionBox(option_id, 'Souhaitable')
            self.keyword_fields.append((entry_id, option_id))
        self.app.stopLabelFrame()
        self.app.addMessage(
            'Keywords_Translation_Note',
            "Astuce : la requête et les mots-clés sont traduits automatiquement en anglais pour interroger Semantic Scholar.",
            row=11,
        )
        self.app.setMessageWidth('Keywords_Translation_Note', 500)
        self.app.setStretch('both')
        self.app.setSticky('se')
        self.app.addNamedButton('Suivant', 'Next1', self.press)

    def show_search_done_alert(self, time, quantity):
        def _update_ui():
            self.app.stopAnimation('loading')
            self.app.hideImage('loading')
            self.app.setLabel('progress_bar_label', f'Recherche terminée : {quantity} article(s) sauvegardé(s)')
            self.app.infoBox('TERMINE', 'Recherche achevée en ' + str(time.seconds) + ' seconde(s) avec ' +
                             quantity + ' article(s) récupéré(s).')
            self.app.setButtonState('Next2', 'normal')

        self.app.queueFunction(_update_ui)
        log_event(
            "SEARCH_SUCCESS",
            "Recherche terminée",
            duration_seconds=time.seconds,
            new_articles=quantity,
        )

    def show_search_failed_alert(self, message):
        def _update_ui():
            self.app.stopAnimation('loading')
            self.app.hideImage('loading')
            self.app.setButtonState('Lancer la recherche', 'normal')
            self.app.setLabel('progress_bar_label', 'Appuyez sur « Lancer la recherche »')
            self.app.errorBox('Recherche échouée', message)

        self.app.queueFunction(_update_ui)
        log_event("SEARCH_FAILED", "La recherche a échoué", reason=message)

    def notify_rate_limit(self, wait_seconds, attempt, max_attempts):
        def _update_ui():
            self.app.setLabel(
                'progress_bar_label',
                f"Limite de requêtes atteinte. Nouvelle tentative dans {wait_seconds} seconde(s) ({attempt}/{max_attempts}).",
            )
            self.app.showImage('loading')
            self.app.startAnimation('loading')

        self.app.queueFunction(_update_ui)
        log_event(
            "SEARCH_RETRY",
            "Limite de requêtes atteinte",
            wait_seconds=wait_seconds,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    def notify_transient_error(self, wait_seconds, attempt, max_attempts):
        def _update_ui():
            self.app.setLabel(
                'progress_bar_label',
                f"Nouvelle tentative dans {wait_seconds} seconde(s)… ({attempt}/{max_attempts})",
            )
            self.app.showImage('loading')
            self.app.startAnimation('loading')

        self.app.queueFunction(_update_ui)
        log_event(
            "SEARCH_RETRY",
            "Erreur transitoire détectée",
            wait_seconds=wait_seconds,
            attempt=attempt,
            max_attempts=max_attempts,
        )

    def notify_strategy_started(self, description, position, total):
        def _update_ui():
            self.app.setLabel(
                'progress_bar_label',
                f"{description} – étape {position}/{total}",
            )
            self.app.showImage('loading')
            self.app.startAnimation('loading')

        self.app.queueFunction(_update_ui)
        log_event(
            "SEARCH_STRATEGY",
            "Exécution d’une stratégie de collecte",
            description=description,
            position=position,
            total=total,
        )

    def notify_strategy_results(self, description, new_items, total_items):
        def _update_ui():
            self.app.setLabel(
                'progress_bar_label',
                f"{description} : {new_items} article(s) pertinent(s) sur {total_items} reçu(s)",
            )

        self.app.queueFunction(_update_ui)
        log_event(
            "SEARCH_STRATEGY_RESULT",
            "Résultats partiels reçus",
            description=description,
            new_items=new_items,
            total_items=total_items,
        )

    def show_download_done_alert(self, time, quantity):
        def _update_ui():
            self.app.infoBox('TERMINE', 'Téléchargements terminés en ' + str(time.seconds) + ' seconde(s) avec ' +
                             quantity + ' article(s) téléchargé(s).')
            self.app.setButtonState('Next3', 'normal')

        self.app.queueFunction(_update_ui)
        log_event(
            "DOWNLOAD_SUCCESS",
            "Téléchargements terminés",
            duration_seconds=time.seconds,
            downloaded=quantity,
        )

    def show_saved_alert(self, saved_path):
        def _ask_user():
            answer = self.app.yesNoBox('ENREGISTRE', 'Votre recherche a été enregistrée ici : ' + saved_path +
                                       '.\nSouhaitez-vous fermer le programme ?')
            if answer:
                self.app.stop()

        self.app.queueFunction(_ask_user)
        log_event("EXPORT_DONE", "Sauvegarde terminée", path=saved_path)

    def show_export_empty_alert(self, merge=False, search=''):
        if merge:
            message = (
                "Aucun article n’a été trouvé dans les dossiers sélectionnés. Vérifiez les résultats enregistrés avant de fusionner."
            )
        else:
            label = search or 'cette recherche'
            message = (
                f"L’export est impossible : {label} ne contient actuellement aucun article. Lancez ou relancez une collecte avant d’enregistrer."
            )

        self.app.errorBox('Export impossible', message)
        log_event("EXPORT_EMPTY", "Tentative d’export sans articles", merge=merge, search=search)

    def progress_bar(self):
        self.app.setStretch('column')
        self.app.setSticky('nwe')
        self.app.addLabel('progress_bar_label', 'Appuyez sur « Lancer la recherche »')
        self.app.setStretch('both')
        self.app.setSticky('nswe')
        
        self.app.setSticky('')

        self.app.addButton('Lancer la recherche', self.press, column=0, row=2)
        self.app.setStretch('both')

        self.app.addImage("loading", "Images/book.gif")
        self.app.setAnimationSpeed("loading", 100)
        self.app.stopAnimation("loading")
        self.app.hideImage('loading')

        self.app.setSticky('se')
        self.app.addNamedButton('Suivant', 'Next2', self.press)
        self.app.setButtonState('Next2', 'disabled')

    def progress_bar2(self):
        self.app.setStretch('column')
        self.app.setSticky('nwe')
        self.app.addLabel('progress_bar_2_label', 'Appuyez sur « Lancer les téléchargements »')
        self.app.setStretch('both')
        self.app.setSticky('nswe')
        self.app.addMeter('progress_bar2', column=0, row=1)
        self.app.setMeterFill('progress_bar2', 'blue')
        self.app.setSticky('')
        self.app.addButton('Lancer les téléchargements', self.press, column=0, row=2)
        self.app.setStretch('both')
        self.app.setSticky('se')
        self.app.addNamedButton('Ignorer', 'Skip_download', self.press, row=3)
        self.app.addNamedButton('Suivant', 'Next3', self.press, row=4)
        self.app.setButtonState('Next3', 'disabled')

    def save_menu(self):
        self.app.setStretch('column')
        self.app.setSticky('we')
        self.app.addLabel('Label_Save_options', 'Comment souhaitez-vous trier votre recherche ?')
        self.app.setSticky('w')
        self.app.addRadioButton('Save_option_radioButton', "Indice d’importance (RECOMMANDÉ)")
        self.app.addRadioButton('Save_option_radioButton', "Nombre de citations")
        self.app.addRadioButton('Save_option_radioButton', "Articles les plus récents")
        self.app.addRadioButton('Save_option_radioButton', "Ordre alphabétique du titre")
        self.app.setSticky('')
        self.app.addButton('Enregistrer', self.press)

    def option_page(self):
        self.app.setStretch('column')
        self.app.addLabel('Label_Option_page', 'Que souhaitez-vous faire ?')
        self.app.addLabel('spacing_label1', '')
        self.app.addLabel('spacing_label2', '')
        self.app.setSticky('nsew')
        self.app.addButton('Nouvelle recherche', self.press)
        self.app.addLabel('spacing_label3', '')
        self.app.addButton('Fusionner des recherches existantes', self.press)

    def _add_folder_to_list(self, folder):
        folder = folder.strip()
        if not folder:
            log_event("MERGE_FOLDER", "Tentative d’ajout d’un dossier vide ignorée")
            return

        if folder in self.folders_list:
            self.app.warningBox('Dossier dupliqué', f'« {folder} » est déjà présent dans la liste.')
            log_event("MERGE_FOLDER", "Dossier dupliqué ignoré", folder=folder)
            return

        self.app.addListItem("folders_list", folder)
        self.folders_list.append(folder)
        log_event("MERGE_FOLDER", "Dossier ajouté à la liste de fusion", folder=folder)

    def external_folders(self, list_folder):
        folders = list_folder.split("} {")

        for text_folder in folders:
            folder = text_folder.strip("{}")
            self._add_folder_to_list(folder)

    def merge_searches(self):
        self.app.setStretch('both')
        self.app.setSticky('n')
        self.app.addLabel('Label_merge_searches',
                          'Glissez-déposez les dossiers à fusionner.', colspan=2)

        self.app.addListBox("folders_list", colspan=2)

        self.drag_and_drop_supported = True
        try:
            self.app.setListBoxDropTarget("folders_list", self.external_folders)
        except Exception:
            self.drag_and_drop_supported = False
            self.app.addLabel("folders_list_warning",
                              "Le glisser-déposer n’est pas disponible sur cette plateforme.\nUtilisez le bouton ci-dessous pour ajouter des dossiers.",
                              row=2, colspan=2)
            self.app.addNamedButton("Ajouter un dossier", "Add_Folder", self.press, row=3, colspan=2)
        self.app.setListBoxWidth("folders_list", 50)
        self.app.setStretch('both')
        self.app.setSticky('nsew')
        self.app.setStretch('')
        self.app.setSticky('s')

        if self.drag_and_drop_supported:
            next_row = 3
        else:
            next_row = 4

        self.app.addButton('Fusionner les recherches', self.press, row=next_row)

    def main_page(self):
        self.menus()

        self.app.startFrameStack("Pages")

        self.app.startFrame('Initial Option')
        self.option_page()
        self.app.stopFrame()

        self.app.startFrame('Search Menu')
        self.main_search()
        self.app.stopFrame()

        self.app.startFrame('Progress')
        self.progress_bar()
        self.app.stopFrame()

        #self.app.startFrame('Downloading Progress')
        #self.progress_bar2()
        #self.app.stopFrame()

        self.app.startFrame('Saving Options')
        self.save_menu()
        self.app.stopFrame()

        self.app.startFrame('Merge Searches')
        self.merge_searches()
        self.app.stopFrame()

        self.app.stopFrameStack()

        self.app.firstFrame('Pages')
        self.app.go()

    def about_screen(self):
        self.app.addImage('Alphas', os.path.join(self.root_directory, 'Images', 'About.gif'))
        self.app.setSticky('n')
        self.app.addButton('Fermer', self.press)

    def help_screen(self):
        self.app.addWebLink("Lien GitHub pour obtenir de l'aide", 'https://github.com/EvertonCa/SeleniumSemanticScraper')
        self.app.addButton('Fermer !', self.press)

    def create_crawler(self):
        log_event(
            "SEARCH_PARAMETERS",
            "Transmission des paramètres de recherche au crawler",
            query=self.search_phrase,
            pages=self.input_pages,
            year_filter=self.year_filter_choice,
            keyword_rules=self.keyword_criteria,
        )
        self.crawler.update_search_parameters(
            self.search_phrase,
            self.input_pages,
            self.year_filter_choice,
            self.keyword_criteria,
        )
        log_event("SEARCH_START", "Lancement de la collecte via le crawler")
        self.crawler.start_search()

    def start_downloads(self):
        downloader = PDFDownloader(self.search_phrase, self.root_directory, self)
        log_event("DOWNLOAD_START", "Démarrage des téléchargements de PDF", query=self.search_phrase)
        downloader.start()

    def press(self, btn):
        if btn == "Next1" or btn == "Next2":
            raw_search = self.app.getEntry('Entry_Search')
            self.search_phrase = self._normalize_search_phrase(raw_search)
            if self.search_phrase != raw_search:
                self.app.setEntry('Entry_Search', self.search_phrase)
            self.input_pages = self.app.getScale('Quantity_scale')
            self.year_filter_choice = self.app.getOptionBox('Year_Filter_Option')
            self.keyword_criteria = self._collect_keyword_criteria()
            log_event(
                "USER_SELECTION",
                "Configuration de la recherche validée",
                query=self.search_phrase,
                pages=self.input_pages,
                year_filter=self.year_filter_choice,
                keywords=self.keyword_criteria,
            )
            if self.input_pages == 0:
                self.app.errorBox('Erreur', 'Choisir 0 article annulera la recherche !')
            else:
                self.app.nextFrame("Pages")

        elif btn == 'Next3':
            self.app.nextFrame("Pages")

        elif btn == 'Skip_download':
            self.app.nextFrame("Pages")

        elif btn == "Lancer la recherche":
            self.app.setLabel('progress_bar_label', 'Préparation en cours…')
            self.app.setButtonState('Lancer la recherche', 'disabled')
            self.app.showImage('loading')
            self.app.startAnimation('loading')
            log_event(
                "SEARCH_TRIGGER",
                "Recherche lancée par l’utilisateur",
                query=self.search_phrase,
                pages=self.input_pages,
                year_filter=self.year_filter_choice,
                keywords=self.keyword_criteria,
                tor_enabled=self.crawler.using_tor,
                tor_proxy=self.crawler._tor_proxy,
            )
            self.app.thread(self.create_crawler)

        elif btn == "Lancer les téléchargements":
            self.app.setLabel('progress_bar_2_label', 'Préparation en cours…')
            self.app.setButtonState('Lancer les téléchargements', 'disabled')
            self.app.setButtonState('Skip_download', 'disabled')
            log_event("DOWNLOAD_TRIGGER", "Téléchargement des PDF demandé")
            self.app.thread(self.start_downloads)

        elif btn == 'Enregistrer':
            ordering = self.app.getRadioButton('Save_option_radioButton')
            log_event(
                "EXPORT_TRIGGER",
                "Demande d’export Excel",
                ordering=ordering,
            )
            self.crawler.saves_excel(ordering)

        elif btn == 'Nouvelle recherche':
            self.app.selectFrame('Pages', 1)
            log_event("NAVIGATION", "Retour à la configuration d’une nouvelle recherche")

        elif btn == 'Fusionner des recherches existantes':
            self.app.selectFrame('Pages', 4)
            log_event("NAVIGATION", "Accès à l’outil de fusion des recherches")

        elif btn == 'Fusionner les recherches':
            self.single_or_merge = True
            self.merger = Merger(self.folders_list)
            self.app.selectFrame('Pages', 3)
            log_event("MERGE_START", "Fusion de recherches demandée", folders=self.folders_list)

        elif btn == 'Add_Folder':
            folder = filedialog.askdirectory(parent=self.app.topLevel,
                                             title='Sélectionnez le dossier de recherche à fusionner')
            if folder:
                self._add_folder_to_list(folder)
                log_event("MERGE_FOLDER", "Ajout d’un dossier à fusionner", folder=folder)

        elif btn == 'Fermer':
            self.app.destroySubWindow('About')

        elif btn == 'Fermer !':
            self.app.destroySubWindow('Help')

    def _collect_keyword_criteria(self):
        criteria = []
        for entry_id, option_id in self.keyword_fields:
            term = self.app.getEntry(entry_id).strip()
            if not term:
                continue
            importance_label = self.app.getOptionBox(option_id)
            importance = 'required' if importance_label == 'Indispensable' else 'optional'
            criteria.append({
                'term': term,
                'importance': importance,
                'label': importance_label,
            })
        if criteria:
            log_event("KEYWORDS_CAPTURED", "Critères de résumé fournis", keywords=criteria)
        return criteria

    def _normalize_search_phrase(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", (value or "").strip())
        if cleaned != value:
            log_event(
                "SEARCH_NORMALIZED",
                "Requête nettoyée avant utilisation",
                original=value,
                sanitized=cleaned,
            )
        return cleaned
