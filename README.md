# spqr services
spqr-servus-publicus.service provides a discord bot with several commands related to the game server, the discord server and more.

spqr-server-monitor.service provides services around the game server.

## usage description
* clone this repo to your workstation
* copy config.json.example to config.json and edit the latter to your liking
* prepare a server so you can access it as root via ssh
* prepare a server with a mysql/mariadb and load the database from database_template.sql
* use deploy.sh like this: ./deploy.sh -d [hostname-or-ip] -u [ssh-and-scp-user] -v
* check for errors - there should be 2 services up and running now: spqr-servus-publicus.service + spqr-server-monitor.service
* journal only receives info for services status changes and discord login information
* app logs are only written to files (spqr-servus-publicus.log + spqr-server-monitor.log)

## requirements
* pip modules
  * discord
  * async-pavlov
  * mysql-connector

## todo
### spqr-servus-publicus
* use map aliases in output of !maplist
* allow map aliases for !setmap
* auto-message new discord users (maybe?)
* pull user access rights from roles
* pull bot-channel-ids from discord directly
* add discord-ui-features (buttons) to trigger commands
* make env a param (main.py)

### spqr-server-monitor
* get top ranks and write them to an updated message in #stats
* extended playerstats (DM + TDM)
  * pull steamusers details
  * ace-detection for playerstats
* add elo/mmr as a (second; at least for now) ranking system
* make env a param (main.py)

### deploy.sh
* remove requirement to access the server as root
* zip/unzip files
