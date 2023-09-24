#!/bin/bash

VERSION=1.3.0
SUBJECT=deploy
USAGE="Usage: $0 -d dsthost -u sshuser -v\n
-d destination host\n
-u ssh/scp user\n
-v verbose output"

# --- options processing -------------------------------------------

if [ $# == 0 ] ; then
    echo -e $USAGE
    exit 1;
fi

while getopts ":d:u:v" optname
  do
    case "$optname" in
      "v")
        echo "[INFO] verbose mode active"
        VERBOSE=true
        ;;
      "d")
        DSTHOST=$OPTARG
        ;;
      "u")
        SSHUSER=$OPTARG
        ;;
      "?")
        echo "[ERROR] unknown option $OPTARG - exiting"
        exit 1;
        ;;
      ":")
        echo "[ERROR] no argument value for option $OPTARG - exiting"
        exit 1;
        ;;
      *)
        echo "[ERROR] unknown error while processing options - exiting"
        exit 1;
        ;;
    esac
  done

shift $(($OPTIND - 1))

# --- body --------------------------------------------------------

read -s -n 1 -p "[WAIT] press any key to continue..." && echo ""
if [ $VERBOSE ]; then echo "[INFO] starting deployment"; fi

if [ $VERBOSE ]; then echo "[INFO] setting defaults"; fi
SSH="$(which ssh) -q -o StrictHostKeyChecking=no -A -F /home/${USER}/.ssh/config -l ${SSHUSER} "
SCP="$(which scp) -F /home/${USER}/.ssh/config "
SERVICENAME="spqr-servus-publicus"
SERVICEUSER="spqr"
SERVICEHOME="/home/${SERVICEUSER}/${SERVICENAME}"
FILES=(
  "meta.json"
  "config.json"
  "main.py"
  "bot.py"
  "responses.py"
  "generate-ranks.cron.py"
  "generate-events.cron.py"
  "generate-reminder.cron.py"
)

if [ ! -n "${DSTHOST}" ]; then
  echo "[ERROR] given destination host is invalid - exiting"; exit 1
fi

if [ ! -n "${SSHUSER}" ]; then
  echo "[ERROR] given ssh user is invalid - exiting"; exit 1
fi

if [ $VERBOSE ]; then echo "[INFO] stopping the server"; fi
$SSH $DSTHOST "/usr/bin/systemctl stop ${SERVICENAME}.service"
sleep 3

if [ $VERBOSE ]; then echo "[INFO] installing dependencies"; fi
$SSH $DSTHOST "sudo su spqr -c 'pip install discord async-pavlov'"

if [ $VERBOSE ]; then echo "[INFO] creating service home"; fi
$SSH $DSTHOST "mkdir -p ${SERVICEHOME}"

if [ $VERBOSE ]; then echo "[INFO] transferring files"; fi
$SCP -r "txt" "${SSHUSER}@${DSTHOST}:${SERVICEHOME}/"
for FILE in "${FILES[@]}"; do
  $SCP "${FILE}" "${SSHUSER}@${DSTHOST}:${SERVICEHOME}/${FILE}"
  $SSH $DSTHOST "/usr/bin/chmod 664 ${SERVICEHOME}/${FILE}; /usr/bin/chown ${SERVICEUSER}:${SERVICEUSER} ${SERVICEHOME}/${FILE}"
done

$SCP "generate-ranks.cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-ranks.cron"
$SSH $DSTHOST "/usr/bin/chmod 664 /etc/cron.d/generate-ranks.cron; /usr/bin/chown spqr:root /etc/cron.d/generate-ranks.cron"

$SCP "generate-events.cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-events.cron"
$SSH $DSTHOST "/usr/bin/chmod 664 /etc/cron.d/generate-events.cron; /usr/bin/chown spqr:root /etc/cron.d/generate-events.cron"

$SCP "generate-reminder.cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-reminder.cron"
$SSH $DSTHOST "/usr/bin/chmod 664 /etc/cron.d/generate-reminder.cron; /usr/bin/chown spqr:root /etc/cron.d/generate-reminder.cron"

$SCP "${SERVICENAME}.service" "${SSHUSER}@${DSTHOST}:/etc/systemd/system/${SERVICENAME}.service"
$SSH $DSTHOST "/usr/bin/chmod 664 /etc/systemd/system/${SERVICENAME}.service; /usr/bin/chown root:root /etc/systemd/system/${SERVICENAME}.service"

if [ $VERBOSE ]; then echo "[INFO] enabling the systemd service"; fi
$SSH $DSTHOST "/usr/bin/systemctl enable ${SERVICENAME}.service"

if [ $VERBOSE ]; then echo "[INFO] starting the systemd service"; fi
$SSH $DSTHOST "/usr/bin/systemctl start ${SERVICENAME}.service"
sleep 3
$SSH $DSTHOST "/usr/bin/systemctl status ${SERVICENAME}.service | grep 'Active:'"

if [ $VERBOSE ]; then echo "[INFO] exiting without errors"; fi

exit 0
