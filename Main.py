# LOOK Reformat (Alt+F). Show Intention Action (Alt+Enter). Completion (Ctrl+Space, Ctrl+Shift+Space)




import json
import csv
import os
import time
import logging

import urllib
import urllib.parse
import urllib.request
from contextlib import closing
from bs4 import BeautifulSoup
from sys import stdout as syso
from socket import timeout


class Game:
    """Describe a single steam app. More often than not, a game. Could also represent software, DLC, and anything bought from steam."""

    def __init__(self, name):
        self.id = None
        self.users_name = name
        self.simplified_name = simplified_name(name)
        self.card_status_known = False
        self.has_cards = False

    def __str__(self):
        return self.users_name

    def __repr__(self):
        return "<SteamApp: %s>" % self.users_name

    def find_id(self, applist=None, config=None, online=True):
        accessed_net = False

        if self.id is not None:
            logging.info("ID for %s is already known.", self.users_name)
            return accessed_net

        if applist is not None:
            """Lookup your own id in the supplied list. If there are multiple games with this name it is better to leave the decision to google, if possible."""
            if not online or not applist.contains_duplicates(self.simplified_name):
                logging.info('Looking in applist for %s' % self.users_name)
                self.id = applist.name_lookup.get(self.simplified_name, None)  # default value = None

        if self.id is None and online:
            """ID wasn't found in the applist. Looking for it in google."""
            logging.info('"%s" was not found in the applist. Looking in google.' % self.users_name)
            # return Game.__scrap_id_from_google__(name)
            if config["key"] is not None:
                self.id = Game.__search_id_google_api__(self.users_name, config["cx"], config["key"])
                accessed_net = True
            else:
                logging.info("Can't search google for %s because API key is not set. Skipping.", self.users_name)

        if self.id is not None:
            logging.info("ID for %s is found. %s", self.users_name, self.id)
        return accessed_net

    @staticmethod
    def __scrap_id_from_google__(name):
        """ Unused. Preform a google search with the name given by the user in order to locate the correct game."""
        url = "http://www.google.com/search?q=site:store.steampowered.com+%s&lr=lang_en" % urllib.parse.quote(name, safe="")
        hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        req = urllib.request.Request(url, headers=hdr)

        try:
            time.sleep(5)
            with urllib.request.urlopen(req) as f:
                html = f.read()

                # html = urllib.request.urlopen(req).read()
        except urllib.error.HTTPError:
            logging.exception("Failed while googling the name %s", name)
            return None

        try:
            soup = BeautifulSoup(html, 'html.parser')
            anchors = soup.find(id="search").findAll('a')
            final_links = [x['href'] for x in anchors if x['href'].startswith("http://store.steampowered.com/app/") or x['href'].startswith("https://store.steampowered.com/app/")]
            # print("\n".join(final_links))
            top_link = final_links[0]
            app_id = top_link[top_link.index("/app/") + len("/app/"):]
            app_id = app_id[:app_id.index("/")]
            return app_id

        except (json.decoder.JSONDecodeError, KeyError):
            logging.exception("Failed to parse google's response to %s", name)
            return None

    @staticmethod
    def __search_id_google_api__(name, cx, key, timeout_time=10):
        """Uses google's custom search api to find your id"""
        url = "https://www.googleapis.com/customsearch/v1?q=%s&cx=%s&key=%s&fields=searchInformation(totalResults),items(title,link)"
        url %= urllib.parse.quote(name, safe=""), urllib.parse.quote(cx, safe=""), urllib.parse.quote(key, safe="")
        hdr = {'User-Agent': 'CardsTool'}
        req = urllib.request.Request(url, headers=hdr)
        try:
            with urllib.request.urlopen(req, timeout=timeout_time) as f:
                json_bytes = f.read()
        except timeout:
            logging.error("Timeout while getting appid for %s. \n\t\t%s", name, req.get_full_url())
            return None
        except urllib.error.HTTPError:
            logging.exception("Failed while googling the name %s", name)
            return None
        json_text = json_bytes.decode("utf-8")
        try:
            data = json.loads(json_text)
            total_results = int(data["searchInformation"]["totalResults"])
            if total_results < 1 or len(data["items"]) < 1:
                logging.error("No results found for %s", name)
                return None


        except (json.decoder.JSONDecodeError, KeyError, ValueError):
            logging.exception("Failed to parse google's response for %s", name)
            return None
        top_result = data["items"][0]["title"]
        top_link = data["items"][0]["link"]

        app_id = top_link[top_link.index("/app/") + len("/app/"):]
        app_id = app_id[:app_id.index("/")]
        return app_id

    def fetch_card_info(self):
        """Use Steam's web api to find out whatever the app has cards."""
        accessed_net = False

        if self.card_status_known:
            logging.info("Card status for %s is already known. %s. Skipping fetch.", self.users_name, self.has_cards)
            return accessed_net
        if self.id is None:
            logging.warning("Unknown app_id: Skipping data fetch for %s.", self.users_name)
            return accessed_net
        logging.info("Fetching card data for app %s (%s).", self.id, self.users_name)
        data = Game.__app_details_steam_api__(self.id)
        accessed_net = True
        if data is None:
            logging.error("Fetching Failed! app %s (%s).", self.id, self.users_name)
            return accessed_net

        self.card_status_known = True
        for tag in data["categories"]:
            if tag["id"] == 29:  # and tag["description"] == "Steam Trading Cards":
                self.has_cards = True
        logging.info("Card status for %s is found. %s", self.users_name, self.has_cards)
        return accessed_net

    @staticmethod
    def __app_details_steam_api__(app_id, timeout_time=20):
        """Use Steam's web api and fetch details about the app whose ID is app_id"""
        req = urllib.request.Request("http://store.steampowered.com/api/appdetails/?appids=" + app_id)
        try:
            with urllib.request.urlopen(req, timeout=timeout_time) as f:
                json_bytes = f.read()

        except timeout:
            logging.error("Timeout while getting details for %s. \n\t\t%s", app_id, req.get_full_url())
            return None
        except urllib.error.HTTPError:
            logging.exception("Failed getting details for app number %s", app_id)
            return None
        json_text = json_bytes.decode("utf-8")
        try:
            game_info = json.loads(json_text)
            if not game_info[app_id]["success"]:
                return None

            data = game_info[app_id]["data"]
            return data

        except (json.decoder.JSONDecodeError, KeyError):
            logging.exception("Failed to parse details for app number %s", app_id)
            return None


class AppList:
    """Describe a list of appIDs and app names. Used to find the name of the app based on the id."""
    FETCH_URL = "http://api.steampowered.com/ISteamApps/GetAppList/v0001/"
    FETCH_LOCAL_PATH = "Applist.txt"

    def __init__(self):
        self.__data__ = None
        self.id_lookup = None
        self.name_lookup = None
        self.simplified_names = None

    @staticmethod
    def fetch_from_net(url=FETCH_URL):
        """Fetch new AppList from the web. See: http://api.steampowered.com/ISteamApps/GetAppList/v0001/ """
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as f:
                json_bytes = f.read()
        except urllib.error.HTTPError:
            logging.exception("Failed to fetch applist from net")
            return None

        return json_bytes.decode("utf-8")

    @staticmethod
    def fetch_from_disk(path=FETCH_LOCAL_PATH):
        """Fetch AppList from the disk where it was previously saved."""
        with open(path, encoding='UTF-8') as file:
            return file.read()

    @staticmethod
    def write_apps_to_disk(data, path=FETCH_LOCAL_PATH):
        """Write ApplList to the disk. Probably because a new one was fetched from the internet."""
        with open(path, "w", encoding='UTF-8') as file:
            file.write(data)

    @staticmethod
    def json_to_list(json_text):
        """Parse the json data and turn it into a list of id-name pairs"""
        try:
            game_info = json.loads(json_text)
            return game_info["applist"]["apps"]["app"]

        except (json.decoder.JSONDecodeError, KeyError):
            logging.exception("Failed to parse fetched applist")
            return None

    def fetch(self, always_fetch_from_net=False):
        """Fill the object with data about app names. get the data either from a local file or from the internet. Automatically access the net if the file is missing."""
        if self.__data__ is not None:
            return self

        if always_fetch_from_net or not os.path.exists(AppList.FETCH_LOCAL_PATH):
            json_text = AppList.fetch_from_net()
            self.__data__ = AppList.json_to_list(json_text)
            AppList.write_apps_to_disk(json_text)
        else:
            self.__data__ = AppList.json_to_list(AppList.fetch_from_disk())

        # Lookup appid->name
        self.id_lookup = {pair["appid"]: pair["name"] for pair in self.__data__}

        # Lookup name->appid. It is possible that there are multiple games with the same name. Remove all of them. Handle it latter in the code.
        self.simplified_names = [simplified_name(pair["name"]) for pair in self.__data__]
        id_strings = [str(pair["appid"]) for pair in self.__data__]

        self.name_lookup = {name: appid for (name, appid) in zip(self.simplified_names, id_strings)}
        return self

    def contains_duplicates(self, name):
        return self.simplified_names.count(name) > 1


def simplified_name(name):
    """Takes a name and transforms it into simpler form that will be used as dict key. Used to make sure that even if the user wrote non-exact name the program will still recognize it.
    For example transforms "Brütal Legend" into "Brutal Legend". Whatever spelling the user used in his list, both will be mapped to the same key.
    """
    ret = name.strip()
    ret = ret.lower()

    translation_table = dict.fromkeys(map(ord, "™®©!,.'’`[](){}\""), None)
    translation_table.update(dict.fromkeys(map(ord, "_-:;"), " "))
    translation_table[ord("&")] = "and"
    translation_table[ord("á")] = "a"
    translation_table[ord("é")] = "e"
    translation_table[ord("í")] = "i"
    translation_table[ord("ó")] = "o"
    translation_table[ord("ö")] = "o"
    translation_table[ord("ú")] = "u"
    translation_table[ord("ü")] = "u"
    translation_table[ord("ﬁ")] = "fi"

    ret = ret.translate(translation_table)
    ret = " ".join(ret.split())
    return ret


class Exporter:
    def __init__(self, *args):
        self.exporter_list = list(args)


    def add_output(self, exporter):
        self.exporter_list.append(exporter)


    def write(self, game):
        for e in self.exporter_list:
            e.write(game.users_name, game.id, game.card_status_known, game.has_cards)

    def close(self):
        for e in self.exporter_list:
            if callable(getattr(e, "close", None)):
                e.close()

    def flush(self):
        for e in self.exporter_list:
            if callable(getattr(e, "flush", None)):
                e.flush()

    class CSVFile:

        def __init__(self, filename):
            self.file = open(filename, mode="w", encoding='UTF-8', newline='')
            self.file_writer = csv.writer(self.file)

        def close(self):
            self.file.close()

        def flush(self):
            """Source: https://stackoverflow.com/a/19756479/2842452"""
            self.file.truncate()
            self.file.seek(0, 0)
            self.file.flush()
            os.fsync(self.file.fileno())



        def write(self, name, appid, card_status_known, has_cards):
            appid = str(appid) if appid is not None else ""
            status = "" if not card_status_known else "TRUE" if has_cards else "FALSE"
            self.file_writer.writerow([name, appid, status])

    class Log:

        def __init__(self, level=logging.INFO):
            self.level = level


        def write(self, name, appid, card_status_known, has_cards):
            appid = str(appid) if appid is not None else "?"
            status = "?" if not card_status_known else "TRUE" if has_cards else "FALSE"
            logging.log(self.level, "%s (%s): [%s]", name, appid, status)

    class TextBox:

        def __init__(self, box, index):
            self.box = box
            self.index = index

        def write(self, name, appid, card_status_known, has_cards):
            appid = str(appid) if appid is not None else "?"
            status = "?" if not card_status_known else "TRUE" if has_cards else "FALSE"
            self.box.insert(self.index, "%s (%s): [%s]\n" % (name, appid, status))



class Delayer:
    def __init__(self, long_sleep_count=50, short_sleep_time=1.5, long_sleep_time=15):
        self.count = long_sleep_count
        self.i = long_sleep_count
        self.short = short_sleep_time
        self.long = long_sleep_time

    def tick(self):
        time.sleep(self.short)
        self.i -= 1
        if self.i <= 0:
            self.i = self.count
            logging.info("Accessed the internet %d times. Taking a short break to avoid overwhelming APIs.", self.count)
            time.sleep(self.long)


def init_log(filename=None, console=False, level=logging.WARNING):
    logger = logging.getLogger()

    if filename is not None:
        handler = logging.FileHandler(filename, encoding="utf-8", mode='w')
        handler.setFormatter(logging.Formatter(fmt='%(asctime)s     %(levelname)s:%(message)s', datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)

    if console:  # False or None means no output. True means syso output. Instance of stream means output to the stream.
        stream = syso if console is True else console
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)

    logger.setLevel(level)


def string_represent_int(s):
    """Source: https://stackoverflow.com/a/1267145/2842452"""
    try:
        int(s)
        return True

    except ValueError:
        return False


def load_config_file(path):
    with open(path, encoding='UTF-8') as file:
        config = json.loads(file.read())
        if config["key"] == "YOUR_KEY_HERE":
            config["key"] = None
            logging.warning("No Google API key is set. Using google search is impossible.")

        return config


def users_game_gen(path):
    """Reads the file located in path and creates a Game object for each game written there. One game name per line."""

    with open(path, encoding='UTF-8', newline="") as file:
        file_reader = csv.reader(file)
        for row in file_reader:
            if len(row) == 0:
                continue

            if len(row) >= 3 and string_represent_int(row[-2]) and row[-1].upper() in ["TRUE", "FALSE", ""]:
                """The line scanned is in the same format as the output of our program"""
                name = "".join(row[:-2])
                game = Game(name)
                game.id = row[-2]
                game.card_status_known = row[-1] != ""
                game.has_cards = game.card_status_known and row[-1].upper() == "TRUE"
            else:
                """The line wasn't written by us. Assuming it is all one long name"""
                name = "".join(row)
                game = Game(name)
            yield game


def users_game_list(path):
    return list(users_game_gen(path))


def main():
    path_in = "Test/big_list.txt"
    path_out = "Test/big_list_out.csv"

    init_log(filename="log.txt", console=True, level=logging.DEBUG)
    logging.info("Loading configuration file")
    config = load_config_file("./config.txt")
    logging.info("Loading AppList")
    app_list = AppList().fetch()
    logging.info("Creating timer")
    sleep = Delayer(50, 1.5, 15)
    logging.info("Creating an exporter")
    with closing(Exporter(Exporter.CSVFile(path_out), Exporter.Log())) as export:

        for game in users_game_gen(path_in):
            err = False
            logging.info("Processing: %s", game.users_name)
            accessed_net = game.find_id(app_list, config)
            if game.id is None:
                logging.error("Couldn't find ID for %s", game.users_name)
                err = True

            if not err:
                accessed_net = game.fetch_card_info() or accessed_net  # Order is important here. You don't want to short-circuit the fetch.
                if not game.card_status_known:
                    logging.error("Couldn't find cards status for %s", game.users_name)
                    err = True

            if not err:
                export.write(game)

            if accessed_net:  # We go to sleep if we gone online. Regardless of "err" and our success with fetching the cards.
                sleep.tick()

    logging.shutdown()


if __name__ == "__main__":
    main()
