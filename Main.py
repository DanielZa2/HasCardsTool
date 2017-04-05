import json
import os
import datetime
import collections
import time
import logging

from urllib import request as urlrequest
from urllib import error as urlerror


class ParseException(Exception):
    pass


class SteamApp:
    """Describe a single steam app. That is, more often than not, a game."""

    def __init__(self, name):
        self.id = None
        self.users_name = name
        self.simplified_name = simplified_name(name)
        self.card_status_known = False
        self.has_cards = False

    def __str__(self):
        return self.users_name

    def __repr__(self):
        return "<SteamApp: {0}>".format(self.users_name)

    def find_id(self, applist):
        """Lookup your own id in the supplied list."""
        self.id = applist.name_lookup.get(self.simplified_name, None)  # default=None
        return self.id

    @staticmethod
    def __fetch_app_detailed_info_from_net__(app_id):
        """Use Steam's web api and fetch details about the app whose ID is app_id"""
        req = urlrequest.Request("http://store.steampowered.com/api/appdetails/?appids=" + app_id)

        try:
            json_bytes = urlrequest.urlopen(req).read()
        except urlerror.HTTPError:
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

    def fetch_card_info(self):
        """Use Steam's web api to find out whatever the app has cards."""
        if self.id is None:
            logging.warning("Unknown app_id: Skipping data fetch for %r.", self.users_name)
            return
        logging.info("Fetching card data for app %s (%r).", self.id, self.users_name)
        data = SteamApp.__fetch_app_detailed_info_from_net__(self.id)
        if data is None:
            logging.error("Fetching Failed! app %s (%r).", self.id, self.users_name)
            return

        self.card_status_known = True

        for tag in data["categories"]:
            if tag["id"] == 29:  # and tag["description"] == "Steam Trading Cards":
                self.has_cards = True
                break


class SteamAppList:
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
        req = urlrequest.Request(url)
        try:
            json_bytes = urlrequest.urlopen(req).read()
        except urlerror.HTTPError:
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
        """Fill the object with data about app names. get the data either from a local file or from the internet. Automaticlly access the net if the file is missing."""
        if self.__data__ is not None:
            return self

        if fetch_from_net or not os.path.exists(SteamAppList.FETCH_LOCAL_PATH):
            json_text = SteamAppList.fetch_from_net()
            self.__data__ = SteamAppList.json_to_list(json_text)
            SteamAppList.write_apps_to_disk(json_text)
        else:
            self.__data__ = SteamAppList.json_to_list(SteamAppList.fetch_from_disk())

        self.id_lookup = {pair["appid"]: pair["name"] for pair in self.__data__}
        self.name_lookup = {simplified_name(pair["name"]): str(pair["appid"]) for pair in self.__data__}
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


def fetch_users_game_list(path, applist=None):
    """Reads the file located in path and creates a SteamApp object for each game written there. One game name per line."""
    if applist is None:
        applist = SteamAppList().fetch()
    with open(path, encoding='UTF-8') as file:
        names = file.read().splitlines()
        users_games = list(map(SteamApp, names))

    for game in users_games:
        game_id = game.find_id(applist)
        if game_id is None:
            logging.error("Couldn't find ID for %r", game.users_name)

    return users_games


def fetch_card_info(users_games):
    """Calls fetch_card_info for each game in users_games. Inserts some delays to not overwhelm Steam's API."""
    cooldown = 0
    for game in users_games:
        game.fetch_card_info()
        time.sleep(1)
        cooldown += 1
        if cooldown >= 100:
            logging.info("Scan card details for 100 games. Going for a 30 seconds nap (To avoid overwhelming Steam's web api).")
            time.sleep(30)
            cooldown = 0


def export_csv(games, filename="output.csv"):
    """Exports the results as a csv file."""
    with open(filename, mode="w", encoding='UTF-8') as file:
        line = "Title, AppID, Cards"
        file.write(line)
        file.write("\n")
        print(line)

        for game in games:
            name = game.users_name if "," not in game.users_name else "\"" + game.users_name + "\""
            app_id = game.id if game.id is not None else ""
            cards = "" if not game.card_status_known else "TRUE" if game.has_cards else "FALSE"
            line = "{0},{1},{2}".format(name, app_id, cards)
            file.write(line)
            file.write("\n")
            print(line)


def log_config(filename="log.log"):
    logging.basicConfig(filename=filename, level=logging.INFO, format='%(asctime)s     %(levelname)s:%(message)s', datefmt="%Y-%m-%d %H:%M:%S")


def main():
    path = "Test/list.txt"
    input_games = fetch_users_game_list(path)
    fetch_card_info(input_games)
    export_csv(input_games, "Test/list_out.csv")


if __name__ == "__main__":
    log_config()
    main()
