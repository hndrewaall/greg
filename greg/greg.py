# Copyright (C) 2012  Manolo Martínez <manolo@austrohungaro.com>
#
# This file is part or Greg.
#
# Greg is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Greg is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Greg.  If not, see <http://www.gnu.org/licenses/>.

import os, sys, configparser, pickle, time, re
from urllib.request import urlretrieve
from urllib.parse import urlparse 
from urllib.error import URLError

import feedparser

try: # Stagger is an optional dependency
    import stagger
    from stagger.id3 import *
    staggerexists = True
except ImportError:
    staggerexists = False

CONFIG_FILENAME_GLOBAL = '/etc/greg.conf'
CONFIG_FILENAME_USER = os.path.expanduser('~/.config/greg/greg.conf')

# Registering a custom date handler for feedparser

_feedburner_date_pattern = re.compile(
    r'\w+, (\w+) (\d{,2}), (\d{4}) - (\d{,2}):(\d{2})')
 
def FeedburnerDateHandler(aDateString):
    months = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6, "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
    # Parse a date sucn as "Sunday, November 25, 2012 - 12:00"
    try: # feedparser is supposed to catch the exception on its own, but it doesn't
        month, day, year, hour, minute = _feedburner_date_pattern.search(aDateString).groups()
        return (int(year), int(months[month]), int(day), int(hour), int(minute), 0, 0, 0, 0)
    except AttributeError:
        return None

feedparser.registerDateHandler(FeedburnerDateHandler)

# The following are some auxiliary functions

def ensure_dir(dirname):
    try:
        os.makedirs(dirname)
    except OSError:
        if not os.path.isdir(dirname):
            raise

def parse_for_download(args):  # Turns an argument such as 4, 6-8, 10 into a list such as [4,6,7,8,10]
    single_arg="" # in the first bit we put all arguments together and take out any extra spaces
    list_of_feeds=[]
    for arg in args.number:
        single_arg = ''.join([single_arg , " " , arg])
    single_arg = single_arg.translate({32:None}) # eliminates spaces
    for group in single_arg.split(sep=","):
        if not("-" in group):
            list_of_feeds.append(group)
        else:
            extremes = group.split(sep="-")
            list_of_feeds = list_of_feeds + [str(x) for x in range (eval(extremes[0]),eval(extremes[1])+1)]
    return list_of_feeds

def retrieve_data_directory(): # Retrieves the data directory (looks first into CONFIG_FILENAME_GLOBAL
    # then into CONFIG_FILENAME_USER. The latest takes preeminence)
    config = configparser.ConfigParser()
    config.read([CONFIG_FILENAME_GLOBAL, CONFIG_FILENAME_USER])
    section = config.default_section
    data_path = config.get(section, 'Data directory', fallback='~/.local/share/greg')
    return os.path.expanduser(data_path)   
        
def retrieve_download_path(feed): # Retrieves the data directory (looks first into CONFIG_FILENAME_GLOBAL
    # then into the [DEFAULT], then the [feed], section of CONFIG_FILENAME_USER. The latest takes preeminence)
    config = configparser.ConfigParser()
    config.read([CONFIG_FILENAME_GLOBAL, CONFIG_FILENAME_USER])
    section = feed if config.has_section(feed) else config.default_section
    download_path = config.get(section, 'Download directory', fallback='~/Podcasts')
    subdirectory = config.get(section, 'Create subdirectories', fallback='no')
    return [os.path.expanduser(download_path), subdirectory]   

def will_tag(feed): # Checks whether the feed should be tagged (looks first into CONFIG_FILENAME_GLOBAL
    # then into the [DEFAULT], then the [feed], section of CONFIG_FILENAME_USER. The latest takes preeminence)
    config = configparser.ConfigParser()
    config.read([CONFIG_FILENAME_GLOBAL, CONFIG_FILENAME_USER])
    section = feed if config.has_section(feed) else config.default_section
    wanttags = config.get(section, 'Tag', fallback='no')
    if wanttags == 'yes':
        if staggerexists:
            willtag = True
        else:
            willtag = False
            sys.stderr.write("You want me to tag this feed, but you have not installed the Stagger module. I cannot honour your request")
    else:
        willtag = False
    return willtag

def tag(entry, podcast, podpath): # Tags the file at podpath with the information in podcast and entry
    stagger.util.set_frames(podpath, {"artist":podcast.feed.title})
    stagger.util.set_frames(podpath, {"title":entry.title})
    stagger.util.set_frames(podpath, {"genre":"Podcast"})

# The following are the functions that correspond to the different commands

def add(args): # Adds a new feed
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    config = configparser.ConfigParser()
    config.read(DATA_FILENAME)
    if args.name in config.sections():
        print ("You already have a feed with that name.")
        return 1
    entry = {}
    for key,value in vars(args).items():
        if value != None and key != "func" and key != "name":
            entry[key] = value
    config[args.name] = entry
    with open(DATA_FILENAME, 'w') as configfile:
        config.write(configfile)

def edit(args): # Edits the information associated with a certain feed
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    if not(args.name in feeds):
        print ("You don't have a feed with that name.")
        return 1
    for key,value in vars(args).items():
        if value != None and key != "func" and key != "name":
            feeds[args.name][key] = str(value)
    with open(DATA_FILENAME, 'w') as configfile:
        feeds.write(configfile)

def remove(args): # Removes a certain feed
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    if not(args.name in feeds):
        print ("You don't have a feed with that name.")
        return 1
    inputtext = "Are you sure you want to remove the {0} feed? (y/N) ".format(args.name)
    reply = input(inputtext)
    if reply != "y" and reply != "Y": 
        return 0
    else:
        feeds.remove_section(args.name)
        with open(DATA_FILENAME, 'w') as configfile:
            feeds.write(configfile)

def info(args): # Provides information of a number of feeds
    if "all" in args.names:
        feeds = list_feeds()
    else:
        feeds = args.names
    for feed in feeds:
        pretty_print(feed)

def pretty_print(feed): # Prints the dictionary entry of a feed in a nice way.
    print ()
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    print (feed)
    print ("-"*len(feed))
    print (''.join(["    url: " , feeds[feed]["url"]]))
    if "downloadfrom" in feeds[feed]:
        if feeds[feed]["downloadfrom"] != None:
            feedtime = tuple(eval(feeds[feed]["downloadfrom"]))
            print (''.join(["    Next sync will download from:", time.strftime("%d %b %Y %H:%M:%S", feedtime),"."]))

def list_for_user(args):
    for feed in list_feeds():
        print (feed, end=" ")
    print ()

def list_feeds(): # Outputs a list of all feed names
    feedslist = []
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    return feeds.sections()


def sync(args):
    if "all" in args.names:
        targetfeeds = list_feeds()
    else:
        targetfeeds = args.names
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    for feed in targetfeeds:
        willtag = will_tag(feed)
        try:
            wentwrong = "urlopen" in str(feedparser.parse(feeds[feed]["url"])["bozo_exception"])
        except KeyError:
            wentwrong = False
        if not wentwrong:
            podcast = feedparser.parse(feeds[feed]["url"])
            print ("Checking",podcast.feed.title, end = "...\n")
            # 
            # The directory to save files is named after the podcast.
            # 
            DOWNLOAD_PATH = retrieve_download_path(feed)[0]
            subdirectory = retrieve_download_path(feed)[1]
            if subdirectory == "title":
                directory = os.path.join(DOWNLOAD_PATH, podcast.feed.title)
            elif subdirectory == "name":
                directory = os.path.join(DOWNLOAD_PATH, feed)
            else:
                directory = DOWNLOAD_PATH
            ensure_dir(directory)
            # 
            # Download entries later than downloadfrom in the feed
            #
            if "downloadfrom" in feeds[feed]:
                if feeds[feed]["downloadfrom"] != None:
                    latest = eval(feeds[feed]["downloadfrom"])
                else:
                    latest = [1,1,1,0,0] # If there is no latest downloadfrom date, download all
            else:
                latest = [1,1,1,0,0] # If there is no latest downloadfrom date, download all
            entrytimes = [latest] # Here we will put the times of each entry, to choose the max for "latest"
            for entry in podcast.entries:
                try: 
                    entrydate = list(entry.updated_parsed)
                except TypeError:
                    try:
                        entrydate = list(entry.published_parsed)
                    except TypeError:
                        print("I'm sorry. I cannot parse the time information of this feed. If you possibly can, please report an issue at github.com/manolomartinez/greg.")
                        break
                if entrydate > latest:
                    entrytimes.append(entrydate)
                    feeds[feed]["downloadfrom"]=str(max(entrytimes))
                    print ("Downloading", entry.title)
                    for enclosure in entry.enclosures: # We will download all audio enclosures
                        if "audio" in enclosure["type"]: # if it's an audio file
                            podname = urlparse(enclosure["href"]).path.split("/")[-1] # preserve the original name
                            podpath = os.path.join(directory, podname)
                            try:
                                urlretrieve(enclosure["href"], podpath)
                                if willtag:
                                    tag(entry, podcast, podpath)
                            except URLError:
                                sys.exit ("... something went wrong. Are you sure you are connected to the internet?")
                with open(DATA_FILENAME, 'w') as configfile: # We write to configfile this often to ensure that downloaded entries count as downloaded.
                    feeds.write(configfile)
            # 
            # New downloadfrom: the date of the latest feed update.
            # 
            print ("Done")
        else:
            msg = ''.join(["I cannot sync " , feed , " just now. Are you connected to the internet?"])
            print(msg)

def check(args):
    DATA_FILENAME =  os.path.join(retrieve_data_directory(), "data")
    feeds = configparser.ConfigParser()
    feeds.read(DATA_FILENAME)
    try:
        wentwrong = "urlopen" in str(feedparser.parse(feeds[args.name]["url"])["bozo_exception"])
    except KeyError:
        wentwrong = False
    if not(wentwrong):
        podcast = feedparser.parse(feeds[args.name]["url"])
    else:
        sys.exit("I cannot check that podcast now. You are probably not connected to the internet.")
    for entry in enumerate(podcast.entries):
        listentry=list(entry)
        print (listentry[0], end =": ")
        print (listentry[1]["title"], end = " (")
        print (listentry[1]["updated"], end =")")
        print ()
    DATA_DIRECTORY = retrieve_data_directory()
    dumpfilename = os.path.join(DATA_DIRECTORY, 'feeddump')
    with open(dumpfilename, mode='wb') as dumpfile:
        pickle.dump(podcast, dumpfile)

def download(args):
    issues = parse_for_download(args)
    DATA_DIRECTORY = retrieve_data_directory()
    dumpfilename = os.path.join(DATA_DIRECTORY, 'feeddump')
    if not(os.path.isfile(dumpfilename)):
        print("You need to run ""greg check <feed>"" before using ""greg download"".")
        return 1
    with open(dumpfilename, mode='rb') as dumpfile:
        podcast = pickle.load(dumpfile)
        try:
            directory = retrieve_download_path("DEFAULT")[0]
        except Exception:
            print("... something went wrong. Are you sure your last check went well?")
            return 1
        ensure_dir(directory)
        for number in issues:
            entry = podcast.entries[eval(number)]
            print ("Downloading", entry.title)
            for enclosure in entry.enclosures:
                if "audio" in enclosure["type"]: # if it's an audio file
                    podname = urlparse(enclosure["href"]).path.split("/")[-1] # preserve the original name
                    try:
                        urlretrieve(enclosure["href"], os.path.join(directory, podname))
                        print("Done")
                    except URLError:
                        print ("... something went wrong. Are you sure you are connected to the internet?")
                        return 1


