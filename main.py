import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import random

class Config:
    def __init__(self, config_file):
        with open(config_file, 'r') as file:
            config_data = json.load(file)
        self.hostname = config_data['hostname']
        self.email = config_data['email']
        self.password = config_data['password']
        self.receiver = config_data['receiver']

class Notifier:
    def __init__(self, config):
        self.config = config

    def send_mail(self, subject, html_content):
        msg = MIMEMultipart()
        msg['From'] = self.config.email
        msg['To'] = self.config.receiver
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))

        try:
            server = smtplib.SMTP(self.config.hostname, 25)
            server.starttls()
            server.login(self.config.email, self.config.password)
            server.send_message(msg)
            server.quit()
            print("Send email successful")
        except Exception as e:
            print(f"Failed to send email: {e}")

class Scraper:
    def __init__(self, url, config_file):
        self.url = url
        self.config = Config(config_file)
        self.notifier = Notifier(self.config)
        self.subject = "找房小助手-"
        self.text_start = self._build_html_header()
        self.text_end = self._build_html_footer()
        self.text = ""
        self.house_count = 0
        self.sep_houses = 0
        self.sep_key_words = ["Sep", "sep", "Aug", "aug"]
        self.date = datetime.now().strftime("%y/%m/%d")
        self.houses_file = os.path.join(os.path.expanduser("~"), "houses.csv")
        self.page_count = 0

    def _build_html_header(self):
        return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<h1>Swift 找房小助手启动！🏄🏄🏄</h1>
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
<tr><th>Name</th><th>Price</th><th>Description</th><th>Location</th><th>Posted Date</th><th>Distance</th><th>Search Date</th><th>URL</th></tr></thead>
<tbody>
"""

    def _build_html_footer(self):
        return """
</tbody>
</table>
</body>
</html>
"""

    def execute(self):
        previous_items = self._read_previous_items()
        self._get_houses(previous_items, self.url)
        self._get_other_pages(previous_items)
        self._finalize_subject()

        self.text = self.text_start + self.text + self.text_end
        self.notifier.send_mail(self.subject, self.text)

    def _read_previous_items(self):
        if os.path.exists(self.houses_file):
            with open(self.houses_file, 'r', encoding='utf-8') as file:
                return file.read().splitlines()
        return []

    def _check_item(self, items, title):
        return any(title in item for item in items)

    def _get_houses(self, previous_items, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        self.page_count += 1
        print(f"爬取第 {self.page_count} 页中～")
        items = soup.find_all(class_="search-item")

        for item in items:
            info = item.find(class_="info")
            title = info.find(class_="title").text.replace(",", ";")
            if previous_items and self._check_item(previous_items, title):
                continue
            self._write_file(info)
            self.house_count += 1
            print(f"添加新房源: {title}.")

    def _get_other_pages(self, previous_items):
        response = requests.get(self.url)
        soup = BeautifulSoup(response.text, 'html.parser')
        print(soup.text)
        pagination = soup.find('nav', {'aria-label': 'Search Pagination'})
        if pagination:
            links = pagination.find_all('a', {'data-testid': 'pagination-link-item'})
            for link in links:
                href = link.get('href')
                if href:
                    next_url = href
                    self._get_houses(previous_items, next_url)
                    sleep_time = random.uniform(1, 10)
                    time.sleep(sleep_time)
                    print(f"等待 {sleep_time:.2f} 秒钟")

    def _write_file(self, info):
        title = info.find(class_="title").text.replace(",", ";")
        detail_url = "https://www.kijiji.ca" + info.find('a').get('href')
        price = '"' + info.find(class_="price").text + '"'
        description = info.find(class_="description").text.replace(",", ";")
        location = info.find(class_="location").text.replace(",", ";")
        date_posted = info.find(class_="date-posted").text.replace(",", ";")
        distance = info.find(class_="distance").text.replace(",", ";")

        file_str = f"{title},{price},{description},{location},{date_posted},{distance},{self.date},{detail_url}\n"
        html_str = f"<tr><td>{title}</td><td>{price}</td><td>{description}</td><td>{location}</td><td>{date_posted}</td><td>{distance}</td><td>{self.date}</td><td>{detail_url}</td></tr>\n"

        for each in self.sep_key_words:
            if each in file_str:
                self.sep_houses += 1
                print("可能找到一个八月九月房源～")

        self.text += html_str

        with open(self.houses_file, 'a', encoding='utf-8') as file:
            file.write(file_str)

    def _finalize_subject(self):
        self.subject += f"{self.date}-新增房源-{self.house_count}套-可能新增8、9月房源-{self.sep_houses}套"
        print(f"新增房源-{self.house_count}套")
        print(f"可能新增8、9月房源-{self.sep_houses}套")
        print("爬取完毕，发送中")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="The target Kijiji house search URL you want.")
    parser.add_argument("url", nargs="?", default="https://www.kijiji.ca/b-room-rental-roommate/ottawa/c36l1700185?address=Algonquin%20College%20Ottawa%20Campus,%20Woodroffe%20Avenue,%20Nepean,%20ON&ll=45.349934%2C-75.754926&radius=3.0", help="The target Kijiji house search URL you want.")
    parser.add_argument("--config", required=True, help="Path to the configuration file.")
    args = parser.parse_args()

    scraper = Scraper(args.url, args.config)
    scraper.execute()
