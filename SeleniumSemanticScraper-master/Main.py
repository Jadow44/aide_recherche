from bootstrap import ensure_environment

ensure_environment(__file__)

from GUI import GUI  # noqa: E402  # import after environment bootstrap
from activity_logger import log_event  # noqa: E402
import os


class Main:
    def __init__(self):
        self.root_directory = os.getcwd()
        log_event("APP_START", "Lancement de l’interface graphique", root=self.root_directory)
        # start GUI
        self.gui = GUI(self.root_directory)
        self.gui.main_page()


if __name__ == "__main__":
    main = Main()
