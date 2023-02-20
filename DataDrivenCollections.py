# Data Driven Collections - A Plex tools

try:
    import os
    import ntpath
    import argparse
    import re
    import sys
    import threading
    import glob
    import datetime
    from plexapi.server import PlexServer
    from plexapi.video import Movie
    from plexapi.video import Show
    from plexapi.media import BaseResource
    from plexapi.media import Poster
    from plexapi.library import MovieSection
    from plexapi.library import ShowSection
    from plexapi.collection import Collection
    from plexapi.exceptions import NotFound
    # from plex_tools import get_map
    # from plex_tools import add_to_collection
    # from plex_tools import delete_collection
    # from plex_tools import get_actor_rkey
    # from plex_tools import get_collection
    # from plex_tools import get_item
    # from imdb_tools import tmdb_get_metadata
    # from imdb_tools import imdb_get_ids
    # from config_tools import Config
    # from config_tools import Plex
    # from config_tools import Radarr
    # from config_tools import TMDB
    # from config_tools import Tautulli
    # from config_tools import TraktClient
    # from config_tools import ImageServer
    # from config_tools import modify_config
    # from config_tools import check_for_attribute
    # from radarr_tools import add_to_radarr
    # from urllib.parse import urlparse
except ModuleNotFoundError:
    print('Requirements Error: Please install requirements using "pip install -r requirements.txt"')
    sys.exit(0)

# CREDENTIALS
PLEX_BASE_URL = "http://192.168.1.176:32400"
PLEX_API_TOKEN = "xxxxxxxxxxxxxxxxxxxx"

# CONFIG
ARTWORK_FILENAME = "artwork"
VIDEO_MEDIA_CONTAINERS = ["asf", "avi", "mov", "mp4", "mpeg", "mpegts", "mkv", "wmv"]

parser = argparse.ArgumentParser()
parser.add_argument("-l", "--library",
                    dest="library",
                    help="name of the Plex library to update",
                    default="")
parser.add_argument("-v", "--verbose",
                    help="verbose logging",
                    action='store_true',
                    default=False)

args = parser.parse_args()
if args.library == "":
    print("Error: please provide a valid Plex library name")
    exit(1)


class Entry:
    
    def __init__(self, name, path, depth, artwork=None):
        self.name = name
        self.path = path
        self.depth = depth
        self.artwork = artwork
        self.media = []
        self.sub_entries = []

    def print(self, plex_maps=[], depth=0):
        """
        Prints this entry's metadata + all sub-entry's metadata recursively
        """
        print(" ") # entry spacing 

        # offset left indentation based on entry tree depth
        depth_offset = ""
        for i in range(0, depth):
            depth_offset = f"    {depth_offset}"
        
        # print mapped status
        guid = None
        for plex_map in plex_maps:
            if self.path in plex_map:
                guid = plex_map[self.path].guid
        if guid:
            print(f"{depth_offset}[MAPPED : {guid}]")
        else:
            print(f"{depth_offset}[NOT MAPPED]")

        # print the base entry line
        entry_line = self.name
        if self.artwork:
            entry_line = f"{entry_line} (A)"
        print(f"{depth_offset}{entry_line}")

        # print media
        for media in self.media:
            print(f"{depth_offset}* {media}")

        # recurse
        for sub_entry in self.sub_entries:
            sub_entry.print(plex_maps, depth + 1)


def build_entry_tree(path, depth=0):
    """
    Recursively construct an entry tree from 'path' with all relevant metadata and sub-entries
    """
    head, tail = ntpath.split(path)
    entry = Entry(tail or ntpath.basename(head), path, depth)
    for entry_element in os.listdir(entry.path):

        # look for entry artwork
        if os.path.isfile(os.path.join(entry.path, entry_element)) and entry_element.split('.')[0].lower() == ARTWORK_FILENAME.lower():
            entry.artwork = os.path.join(entry.path, entry_element)
        
        # look for entry media
        elif os.path.isfile(os.path.join(entry.path, entry_element)) and entry_element.split('.')[1].lower() in VIDEO_MEDIA_CONTAINERS:
            entry.media.append(os.path.join(entry.path, entry_element))

        # if we have a subdirectory, capture it as a sub-entry
        if not os.path.isfile(os.path.join(entry.path, entry_element)):
            entry.sub_entries.append(build_entry_tree(os.path.join(entry.path, entry_element), depth + 1))

    return entry


def update_plex_movie_library(server, section, roots):
    """
    Updates all collections and posters for the specified movie library section
    """
    
    # split all merged media before building map
    print(f"searching for merged movies that should be split for section '{section.title}'...")
    for movie in section.all():
        if len(movie.locations) > 1:
            if args.verbose:
                print(f"splitting merged movie entry {movie.title} into {str(len(movie.locations))} independent movie entries:")
                for location in movie.locations:
                    print(f"    * {location}")
            movie.split()

    # map media directories to their Plex movie entry(s) - multiple entries with the same directory will be merged
    plex_basedir_to_movie = {}
    for movie in section.all():
        if len(movie.locations) != 1:
            # if this occurs, we have merged media even after the split step above, or we have an entry with no associated file locations! Skip
            print(f"Warning: movie '{movie.title}' still contains an unexpected number of media files after split step: {str(len(movie.locations))}")
            continue
        basedir, tail = ntpath.split(movie.locations[0])
        if not tail:
            basedir, tail = ntpath.split(basedir)
        if basedir not in plex_basedir_to_movie:
            plex_basedir_to_movie[basedir] = []
        plex_basedir_to_movie[basedir].append(movie)
    
    # merge any movie entries that share the same basedir. Flatten map from one-to-many to one-to-one
    print(f"merging movie entries with identical media directories...")
    for basedir in plex_basedir_to_movie:
        if len(plex_basedir_to_movie[basedir]) > 1:
            base_movie = plex_basedir_to_movie[basedir][0]
            ratingkeys_to_merge = []
            for i in range(1, len(plex_basedir_to_movie[basedir])):
                ratingkeys_to_merge.append(str(plex_basedir_to_movie[basedir][i].ratingKey))
            if args.verbose:
                print(f"Found {str(len(plex_basedir_to_movie[basedir]))} media files under base directory {basedir}. Merging into a single movie entry")
            base_movie.merge(ratingkeys_to_merge)
        
        # flatten mapping, taking first movie entry (the sole movie, or the base movie used when merging)
        base_movie = plex_basedir_to_movie[basedir][0]
        plex_basedir_to_movie[basedir] = base_movie

    # iterate our entry trees and build collections + assign metadata
    for root in roots:
        for entry in root.sub_entries:

            # process movie collection entry
            if len(entry.sub_entries) > 0:

                # recursively locate all sub-entries from the root 
                def find_mapped_entries_recursive(entry, is_root=True):
                    entries = []
                    for sub_entry in entry.sub_entries:
                        entries = entries + find_mapped_entries_recursive(sub_entry, False)
                    if not is_root:
                        if entry.path in plex_basedir_to_movie:
                            entries.append(entry)
                    return entries
                entries_for_collection = find_mapped_entries_recursive(entry)

                # add all mapped items to collection
                items_for_collection = [plex_basedir_to_movie[i.path] for i in entries_for_collection]
                collection = None
                try:
                    collection = section.collection(entry.name)
                    collection.addItems(items_for_collection)
                except NotFound:
                    collection = section.createCollection(entry.name, items_for_collection)

                # add artwork to all sub-entries in collection
                for sub_entry in entries_for_collection:
                    if sub_entry.artwork:
                        movie = plex_basedir_to_movie[sub_entry.path]
                        movie.uploadPoster(url=None, filepath=sub_entry.artwork)
                        print(f"applied artwork '{sub_entry.artwork}' to poster for movie '{movie.title}'")

                # add collection artwork if provided
                if entry.artwork:
                    collection.uploadPoster(url=None, filepath=entry.artwork)
                    print(f"applied artwork '{entry.artwork}' to poster for collection '{collection.title}'")

            # process movie entry
            else:
                if entry.artwork:
                    if entry.path in plex_basedir_to_movie:
                        movie = plex_basedir_to_movie[entry.path]
                        movie.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for movie '{movie.title}'")

    # dump tree state if logging is set to verbose
    if args.verbose:
        for root in roots:
            print(f"==========|{root.path}|==========")
            root.print([plex_basedir_to_movie])


def update_plex_show_library(server, section, roots):
    """
    Updates all collections and posters for the specified show library section
    """

    # map disk paths to Plex shows
    plex_basedir_to_show = {}

    # map disk paths to Plex show seasons
    plex_basedir_to_season = {}

    # scan for media and attempt to correlate it to show / season base directories
    for show in section.all():
        show_basedir = None
        for season in show.seasons():
            season_base_dirs = []
            for episode in season.episodes():
                for location in episode.locations:
                    basedir, tail = ntpath.split(location)
                    if not tail:
                        basedir, tail = ntpath.split(basedir)
                    if basedir not in season_base_dirs:
                        season_base_dirs.append(basedir)
            
            # multiple seasons point to the same directory. Don't apply any artwork or metadata to seasons with base directory ambiguity.
            if len(season_base_dirs) != 1:
                print(f"Warning: Season {season.seasonNumber} of '{show.title}' is ambiguous (media files across multiple directories). Skipping.")
                if args.verbose:
                    print(f"    Located {str(len(season_base_dirs))} media directories")
                    for dir in season_base_dirs:
                        print(f"    * {dir}")
                continue

            # a season has media in multiple directories. Don't apply any artwork or metadata to seasons with base directory ambiguity.
            if season_base_dirs[0] in plex_basedir_to_season:
                print(f"Warning: Season {season.seasonNumber} of '{show.title}' is ambiguous (multiple seasons have media files in this directory). Skipping")
                if args.verbose:
                    print(f"    Season {str(plex_basedir_to_season[season_base_dirs[0]].seasonNumber)} of '{show.title}' also has media files in this directory! Skipping")
                del plex_basedir_to_season[season_base_dirs[0]]
                continue
            
            # at least one season passed ambiguity checks, so we can make an assumption about the show's base directory as well
            plex_basedir_to_season[season_base_dirs[0]] = season
            show_basedir, tail = ntpath.split(season_base_dirs[0])
            if not tail:
                show_basedir, tail = ntpath.split(show_basedir)
        
        if show_basedir:
            if show_basedir in plex_basedir_to_show:
                print(f"Warning: '{show.title}' and '{plex_basedir_to_show[show_basedir].title}' are ambiguous (both shows have media files in the same directory). Skipping")
                del plex_basedir_to_show[show_basedir]
                continue
            plex_basedir_to_show[show_basedir] = show


    # iterate our entry trees and build collections + assign metadata
    for root in roots:
        for entry in root.sub_entries:

            # process show collection entry
            if entry.path not in plex_basedir_to_show:

                # recursively locate all show and season sub-entries from the root 
                def find_mapped_entries_recursive(entry, plex_map, is_root=True):
                    entries = []
                    for sub_entry in entry.sub_entries:
                        entries = entries + find_mapped_entries_recursive(sub_entry, plex_map, False)
                    if not is_root:
                        if entry.path in plex_map:
                            entries.append(entry)
                    return entries
                show_entries = find_mapped_entries_recursive(entry, plex_basedir_to_show)
                season_entries = find_mapped_entries_recursive(entry, plex_basedir_to_season)
                
                # map and store show entries as an item list for adding to the collection
                items_for_collection = [plex_basedir_to_show[i.path] for i in show_entries]

                # add all mapped items to collection
                collection = None
                try:
                    collection = section.collection(entry.name)
                    collection.addItems(items_for_collection)
                except NotFound:
                    collection = section.createCollection(entry.name, items_for_collection)

                # add artwork to all mapped shows in collection
                for sub_entry in show_entries:
                    if sub_entry.artwork:
                        show = plex_basedir_to_show[sub_entry.path]
                        show.uploadPoster(url=None, filepath=sub_entry.artwork)
                        print(f"applied artwork '{sub_entry.artwork}' to poster for show '{show.title}'")
                
                # add artwork to all mapped seasons of all mapped shows in collection
                for sub_entry in season_entries:
                    if sub_entry.artwork:
                        season = plex_basedir_to_season[sub_entry.path]
                        season.uploadPoster(url=None, filepath=sub_entry.artwork)
                        print(f"applied artwork '{sub_entry.artwork}' to poster for season {season.seasonNumber} of show '{season.parentTitle}'")

                # add collection artwork if provided
                if entry.artwork:
                    collection.uploadPoster(url=None, filepath=entry.artwork)
                    print(f"applied artwork '{entry.artwork}' to poster for collection '{collection.title}'")

            # process show entry
            else:

                # show artwork
                if entry.artwork:
                    if entry.path in plex_basedir_to_show:
                        show = plex_basedir_to_show[entry.path]
                        show.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for show '{show.title}'")
                
                # seasons artwork
                for sub_entry in entry.sub_entries:
                    if sub_entry.artwork:
                        if sub_entry.path in plex_basedir_to_season:
                            season = plex_basedir_to_season[sub_entry.path]
                            season.uploadPoster(url=None, filepath=sub_entry.artwork)
                            print(f"applied artwork '{sub_entry.artwork}' to poster for show '{season.title}'")

    # dump tree state if logging is set to verbose
    if args.verbose:
        for root in roots:
            print(f"==========|{root.path}|==========")
            root.print([plex_basedir_to_show, plex_basedir_to_season])
    

def update_plex_video_library(server, section, roots):
    pass


# connect to plex and gather lib info
server = PlexServer(PLEX_BASE_URL, PLEX_API_TOKEN)
section = server.library.section(args.library)

# construct an entry tree for each physical disk location that makes up the section
roots = []
for location in section.locations:
    print(f"building entry tree for section '{args.library}' location '{location}'...")
    roots.append(build_entry_tree(location))

# update plex with metadata based on the entry trees constructed above
if section.type == "movie":
    update_plex_movie_library(server, section, roots)
elif section.type == "show":
    update_plex_show_library(server, section, roots)
else:
    print(f"Error: attempted to update an unsupported section type '{section.type}'")




        



