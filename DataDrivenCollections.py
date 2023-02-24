# Data Driven Collections - Patrick Hirsh (February 2023)
try:
    import os
    import ntpath
    import argparse
    import re
    import sys
    import threading
    import glob
    import datetime
    import configparser
    from plexapi.server import PlexServer
    from plexapi.myplex import MyPlexAccount
    from plexapi.video import Movie
    from plexapi.video import Show
    from plexapi.media import BaseResource
    from plexapi.media import Poster
    from plexapi.library import MovieSection
    from plexapi.library import ShowSection
    from plexapi.collection import Collection
    from plexapi.exceptions import NotFound
except ModuleNotFoundError:
    print('Requirements Error: Please install requirements using "pip install -r requirements.txt"')
    sys.exit(0)

# Plex default supported media containers - used to match media when scanning directories
VIDEO_MEDIA_CONTAINERS = ["asf", "avi", "mov", "mp4", "mpeg", "mpegts", "mkv", "wmv"]

# read args
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--library",
                    dest="library",
                    help="name of the Plex library to update",
                    default="")
parser.add_argument("-u", "--user", "--username",
                    dest="user",
                    help="Plex username, used for authentication when communicating with the Plex API",
                    default="")
parser.add_argument("-p", "--pass", "--password",
                    dest="password",
                    help="Plex password, used for authentication when communicating with the Plex API",
                    default="")
parser.add_argument("-t", "--token",
                    dest="token",
                    help="Plex API token 'X-Plex-Token', used as an alternate auth method to basic auth (user and password)",
                    default="")
parser.add_argument("-s", "--server-url," "--server_url",
                    dest="server_url",
                    help="Plex server url, needed for token auth",
                    default="")
parser.add_argument("-n", "--server-name," "--server_name",
                    dest="server_name",
                    help="Plex server name, needed for basic (username/password) auth",
                    default="")
parser.add_argument("-a", "--artwork-filename", "--artwork_filename",
                    dest="artwork",
                    help="filename to match when looking for poster artwork adjacent to Plex media",
                    default="")
parser.add_argument("-c", "--collection-priority", "--collection_priority",
                    dest="collection_priority",
                    help="put all collections at the top of the sort order",
                    action='store_true',
                    default=False)
parser.add_argument("-v", "--verbose",
                    help="verbose logging",
                    action='store_true',
                    default=False)
args = parser.parse_args()

# read config data - command line takes priority over .ini
has_config = False
if os.path.exists("DataDrivenCollections.ini"):
    config = configparser.ConfigParser()
    config.read("DataDrivenCollections.ini")
    has_config = True

# [Auth]
username = None
if has_config and "username" in config["Auth"]:
    username = config["Auth"]["username"]
if args.user != "":
    username = args.user

password = None
if has_config and "password" in config["Auth"]:
    password = config["Auth"]["password"]
if args.password != "":
    password = args.password

token = None
if has_config and "token" in config["Auth"]:
    token = config["Auth"]["token"]
if args.token != "":
    token = args.token

server_url = None
if has_config and "server_url" in config["Auth"]:
    server_url =  config["Auth"]["server_url"]
if args.server_url != "":
    server_url = args.server_url

server_name = None
if has_config and "server_name" in config["Auth"]:
    server_name =  config["Auth"]["server_name"]
if args.server_name != "":
    server_name = args.server_name

# [Config]
library = None
if has_config and "library" in config["Config"]:
    library = config["Config"]["library"]
if args.library != "":
    library = args.library

artwork_filename = "artwork"
if has_config and "artwork" in config["Config"]:
    artwork_filename = config["Config"]["artwork"]
if args.artwork != "":
    artwork_filename = args.artwork

collection_priority = "collection_priority"
if has_config and "collection_priority" in config["Config"]:
    if config["Config"]["collection_priority"] == "1":
        collection_priority = True
if args.collection_priority:
    collection_priority = True

if not library:
    print("Error: must provide a Plex library name")
    exit(1)

# connect to Plex
server = None
if token:
    if not server_url:
        print("Error: must provide a Plex server url 'server_url' to use token authentication")
        exit(1)
    server = PlexServer(server_url, token)

elif username and password:
    if not server_name:
        print("Error: must provide a Plex server name 'server_name' to use basic authentication (authorizing with username/password)")
        exit(1)
    account = MyPlexAccount(username, password)
    server = account.resource(server_name).connect()

else:
    print("Error: please provide a form of Plex server authentication (username/password, or Plex API token)")
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
        if os.path.isfile(os.path.join(entry.path, entry_element)) and entry_element.split('.')[0].lower() == artwork_filename.lower():
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

    # maps media disk paths to Plex movies
    plex_media_dir_to_movie = {}

    # first, split all media Plex has auto-merged. We'll re-merge directory-adjacent media later, but doing the split upfront greatly simplifies things
    print(f"========== splitting all Plex auto-merged media in '{section.title}' ==========")
    for movie in section.all():
        if len(movie.locations) > 1:
            print(f"splitting merged movie entry '{movie.title}' into {str(len(movie.locations))} independent movie entries:")
            for location in movie.locations:
                print(f"    * {location}")
            movie.split()

    # map media directories to their Plex movie entry(s) - at this stage, there may be multiple movie entries with their media files in the same directory
    for movie in section.all():
        if len(movie.locations) > 0:
            basedir, tail = ntpath.split(movie.locations[0])
            if not tail:
                basedir, tail = ntpath.split(basedir)
            if basedir not in plex_media_dir_to_movie:
                plex_media_dir_to_movie[basedir] = []
            plex_media_dir_to_movie[basedir].append(movie)
            if args.verbose:
                print(f"mapped '{movie.title}' to directory '{basedir}'")
    
    # merge movies with directory-adjacent media files into the same movie entry. Flatten map from one-to-many to one-to-one
    print(f"merging movie entries with identical media directories...")
    for basedir in plex_media_dir_to_movie:
        if len(plex_media_dir_to_movie[basedir]) > 1:
            base_movie = plex_media_dir_to_movie[basedir][0]
            ratingkeys_to_merge = []
            for i in range(1, len(plex_media_dir_to_movie[basedir])):
                ratingkeys_to_merge.append(str(plex_media_dir_to_movie[basedir][i].ratingKey))
            print(f"Found {str(len(plex_media_dir_to_movie[basedir]))} media files under base directory {basedir}. Merging into a single movie entry")
            base_movie.merge(ratingkeys_to_merge)
        
        # flatten mapping, merging all other media files into the first and creating a single movie entry
        base_movie = plex_media_dir_to_movie[basedir][0]
        plex_media_dir_to_movie[basedir] = base_movie


    # iterate our entry trees and build collections + assign metadata
    print("========== applying artwork and building collections ==========")
    for root in roots:
        for entry in root.sub_entries:

            # if this entry is mapped, apply artwork
            if entry.path in plex_media_dir_to_movie:
                if entry.artwork:
                    movie = plex_media_dir_to_movie[entry.path]
                    movie.uploadPoster(url=None, filepath=entry.artwork)
                    print(f"applied artwork '{entry.artwork}' to poster for movie '{movie.title}'")

            # evaluate the sub-entries of this entry, if any
            if len(entry.sub_entries) > 0:

                # recursively locate all sub-entries from the root 
                def find_mapped_entries_recursive(entry, is_root=True):
                    entries = []
                    for sub_entry in entry.sub_entries:
                        entries = entries + find_mapped_entries_recursive(sub_entry, False)
                    if entry.path in plex_media_dir_to_movie and not is_root:
                        entries.append(entry)
                    return entries
                mapped_entries = find_mapped_entries_recursive(entry)

                # if a top-level entry has any mapped sub-entries (at any depth), build a collection
                if len(mapped_entries) > 0:

                    # add all mapped items to collection
                    print(f"creating collection '{entry.name}'")
                    items_for_collection = [plex_media_dir_to_movie[i.path] for i in mapped_entries]
                    collection = None
                    try:
                        collection = section.collection(entry.name)
                        collection.addItems(items_for_collection)
                    except NotFound:
                        collection = section.createCollection(entry.name, items_for_collection)

                    # add artwork to all sub-entries in collection
                    for sub_entry in mapped_entries:
                        if sub_entry.artwork:
                            movie = plex_media_dir_to_movie[sub_entry.path]
                            movie.uploadPoster(url=None, filepath=sub_entry.artwork)
                            print(f"applied artwork '{sub_entry.artwork}' to poster for movie '{movie.title}'")

                    # add collection artwork if provided
                    if entry.artwork:
                        collection.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for collection '{collection.title}'")

    # dump tree state if logging is set to verbose
    if args.verbose:
        for root in roots:
            print(f"==========|{root.path}|==========")
            root.print([plex_media_dir_to_movie])


def update_plex_show_library(server, section, roots):
    """
    Updates all collections and posters for the specified show library section
    """

    # map media disk paths to Plex shows
    plex_media_dir_to_show = {}

    # map media disk paths to Plex show seasons
    plex_media_dir_to_season = {}

    # first, split all media Plex has auto-merged. We'll re-merge directory-adjacent media later, but doing the split upfront greatly simplifies things
    print(f"========== splitting all Plex auto-merged media in '{section.title}' ==========")
    for show in section.all():

        # any episode with multiple media locations implies a show with merged media
        def contains_merged_content(show):
            for season in show.seasons():
                for episode in season.episodes():
                    if len(episode.locations) > 1:
                        return True
            return False

        # split all merged media
        if contains_merged_content(show):
            print(f"splitting merged show entry '{show.title}' into independent show entries")
            show.split()

    # container for tracking all the different unique media directories for each season's episodes. We need this data to check against show/season directory ambiguity
    class Show:
        def __init__(self, show):
            self.show = show
            self.unique_season_media_locations = {}     # maps the show's season number to a list of the unique media directories referenced by the season's episodes

    # scan for media and attempt to correlate it to show / season base directories
    for show in section.all():
        s = Show(show)
        for season in show.seasons():

            # build a list of all unique directories that media in this season is located in (if this list's length == 1, we know all its media is in one directory)
            s.unique_season_media_locations[season.seasonNumber] = []
            for episode in season.episodes():
                for location in episode.locations:
                    basedir, tail = ntpath.split(location)
                    if not tail:
                        basedir, tail = ntpath.split(basedir)
                    if basedir not in s.unique_season_media_locations[season.seasonNumber]:
                        s.unique_season_media_locations[season.seasonNumber].append(basedir)
            
            # season has media files across multiple directories. Don't apply any artwork or metadata to seasons with base directory ambiguity.
            if len(s.unique_season_media_locations[season.seasonNumber]) > 1:
                print(f"Warning: Season {season.seasonNumber} of '{show.title}' is ambiguous (media files across multiple directories). Skipping.")
                print(f"    Located {str(len(s.unique_season_media_locations[season.seasonNumber]))} media directories:")
                for location in s.unique_season_media_locations[season.seasonNumber]:
                    print(f"        * {location}")
                continue
            
            # as far as I know, this is impossible... but if we really have no media files associated with a season, ignore it
            elif len(s.unique_season_media_locations[season.seasonNumber]) < 1:
                print(f"Warning: Season {season.seasonNumber} of '{show.title}' has no media associated with it. Skipping.")
                continue

            else:
                # all this season's media is in the same directory. Store in our one-to-many map so we can ensure no other seasons also have media in this directory
                season_media_directory = s.unique_season_media_locations[season.seasonNumber][0]
                if season_media_directory not in plex_media_dir_to_season:
                    plex_media_dir_to_season[season_media_directory] = []
                plex_media_dir_to_season[season_media_directory].append(season)
                if args.verbose:
                    print(f"mapped season {str(season.seasonNumber)} of '{show.title}' to directory '{season_media_directory}'")
            
        # finally, we only map a show to a directory if all the season base directories agree on a common top leave "show" directory
        show_roots = []
        for season in show.seasons():
            for location in s.unique_season_media_locations[season.seasonNumber]:
                basedir, tail = ntpath.split(location)
                if not tail:
                    basedir, tail = ntpath.split(basedir)
                if basedir not in show_roots:
                    show_roots.append(basedir)
        
        # if the seasons all agree, we now map the show's media directory to the show in one-to-many so we can identify other shows with the same media directories later
        if len(show_roots) == 1:
            if show_roots[0] not in plex_media_dir_to_show:
                plex_media_dir_to_show[show_roots[0]] = []
            plex_media_dir_to_show[show_roots[0]].append(s)
            if args.verbose:
                    print(f"mapped the root directory of show '{show.title}' to directory '{show_roots[0]}'")
        else:
            print(f"Warning: show directory extrapolated from media locations for '{show.title}' is ambiguous (show's media organization suggests multiple possible root show directories). Skipping.")
            print(f"    Found {str(len(show_roots))} possible root directories:")
            for root in show_roots:
                print(f"        * {root}")

    # merge or strip ambiguous shows from mapping, flattening map to one-to-one
    for media_dir in plex_media_dir_to_show:
        if len(plex_media_dir_to_show[media_dir]) > 1:
            ambiguous_shows = plex_media_dir_to_show[media_dir]

            # returns True as long as all shows in "shows" have identical media locations for any seasons they have media for
            def should_merge_shows(shows):
                base_show = shows[0]
                for season in base_show.show.seasons():
                    for i in range(1, len(shows)):
                        if len(base_show.unique_season_media_locations) > 0 and len(shows[i].unique_season_media_locations) > 0:
                            if base_show.unique_season_media_locations[season.seasonNumber] != shows[i].unique_season_media_locations[season.seasonNumber]:
                                return False

            # since all these shows map to the same directory, we either merge them (all media directories match) or they're all marked ambiguous and rejected
            if should_merge_shows(ambiguous_shows):

                # before actually merging, we need to make sure to reconcile this change in the season map, so seasons aren't falsely marked as ambiguous
                for season in ambiguous_shows[0].seasons():

                    # seasons that don't meet this criteria are never even mapped, so we only care about seasons with a single media location
                    if len(ambiguous_shows[0].unique_season_media_locations) == 1:
                        season_media_location = ambiguous_shows[0].unique_season_media_locations[0]
                        mapped_seasons = plex_media_dir_to_season[season_media_location]
                        
                        # flatten if all the entries in the seasons map are from this now merged show
                        if len(plex_media_dir_to_season[season_media_location]) == len(ambiguous_shows):
                            base_season = plex_media_dir_to_season[season_media_location][0]
                            plex_media_dir_to_season[season_media_location] = base_season
                        
                        else:
                            # if all the mapped seasons aren't accounted for by this merged show, the season mapping is guaranteed to be ambiguous. remove the mapping
                            del plex_media_dir_to_season[season_media_location]

                # merge these shows
                ratingkeys_to_merge = []
                for i in range(1, len(ambiguous_shows)):
                    s = ambiguous_shows[i]
                    ratingkeys_to_merge.append(s.show.seasons()[0].parentRatingKey)     # not sure why the PlexAPI has parentRatingKeys on seasons, but no exposed ratingKey on the show itself?? 
                ambiguous_shows[0].show.merge()
            
            else:
                # if we aren't merging these shows, they're ambiguous - remove from mapping
                print(f"Warning: '{plex_media_dir_to_show[media_dir][0].show.title}' is ambiguous (More than one show was mapped to this directory). Skipping")
                print(f"    Found {str(len(plex_media_dir_to_show[media_dir]))} other show(s) mapped to '{media_dir}':")
                for s in plex_media_dir_to_show[media_dir]:
                    print(f"        * '{s.show.title}'")
                del plex_media_dir_to_show[media_dir]
                continue
        
        # flatten mapping - if we got here, we either merged down to one show, or there was only one show in this mapping pair to begin with
        base_show = plex_media_dir_to_show[media_dir][0]
        plex_media_dir_to_show[media_dir] = base_show.show

    # strip ambiguous seasons from mapping, flattening map to one-to-one
    for media_dir in plex_media_dir_to_season:
        if len(plex_media_dir_to_season[media_dir]) > 1:
            print(f"Warning: season {str(plex_media_dir_to_season[media_dir][0].seasonNumber)} of '{plex_media_dir_to_season[media_dir][0].parentTitle}' mapped to '{media_dir}' is ambiguous (other seasons mapped to the same directory). Skipping")
            print(f"    Found {str(len(plex_media_dir_to_season[media_dir]))} other season(s) with media mapped to '{media_dir}':")
            for season in plex_media_dir_to_season[media_dir]:
                print(f"        * season {str(season.seasonNumber)} of '{season.parentTitle}'")
            del plex_media_dir_to_season[season]
        else:
            base_season = plex_media_dir_to_season[media_dir][0]
            plex_media_dir_to_season[media_dir] = base_season

    # iterate our entry trees and build collections + assign metadata
    print("========== applying artwork and building collections ==========")
    for root in roots:
        for entry in root.sub_entries:

            # if we have sub-entries, we need to check if any are mapped as shows. Mapped show sub-entries mean this should be treated as a collection
            if len(entry.sub_entries) > 0:

                # recursively locate all show and season sub-entries from the root 
                def find_mapped_entries_recursive(entry, plex_map, is_root=True):
                    entries = []
                    for sub_entry in entry.sub_entries:
                        entries = entries + find_mapped_entries_recursive(sub_entry, plex_map, False)
                    if not is_root:
                        if entry.path in plex_map:
                            entries.append(entry)
                    return entries
                show_entries = find_mapped_entries_recursive(entry, plex_media_dir_to_show)
                season_entries = find_mapped_entries_recursive(entry, plex_media_dir_to_season)
                
                # map and store show entries as an item list for adding to the collection
                items_for_collection = [plex_media_dir_to_show[i.path] for i in show_entries]

                # treat this as a collection
                if len(items_for_collection) > 0:

                    # add all mapped items to collection
                    print(f"creating collection '{entry.name}'")
                    collection = None
                    try:
                        collection = section.collection(entry.name)
                        collection.addItems(items_for_collection)
                    except NotFound:
                        collection = section.createCollection(entry.name, items_for_collection)

                    # add artwork to all mapped shows in collection
                    for sub_entry in show_entries:
                        if sub_entry.artwork:
                            show = plex_media_dir_to_show[sub_entry.path]
                            show.uploadPoster(url=None, filepath=sub_entry.artwork)
                            print(f"applied artwork '{sub_entry.artwork}' to poster for show '{show.title}'")
                    
                    # add artwork to all mapped seasons of all mapped shows in collection
                    for sub_entry in season_entries:
                        if sub_entry.artwork:
                            season = plex_media_dir_to_season[sub_entry.path]
                            season.uploadPoster(url=None, filepath=sub_entry.artwork)
                            print(f"applied artwork '{sub_entry.artwork}' to poster for season {season.seasonNumber} of show '{season.parentTitle}'")

                    # add collection artwork if provided
                    if entry.artwork:
                        collection.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for collection '{collection.title}'")
                
                # if none of the sub-entries are mapped shows, but this directory is mapped, treat this like a show entry
                elif entry.path in plex_media_dir_to_show:

                    # show artwork
                    if entry.artwork:
                        show = plex_media_dir_to_show[entry.path]
                        show.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for show '{show.title}'")
                
                    # seasons artwork
                    for sub_entry in entry.sub_entries:
                        if sub_entry.artwork:
                            if sub_entry.path in plex_media_dir_to_season:
                                season = plex_media_dir_to_season[sub_entry.path]
                                season.uploadPoster(url=None, filepath=sub_entry.artwork)
                                print(f"applied artwork '{sub_entry.artwork}' to poster for show '{season.title}'")

            # process show entry
            else:

                # show artwork
                if entry.artwork:
                    if entry.path in plex_media_dir_to_show:
                        show = plex_media_dir_to_show[entry.path]
                        show.uploadPoster(url=None, filepath=entry.artwork)
                        print(f"applied artwork '{entry.artwork}' to poster for show '{show.title}'")
                
                # seasons artwork
                for sub_entry in entry.sub_entries:
                    if sub_entry.artwork:
                        if sub_entry.path in plex_media_dir_to_season:
                            season = plex_media_dir_to_season[sub_entry.path]
                            season.uploadPoster(url=None, filepath=sub_entry.artwork)
                            print(f"applied artwork '{sub_entry.artwork}' to poster for show '{season.title}'")

    # dump tree state if logging is set to verbose
    if args.verbose:
        for root in roots:
            print(f"==========|{root.path}|==========")
            root.print([plex_media_dir_to_show, plex_media_dir_to_season])

# connect to plex and gather lib info
section = server.library.section(library)

# construct an entry tree for each physical disk location that makes up the section
roots = []
for location in section.locations:
    print(f"building entry tree for section '{library}' location '{location}'...")
    roots.append(build_entry_tree(location))

# update plex with metadata based on the entry trees constructed above
if section.type == "movie":
    update_plex_movie_library(server, section, roots)
elif section.type == "show":
    update_plex_show_library(server, section, roots)
else:
    print(f"Error: attempted to update an unsupported section type '{section.type}'")

# update collection sort order, if specified
if args.collection_priority:
    print("updating sort titles to prioritize collections")
    for collection in section.collections():
        collection.editSortTitle(f"_{collection.title}")
        
print("Done.")




        



