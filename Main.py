# INFO Reformat (Alt+F). Show Intention Action (Alt+Enter). Completion (Ctrl+Space, Ctrl+Shift+Space)

# TODO Find out why the code sometimes hangs while processing the big list.
# TODO cleanup the printing after you fixed the problem above
# FIXME You should go to sleep only if you actually accessed some API. No point in slowing your program for no reason.
# TODO GUI



import json
import csv
import os
import time
import logging

import urllib
import urllib.parse
import urllib.request
import contextlib
from bs4 import BeautifulSoup
from sys import stdout as syso


class ParseException(Exception):
    pass


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

    def find_id(self, applist=None):
        if applist is not None:
            """Lookup your own id in the supplied list."""
            logging.info('  Looking in applist for %s' % self.users_name)
            self.id = applist.name_lookup.get(self.simplified_name, None)  # default value = None

        if self.id is None:
            """ID wasn't found in the applist. Looking for it in google."""
            logging.info('  "%s" was not found in the applist. Looking in google.' % self.users_name)
            # return Game.__scrap_id_from_google__(name)
            global config
            if config["key"] is not None:
                self.id = Game.__search_id_google_api__(self.users_name, config["cx"], config["key"])
            else:
                logging.info("Can't search google for %s because API key is not set. Skipping.", self.users_name)

        return self.id

    @staticmethod
    def __scrap_id_from_google__(name):
        """ Unused. Preform a google search with the name given by the user in order to locate the correct game."""
        url = "http://www.google.com/search?q=site:store.steampowered.com+%s&lr=lang_en" % urllib.parse.quote(name, safe="")
        hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        req = urllib.request.Request(url, headers=hdr)

        try:
            time.sleep(5)
            with contextlib.closing(urllib.request.urlopen(req)) as x:
                html = x.read()

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
    def __search_id_google_api__(name, cx, key):
        """Uses google's custom search api to find your id"""
        url = "https://www.googleapis.com/customsearch/v1?q=%s&cx=%s&key=%s&fields=searchInformation(totalResults),items(title,link)"
        url %= urllib.parse.quote(name, safe=""), urllib.parse.quote(cx, safe=""), urllib.parse.quote(key, safe="")
        hdr = {'User-Agent': 'CardsTool'}
        req = urllib.request.Request(url, headers=hdr)

        try:
            time.sleep(1)
            with contextlib.closing(urllib.request.urlopen(req)) as x:
                json_bytes = x.read()
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
        if self.card_status_known:
            logging.info("Card status for %s is already known. Skipping fetch.", self.users_name)
            return True
        if self.id is None:
            logging.warning("Unknown app_id: Skipping data fetch for %s.", self.users_name)
            return False
        logging.info("  Fetching card data for app %s (%s).", self.id, self.users_name)
        data = Game.__app_details_steam_api__(self.id)
        if data is None:
            logging.error("Fetching Failed! app %s (%s).", self.id, self.users_name)
            return False

        self.card_status_known = True

        for tag in data["categories"]:
            if tag["id"] == 29:  # and tag["description"] == "Steam Trading Cards":
                self.has_cards = True

        return True

    @staticmethod
    def __app_details_steam_api__(app_id):
        """Use Steam's web api and fetch details about the app whose ID is app_id"""
        req = urllib.request.Request("http://store.steampowered.com/api/appdetails/?appids=" + app_id)

        try:
            json_bytes = urllib.request.urlopen(req).read()

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

    @staticmethod
    def fetch_from_net(url=FETCH_URL):
        """Fetch new AppList from the web. See: http://api.steampowered.com/ISteamApps/GetAppList/v0001/ """
        req = urllib.request.Request(url)
        try:
            json_bytes = urllib.request.urlopen(req).read()
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

    def fetch(self, fetch_from_net=False):
        """Fill the object with data about app names. get the data either from a local file or from the internet. Automatically access the net if the file is missing."""
        if self.__data__ is not None:
            return self

        if fetch_from_net or not os.path.exists(AppList.FETCH_LOCAL_PATH):
            json_text = AppList.fetch_from_net()
            self.__data__ = AppList.json_to_list(json_text)
            AppList.write_apps_to_disk(json_text)
        else:
            self.__data__ = AppList.json_to_list(AppList.fetch_from_disk())

        # Lookup appid->name
        self.id_lookup = {pair["appid"]: pair["name"] for pair in self.__data__}

        # Lookup name->appid. It is possible that there are multiple games with the same name. Remove all of them. Handle it latter in the code.
        simplified_names = [simplified_name(pair["name"]) for pair in self.__data__]
        id_strings = [str(pair["appid"]) for pair in self.__data__]
        pairs = zip(simplified_names, id_strings)

        self.name_lookup = {name: appid for (name, appid) in pairs if simplified_names.count(name) == 1}

        return self


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


class CSVExporter:
    def __init__(self, filename, log_to_console=False):
        self.file = open(filename, mode="w", encoding='UTF-8', newline='')
        self.file_writer = csv.writer(self.file)
        self.console_writer = csv.writer(syso) if log_to_console else None

    def close(self):
        self.file.close()

    def write(self, game):
        line = [game.users_name, game.id, "" if not game.card_status_known else "TRUE" if game.has_cards else "FALSE"]
        self.file_writer.writerow(line)
        if self.console_writer is not None:
            self.console_writer.writerow(line)  # TODO figure out how to pretty print this in case I'm displaying it on the console


def log_config(filename=None, console=False, level=logging.INFO):
    logger = logging.getLogger()

    if filename is not None:
        bob = logging.FileHandler("log.log", encoding="utf-8")
        bob.setFormatter(logging.Formatter(fmt='%(asctime)s     %(levelname)s:%(message)s', datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(bob)

    if console:  # False or None means no output. True means syso output. Instance of stream means output to the stream.
        stream = syso if console is True else console
        joe = logging.StreamHandler(stream)
        logger.addHandler(joe)

    logger.setLevel(level)
    logging.info("------------------------------------------Starting------------------------------------------")


def string_is_int(s):
    """Source: https://stackoverflow.com/a/1267145/2842452"""
    try:
        int(s)
        return True

    except ValueError:
        return False


def load_config(path):
    global config
    with open(path, encoding='UTF-8') as file:
        config = json.loads(file.read())
        if config["key"] == "123":
            config["key"] = None
            logging.warning("No Google API key is set. Using google search is impossible.")

        return config


def users_game_list(path):
    """Reads the file located in path and creates a Game object for each game written there. One game name per line."""

    with open(path, encoding='UTF-8', newline="") as file:
        file_reader = csv.reader(file)
        for row in file_reader:
            if len(row) == 0:
                continue

            if len(row) >= 3 and string_is_int(row[-2]) and row[-1].upper() in ["TRUE", "FALSE", ""]:
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


def main():
    # TODO clean main function. Maybe split into smaller functions or make it gui friendly.

    path_in = "Test/big_list.txt"
    path_out = "Test/big_list_out.csv"

    logging.info("Loading config file")
    load_config("./config.txt")
    logging.info("Loading AppList")
    app_list = AppList().fetch()
    export = CSVExporter(path_out, log_to_console=True)
    cooldown = 0

    try:
        for game in users_game_list(path_in):
            logging.info("%d) %s", cooldown, game.users_name)
            if game.id is None:
                succ = game.find_id(app_list)
                if not succ:
                    logging.error("Couldn't find ID for %s", game.users_name)

            succ = game.fetch_card_info()
            if not succ:
                logging.error("Couldn't find cards status for %s", game.users_name)

            logging.info("  exporting")
            export.write(game)
            logging.info("  resting")
            time.sleep(1)
            cooldown += 1
            if cooldown % 100 == 0:
                logging.info("Scan card details for 100 games. Going for a 30 seconds nap (To avoid overwhelming Steam's web api).")
                time.sleep(30)
            logging.info("  back to work")

    finally:
        export.close()


if __name__ == "__main__":
    config = None
    log_config(filename="log.log", console=True)
    main()
    logging.shutdown()
