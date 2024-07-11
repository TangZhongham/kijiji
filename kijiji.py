import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from collections import namedtuple


class KijijiScraper:
    def __init__(self, url):
        self.driver = webdriver.Chrome()
        self.base_url = url
        self.old_listings = []
        self.listings = []
        self.current_datetime = datetime.now()
        self.formatted_datetime = self.current_datetime.strftime("%Y-%m-%d %Hh+")

    def scrape_listings(self):
        self.driver.get(self.base_url)
        self._scrape_page()

        while self._has_next_page():
            next_link = self._get_next_link()
            if next_link:
                self.driver.get(next_link)
                self._scrape_page()

    def _scrape_page(self):
        result = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="srp-search-list"]')
        item_selectors = result.find_elements(By.CSS_SELECTOR, '[data-testid^="listing-card-list-item-"]')

        Listing = namedtuple('Listing', ['title', 'price', 'location', 'post_time', 'distance', 'link', 'description'])

        for each in item_selectors:
            title = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-title"]').text
            price = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-price"]').text
            location = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-location"]').text
            _post_time = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-date"]').text
            post_time = self.formatted_datetime + _post_time
            distance = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-proximity"]').text
            link = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-link"]').get_attribute('href')

            # check duplicates
            if not any(listing.title == title and listing.price == price for listing in self.old_listings):
                listing = Listing(title, price, location, post_time, distance, link, "")
                self.listings.append(listing)

        print("add " + str(len(self.listings)) + " new listings")

    def _has_next_page(self):
        try:
            next_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="pagination-next-link"]'))
            )
            return next_button.is_displayed()
        except Exception:
            return False

    def _get_next_link(self):
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="pagination-next-link"]')
            return next_button.find_element(By.TAG_NAME, 'a').get_attribute('href')
        except Exception:
            return None

    def load_listings(self):
        if os.path.exists('listings.txt'):
            with open('listings.txt', 'r', encoding='utf-8') as file:
                for line in file:
                    data = line.strip().split('\t')
                    if len(data) == 7:
                        listing = namedtuple('Listing', ['title', 'price', 'location', 'post_time', 'distance', 'link',
                                                         'description'])(*data)
                        self.old_listings.append(listing)

    def visit_listings(self):
        for each in self.listings:
            self.driver.get(each.link)
            try:
                description_element = self.driver.find_element(By.ID, 'vip-body').find_element(By.CSS_SELECTOR,
                                                                                               '[class^="descriptionContainer-"]')
                description_text = description_element.text.strip()  # Get the text and strip any surrounding whitespace
                each = each._replace(description=description_text)  # Update the namedtuple with description
                print(f"Visited: {each.link}")
            except Exception as e:
                print(f"Error fetching description for {each.link}: {str(e)}")

    def save_listings(self):
        with open('listings.txt', 'w', encoding='utf-8') as file:
            for listing in self.listings:
                file.write(
                    f"{listing.title}\t{listing.price}\t{listing.location}\t{listing.post_time}\t{listing.distance}\t{listing.link}\t{listing.description}\n")


    def close(self):
        self.driver.quit()


if __name__ == '__main__':
    url = "https://www.kijiji.ca/b-room-rental-roommate/ottawa/c36l1700185?address=Algonquin%20College%20Ottawa%20Campus,%20Woodroffe%20Avenue,%20Nepean,%20ON&ll=45.349934%2C-75.754926&radius=3.0"
    scraper = KijijiScraper(url)
    scraper.scrape_listings()
    scraper.visit_listings()

    for listing in scraper.listings:
        print(listing)

    scraper.close()
