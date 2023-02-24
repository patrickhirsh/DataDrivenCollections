# Data Driven Collections for Plex
Data Driven Collections is a tool that builds and applies Plex collections, poster artwork, and other metadata to Plex libraries automatically based on the file structure of the original media on disk. 

## Why Data Driven Collections?

A big part of building and maintaining a Plex server is the satisfaction of having it nicely organized with collections and custom poster artwork. Using Plex's web client to do all this organization is convenient, but all this time and effort is lost when a server needs to be migrated or a hardware failure occurs. Plex has loose built-in support for backing this data up, but the recovery process is inconsistent and the backup task is unreliably at best. More importantly, this organization exists on a Plex server, *not* through the arrangement of media on disk.

Data Driven Collections is no more than a script that looks at the file structure your media is organized in and builds collections / applies poster artwork in Plex accordingly. **The main benefits of organizing media this way are**: 
* Collection/artwork organization data isn't lost when migrating a plex server to new hardware or after a failure, as long as the original media is sufficiently backed up, all that's needed after setting up a new server is to run the script again.
* Since this collection/artwork organization exists outside of Plex, it's easy to move to a new media server host platform with all your library organization intact.

## How does it work?
Data Driven Collections uses a simple set of rules to interpret how to translate the organization of Plex media on-disk into Plex collections and artwork. Running the tool scans the library's media directory and automatically translates filestructure organization into Plex collections, poster artwork, and metadata. 

**The Data Driven Collections tool follows these rules:**
* Each movie file should be in its own folder.
    * A poster art file placed inside this folder will be applied to the movie's poster in Plex.
    * Multiple movie files in a folder are treated as different versions of the same movie (eg. Theatrical, Extended, Directors Cut..).
* A folder with nested movie folders is treated as a collection.
    * The collection name is based off the name of the top-level folder.
    * A poster art file placed inside this top level folder will be applied to the collection's poster.
* A TV Show folder should have folders for each season inside - each containing all the media files for the season.
   * A poster artwork file in the show's root folder will get applied to the show's main poster.
   * A poster artwork file in a show's season folder will be applied to the poster for that show's season.
   * TV Shows can be nested inside a folder to create collections in the same way as Movies.

*if any media is organized in a way that conflicts with these rules, or is otherwise ambiguous, it's simply ignored.*

### Example:

```
The Hateful Eight
    TheHatefulEight.mp4
Django Unchained
    artwork.png
    DjangoUnchained.mp4
Tarantino's Best Movies
    artwork.png
    Inglourious Basterds
        InglouriousBasterds.mp4
        InglouriousBasterds_MoreItalian.mp4
    Pulp Fiction
        artwork.png
        PulpFiction.mp4
```
Would produce a collection called "Tarantino's Best Movies" with "Inglorious Basterds" and "Pulp Fiction" inside. "Django Unchained" and "The Hateful Eight" would not be included in a collection.

"Django Unchained" and "Pulp Fiction" would both have their respective "artwork.png" files applied as poster art, however "The Hateful Eight" and "Inglorious Basterds" would have no custom poster artwork applied. The collection "Tarantino's Best Movies" would also receive collection poster art applied from it's "artwork.png" file

Finally, "Inglorious Basterds" would have two versions available in Plex under the "Play Version" option, one for "InglouriousBasterds.mp4" and one for "InglouriousBasterds_MoreItalian.mp4", which presumably includes extended scenes of Brad Pitt trying to speak Italian.

### TV Show Example:
```
Avatar The Last Airbender
    artwork.png
    Season 1
        artwork.png
        S01E01.mp4
        S01E02.mp4
        S01E03.mp4
        S01E04.mp4
        S01E05.mp4
    Season 2
        S02E01.mp4
        S02E02.mp4
        S02E03.mp4
Shows About Horses
    Bojack Horseman
        Season 1
            S01E01.mp4
            S01E02.mp4
            S01E03.mp4
        Season 2
            artwork.png
            S02E01.mp4
            S02E02.mp4
            S02E03.mp4
    Free Rein
    artwork.png
        Season 1
        artwork.png
            S01E01.mp4
            S01E02.mp4
            S01E03.mp4
```
Would produce a collection called "Shows About Horses" containing both "Bojack Horseman" and "Free Rein". "Avatar The Last Airbender" would not be added to any collections. 

The show poster for "Avatar The Last Airbender" would have the "artwork.png" file located at "Avatar The Last Airbender/artwork.png" applied. The "artwork.png" in its first season folder would be applied to the Season 1 poster. "Bojack Horseman" would only have artwork applied to its Season 2 poster, but "Free Rein" would have corresponding artwork.png files applied to both its main show poster and Season 1 poster.

TV Show media merging rules are slightly different in that the tool will *not* attempt to merge any media. If Plex has auto-merged two versions of a show on import (say, an HD version and a lower quality SD version to save on transcoding) this tool will split these into two separate shows *only if the media files for these are not in the same folders*. Otherwise, it'll do nothing.

## Usage
Anytime DataDrivenCollections.py is ran, the structure of that library's media directory is propogated into Plex. This script will never remove collections / poster artwork, only add them - meaning if changes are made to a library that remove collections or artwork, it's best to just delete the library in Plex, re-add it, then run the script.

1. Install [Python 3](https://www.python.org/downloads/)
2. Install required packages with pip by running: ```pip install -r requirements.txt``` from within the project directory
3. Provide a form of server authentication via the .ini file or command line arguments (more info on .ini and command line arguments below)
    * **Basic Auth:** supply a Plex **username/password** and a **Plex server name**
    * **Token Auth:** supply an **[X-Plex-Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)** and a **Plex server URL**
4. Run DataDrivenCollections.py on a Plex library at any time to update its collections and poster artwork!

This script can be configured either through a ```DataDrivenCollections.ini``` file placed in the project directory, or via commandline arguments. Below are the various configuration options for DataDrivenCollections:
|Option|Description|Command Line Aliases|.ini Alias|.ini Section|
|---|---|---|---|---|
|Library (required) |name of the Plex library to update|```-l```, ```--library```|```library```|Config|
|Artwork|files matching this name will be used as poster art (default: ```artwork```)|```-a```, ```--artwork```|```artwork```|Config|
|Collection Priority|if ```1```, all collections will sort to the top of the library (default: ```0```)|```-c```, ```--collection-priority```, ```--collection_priority```|```collection_priority```|Config|
|Username|Plex account username for basic auth|```-u```, ```--user```, ```--username```|```username```|Auth|
|Password|Plex account password for basic auth|```-p```, ```--pass```, ```--password```|```password```|Auth|
|X-Plex-Token|Plex API token for token auth|```-t```, ```--token```|```token```|Auth|
|Server URL|Plex server url for token auth|```-s```, ```--server-url```, ```--server_url```|```server_url```|Auth|
|Server Name|Plex server name for token auth|```-n```, ```--server-name```, ```--server_name```|```server_name```|Auth|

### Command Examples:
```py DataDriveCollections.py -l Movies --artwork poster --user MYPLEXUSER --pass MYPLEXPASS --server-name MYPLEXSERVERNAME```
```py DataDriveCollections.py --library "TV Shows" -c 1 -t MYPLEXAPITOKEN```

### .ini Examples:
```
[Auth]
server_url=http://192.168.1.1:32400
token=gTo557jqjty2EWmcYUOp

[Config]
artwork=artwork
collection_priority=0
```

```
[Auth]
server_name=My Plex Server
username=myplexuser@gmail.com
password=myplexpassword

[Config]
artwork=art
```
