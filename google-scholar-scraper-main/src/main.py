
from src.google_articles import ScholarScraper


def main():
    scraper = ScholarScraper()
    scraper.get_articles()
    # print('"hello"')


if __name__ == "__main__":
    main()