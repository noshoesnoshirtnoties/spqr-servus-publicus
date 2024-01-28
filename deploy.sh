#!/bin/bash

VERSION=2.0.0
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


# defaults
if [ $VERBOSE ]; then echo "[INFO] setting defaults"; fi
SSH="$(which ssh) -q -o StrictHostKeyChecking=no -A -F /home/${USER}/.ssh/config -l ${SSHUSER} "
SCP="$(which scp) -F /home/${USER}/.ssh/config "
SERVICES[0]="spqr-servus-publicus"
SERVICES[1]="spqr-server-monitor"
SERVICEUSER="steam"
BASEPATH="/home/${SERVICEUSER}/spqr"
FILES=(
  "config.json"
  "database_template.sql"
  "generate-ranks-cron.py"
  "generate-events-cron.py"
  "generate-reminder-cron.py"
  "generate-stats-cron.py"
  "spqr-servus-publicus.log"
  "spqr-servus-publicus/meta.json"
  "spqr-servus-publicus/main.py"
  "spqr-servus-publicus/bot.py"
  "spqr-server-monitor.log"
  "spqr-server-monitor/meta.json"
  "spqr-server-monitor/main.py"
  "spqr-server-monitor/bot.py"
)


# error if host is invalid
if [ ! -n "${DSTHOST}" ]; then
  echo "[ERROR] given destination host is invalid - exiting"; exit 1
fi


# error if sshuser is invalid
if [ ! -n "${SSHUSER}" ]; then
  echo "[ERROR] given ssh user is invalid - exiting"; exit 1
fi


# create base path
if [ $VERBOSE ]; then echo "[INFO] creating service home"; fi
$SSH $DSTHOST "mkdir -p ${BASEPATH}"
$SSH $DSTHOST "/usr/bin/chown -R ${SERVICEUSER}:${SERVICEUSER} ${BASEPATH}"


# disable services before deployment + create home folders
for SERVICE in ${SERVICES[@]}
do
  # disable running service
  if [ $VERBOSE ]; then echo "[INFO] stopping the service: ${SERVICE}"; fi
  $SSH $DSTHOST "/usr/bin/systemctl stop ${SERVICE}.service"
  sleep 2

  # create home folder
  if [ $VERBOSE ]; then echo "[INFO] creating service home"; fi
  $SSH $DSTHOST "mkdir -p ${BASEPATH}/${SERVICE}"
  $SSH $DSTHOST "/usr/bin/chown -R ${SERVICEUSER}:${SERVICEUSER} ${BASEPATH}/${SERVICE}"
done


# transfer files
if [ $VERBOSE ]; then echo "[INFO] transferring files"; fi


# everything listed in FILES
for FILE in "${FILES[@]}"; do
  $SCP "${FILE}" "${SSHUSER}@${DSTHOST}:${BASEPATH}/${FILE}"
  $SSH $DSTHOST "/usr/bin/chmod 664 ${BASEPATH}/${FILE}; /usr/bin/chown ${SERVICEUSER}:${SERVICEUSER} ${BASEPATH}/${FILE}"
done


# cron files
$SCP "generate-events-cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-events-cron"
$SSH $DSTHOST "/usr/bin/chmod 644 /etc/cron.d/generate-events-cron; /usr/bin/chown root:root /etc/cron.d/generate-events-cron"
$SCP "generate-reminder-cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-reminder-cron"
$SSH $DSTHOST "/usr/bin/chmod 644 /etc/cron.d/generate-reminder-cron; /usr/bin/chown root:root /etc/cron.d/generate-reminder-cron"
$SCP "generate-stats-cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-stats-cron"
$SSH $DSTHOST "/usr/bin/chmod 644 /etc/cron.d/generate-stats-cron; /usr/bin/chown root:root /etc/cron.d/generate-stats-cron"
$SCP "generate-ranks-cron" "${SSHUSER}@${DSTHOST}:/etc/cron.d/generate-ranks-cron"
$SSH $DSTHOST "/usr/bin/chmod 644 /etc/cron.d/generate-ranks-cron; /usr/bin/chown root:root /etc/cron.d/generate-ranks-cron"


# txt files for servus-publicus
$SCP -r "spqr-servus-publicus/txt" "${SSHUSER}@${DSTHOST}:${BASEPATH}/spqr-servus-publicus/"


# install pip dependencies
if [ $VERBOSE ]; then echo "[INFO] installing dependencies"; fi
$SSH $DSTHOST "sudo su ${SERVICEUSER} -c 'pip3 install discord async-pavlov mysql-connector'"


# install services and run them
for SERVICE in ${SERVICES[@]}
do
  $SCP "${SERVICE}.service" "${SSHUSER}@${DSTHOST}:/etc/systemd/system/${SERVICE}.service"
  $SSH $DSTHOST "/usr/bin/chmod 664 /etc/systemd/system/${SERVICE}.service; /usr/bin/chown root:root /etc/systemd/system/${SERVICE}.service"

  $SCP "${SERVICE}-logrotate" "${SSHUSER}@${DSTHOST}:/etc/logrotate.d/"
  $SSH $DSTHOST "/usr/bin/chmod 644 /etc/logrotate.d/${SERVICE}-logrotate; /usr/bin/chown root:root /etc/logrotate.d/${SERVICE}-logrotate"

  if [ $VERBOSE ]; then echo "[INFO] enabling the systemd service"; fi
  $SSH $DSTHOST "/usr/bin/systemctl enable ${SERVICE}.service"

  if [ $VERBOSE ]; then echo "[INFO] starting the systemd service"; fi
  $SSH $DSTHOST "/usr/bin/systemctl start ${SERVICE}.service"
  sleep 3
  $SSH $DSTHOST "/usr/bin/systemctl status ${SERVICE}.service | grep 'Active:'"
done


# done
if [ $VERBOSE ]; then echo "[INFO] exiting without errors"; fi
exit 0