import json
import os
import datetime
import collections
import logging

from urllib import request as urlrequest
from urllib import error as urlerror

logging.basicConfig(filename="log.log")


class ParseException(Exception):
    pass




def simplified_name(name):
    ret = name.strip()
    ret = ret.translate(None, "™®©!,.'[](){}")  # Remove these characters from the string
    for ch in ["_", "-", ":", ";"]:
        if ch in ret:
            ret = ret.replace(ch, " ")

    # ret = ret.replace("'s", "")
    ret = ret.replace("&", " and ")
    return ret


def fetch_game_list(path):
    with open(path, encoding='UTF-8') as file:
        names = file.read().splitlines()
        return map(SteamApp, names)





class SteamApp:
    """Describe a single steam app. That is, more often than not, a game."""

    def __init__(self, name):
        self.id = None
        self.simplified_name = simplified_name(name)
        self.users_name = name
        self.known_cards = False
        self.has_cards = False

    def __str__(self):
        return self.users_name

    def __repr__(self):
        return "<SteamApp: " + self.users_name + ">"

    def get_id(self, applist):
        """Lookup your own name in the supplied list of names."""
        self.id = applist.name_lookup.get(self.simplified_name, None)  # default=None
        return self.id


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

    def get_id(self, lst):
        """Give names to all the apps in the list,"""
        for game in lst:
            game.get_id(self)

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
        self.name_lookup = {simplified_name(pair["name"]): pair["appid"] for pair in self.__data__}
        return self


@staticmethod
def fetch_game_data_static(app_id):
    req = urlrequest.Request("http://store.steampowered.com/api/appdetails/?appids=" + app_id)

    try:
        json_bytes = urlrequest.urlopen(req).read()
    except urlerror.HTTPError:
        logging.exception("Failed getting details for app " + app_id)
        return None

    json_text = json_bytes.decode("utf-8")
    try:
        game_info = json.loads(json_text)

        if not game_info[app_id]["success"]:
            return None

        data = game_info[app_id]["data"]
        return data

    except (json.decoder.JSONDecodeError, KeyError):
        logging.exception("Failed to parse details for app " + app_id)
        return None


def main():
    path = "Test/list.txt"
    applist = SteamAppList().fetch()
    input_games = fetch_game_list(path)
    applist.get_id(input_games)










if __name__ == "__main__":
    main()
