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
        filename='../spqr-servus-publicus.log',
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


    # event: discord bot ready
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

