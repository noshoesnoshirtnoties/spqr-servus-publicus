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

## todo (aside from finding and fixing bugs)
* parse rcon response data for !serverinfo, !maplist
* !getstats, !getrank, !unregister
* allow map aliases for !setmap
* auto-message new discord users
* pull user access rights from specific discord messages (instead of a config file)
  * !updateaccessrights to allow senate members to update the access rights for certain commands
* create logrotate config for the log file
* remove requirement to access the server as root (deploy.sh)
* add discord-ui-features (buttons) to trigger commands
