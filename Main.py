# TODO Remap shortcut keys. Shift+Space. Rename (Shift+F6). Reformal (Ctrl+Alt+L)
# Play around with the windows. Use the real estate from your second secreen for some of the bars.

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
        if self.id is not None:
            return True

        if applist is not None:
            """Lookup your own id in the supplied list."""
            logging.info('Looking for %s in the applist' % self.users_name)
            self.id = applist.name_lookup.get(self.simplified_name, None)  # default value = None

        if self.id is None:
            """ID wasn't found in the applist. Looking for it in google."""
            logging.warning('"%s" was not found in the applist. Looking in google.' % self.users_name)
            self.id = Game.__fetch_id_from_net__(self.users_name)

        return self.id is not None

    @staticmethod
    def __fetch_app_detailed_info_from_net__(app_id):
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

    @staticmethod
    def __fetch_id_from_net__(name):
        return Game.__search_id_google_api__(name)

    @staticmethod
    def __scrap_id_from_google__(name):
        """Preform a google search with the name given by the user in order to locate the correct game."""
        url = "http://www.google.com/search?q=site:store.steampowered.com+%s&lr=lang_en" % urllib.parse.quote(name, safe="")
        hdr = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36'}
        req = urllib.request.Request(url, headers=hdr)

        try:
            time.sleep(5)
            with contextlib.closing(urllib.request.urlopen(req)) as x:
                html = x.read()
                # TODO check HTML code and make sure that the answer returned is an actual answer. Stop googling if you capacity is expended.

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
    def __search_id_google_api__(name, cx="001484053352446370655:wd3-r7pqncc", key="AIzaSyD-XEIVjk9wrv4XDv1hKqFrvOHZyKkwGYU"):
        """Uses google's custom search api to find your id"""
        url = "https://www.googleapis.com/customsearch/v1?q=%s&cx=%s&key=%s&fields=items(title,link)"
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

        except (json.decoder.JSONDecodeError, KeyError):
            logging.exception("Failed to parse google's response for %s", name)
            return None

        data = data["items"]
        if len(data) < 1:
            return None
        top_result = data[0]["title"]
        top_link = data[0]["link"]

        app_id = top_link[top_link.index("/app/") + len("/app/"):]
        app_id = app_id[:app_id.index("/")]
        return app_id

    def fetch_card_info(self):
        """Use Steam's web api to find out whatever the app has cards."""
        if self.id is None:
            logging.warning("Unknown app_id: Skipping data fetch for %r.", self.users_name)
            return
        logging.info("Fetching card data for app %s (%r).", self.id, self.users_name)
        data = Game.__fetch_app_detailed_info_from_net__(self.id)
        if data is None:
            logging.error("Fetching Failed! app %s (%r).", self.id, self.users_name)
            return

        self.card_status_known = True

        for tag in data["categories"]:
            if tag["id"] == 29:  # and tag["description"] == "Steam Trading Cards":
                self.has_cards = True
                break


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


def fetch_users_game_list(path, app_list=None):
    """Reads the file located in path and creates a Game object for each game written there. One game name per line."""
    if app_list is None:
        app_list = AppList().fetch()
    logging.info("Got applist: %s", app_list is not None)

    with open(path, encoding='UTF-8', newline="") as file:
        file_reader = csv.reader(file)
        users_games = []
        for row in file_reader:

            if len(row) >= 3 and string_is_int(row[-2]) and row[-1] in ["True", "False", ""]:
                """The line scanned is in the same format as the output of our program"""
                name = "".join(row[:-2])
                game = Game(name)
                game.id = row[-2]
                game.card_status_known = row[-1] is not ""
                game.has_cards = bool(row[-1]) if game.card_status_known else False
            else:
                """The line wasn't written by us. Assuming it is all one long name"""
                name = "".join(row)
                game = Game(name)
            users_games.append(game)

    return users_games


def find_app_ids_for_games(users_games, app_list=None):
    for game in users_games:
        succ = game.find_id(app_list)
        if not succ:
            logging.error("Couldn't find ID for %r", game.users_name)


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


def export_csv(games, filename="output.csv", log_to_console=False):
    """Exports the results as a csv file."""
    with open(filename, mode="w", encoding='UTF-8', newline='') as file:
        file_writer = csv.writer(file)
        file_writer.writerow(["Title", "AppID", "Cards"])

        for game in games:
            line = [game.users_name, game.id, "" if not game.card_status_known else "TRUE" if game.has_cards else "FALSE"]
            file_writer.writerow(line)

    if log_to_console:
        with open(filename, encoding='UTF-8') as file:
            print(file.read())

def log_config(filename="log.log", log_to_console=False):
    logging.basicConfig(filename=filename, level=logging.INFO, format='%(asctime)s     %(levelname)s:%(message)s', datefmt="%Y-%m-%d %H:%M:%S")
    if log_to_console:
        logging.getLogger().addHandler(logging.StreamHandler(syso))
    logging.info("------------------------------------------Starting------------------------------------------")


def string_is_int(s):
    """Source: https://stackoverflow.com/a/1267145/2842452"""
    try:
        int(s)
        return True
    except ValueError:
        return False


def main():
    path = "Test/list_with_csv.txt"
    input_games = fetch_users_game_list(path)
    print(input_games)
    # find_app_ids_for_games(input_games)
    # fetch_card_info(input_games)
    export_csv(input_games, "Test/list_out.csv", log_to_console=True)


def main2():
    ans = Game.__search_id_google_api__("Bioshock")
    print(ans)


if __name__ == "__main__":
    log_config(log_to_console=True) # TODO Test Code
    main()
