# spqr-servus-publicus
general purpose bot for the spqr discord server and server monitor for the pavlov game server.

## usage description
* clone this repo to your workstation
* copy config.json.example to config.json and edit the latter to your liking
* prepare a server so you can access it as root via ssh
* prepare a server with a mysql/mariadb and load the database from spqr-database.sql
* use deploy.sh like this: ./deploy.sh -d [hostname-or-ip] -u [ssh-and-scp-user] -v
* check for errors - the service should be up and running now as spqr-servus-publicus.service
* journal only receives info for service status changes and discord login information
* app log is only written to file (spqr-servus-publicus.log)

## requirements
* pip modules
  * discord
  * async-pavlov
  * mysql-connector

## todo (aside from finding and fixing bugs and improving the code in general)
* add !genteams
* get top ranks and write them to an updated message in #stats
* extended playerstats (DM + TDM)
  * pull steamusers details
  * ace-detection for playerstats
* use map aliases in output of !maplist
* allow map aliases for !setmap
* add elo/mmr as a (second; at least for now) ranking system
* auto-message new discord users (maybe?)
* pull user access rights from roles
* pull bot-channel-ids from discord directly
* make env a param (main.py)
* remove requirement to access the server as root (deploy.sh)
* zip/unzip files (deploy.sh)
* add discord-ui-features (buttons) to trigger commands
