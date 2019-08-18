import re
import json
import uuid
import os

import requests
from bs4 import BeautifulSoup

from carecog.data.scraper.configs import HEADERS


class AutoTraderScraper:
    domain = "https://www.autotrader.ca"
    write_data_folder = "data/raw/auto_trader/"

    def __init__(self, current_search_idx=0, search_by=100):
        self.current_search_idx = current_search_idx
        self.search_by = search_by

        self.cache_car_urls = set()

    @property
    def payload(self):
        payload = {"rcp": self.search_by,
                   "rcs": self.current_search_idx,
                   "srt": 9,
                   "prx": -1,
                   "hprc": True,
                   "wcp": True,
                   "loc": "J5Y3L1",
                   "sts": "New-Used",
                   "inMarket": "advancedSearch"}

        return payload

    def _get_auto_urls(self, search_page):
        soup = BeautifulSoup(search_page.content, 'html.parser')
        car_urls = list()

        for link in soup.find_all('a', href=True):
            rel_link = link["href"]

            if rel_link.startswith("/a/") and rel_link not in self.cache_car_urls:
                car_urls.append(rel_link)
                self.cache_car_urls.add(rel_link)

        return car_urls

    def process_search_page(self):
        search_page = requests.get(self.domain + "/cars/", headers=HEADERS, params=self.payload)
        car_urls = self._get_auto_urls(search_page)

        for car_url in car_urls:
            url = self.domain + car_url
            self.process_car_page(url)

        print("End search page " + str(self.current_search_idx))
        self.current_search_idx += self.search_by

    @staticmethod
    def _extract_vehicle_data(car_soup):
        pattern = re.compile(r"vehicleData\s+=\s+(\{.*?\});\n")
        script = car_soup.find("script", text=pattern)

        vehicle_data = pattern.search(script.text).group(1)
        vehicle_data = json.loads(vehicle_data)

        return vehicle_data

    @staticmethod
    def _extract_img_urls(car_soup):
        urls = list()
        for img in car_soup.find_all("img"):
            rel_url = img.get('data-src')

            if rel_url is not None:
                img_url = rel_url.split(".jpg")[0] + ".jpg"
                urls.append(img_url)

        return urls

    def process_car_page(self, car_url):
        car_id = str(uuid.uuid4())
        car_path = self.write_data_folder + car_id + "/"

        if not os.path.exists(car_path):
            os.makedirs(car_path)

        car_page = requests.get(car_url, headers=HEADERS)
        car_soup = BeautifulSoup(car_page.content, 'html.parser')

        vehicle_data = self._extract_vehicle_data(car_soup)
        img_urls = self._extract_img_urls(car_soup)
        vehicle_data["img_urls"] = img_urls

        for img_url in img_urls:
            self._download_img(img_url, car_path + img_url.split("/")[-1])

        with open(car_path + "meta.json", "w") as f:
            json.dump(vehicle_data, f)

        print(car_id)

    def start_crawl(self):
        while True:
            self.process_search_page()

    @staticmethod
    def _download_img(img_url, img_path):
        img = requests.get(img_url).content

        with open(img_path, "wb") as handler:
            handler.write(img)