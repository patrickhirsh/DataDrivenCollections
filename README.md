# Data Driven Collections for Plex
Data Driven Collections is a tool that builds and applies Plex collections, poster artwork, and other metadata to Plex libraries automatically based on the file structure of the original media on disk. 

## Why Data Driven Collections?

A big part of building and maintaining a Plex server is the satisfaction of having it nicely organized with collections and custom poster artwork. Using Plex's web client to do all this organization is convenient, but all this time and effort is lost when a server needs to be migrated or a hardware failure occurs. Plex has loose built-in support for backing this data up, but the recovery process is inconsistent and the backup task is unreliably at best. More importantly, this organization exists on a Plex server, *not* through the arrangement of media on disk.

Data Driven Collections is no more than a script that looks at the file structure your media is organized in and builds collections / applies poster artwork in Plex accordingly. **The main benefits of this organizing your media this way are**: 
* Collection/artwork organization data isn't lost when migrating a plex server to new hardware or after a failure, as long as the original media is sufficiently backed up, all that's needed after setting up a new server is to run the script again.
* Since this collection/artwork organization exists outside of Plex, it's easy to move to a new media server host platform with all your library organization intact.

## How does it work?
Data Driven Collections uses a simple set of rules to interpret how to translate the organization of Plex media on-disk into Plex collections and artwork. Running the tool scans the library's media directory and automatically translates the way it's organized into Plex collections, poster artwork, and metadata. 

**The Data Driven Collections tool follows these rules:**
* Each movie file should be in its own folder.
    * A poster art file placed inside this folder will be applied to the movie's poster in Plex.
    * Multiple movie files in a folder are treated as different versions of the same movie (eg. Theatrical, Extended, Directors Cut..).
* A folder with nested movie folders is treated as a collection.
    * The collection name is based off the name of the top-level folder
    * a poster art file placed inside this top level folder will be applied to the collection's poster

*if any media is organized in a way that conflicts with these rules, or is otherwise ambiguous, it's simply ignored.*

#### Example:

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

**TV Shows** are handled identically to Movies - except the tool expects to find sub-folders for each season inside the show's root folder. A poster artwork file at the show's root will get applied to the show's main poster, while a poster artwork file in a show's season folder will be applied to the poster for that show's season. 

While *technically* TV Show collections are supported in the same way as Movie collections, Plex often gets confused when TV Shows are put in nested directories.

#### TV Show Example:
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