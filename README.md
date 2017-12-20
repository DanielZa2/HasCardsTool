# Bulk Card Checker
This applicatiopn take a list of games and tells you if they have Steam cards associated with them.
This is useful if you have a large bunch of keys laying around that you want to trade away or farm for cards.

# Under the hood
This application uses the steam web api to get the list of all the application currently on Steam and tries to match these with the games on the input list. Sometimes, when the name of the game is significantly different from the name on the list, the application might fail to recognize it. For example if your list contains "assassins creed 1" instead of "Assassin's Creed™: Director's Cut Edition". In these cases the application can use Google to recognize the name. Regardless when the appid of the game is found the application uses another Steam web api to check if it has any trading cards.


# Input
The application takes a file with a list of games as input. This list can be in two formats. The first is simple, just the game names each on a seperate line.
Foe example:

    Ori and the Blind Forest
    Antichamber
    Hand of Fate
	Evoland 2
    Mark of the Ninja
    Bastion

The program will produce output of the following format:

    Ori and the Blind Forest,261570,TRUE
    Antichamber,219890,TRUE
    Hand of Fate,266510,
    Evoland 2,359310,FALSE
    Mark of the Ninja,214560,
    Bastion,107100,TRUE


The number after the name is the appid of the game and the last column indicates whatever the game has cards (TRUE) does not (FALSE) or the program haven't been able to determine either (empty).

Alternatively you can input a list with the same format as the output. This way the program won't have to look again for all the information it already found, like appids, and can finish the task faster. This is also useful in case something gone wrong during the original lookup, like a power-cut. The process can continue straight from where it was stopped.

Most importantly you can also mix and match both formats, in case you acquired more keys and you don't want to scan all the list from the begining. For example:

<pre>
    Ori and the Blind Forest,261570,TRUE
    Antichamber,219890,TRUE
    <b>Braid</b>
    Hand of Fate,266510,
    <b>Rollers of the Realm</b>
    <b>Recettear: An Item Shop's Tale</b>
    Evoland 2,359310,FALSE
    Mark of the Ninja,214560,
    Bastion,107100,TRUE
    <b>Mages of Mystralia</b>
    <b>Freedom Fall</b>
    <b>SteamWorld Dig</b>
</pre>

# Using Google
This application can use the google web api in order to search for the games in your list that it could not locate on its own. In order to do that, you'll need to recive an api key using your Google account and input it into the config.txt file. Google allows up to a 100 searches through their web api, per day, for free. You can generate a key [here](https://developers.google.com/custom-search/json-api/v1/overview).
