import os
import csv
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
from collections import namedtuple
import time
import random


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# Create a file handler to save logs to a file
file_handler = logging.FileHandler('./log/app.log')
file_handler.setLevel(logging.INFO)  # Set the logging level for the file handler
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

# Create a stream handler to print logs to the console
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # Set the logging level for the stream handler
stream_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(stream_formatter)

# Add the stream handler to the logger
logger.addHandler(stream_handler)

class ListingsManager:
    def __init__(self, filename='./log/listings.txt'):
        self.filename = filename

    def load_listings(self):
        listings = []
        if os.path.exists(self.filename):
            with open(self.filename, 'r', encoding='utf-8') as file:
                reader = csv.reader(file, delimiter='\t')
                next(reader)  # Skip header
                for row in reader:
                    if len(row) == 9:
                        listing = namedtuple('Listing', ['title', 'price', 'location', 'post_time', 'distance', 'link', 'description', 'create_date', 'email_sent'])(*row)
                        listings.append(listing)
        return listings

    def save_listings(self, listings):
        with open(self.filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file, delimiter='\t')
            header = ['title', 'price', 'location', 'post_time', 'distance', 'link', 'description', 'create_date', 'email_sent']
            writer.writerow(header)
            for listing in listings:
                writer.writerow(listing)


class EmailManager:
    def __init__(self, smtp_server, smtp_port, sender_email, receiver_email, email_password):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.receiver_email = receiver_email
        self.email_password = email_password

    def send_email(self, subject, body):
        message = MIMEMultipart()
        message['From'] = self.sender_email
        message['To'] = self.receiver_email
        message['Subject'] = subject

        message.attach(MIMEText(body, 'html'))

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.email_password)
                server.sendmail(self.sender_email, self.receiver_email, message.as_string())
                logger.info("Email sent successfully")
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            # Save HTML content to local file
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f'./log/email_fail_{timestamp}.html'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(body)
            logger.info(f"Saved HTML content to {filename}")


class KijijiScraper:
    def __init__(self, url, listings_manager, email_manager):
        self.driver = webdriver.Chrome()
        self.base_url = url
        self.listings_manager = listings_manager
        self.email_manager = email_manager
        self.old_listings = self.listings_manager.load_listings()
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

        Listing = namedtuple('Listing', ['title', 'price', 'location', 'post_time', 'distance', 'link', 'description', 'create_date', 'email_sent'])

        for each in item_selectors:
            title = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-title"]').text
            price = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-price"]').text
            location = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-location"]').text
            _post_time = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-date"]').text
            post_time = self.formatted_datetime + _post_time
            distance = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-proximity"]').text
            link = each.find_element(By.CSS_SELECTOR, '[data-testid="listing-link"]').get_attribute('href')

            # Check duplicates in old_listings
            if not any(listing.title == title and listing.price == price for listing in self.old_listings):
                listing = Listing(title, price, location, post_time, distance, link, "", self.current_datetime, False)
                self.listings.append(listing)

        logger.info(f"Added {len(self.listings)} new listings")

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

    def visit_listings(self):
        for each in self.listings:
            self.driver.get(each.link)
            try:
                # Random wait between 1 to 3 seconds
                wait_time = random.uniform(1, 3)
                time.sleep(wait_time)

                description_element = self.driver.find_element(By.ID, 'vip-body').find_element(By.CSS_SELECTOR,
                                                                                               '[class^="descriptionContainer-"]')
                description_text = description_element.text.strip()  # Get the text and strip any surrounding whitespace
                each = each._replace(description=description_text)  # Update the namedtuple with description
                logger.info(f"Visited: {each.link}")

            except Exception as e:
                logger.error(f"Error fetching description for {each.link}: {str(e)}")
                # Handle the error or log further if necessary

    def save_listings(self):
        self.listings_manager.save_listings(self.listings)

    def send_new_listings_email(self):
        new_listings = self.check_for_new_listings()
        if new_listings:
            html_content = self._build_html_email(new_listings)
            subject = 'New Kijiji Listings'
            self.email_manager.send_email(subject, html_content)
            self.mark_listings_as_emailed(new_listings)
            logger.info("Email sent successfully")

    def _build_html_email(self, listings):
        html_header = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8" />
        <h1>New Kijiji Listings</h1>
        <style>
          .gmail-table {
            border: solid 2px #DDEEEE;
            border-collapse: collapse;
            border-spacing: 0;
            font: normal 14px Roboto, sans-serif;
          }
          .gmail-table thead th {
            background-color: #DDEFEF;
            border: solid 1px #DDEEEE;
            color: #336B6B;
            padding: 10px;
            text-align: left;
            text-shadow: 1px 1px 1px #fff;
          }
          .gmail-table tbody td {
            border: solid 1px #DDEEEE;
            color: #333;
            padding: 10px;
            text-shadow: 1px 1px 1px #fff;
          }
        </style>
        </head>
        <body>
        <table id="tfhover" class="gmail-table" border="1">
        <thead>
        <tr><th>Title</th><th>Price</th><th>Description</th><th>Location</th><th>Posted Date</th><th>Distance</th><th>Search Date</th><th>URL</th></tr></thead>
        <tbody>
        """

        html_footer = """
        </tbody>
        </table>
        </body>
        </html>
        """

        html_body = ""
        for listing in listings:
            html_body += f"<tr><td>{listing.title}</td><td>{listing.price}</td><td>{listing.description}</td><td>{listing.location}</td><td>{listing.post_time}</td><td>{listing.distance}</td><td>{listing.create_date}</td><td><a href='{listing.link}'>Link</a></td></tr>"

        return html_header + html_body + html_footer

    def check_for_new_listings(self):
        new_listings = []
        for listing in self.listings:
            if listing not in self.old_listings and not listing.email_sent:
                new_listings.append(listing)
        return new_listings

    def mark_listings_as_emailed(self, listings):
        for listing in listings:
            listing_index = next((i for i, l in enumerate(self.listings) if l.link == listing.link), None)
            if listing_index is not None:
                self.listings[listing_index] = self.listings[listing_index]._replace(email_sent=True)

    def close(self):
        self.driver.quit()


if __name__ == '__main__':
    url = "https://www.kijiji.ca/b-room-rental-roommate/ottawa/c36l1700185?address=Algonquin%20College%20Ottawa%20Campus,%20Woodroffe%20Avenue,%20Nepean,%20ON&ll=45.349934%2C-75.754926&radius=3.0"

    smtp_server = ''
    smtp_port = 0
    sender_email = '.com'
    receiver_email = '.com'
    email_password = ''

    listings_manager = ListingsManager()
    email_manager = EmailManager(smtp_server, smtp_port, sender_email, receiver_email, email_password)

    scraper = KijijiScraper(url, listings_manager, email_manager)

    try:
        scraper.scrape_listings()
        # TODO better logic to get descriptions
        # scraper.visit_listings()
        scraper.save_listings()
        scraper.send_new_listings_email()
    except Exception as e:
        logger.error(f"Error in main script: {str(e)}")
    finally:
        scraper.close()
