# spqr-servus-publicus
general purpose bot for the spqr discord server

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
* add !modlist, !blacklist, !pings
* allow map aliases for !setmap
* auto-message new discord users
* pull user access rights from roles
  * alternatively: pull them from specific discord messages
* pull bot-channel-ids from discord directly
  * alternatively: pull them from a specific discord message
* create logrotate config for the log file
* make env (main.py) a param
* remove requirement to access the server as root (deploy.sh)
* add discord-ui-features (buttons) to trigger commands
