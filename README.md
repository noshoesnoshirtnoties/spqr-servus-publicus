# spqr-servus-publicus
general purpose bot for the spqr discord server.

meant to work in coop with https://github.com/noshoesnoshirtnoties/spqr-pavlov-srvmon

## usage description
* clone this repo to your workstation
* copy config.json.example to config.json and edit the latter to your liking
* prepare a server so you can access it as root via ssh
* use deploy.sh like this: ./deploy.sh -d [hostname-or-ip] -u [ssh-and-scp-user] -v
* check for errors - the service should be up and running now as spqr-servus-publicus.service
* journal only receives info for service status changes and discord login information
* app log is only written to file (spqr-servus-publicus.log)

## requirements
* pip modules:
  * discord
  * async-pavlov
  * mysql-connector

## todo (aside from finding and fixing bugs and improving the code in general)
* add !genteams
* add event message cleanup
* get top ranks and write them to an updated message in #stats
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
