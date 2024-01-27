import os
import re
import sys
import json
import time
import logging
import discord
import random
import asyncio
import operator
from pavlov import PavlovRCON
import mysql.connector
from pathlib import Path
from pavlov import PavlovRCON
from datetime import datetime,timezone

def run_bot(meta,config):


    # init logging
    if bool(config['debug'])==True:
        level=logging.DEBUG
    else:
        level=logging.INFO
    logging.basicConfig(
        filename='spqr-servus-publicus.log',
        filemode='a',
        format='%(asctime)s,%(msecs)d [%(levelname)s] spqr-sp: %(message)s',
        datefmt='%m/%d/%Y %H:%M:%S',
        level=level)
    logfile=logging.getLogger('logfile')


    # init discord
    intents=discord.Intents.default()
    intents.message_content=True
    intents.members=True
    client=discord.Client(intents=intents)


    # function: log to file
    def logmsg(lvl,msg):
        lvl=lvl.lower()
        match lvl:
            case 'debug':
                logfile.debug(msg)
            case 'info':
                logfile.info(msg)
            case 'warn':
                logfile.warning(msg)
            case _:
                logfile.debug(msg)


    # function: log to discord
    async def log_discord(channel,message):
        logmsg('debug','log_discord called')

        target_message=message
        target_channel_id=config['bot-channel-ids'][channel]
        target_channel=client.get_channel(int(target_channel_id))
        logmsg('debug','target_message: '+str(target_message))
        logmsg('debug','target_channel: '+str(target_channel_id))
        logmsg('debug','target_channel: '+str(target_channel))
        try:
            await target_channel.send(target_message)
        except Exception as e:
            logmsg('debug',str(e))


    # function: query database
    def dbquery(query,values):
        conn=mysql.connector.connect(
            host=config['mysqlhost'],
            port=config['mysqlport'],
            user=config['mysqluser'],
            password=config['mysqlpass'],
            database=config['mysqldatabase'])
        cursor=conn.cursor(buffered=True,dictionary=True)
        cursor.execute(query,(values))
        conn.commit()
        data={}
        data['rowcount']=cursor.rowcount
        query_type0=query.split(' ',2)
        query_type=str(query_type0[0])

        if query_type.upper()=="SELECT":
            data['rows']=cursor.fetchall()
            print('[DEBUG] data[rows]: '+str(data['rows']))
        else:
            data['rows']=False
        cursor.close()
        conn.close()
        return data


    # function: rcon command
    async def rcon(rconcmd,rconparams):
        logmsg('debug','rcon called')
        logmsg('debug','rconcmd: '+str(rconcmd))
        logmsg('debug','rconparams: '+str(rconparams))
        conn=PavlovRCON(config['rconip'],config['rconport'],config['rconpass'])
        for rconparam in rconparams:
            rconcmd+=' '+str(rconparam)
        data=await conn.send(rconcmd)
        data_json=json.dumps(data)
        data=json.loads(data_json)
        logmsg('debug','rcon data: '+str(data))
        await conn.send('Disconnect')
        return data


    # function: wrapper to retrieve all params from full message
    def get_rconparams_from_user_message(user_message):
        maxnumparams=3
        user_message_split=user_message.split(' ',maxnumparams+1)
        rconparams=[]
        i=0
        while i<(len(user_message_split)-1):
            pos=i+1 # to strip the command itself
            rconparams.append(user_message_split[pos])
            i+=1
        return rconparams


    # function: get wrapper for rcon serverinfo
    async def get_serverinfo():
        logmsg('debug','get_serverinfo called')

        # get the serverinfo data
        data=await rcon('ServerInfo',{})

        if data['Successful'] is True:
            # unless during rotation, analyze and if necessary modify serverinfo before returning it
            if data['ServerInfo']['RoundState']!='Rotating':
                new_serverinfo=data['ServerInfo']

                # make sure gamemode is uppercase
                new_serverinfo['GameMode']=new_serverinfo['GameMode'].upper()

                # demo rec counts as 1 player in SND
                if new_serverinfo['GameMode']=="SND":
                    numberofplayers0=new_serverinfo['PlayerCount'].split('/',2)
                    numberofplayers1=numberofplayers0[0]
                    if int(numberofplayers1)>0: # demo only exists if there is players
                        numberofplayers2=(int(numberofplayers1)-1)
                    else:
                        numberofplayers2=(numberofplayers0[0])
                    maxplayers=numberofplayers0[1]
                    numberofplayers=str(numberofplayers2)+'/'+str(maxplayers)
                else:
                    numberofplayers=new_serverinfo['PlayerCount']
                new_serverinfo['PlayerCount']=numberofplayers

                # for SND get info if match has ended and which team won
                new_serverinfo['MatchEnded']=False
                new_serverinfo['WinningTeam']='none'
                if new_serverinfo['GameMode']=="SND" and new_serverinfo['Teams'] is True:
                    if int(new_serverinfo['Team0Score'])==10:
                        new_serverinfo['MatchEnded']=True
                        new_serverinfo['WinningTeam']='team0'
                    elif int(new_serverinfo['Team1Score'])==10:
                        new_serverinfo['MatchEnded']=True
                        new_serverinfo['WinningTeam']='team1'
                else:
                    new_serverinfo['Team0Score']=0
                    new_serverinfo['Team1Score']=0
                
                data['ServerInfo']=new_serverinfo
            else:
                data['Successful']=False
                data['ServerInfo']=False
        else:
            data['ServerInfo']=False
        return data


    # function: action: retrieve and output serverinfo
    async def action_serverinfo():
        logmsg('debug','action_serverinfo called')

        serverinfo=await get_serverinfo()
        if serverinfo['Successful'] is True:

            # unless during rotation, output server info to log
            if serverinfo['ServerInfo']['RoundState']!='Rotating':
                logmsg('info','srvname:     '+str(serverinfo['ServerInfo']['ServerName']))
                logmsg('info','playercount: '+str(serverinfo['ServerInfo']['PlayerCount']))
                logmsg('info','mapugc:      '+str(serverinfo['ServerInfo']['MapLabel']))
                logmsg('info','gamemode:    '+str(serverinfo['ServerInfo']['GameMode']))
                logmsg('info','roundstate:  '+str(serverinfo['ServerInfo']['RoundState']))
                logmsg('info','teams:       '+str(serverinfo['ServerInfo']['Teams']))
                if serverinfo['ServerInfo']['Teams']==True:
                    logmsg('info','team0score:  '+str(serverinfo['ServerInfo']['Team0Score']))
                    logmsg('info','team1score:  '+str(serverinfo['ServerInfo']['Team1Score']))
            else:
                logmsg('warn','cant complete serverinfo because map is rotating')
        else:
            logmsg('warn','get_serverinfo returned unsuccessful')


    # function: action: set/unset pin depending on map, playercount and gamemode
    async def action_autopin():
        logmsg('debug','action_autopin called')

        serverinfo=await get_serverinfo()
        if serverinfo['Successful'] is True:

            # unless during rotation, set playercount limit depending on gamemode
            if serverinfo['ServerInfo']['RoundState']!='Rotating':
                limit=8
                if serverinfo['ServerInfo']['GameMode']=="TDM":
                    limit=8
                elif serverinfo['ServerInfo']['GameMode']=="DM":
                    limit=6

                # decide wether to set the pin or remove it
                playercount_split=serverinfo['ServerInfo']['PlayerCount'].split('/',2)
                if (int(playercount_split[0]))>=limit:
                    logmsg('debug','limit ('+str(limit)+') reached - setting pin 9678')
                    command='SetPin'
                    params={'9678'}
                    data=await rcon(command,params)
                    await log_discord('e-bot-log','[server-monitor] server pin has been set')
                else:
                    logmsg('debug','below limit ('+str(limit)+') - removing pin')
                    command='SetPin'
                    params={''}
                    data=await rcon(command,params)
                    await log_discord('e-bot-log','[server-monitor] server pin has been removed')
            else:
                logmsg('warn','cant complete auto-pin because map is rotating')
        else:
            logmsg('warn','action_autopin was unsuccessful because get_serverinfo failed - not touching pin')


    # function: action: kick players with high pings
    async def action_autokickhighping():
        logmsg('debug','action_autokickhighping called')

        hard_limit=70
        soft_limit=50
        delta_limit=40
        min_entries=5
        del_entries=min_entries*3
        keep_entries=4
        act_on_breach=False

        # check gamemode and roundstate in snd
        serverinfo=await get_serverinfo()
        if serverinfo['Successful'] is True:
            if serverinfo['ServerInfo']['GameMode']=='SND':
                if serverinfo['ServerInfo']['MatchEnded'] is True:
                    act_on_breach=True
            elif serverinfo['ServerInfo']['GameMode']=='TDM':
                act_on_breach=True
            elif serverinfo['ServerInfo']['GameMode']=='DM':
                act_on_breach=True
                
        # get the scoreboard for all players
        inspectall=await rcon('InspectAll',{})
        inspectlist=inspectall['InspectList']
        logmsg('debug','inspectlist: '+str(inspectlist))

        # go over each players
        for player in inspectlist:

            kick_player=False
            delete_data=False
            add_data=True

            steamusers_id=player['UniqueId']
            current_ping=player['Ping']

            logmsg('info','checking entries in pings db for player: '+str(steamusers_id))

            # get averages for current player
            query="SELECT steamid64,ping,"
            query+="AVG(ping) as avg_ping,"
            query+="MIN(ping) as min_ping,"
            query+="MAX(ping) as max_ping,"
            query+="COUNT(id) as cnt_ping "
            query+="FROM pings "
            query+="WHERE steamid64 = %s"
            values=[]
            values.append(steamusers_id)
            pings=dbquery(query,values)

            avg_ping=pings['rows'][0]['avg_ping']
            min_ping=pings['rows'][0]['min_ping']
            max_ping=pings['rows'][0]['max_ping']
            cnt_ping=pings['rows'][0]['cnt_ping']

            # check if there is enough samples
            if cnt_ping>=min_entries:
                logmsg('debug','rowcount ('+str(cnt_ping)+') >= minentries ('+str(min_entries)+')')

                # calc min-max-delta
                min_max_delta=int(max_ping)-int(min_ping)

                # decide wether old entries for this player should be deleted
                if cnt_ping>=del_entries:
                    delete_data=True

                # check players avg ping
                if int(avg_ping)>soft_limit:
                    kick_player=False
                    logmsg('warn','ping average ('+str(int(avg_ping))+') exceeds the soft limit ('+str(soft_limit)+')')
                else:
                    logmsg('info','ping average ('+str(int(avg_ping))+') is within soft limit ('+str(soft_limit)+')')
                if int(avg_ping)>hard_limit:
                    kick_player=True
                    logmsg('warn','ping average ('+str(int(avg_ping))+') exceeds the hard limit ('+str(hard_limit)+')')
                    await log_discord('e-bot-log','[server-monitor] ping average ('+str(int(avg_ping))+') exceeds the hard limit ('+str(hard_limit)+') for player: '+str(steamusers_id))
                else:
                    logmsg('info','ping average ('+str(int(avg_ping))+') is within hard limit ('+str(hard_limit)+')')

                # check players min-max-delta
                if int(min_max_delta)>delta_limit:
                    kick_player=False
                    logmsg('warn','ping min-max-delta ('+str(int(min_max_delta))+') exceeds the delta limit ('+str(delta_limit)+')')
                else:
                    logmsg('info','ping min-max-delta ('+str(int(min_max_delta))+') is within delta limit ('+str(delta_limit)+')')

                # kick unless canceled
                if kick_player is True:
                    if act_on_breach is True:
                        await rcon('Kick',{steamusers_id})
                        logmsg('warn','player ('+str(steamusers_id)+') has been kicked by autokick-highping')
                        await log_discord('e-bot-log','[server-monitor] player ('+str(steamusers_id)+') has been kicked by autokick-highping')
                        delete_data=True
                    else:
                        logmsg('warn','player ('+str(steamusers_id)+') would have been kicked by autokick-highping, but this got canceled')
            else:
                logmsg('debug','not enough data on pings yet')

            # delete accumulated entries (if...), but keep some recent ones
            if delete_data:
                logmsg('debug','deleting entries for player in pings db')
                query="DELETE FROM pings WHERE steamid64 = %s ORDER BY id ASC LIMIT %s"
                values=[]
                values.append(steamusers_id)
                values.append(del_entries-keep_entries)
                dbquery(query,values)

            # remove invalid new samples
            if str(current_ping)=='0': # not sure yet what these are
                add_data=False
                logmsg('warn','ping is 0 - simply gonna ignore this for now')

            # add the current sample for the current player
            if add_data:
                logmsg('debug','adding entry for user in pings db')
                timestamp=datetime.now(timezone.utc)            
                query="INSERT INTO pings ("
                query+="steamid64,ping,timestamp"
                query+=") VALUES (%s,%s,%s)"
                values=[steamusers_id,current_ping,timestamp]
                dbquery(query,values)


    # function: action: pull stats
    async def action_pullstats():
        logmsg('debug','action_pullstats called')
        serverinfo=await get_serverinfo()

        if serverinfo['Successful'] is True:

            # drop maxplayers from playercount
            numberofplayers0=serverinfo['ServerInfo']['PlayerCount'].split('/',2)
            numberofplayers=numberofplayers0[0]
            serverinfo['ServerInfo']['PlayerCount']=numberofplayers

            # only pull stats if match ended, gamemode is SND and state is not rotating
            if serverinfo['ServerInfo']['MatchEnded'] is True:
                if serverinfo['ServerInfo']['GameMode']=="SND":
                    logmsg('debug','actually pulling stats now')

                    # pull scoreboard
                    inspectall=await rcon('InspectAll',{})
                    inspectlist=inspectall['InspectList']
                    for player in inspectlist:
                        kda=player['KDA'].split('/',3)
                        kills=kda[0]
                        deaths=kda[1]
                        assists=kda[2]
                        score=player['Score']
                        ping=player['Ping']

                        logmsg('debug','player: '+str(player))
                        logmsg('debug','player[PlayerName]: '+str(player['PlayerName']))
                        logmsg('debug','player[UniqueId]: '+str(player['UniqueId']))
                        logmsg('debug','player[KDA]: '+str(player['KDA']))
                        logmsg('debug','kills: '+str(kills))
                        logmsg('debug','deaths: '+str(deaths))
                        logmsg('debug','assists: '+str(assists))
                        logmsg('debug','score: '+str(score))
                        logmsg('debug','ping: '+str(ping))
                        if str(player['TeamId'])!='':
                            logmsg('debug','player[TeamId]: '+str(player['TeamId']))

                        # check if user exists in steamusers
                        logmsg('debug','checking if user exists in db')
                        query="SELECT * FROM steamusers WHERE steamid64 = %s LIMIT 1"
                        values=[]
                        values.append(str(player['UniqueId']))
                        steamusers=dbquery(query,values)

                        # if user does not exist, add user
                        if steamusers['rowcount']==0:
                            logmsg('debug','adding user to db because not found')
                            query="INSERT INTO steamusers (steamid64) VALUES (%s)"
                            values=[]
                            values.append(str(player['UniqueId']))
                            dbquery(query,values)
                        else:
                            logmsg('debug','steam user already in db: '+str(player['UniqueId']))

                        # read steamuser id
                        logmsg('debug','getting steamusers id from db')
                        query="SELECT id FROM steamusers WHERE steamid64=%s LIMIT 1"
                        values=[]
                        values.append(str(player['UniqueId']))
                        steamusers=dbquery(query,values)
                        steamuser_id=steamusers['rows'][0]['id']

                        # add stats for user
                        logmsg('info','adding stats for user')
                        timestamp=datetime.now(timezone.utc)            
                        query="INSERT INTO stats ("
                        query+="steamusers_id,kills,deaths,assists,score,ping,servername,playercount,mapugc,"
                        query+="gamemode,matchended,teams,team0score,team1score,timestamp"
                        query+=") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                        values=[
                            steamuser_id,kills,deaths,assists,score,ping,serverinfo['ServerInfo']['ServerName'],serverinfo['ServerInfo']['PlayerCount'],
                            serverinfo['ServerInfo']['MapLabel'],serverinfo['ServerInfo']['GameMode'],serverinfo['ServerInfo']['MatchEnded'],
                            serverinfo['ServerInfo']['Teams'],serverinfo['ServerInfo']['Team0Score'],serverinfo['ServerInfo']['Team1Score'],timestamp]
                        dbquery(query,values)

                    logmsg('info','processed all current players')
                    await log_discord('e-bot-log','[server-monitor] stats have been pulled and processed for all current players')
                else:
                    logmsg('warn','not pulling stats because gamemode is not SND')
            else:
                logmsg('warn','not pulling stats because matchend is not True')
        else:
            logmsg('warn','not pulling stats because serverinfo returned unsuccessful')


    # function: decide what to do once a keyword appears
    async def process_found_keyword(line,keyword):
        match keyword:
            case 'Rotating map':
                logmsg('info','map rotation called')
            case 'LogLoad: LoadMap':
                if '/Game/Maps/ServerIdle' in line:
                    logmsg('info','map switch called')
                elif '/Game/Maps/download.download' in line:
                    mapugc0=line.split('UGC',1)
                    mapugc=('UGC'+str(mapugc0[1]))
                    logmsg('info','map is being downloaded: '+str(mapugc).strip())
                elif 'LoadMap: /UGC' in line:
                    mapugc0=line.split('LoadMap: /',1)
                    mapugc1=mapugc0[1].split("/",1)
                    mapugc=mapugc1[0]
                    gamemode0=line.split('game=',1)
                    gamemode=gamemode0[1]
                    logmsg('info','custom map is loading: '+str(mapugc).strip()+' as '+str(gamemode).strip())
                elif '/Game/Maps' in line:
                    mapugc0=line.split('Maps/',1)
                    mapugc1=mapugc0[1].split("/",1)
                    mapugc=mapugc1[0]
                    gamemode0=line.split('game=',1)
                    gamemode=gamemode0[1]
                    logmsg('info','vrankrupt map is loading: '+str(mapugc).strip()+' as '+str(gamemode).strip())
            case 'Updating blacklist':
                logmsg('info','access configs reloaded')
            case 'PavlovLog: StartPlay':
                logmsg('info','map started')
            case '"State":':
                roundstate0=line.split('": "',1)
                roundstate1=roundstate0[1].split('"',1)
                roundstate=roundstate1[0]
                logmsg('info','round state changed to: '+str(roundstate).strip())
                match roundstate:
                    case 'Starting':
                        asyncio.run(action_serverinfo())
                    case 'Started':
                        asyncio.run(action_autokickhighping())
                    case 'StandBy':
                        asyncio.run(action_autopin())
                    case 'Ended':
                        asyncio.run(action_autokickhighping())
                        asyncio.run(action_pullstats())
            case 'Preparing to exit':
                logmsg('info','server is shutting down')
            case 'LogHAL':
                logmsg('info','server is starting up')
            case 'Server Status Helper':
                logmsg('info','server is now online')
            case 'Rcon: User':
                rconclient0=line.split(' authenticated ',2)
                if len(rconclient0)>1:
                    rconclient=rconclient0[1]
                else:
                    rconclient=rconclient0[0]
                logmsg('debug','rcon client auth: '+str(rconclient).strip())
            case 'SND: Waiting for players':
                logmsg('info','waiting for players')
            case 'long time between ticks':
                logmsg('warn','long tick detected')
            case 'Login request':
                loginuser0=line.split(' ?Name=',2)
                loginuser1=loginuser0[1].split('?',2)
                loginuser=loginuser1[0]
                loginid0=line.split('NULL:',2)
                loginid1=loginid0[1].split(' ',2)
                loginid=loginid1[0]
                logmsg('info','login request from user: '+str(loginuser).strip()+' ('+str(loginid).strip()+')')
            case 'Client netspeed':
                netspeed0=line.split('Client netspeed is ',2)
                netspeed=netspeed0[1]
                logmsg('debug','client netspeed: '+str(netspeed).strip())
            case 'Join request':
                joinuser0=line.split('?name=',2)
                joinuser1=joinuser0[1].split('?',2)
                joinuser=joinuser1[0]
                logmsg('info','join request from user: '+str(joinuser).strip())
            case 'Join succeeded':
                joinuser0=line.split('succeeded: ',2)
                joinuser=joinuser0[1]
                logmsg('info','join successful for user: '+str(joinuser).strip())
                asyncio.run(action_autopin())
            case 'LogNet: UChannel::Close':
                leaveuser0=line.split('RemoteAddr: ',2)
                leaveuser1=leaveuser0[1].split(',',2)
                leaveuser=leaveuser1[0]
                logmsg('info','user left the server: '+str(leaveuser).strip())
                asyncio.run(action_autopin())
            case '"KillData":':
                logmsg(logfile,'info','a player died...')
                #asyncio.run(action_autokickhighping())
            case '"Killer":':
                killer0=line.split('"',4)
                killer=killer0[3]
                logmsg('info','killer: '+str(killer).strip())
            case '"KillerTeamID":':
                killerteamid0=line.split('": ',2)
                killerteamid1=killerteamid0[1].split(',',2)
                killerteamid=killerteamid1[0]
                logmsg('info','killerteamid: '+str(killerteamid).strip())
            case '"Killed":':
                killed0=line.split('"',4)
                killed=killed0[3]
                logmsg('info','killed: '+str(killed).strip())
            case '"KilledTeamID":':
                killedteamid0=line.split('": ',2)
                killedteamid1=killedteamid0[1].split(',',2)
                killedteamid=killedteamid1[0]
                logmsg('info','killedteamid: '+str(killedteamid).strip())
            case '"KilledBy":':
                killedby0=line.split('"',4)
                killedby=killedby0[3]
                logmsg('info','killedby: '+str(killedby).strip())
            case '"Headshot":':
                headshot0=line.split('": ',2)
                headshot=headshot0[1]
                logmsg('info','headhot: '+str(headshot).strip())
            case 'LogTemp: Rcon: KickPlayer':
                kickplayer0=line.split('KickPlayer ',2)
                kickplayer=kickplayer0[1]
                logmsg('info','player kicked: '+str(kickplayer).strip())
                await log_discord('e-bot-log','[server-monitor] user '+str(kickplayer).strip()+' has been kicked')
            case 'LogTemp: Rcon: BanPlayer':
                banplayer0=line.split('BanPlayer ',2)
                banplayer=banplayer0[1]
                logmsg('info','player banned: '+str(banplayer).strip())
                await log_discord('e-bot-log','[server-monitor] user '+str(banplayer).strip()+' has been banned')
            case 'BombData':
                logmsg('info','something happened with the bomb')
                #asyncio.run(action_autokickhighping())
            case '"Player":':
                bombplayer0=line.split('": "',2)
                bombplayer1=bombplayer0[1].split('"',2)
                bombplayer=bombplayer1[0]
                logmsg('info','player interacted with bomb: '+str(bombplayer).strip())
            case '"BombInteraction":':
                bombinteraction0=line.split('": "',2)
                bombinteraction1=bombinteraction0[1].split('"',2)
                bombinteraction=bombinteraction1[0]
                logmsg('info','bomb interaction: '+ str(bombinteraction).strip())


    # function: find relevant keywords in target log
    def find_keyword_in_line(line,keywords):
        for keyword in keywords:
            if keyword in line:
                logmsg('debug','original line: '+str(line).strip())
                logmsg('debug','matched keyword: '+str(keyword).strip())
                return keyword


    # function: follow the target log
    def follow_log(target_log):
        seek_end=True
        while True:
            with open(target_log) as f:
                if seek_end:
                    f.seek(0,2)
                while True:
                    line=f.readline()
                    if not line:
                        try:
                            if f.tell() > os.path.getsize(target_log):
                                f.close()
                                seek_end = False
                                break
                        except FileNotFoundError:
                            pass
                        time.sleep(1)
                    yield line


    # function: send discord message as response to bot commands
    async def send_answer(client,message,user_message,is_private):
        logmsg('debug','send_answer called')

        response=''
        user_message_split=user_message.split(' ',2)
        command=user_message_split[0]

        if str(command)!='': # this seems to occur with system messages (in discord; like in new-arrivals)

            paramsgiven=False
            if len(user_message_split)>1:
                logmsg('debug','params have been given')
                paramsgiven=True

            is_senate=False
            for id in config['senate-member']:
                if str(id)==str(message.author.id):
                    is_senate=True
                    logmsg('info','user has senate role')

            access_granted=True
            for senatecmd in config['senate-cmds']:
                if senatecmd==command:
                    logmsg('info','senate-cmd found')
                    if is_senate is not True:
                        access_granted=False

            if access_granted:
                logmsg('info','access to command has been granted')
                log_to_discord=False
                match command:
                    case '!help':
                        log_to_discord=True
                        response=Path('txt/help.txt').read_text()
                    case '!spqr':
                        log_to_discord=True
                        response=Path('txt/spqr.txt').read_text()
                    case '!loremipsum':
                        log_to_discord=True
                        response=Path('txt/loremipsum.txt').read_text()
                    case '!roles':
                        log_to_discord=True
                        response=Path('txt/roles.txt').read_text()
                    case '!rules':
                        log_to_discord=True
                        response=Path('txt/rules.txt').read_text()
                    case '!reqs':
                        log_to_discord=True
                        response=Path('txt/requirements.txt').read_text()
                    case '!suntzu':
                        log_to_discord=True
                        randomquote=random.choice(os.listdir('txt/suntzu'))
                        quotepath="txt/suntzu/"+randomquote
                        response=Path(str(quotepath)).read_text()
                    case '!serverinfo':
                        log_to_discord=True
                        serverinfo=await get_serverinfo()
                        if serverinfo['Successful'] is True:
                            parts=[
                                user_message+': successful\n',
                                'ServerName: '+str(serverinfo['ServerInfo']['ServerName']),
                                'PlayerCount: '+str(serverinfo['ServerInfo']['PlayerCount']),
                                'MapLabel: '+str(serverinfo['ServerInfo']['MapLabel']),
                                'GameMode: '+str(serverinfo['ServerInfo']['GameMode']),
                                'RoundState: '+str(serverinfo['ServerInfo']['RoundState']),
                                'Teams: '+str(serverinfo['ServerInfo']['Teams']),
                                'Team0Score: '+str(serverinfo['ServerInfo']['Team0Score']),
                                'Team1Score: '+str(serverinfo['ServerInfo']['Team1Score']),
                                'MatchEnded: '+str(serverinfo['ServerInfo']['MatchEnded']),
                                'WinningTeam: '+str(serverinfo['ServerInfo']['WinningTeam'])]
                            for part in parts:
                                response=response+'\n'+part
                        else:
                            response=user_message+': something went wrong'
                    case '!maplist':
                        log_to_discord=True
                        maplist=await rcon('MapList',{})
                        if maplist['Successful'] is True:
                            response=user_message+': successful'

                            for part in maplist['MapList']:
                                response=response+'\n'+str(part['MapId'])+' as '+str(part['GameMode'])
                        else:
                            response=user_message+': something went wrong'
                    case '!playerlist':
                        log_to_discord=True
                        inspectall=await rcon('InspectAll',{})
                        if inspectall['Successful'] is True:
                            response=user_message+': successful'

                            for player in inspectall['InspectList']:
                                response=response+'\n'+str(player['PlayerName'])+' ('+str(player['UniqueId'])+')'
                        else:
                            response=user_message+': something went wrong'
                    case '!resetsnd':
                        log_to_discord=True
                        resetsnd=await rcon('ResetSND',{})
                        if resetsnd['Successful'] is True:
                            response=user_message+' successful'
                        else:
                            response=user_message+' something went wrong'
                    case '!rotatemap':
                        log_to_discord=True
                        rotatemap=await rcon('RotateMap',{})
                        if rotatemap['Successful'] is True:
                            response=user_message+' successful'
                        else:
                            response=user_message+' something went wrong'
                    case '!setmap':
                        log_to_discord=True
                        rconparams={}
                        rconparams=get_rconparams_from_user_message(user_message)
                        if (len(rconparams))<1:
                            response='SwitchMap is missing parameters'
                        else:
                            switchmap=await rcon('SwitchMap',rconparams)
                            if switchmap['Successful'] is True:
                                response=user_message+' successful'
                            else:
                                response=user_message+' something went wrong'
                    case '!setrandommap':
                        log_to_discord=True
                        maplist=await rcon('MapList',{})
                        poolofrandommaps={}
                        i=0
                        for mapentry in maplist['MapList']:
                            if mapentry['GameMode'].upper()=='SND':
                                if mapentry['MapId'] not in poolofrandommaps:
                                    poolofrandommaps[i]=mapentry['MapId']
                                    i+=1
                        randommap=random.choice(poolofrandommaps)
                        gamemode='SND'
                        rconcmd='SwitchMap'
                        rconparams={randommap,gamemode}
                        switchmap=await rcon(rconcmd,rconparams)
                        if switchmap['Successful'] is True:
                            response=user_message+' successful'
                        else:
                            response=user_message+' something went wrong'
                    case '!kick':
                        log_to_discord=True
                        rconparams={}
                        rconparams=get_rconparams_from_user_message(user_message)
                        if (len(rconparams))<1:
                            response='Kick is missing parameters'
                        else:
                            kick=await rcon('Kick',{rconparams[0]})
                            if kick['Successful'] is True:
                                response=user_message+' successful'
                            else:
                                response=user_message+' something went wrong'
                    case '!ban':
                        log_to_discord=True
                        rconparams={}
                        rconparams=get_rconparams_from_user_message(user_message)
                        if (len(rconparams))<1:
                            response='Ban is missing parameters'
                        else:
                            ban=await rcon('Ban',{rconparams[0]})
                            if ban['Successful'] is True:
                                response=user_message+' successful'
                            else:
                                response=user_message+' something went wrong'
                    case '!unban':
                        log_to_discord=True
                        rconparams={}
                        rconparams=get_rconparams_from_user_message(user_message)
                        if (len(rconparams))<1:
                            response='Unban is missing parameters'
                        else:
                            unban=await rcon('Unban',{rconparams[0]})
                            if unban['Successful'] is True:
                                response=user_message+' successful'
                            else:
                                response=user_message+' something went wrong'
                    case '!modlist':
                        log_to_discord=True
                        modlist=await rcon('ModeratorList',{})
                        if modlist['Successful'] is True:
                            response=user_message+': successful'

                            for part in modlist['ModeratorList']:
                                response=response+'\n'+str(part)
                        else:
                            response=user_message+': something went wrong'
                    case '!blacklist':
                        log_to_discord=True
                        banlist=await rcon('Banlist',{})
                        if banlist['Successful'] is True:
                            response=user_message+': successful'

                            for part in banlist['BanList']:
                                response=response+'\n'+str(part)
                        else:
                            response=user_message+': something went wrong'
                    case '!pings':
                        log_to_discord=True
                        inspectall=await rcon('InspectAll',{})
                        if inspectall['Successful'] is True:
                            response=user_message+': successful'

                            for player in inspectall['InspectList']:
                                steamusers_id=player['UniqueId']
                                current_ping=player['Ping']

                                # get averages for current player
                                query="SELECT steamid64,ping,"
                                query+="AVG(ping) as avg_ping "
                                query+="FROM pings "
                                query+="WHERE steamid64 = %s"
                                values=[]
                                values.append(steamusers_id)
                                pings=dbquery(query,values)

                                average_ping=pings['rows'][0]['avg_ping']

                                response=response+'\n'+steamusers_id+': '+str(current_ping)+' (current), '+str(average_ping)+' (average)'
                        else:
                            response=user_message+': something went wrong'
                    case '!echo':
                        log_to_discord=True
                        if paramsgiven: # requires 1 param
                            echo_user_message_split0=user_message.split(' ',2)
                            echo_command=echo_user_message_split0[0]
                            echo_user_message_split1=user_message.split(echo_command+' ',2)
                            echo_param=echo_user_message_split1[1]
                            response=echo_param
                        else:
                            logmsg('warn','missing parameters')
                            response='missing parameters - use !help for more info'
                    case '!writeas':
                        log_to_discord=True
                        if len(user_message_split)>=3: # requires 2 params
                            wa_user_message_split0=user_message.split(' ',3)
                            wa_command=wa_user_message_split0[0]
                            wa_channel=wa_user_message_split0[1]
                            wa_user_message_split1=user_message.split(wa_command+' '+wa_channel+' ',2)
                            wa_param=wa_user_message_split1[1]
                            target_channel_id=config['bot-channel-ids'][wa_channel]
                            target_message=wa_param
                            target_channel=client.get_channel(int(target_channel_id))
                            try:
                                await target_channel.send(target_message)
                                response='message sent successfully'
                            except Exception as e:
                                response=str(e).strip()
                        else:
                            logmsg('warn','missing parameters')
                            response='missing parameters - use !help for more info'
                    case '!register':
                        log_to_discord=True
                        if paramsgiven:
                            user_message_split=user_message.split(' ',2)
                            steamid64=user_message_split[1]
                            discordid=message.author.id

                            # check if steamuser exists
                            logmsg('debug','checking if steamid64 exists in steamuser db')
                            query="SELECT id FROM steamusers WHERE steamid64 = %s LIMIT 1"
                            values=[]
                            values.append(steamid64)
                            steamusers=dbquery(query,values)
                            logmsg('debug','steamusers: '+str(steamusers))

                            # add steamuser if it does not exist
                            if steamusers['rowcount']==0:
                                logmsg('debug','steamid64 not found in steamusers db')
                                query="INSERT INTO steamusers (steamid64) VALUES (%s)"
                                values=[]
                                values.append(steamid64)
                                dbquery(query,values)
                                logmsg('info','created entry in steamusers db for steamid64 '+str(steamid64))
                            else:
                                logmsg('debug','steamid64 already exists in steamusers db')
                            
                            # get the steamuser id
                            query="SELECT id FROM steamusers WHERE steamid64 = %s LIMIT 1"
                            values=[]
                            values.append(steamid64)
                            steamusers=dbquery(query,values)
                            steamusers_id=steamusers['rows'][0]['id']
                            
                            # get discorduser id
                            logmsg('debug','checking if discordid exists in discordusers db')
                            query="SELECT id FROM discordusers WHERE discordid = %s LIMIT 1"
                            values=[]
                            values.append(discordid)
                            discordusers=dbquery(query,values)
                            logmsg('debug','discordusers: '+str(discordusers))

                            # add discorduser if it does not exist
                            if discordusers['rowcount']==0:
                                logmsg('debug','discordid not found in discordusers db')
                                query="INSERT INTO discordusers (discordid) VALUES (%s)"
                                values=[]
                                values.append(discordid)
                                dbquery(query,values)
                                logmsg('info','created entry in discordusers db for discordid '+str(discordid))
                            else:
                                logmsg('debug','discordid already exists in discordusers db')

                            # get discorduser id
                            query="SELECT id FROM discordusers WHERE discordid = %s LIMIT 1"
                            values=[]
                            values.append(discordid)
                            discordusers=dbquery(query,values)
                            discordusers_id=discordusers['rows'][0]['id']

                            # check if steamuser and discorduser are already registered
                            logmsg('debug','checking if entry in register db exists')
                            query="SELECT id FROM register WHERE steamusers_id = %s AND discordusers_id = %s LIMIT 1"
                            values=[]
                            values.append(steamusers_id)
                            values.append(discordusers_id)
                            register=dbquery(query,values)

                            # if discorduser is not registered with given steamuser, check if there is another steamid64
                            if register['rowcount']==0:
                                logmsg('debug','checking if discorduser is known with another steamuser')
                                query="SELECT id FROM register WHERE NOT steamusers_id = %s AND discordusers_id = %s LIMIT 1"
                                values=[]
                                values.append(steamusers_id)
                                values.append(discordusers_id)
                                register=dbquery(query,values)

                                # if discorduser is not registered with a different steamid64, add new entry in register
                                if register['rowcount']==0:
                                    logmsg('debug','not entry found in register db')
                                    query="INSERT INTO register (steamusers_id,discordusers_id) VALUES (%s,%s)"
                                    values=[]
                                    values.append(steamusers_id)
                                    values.append(discordusers_id)
                                    dbquery(query,values)
                                    logmsg('info','registered steamid64 '+str(steamid64)+' with discordid ('+str(discordid)+')')
                                    response='registered steamid64 ('+str(steamid64)+') with discordid ('+str(discordid)+')'
                                else:
                                    # discorduser is registered with a different steamid64
                                    register_id=register['rows'][0]['id']
                                    logmsg('warn','entry found in register db discordusers_id ('+str(discordusers_id)+') with id ('+str(register_id)+'), but with a different steamid64')
                                    response='already registered discordusers_id ('+str(discordusers_id)+') as id ('+str(register_id)+'), but with a different steamid64'
                            else:
                                # discorduser is already registered with given steamid64
                                register_id=register['rows'][0]['id']
                                logmsg('warn','entry found in register db for steamusers_id ('+str(steamusers_id)+') and discordusers_id ('+str(discordusers_id)+') with id ('+str(register_id)+')')
                                response='already registered steamusers_id ('+str(steamusers_id)+') with discordusers_id ('+str(discordusers_id)+') as id ('+str(register_id)+')'
                        else:
                            # missing parameters
                            logmsg('warn','missing parameter')
                            response='missing parameter - use !help for more info'
                    case '!unregister':
                        log_to_discord=True
                        if paramsgiven:
                            user_message_split=user_message.split(' ',2)
                            db_param=user_message_split[1]
                            steamid64=db_param
                            discordid=message.author.id
                            logmsg('debug','deleting entry in register for discorduser')

                            # get discorduser id
                            query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                            values=[]
                            values.append(discordid)
                            discordusers=dbquery(query,values)

                            if discordusers['rowcount']==0:
                                # actually delete
                                discordusers_id=discordusers['rows'][0]['id']
                                query="DELETE FROM register WHERE discordusers_id = %s LIMIT 1"
                                values=[]
                                values.append(discordusers_id)
                                register=dbquery(query,values)
                                logmsg('info','deleted entry in register for given discorduser: '+str(discordid)+')')
                                response='deleted entry in register for given discorduser: '+str(discordid)+')'
                            else:
                                # could not find discorduser with given discordid
                                logmsg('warn','could not find discorduser in discordusers db')
                                response='could not find discorduser in discordusers db'
                        else:
                            # missing parameters
                            logmsg('warn','missing parameter')
                            response='missing parameter - use !help for more info'
                    case '!getstats':
                        log_to_discord=True
                        discordid=str(message.author.id)

                        # get id from discordusers db
                        query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                        values=[]
                        values.append(discordid)
                        discordusers=dbquery(query,values)
                        if discordusers['rowcount']==0:
                            # discorduser does not exist
                            logmsg('warn','discordid not registered')
                            response='discordid not registered - use !help for more info'
                        else:
                            # discorduser exists
                            discordusers_id=discordusers['rows'][0]['id']

                            # get id for steamuser from register db
                            query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
                            values=[]
                            values.append(discordusers_id)
                            register=dbquery(query,values)
                            steamusers_id=register['rows'][0]['steamusers_id']

                            # get steamusers steamid64
                            query="SELECT steamid64 FROM steamusers WHERE id=%s LIMIT 1"
                            values=[]
                            values.append(steamusers_id)
                            steamusers=dbquery(query,values)
                            steamusers_steamid64=steamusers['rows'][0]['steamid64']

                            # get steamusers details
                            #query="SELECT ... FROM steamusers_details WHERE steamusers_id=%s LIMIT 1"
                            #values=[]
                            #values.append(steamusers_id)
                            #steamusers_details=dbquery(query,values)
                            #...

                            # get averages for steamuser from stats db
                            query="SELECT kills,deaths,assists,score,ping"
                            query+=",AVG(kills) as avg_kills,AVG(deaths) as avg_deaths,AVG(assists) as avg_assists,AVG(score) as avg_score,AVG(ping) as avg_ping"
                            query+=",MIN(kills) as min_kills,MIN(deaths) as min_deaths,MIN(assists) as min_assists,MIN(score) as min_score,MIN(ping) as min_ping"
                            query+=",MAX(kills) as max_kills,MAX(deaths) as max_deaths,MAX(assists) as max_assists,MAX(score) as max_score,MAX(ping) as max_ping"
                            query+=" FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                            query+="AND matchended IS TRUE AND playercount=10 "
                            query+="ORDER BY timestamp ASC"
                            values=[]
                            values.append(steamusers_id)
                            stats=dbquery(query,values)
                            logmsg('debug','stats: '+str(stats))

                            # get all entries for steamuser (for rowcount)
                            query="SELECT id FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                            query+="AND matchended IS TRUE AND playercount=10 "
                            query+="ORDER BY timestamp ASC"
                            values=[]
                            values.append(steamusers_id)
                            all_stats=dbquery(query,values)

                            limit_stats=3
                            if all_stats['rowcount']<limit_stats:
                                # not enough stats
                                logmsg('info','not enough data to generate stats ('+str(all_stats['rowcount'])+')')
                                response='not enough data to generate stats ('+str(all_stats['rowcount'])+')'
                            else:
                                parts=[
                                    user_message+': successful\n'
                                    '',
                                    'WIP',
                                    '',
                                    'Entries found for player '+str(steamusers_steamid64)+': '+str(all_stats['rowcount']),
                                    'AVG Score: '+str(stats['rows'][0]['avg_score']),
                                    'AVG Kills: '+str(stats['rows'][0]['avg_kills']),
                                    'AVG Deaths: '+str(stats['rows'][0]['avg_deaths']),
                                    'AVG Assists: '+str(stats['rows'][0]['avg_assists']),
                                    'AVG Ping: '+str(stats['rows'][0]['avg_ping'])
                                ]
                                response=''
                                for part in parts:
                                    response=response+'\n'+part
                    case '!getrank':
                        log_to_discord=True
                        discordid=str(message.author.id)

                        # get id from discordusers db
                        query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                        values=[]
                        values.append(discordid)
                        discordusers=dbquery(query,values)
                        if discordusers['rowcount']==0:
                            # discorduser does not exist
                            logmsg('warn','discordid not registered')
                            response='discordid not registered - use !help for more info'
                        else:
                            # discorduser exists
                            discordusers_id=discordusers['rows'][0]['id']

                            # get id for steamuser from register db
                            query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
                            values=[]
                            values.append(discordusers_id)
                            register=dbquery(query,values)
                            steamusers_id=register['rows'][0]['steamusers_id']

                            # get rank for steamuser from ranks db
                            query="SELECT rank,title FROM ranks WHERE steamusers_id=%s LIMIT 1"
                            values=[]
                            values.append(steamusers_id)
                            ranks=dbquery(query,values)

                            if ranks['rowcount']==0:
                                # no rank found
                                logmsg('warn','no rank found')
                                response='no rank found - maybe because there are not enough stats to generate them - use !getstats to show your stats'
                            else:
                                rank=ranks['rows'][0]['rank']
                                title=ranks['rows'][0]['title']
                                parts=[
                                    user_message+': successful\n'
                                    '',
                                    'WIP',
                                    '',
                                    'rank: '+str(rank),
                                    'title: '+str(title)]
                                response=''
                                for part in parts:
                                    response=response+'\n'+part
                    case '!genteams':
                        log_to_discord=True
                        if paramsgiven:
                            user_message_split=user_message.split(' ',2)
                            match_msg_id=user_message_split[1]

                            # get channel by id
                            #chnid=config['bot-channel-ids']['g-matches']
                            chnid=config['bot-channel-ids']['g-matches-test']
                            chn=await client.fetch_channel(chnid)

                            # get message by id
                            match_msg=await chn.fetch_message(match_msg_id)

                            # get guild members for later...
                            guild=await client.fetch_guild(config['guild-id'])

                            # iterate over reactions
                            count=0
                            players=[]
                            for reaction in match_msg.reactions:

                                # iterate over users of each reaction
                                async for user in reaction.users():

                                    # iterate over ALL GUILD MEMBERS to find the one with the same name...
                                    async for member in guild.fetch_members(limit=None):
                                        if member==user:
                                            reaction_userid=member.id
                                            players.append(member.id)

                                count=count+reaction.count

                            if count==10: # 10 players signed up
                                default_rank=5.5
                                players_ranked={}
                                for player in players:
                                    # get id from discordusers db
                                    query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                                    values=[]
                                    values.append(player)
                                    discordusers=dbquery(query,values)
                                    if discordusers['rowcount']==0: # discorduser does not exist
                                        players_ranked[player]=default_rank
                                    else: # discorduser exists
                                        discordusers_id=discordusers['rows'][0]['id']

                                        # get id for steamuser from register db
                                        query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
                                        values=[]
                                        values.append(discordusers_id)
                                        register=dbquery(query,values)
                                        steamusers_id=register['rows'][0]['steamusers_id']

                                        # get rank for steamuser from ranks db
                                        query="SELECT rank,title FROM ranks WHERE steamusers_id=%s LIMIT 1"
                                        values=[]
                                        values.append(steamusers_id)
                                        ranks=dbquery(query,values)

                                        if ranks['rowcount']==0: # no rank found
                                            players_ranked[player]=default_rank
                                        else:
                                            players_ranked[player]=ranks['rows'][0]['rank']
                                
                                players_ranked_sorted=dict(sorted(players_ranked.items(),key=operator.itemgetter(1),reverse=True))
                                logmsg('debug','players_ranked_sorted: '+str(players_ranked_sorted))

                                # generate 2 teams
                                team1=[]
                                team2=[]
                                number=0
                                for player in players_ranked_sorted:
                                    match number:
                                        case 0: team1.append(player)
                                        case 1: team2.append(player)
                                        case 2: team1.append(player)
                                        case 3: team2.append(player)
                                        case 4: team2.append(player)
                                        case 5: team1.append(player)
                                        case 6: team2.append(player)
                                        case 7: team1.append(player)
                                        case 8: team2.append(player)
                                        case 9: team1.append(player)
                                    number+=1
                                
                                logmsg('debug','team1: '+str(team1))
                                logmsg('debug','team2: '+str(team2))

                                # generate response message
                                part_team1="team 1: "
                                for player in team1:
                                    part_team1+="<@"+str(player)+"> "
                                part_team1+='  starting as T'

                                part_team2="team 2: "
                                for player in team2:
                                    part_team2+="<@"+str(player)+"> "
                                part_team2+='  starting as CT'

                                parts=[
                                        user_message+': successful\n'
                                        '',
                                        str(part_team1),
                                        str(part_team2)
                                ]
                                response=''
                                for part in parts:
                                    response=response+'\n'+part
                            else:
                                # not enough players
                                logmsg('warn','not enough players')
                                response='not enough players to generate teams - need 10'
                        else:
                            # missing parameters
                            logmsg('warn','missing parameter(s)')
                            response='missing parameter(s) - use !help for more info'
                if log_to_discord:
                    await log_discord('e-bot-log','[servus-publicus] command '+str(command)+' has been called by user '+str(message.author.name)+' ('+str(message.author.id)+')')
            else: # access denied
                logmsg('warn','missing access rights for command: '+str(command))
                response='missing access rights for command: '+str(command)+' - use !help for more info'

        # check if there is a response and if there is, send it
        if int(len(response))<1:
            logmsg('debug','nothing to do - response was found empty')
        else:
            logmsg('debug','response: '+str(response))
            try:
                await message.author.send(response) if is_private else await message.channel.send(response)
            except Exception as e:
                logmsg('debug',str(e))


    # event: bot ready
    @client.event
    async def on_ready():
        logmsg('info',str(meta['name'])+' '+str(meta['version'])+' is now running')


    # event: possible command received
    @client.event
    async def on_message(message):
        if message.author==client.user:
            logmsg('debug','message.author == client.user -> dont get high on your own supply')
            return
        username=str(message.author)
        user_message=str(message.content)
        channel=str(message.channel)

        is_private=False
        if len(user_message)>0:
            if user_message[0]=='?':
                user_message=user_message[1:]
                is_private=True
            
        await send_answer(client,message,user_message,is_private)


    # run discord client
    client.run(config['bot_token'])


    # keywords for target log
    keywords=[
        'Rotating map',
        'LogLoad: LoadMap',
        'Updating blacklist'
        'StartPlay',
        '"State":',
        'Preparing to exit',
        'LogHAL',
        'Server Status Helper',
        'Rcon: User',
        'SND: Waiting for players',
        'long time between ticks',
        'Login request',
        'Client netspeed',
        'Join request',
        'Join succeeded',
        'LogNet: UChannel::Close',
        '"Killer":',
        '"KillData":',
        '"KillerTeamID":',
        '"Killed":',
        '"KilledTeamID":',
        '"KilledBy":',
        '"Headshot":',
        'LogTemp: Rcon: KickPlayer',
        'LogTemp: Rcon: BanPlayer',
        'BombData',
        '"Player":',
        '"BombInteraction":']


    # read the target log, find keywords and do stuff on match
    logmsg('info','starting to read from the target log file...')
    loglines=follow_log(config['logfile_path'])
    for line in loglines:
        if line!="":
            found_keyword=find_keyword_in_line(line,keywords)
            if found_keyword!='':
                process_found_keyword(line,found_keyword)