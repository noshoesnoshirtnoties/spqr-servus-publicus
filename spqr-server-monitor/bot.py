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
        filename='../spqr-server-monitor.log',
        filemode='a',
        format='%(asctime)s,%(msecs)d [%(levelname)s] %(message)s',
        datefmt='%m/%d/%Y %H:%M:%S',
        level=level)
    logfile=logging.getLogger('logfile')


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
    def log_to_discord(message):
        logmsg('debug','log_to_discord called')

        intents=discord.Intents.default()
        intents.message_content=True
        client=discord.Client(intents=intents)

        @client.event
        async def on_ready():
            channel=client.get_channel(int(config['bot-channel-ids']['e-bot-log']))
            try:
                await channel.send(message)
            except Exception as e:
                logmsg('debug',str(e))
            await client.close()

        client.run(config['bot_token'])


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
                limit=config['autopin_limit_default']
                if serverinfo['ServerInfo']['GameMode']=="TDM":
                    limit=config['autopin_limit_tdm']
                elif serverinfo['ServerInfo']['GameMode']=="DM":
                    limit=config['autopin_limit_snd']

                # decide wether to set the pin or remove it
                playercount_split=serverinfo['ServerInfo']['PlayerCount'].split('/',2)
                if (int(playercount_split[0]))>=limit:
                    logmsg('debug','limit ('+str(limit)+') reached - setting pin '+str(config['autopin_pin'])+'')
                    command='SetPin'
                    params={config['autopin_pin']}
                    data=await rcon(command,params)
                else:
                    logmsg('debug','below limit ('+str(limit)+') - removing pin')
                    command='SetPin'
                    params={''}
                    data=await rcon(command,params)
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
                else:
                    logmsg('warn','not pulling stats because gamemode is not SND')
            else:
                logmsg('warn','not pulling stats because matchend is not True')
        else:
            logmsg('warn','not pulling stats because serverinfo returned unsuccessful')


    # function: decide what to do once a keyword appears
    def process_found_keyword(line,keyword):
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
            #case 'Rcon: User':
            #    rconclient0=line.split(' authenticated ',2)
            #    if len(rconclient0)>1:
            #        rconclient=rconclient0[1]
            #    else:
            #        rconclient=rconclient0[0]
            #    logmsg('debug','rcon client auth: '+str(rconclient).strip())
            case 'Join succeeded':
                joinuser0=line.split('succeeded: ',2)
                joinuser=joinuser0[1]
                logmsg('info','join successful for user: '+str(joinuser).strip())
                log_to_discord('[server-monitor] join successful for user: '+str(joinuser).strip())
                asyncio.run(action_autopin())
            case 'LogNet: UChannel::Close':
                leaveuser0=line.split('RemoteAddr: ',2)
                leaveuser1=leaveuser0[1].split(',',2)
                leaveuser=leaveuser1[0]
                logmsg('info','user left the server: '+str(leaveuser).strip())
                log_to_discord('[server-monitor] user left the server: IP_REMOVED')
                asyncio.run(action_autopin())
            case '"KillData":':
                logmsg('info','a player died...')
                asyncio.run(action_autokickhighping())
            case 'LogTemp: Rcon: KickPlayer':
                kickplayer0=line.split('KickPlayer ',2)
                kickplayer=kickplayer0[1]
                logmsg('info','player kicked: '+str(kickplayer).strip())
                log_to_discord('[server-monitor] user '+str(kickplayer).strip()+' has been kicked')
            case 'LogTemp: Rcon: BanPlayer':
                banplayer0=line.split('BanPlayer ',2)
                banplayer=banplayer0[1]
                logmsg('info','player banned: '+str(banplayer).strip())
                log_to_discord('[server-monitor] user '+str(banplayer).strip()+' has been banned')


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


    # read the target log, find keywords and do stuff on match
    logmsg('info',str(meta['name'])+' '+str(meta['version'])+' is now running')
    log_to_discord('[server-monitor] server-monitor is now active')
    loglines=follow_log(config['logfile_path'])
    for line in loglines:
        if line!="":
            found_keyword=find_keyword_in_line(line,keywords=[
                'Rotating map',
                'LogLoad: LoadMap',
                'StartPlay',
                '"State":',
                'Preparing to exit',
                'LogHAL',
                'Server Status Helper',
                'Rcon: User',
                'Join succeeded',
                'LogNet: UChannel::Close',
                '"KillData":',
                'LogTemp: Rcon: KickPlayer',
                'LogTemp: Rcon: BanPlayer'])
            if found_keyword!='':
                process_found_keyword(line,found_keyword)