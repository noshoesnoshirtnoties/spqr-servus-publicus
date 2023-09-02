import os
import json
import random
import asyncio
import logging
import mysql.connector
from pathlib import Path
from pavlov import PavlovRCON
from datetime import datetime,timezone

# gather information to create a response
async def get_response(config,logfile,client,message,user_message,is_private):

    response=''

    def logmsg(logfile,lvl,msg):
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

    logmsg(logfile,'debug','client: '+str(client))
    #logmsg(logfile,'debug','message: '+str(message))
    logmsg(logfile,'debug','type(message): '+str(type(message)))
    logmsg(logfile,'info','message.id: '+str(message.id))
    logmsg(logfile,'info','message.channel: '+str(message.channel))
    logmsg(logfile,'info','message.channel.id: '+str(message.channel.id))
    logmsg(logfile,'debug','message.author: '+str(message.author))
    logmsg(logfile,'info','message.author.id: '+str(message.author.id))
    logmsg(logfile,'info','message.author.name: '+str(message.author.name))
    logmsg(logfile,'info','message.author.global_name: '+str(message.author.global_name))
    if str(message.guild)!="None":
        logmsg(logfile,'debug','message.guild: '+str(message.guild))
        logmsg(logfile,'debug','message.guild.id: '+str(message.guild.id))
        logmsg(logfile,'debug','message.guild.name: '+str(message.guild.name))
    else:
        logmsg(logfile,'debug','message.guild: '+str(message.guild))
    #logmsg(logfile,'debug','user_message: '+str(user_message))
    logmsg(logfile,'debug','is_private: '+str(is_private))

    def dbquery(query,values):
        logmsg(logfile,'debug','dbquery called')
        logmsg(logfile,'debug','query: '+str(query))
        logmsg(logfile,'debug','values: '+str(values))
        logmsg(logfile,'debug','len(values): '+str(len(values)))
        conn=mysql.connector.connect(
            host=config['mysqlhost'],
            port=config['mysqlport'],
            user=config['mysqluser'],
            password=config['mysqlpass'],
            database=config['mysqldatabase'])
        logmsg(logfile,'debug','conn: '+str(conn))
        cursor=conn.cursor(buffered=True)
        cursor.execute(query,(values))
        conn.commit()
        data={}
        data['rowcount']=cursor.rowcount
        logmsg(logfile,'debug','data[rowcount]: '+str(data['rowcount']))
        query_type0=query.split(' ',2)
        query_type=str(query_type0[0])
        logmsg(logfile,'debug','query_type: '+query_type)
        if query_type.upper()=="SELECT":
            rows=cursor.fetchall()
            logmsg(logfile,'debug','rows: '+str(rows))
            i=0
            data['rows']={}
            for row in rows:
                logmsg(logfile,'debug','row: '+str(row))
                data['rows'][0]=row
                i+=1
        else:
            data['rows']=False
        logmsg(logfile,'debug','dbquery data: '+str(data))
        cursor.close()
        conn.close()
        logmsg(logfile,'debug','conn and conn closed')
        return data

    async def rcon(rconcmd,rconparams):
        logmsg(logfile,'debug','rcon called')
        logmsg(logfile,'debug','rconcmd: '+str(rconcmd))
        logmsg(logfile,'debug','rconparams: '+str(rconparams))
        conn=PavlovRCON(config['rconip'],config['rconport'],config['rconpass'])
        for rconparam in rconparams:
            rconcmd+=' '+rconparam
        data=await conn.send(rconcmd)
        data_json=json.dumps(data)
        data=json.loads(data_json)
        logmsg(logfile,'debug','rcon data: '+str(data))
        await conn.send('Disconnect')
        return data

    def get_rconparams_from_user_message(user_message):
        maxnumparams=3
        numsplitparts=maxnumparams+1
        user_message_split=user_message.split(' ',numsplitparts)
        rconparams=[]
        i=0
        while i<(len(user_message_split)-1):
            pos=i+1 # to strip the command itself
            rconparams.append(user_message_split[pos])
            i+=1
        return rconparams

    async def get_serverinfo():
        logmsg(logfile,'info','get_serverinfo called')
        data=await rcon('ServerInfo',{})
        serverinfo=data['ServerInfo']
        logmsg(logfile,'debug','serverinfo: '+str(serverinfo))

        # make sure gamemode is uppercase
        serverinfo['GameMode']=serverinfo['GameMode'].upper()

        # demo rec counts as 1 player in SND
        if serverinfo['GameMode']=="SND":
            numberofplayers0=serverinfo['PlayerCount'].split('/',2)
            numberofplayers1=numberofplayers0[0]
            if int(numberofplayers1)>0: # demo only exists if there is a player?
                numberofplayers2=(int(numberofplayers1)-1)
            else:
                numberofplayers2=(numberofplayers0[0])
            maxplayers=numberofplayers0[1]
            numberofplayers=str(numberofplayers2)+'/'+str(maxplayers)
        else:
            numberofplayers=serverinfo['PlayerCount']
        serverinfo['PlayerCount']=numberofplayers

        # for SND get info if match has ended and which team won if there were teams
        serverinfo['MatchEnded']=False
        serverinfo['WinningTeam']='none'
        if serverinfo['GameMode']=="SND" and serverinfo['Teams'] is True:
            if int(serverinfo['Team0Score'])==10:
                serverinfo['MatchEnded']=True
                serverinfo['WinningTeam']='team0'
            elif int(serverinfo['Team1Score'])==10:
                serverinfo['MatchEnded']=True
                serverinfo['WinningTeam']='team1'
        else:
            serverinfo['Team0Score']=0
            serverinfo['Team1Score']=0
        if serverinfo['MatchEnded'] is True:
            logmsg(logfile,'info','end of match detected')
            logmsg(logfile,'info','team0score: '+str(serverinfo['Team0Score']))
            logmsg(logfile,'info','team1score: '+str(serverinfo['Team1Score']))
        data['ServerInfo']=serverinfo
        return data

    paramsgiven=False
    user_message_split=user_message.split(' ',2)
    command=user_message_split[0]
    #logmsg(logfile,'debug','command: '+str(command))
    paramsgiven=False
    if len(user_message_split)>1:
        logmsg(logfile,'debug','params have been given')
        paramsgiven=True

    is_praefectus=False
    for id in config['praefectus-member']:
        if str(id)==str(message.author.id):
            is_praefectus=True
            logmsg(logfile,'info','user has praefectus role')
    is_senate=False
    for id in config['senate-member']:
        if str(id)==str(message.author.id):
            is_senate=True
            logmsg(logfile,'info','user has senate role')
    is_architecti=False
    for id in config['architecti-member']:
        if str(id)==str(message.author.id):
            is_architecti=True
            logmsg(logfile,'info','user has architecti role')

    access_granted=True
    for praefectuscmd in config['praefectus-cmds']:
        if praefectuscmd==command:
            logmsg(logfile,'info','praefectus-cmd found')
            if is_praefectus is not True:
                logmsg(logfile,'warn','missing access rights for command: '+str(command))
                access_granted=False
    for senatecmd in config['senate-cmds']:
        if senatecmd==command:
            logmsg(logfile,'info','senate-cmd found')
            if is_senate is not True:
                logmsg(logfile,'warn','missing access rights for command: '+str(command))
                access_granted=False
    for architecticmd in config['architecti-cmds']:
        if architecticmd==command:
            logmsg(logfile,'info','architecti-cmd found')
            if is_architecti is not True:
                logmsg(logfile,'warn','missing access rights for command: '+str(command))
                access_granted=False

    if access_granted:
        logmsg(logfile,'info','access to command has been granted')
        match command:
            case '!help':
                response=Path('txt/help.txt').read_text()

            case '!spqr':
                response=Path('txt/spqr.txt').read_text()

            case '!loremipsum':
                response=Path('txt/loremipsum.txt').read_text()

            case '!invite':
                response=Path('txt/invite.txt').read_text()

            case '!roles':
                response=Path('txt/roles.txt').read_text()

            case '!rules':
                response=Path('txt/rules.txt').read_text()

            case '!reqs':
                response=Path('txt/requirements.txt').read_text()

            case '!suntzu':
                randomquote=random.choice(os.listdir('txt/suntzu'))
                quotepath="txt/suntzu/"+randomquote
                response=Path(str(quotepath)).read_text()

            case '!serverinfo':
                serverinfo=await get_serverinfo()
                if serverinfo['Successful'] is True:
                    logmsg(logfile,'debug','!serverinfo successful')

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
                maplist=await rcon('MapList',{})
                if maplist['Successful'] is True:
                    logmsg(logfile,'debug','!maplist successful')
                    response=user_message+': successful'

                    for part in maplist['MapList']:
                        response=response+'\n'+part['MapId']+' as '+part['GameMode']
                else:
                    response=user_message+': something went wrong'

            case '!resetsnd':
                resetsnd=await rcon('ResetSND',{})
                if resetsnd['Successful'] is True:
                    response=user_message+' successful'
                else:
                    response=user_message+' something went wrong'

            case '!rotatemap':
                rotatemap=await rcon('RotateMap',{})
                if rotatemap['Successful'] is True:
                    response=user_message+' successful'
                else:
                    response=user_message+' something went wrong'

            case '!setmap':
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
                rconparams={}
                rconparams[0]=randommap
                rconparams[1]=gamemode
                switchmap=await rcon(rconcmd,rconparams)
                if switchmap['Successful'] is True:
                    response=user_message+' successful'
                else:
                    response=user_message+' something went wrong'

            case '!kick':
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

            case '!echo':
                if paramsgiven: # requires 1 param
                    echo_user_message_split0=user_message.split(' ',2)
                    echo_command=echo_user_message_split0[0]
                    echo_user_message_split1=user_message.split(echo_command+' ',2)
                    echo_param=echo_user_message_split1[1]
                    logmsg(logfile,'debug','echo_user_message_split0: '+str(echo_user_message_split0))
                    logmsg(logfile,'debug','echo_user_message_split1: '+str(echo_user_message_split1))
                    logmsg(logfile,'debug','echo_command: '+str(echo_command))
                    logmsg(logfile,'debug','echo_param: '+str(echo_param))
                    response=echo_param
                else:
                    logmsg(logfile,'warn','missing parameters')
                    response='missing parameters - use !help for more info'

            case '!writeas':
                if len(user_message_split)>=3: # requires 2 params
                    wa_user_message_split0=user_message.split(' ',3)
                    wa_command=wa_user_message_split0[0]
                    wa_channel=wa_user_message_split0[1]
                    wa_user_message_split1=user_message.split(wa_command+' '+wa_channel+' ',2)
                    wa_param=wa_user_message_split1[1]
                    logmsg(logfile,'debug','user_message: '+str(user_message))
                    logmsg(logfile,'debug','wa_user_message_split0: '+str(wa_user_message_split0))
                    logmsg(logfile,'debug','wa_user_message_split1: '+str(wa_user_message_split1))
                    logmsg(logfile,'debug','wa_command: '+str(wa_command))
                    logmsg(logfile,'debug','wa_channel: '+str(wa_channel))
                    logmsg(logfile,'debug','wa_param: '+str(wa_param))
                    target_channel_id=config['bot-channel-ids'][wa_channel]
                    target_message=wa_param
                    target_channel=client.get_channel(int(target_channel_id))
                    logmsg(logfile,'debug','target_channel: '+str(target_channel_id))
                    logmsg(logfile,'debug','target_channel: '+str(target_channel))
                    try:
                        await target_channel.send(target_message)
                        response='message sent successfully'
                    except Exception as e:
                        response=str(e).strip()
                else:
                    logmsg(logfile,'warn','missing parameters')
                    response='missing parameters - use !help for more info'

            case '!register':
                if paramsgiven:
                    user_message_split=user_message.split(' ',2)
                    db_param=user_message_split[1]
                    steamid64=db_param
                    discordid=message.author.id

                    # check if steamuser exists
                    logmsg(logfile,'debug','checking if steamid64 exists in steamuser db')
                    query="SELECT id FROM steamusers WHERE steamid64 = %s LIMIT 1"
                    values=[]
                    values.append(steamid64)
                    steamusers=dbquery(query,values)

                    # add steamuser if it does not exist
                    if steamusers['rowcount']==0:
                        logmsg(logfile,'debug','steamid64 not found in steamusers db')
                        query="INSERT INTO steamusers (steamid64) VALUES (%s)"
                        values=[]
                        values.append(steamid64)
                        dbquery(query,values)
                        logmsg(logfile,'info','created entry in steamusers db for steamid64 '+str(steamid64))
                    else:
                        logmsg(logfile,'debug','steamid64 already exists in steamusers db')
                    
                    # get the steamuser id
                    query="SELECT id FROM steamusers WHERE steamid64=%s LIMIT 1"
                    values=[]
                    values.append(steamid64)
                    steamusers=dbquery(query,values)
                    steamusers_id=data['rows'][0][0]
                    
                    # get discorduser id
                    logmsg(logfile,'debug','checking if discordid exists in discordusers db')
                    query="SELECT id FROM discordusers WHERE discordid = %s LIMIT 1"
                    values=[]
                    values.append(discordid)
                    discordusers=dbquery(query,values)

                    # add discorduser if it does not exist
                    if discordusers['rowcount']==0:
                        logmsg(logfile,'debug','discordid not found in discordusers db')
                        query="INSERT INTO discordusers (discordid) VALUES (%s)"
                        values=[]
                        values.append(discordid)
                        dbquery(query,values)
                        logmsg(logfile,'info','created entry in discordusers db for discordid '+str(discordid))
                    else:
                        logmsg(logfile,'debug','discordid already exists in discordusers db')

                    # get discorduser id
                    query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                    values=[]
                    values.append(discordid)
                    discordusers=dbquery(query,values)
                    discordusers_id=data['rows'][0][0]

                    # check if steamuser and discorduser are already registered
                    logmsg(logfile,'debug','checking if entry in register db exists')
                    query="SELECT id FROM register WHERE steamusers_id = %s AND discordusers_id = %s LIMIT 1"
                    values=[]
                    values.append(steamusers_id)
                    values.append(discordusers_id)
                    register=dbquery(query,values)

                    # if discorduser is not registered with given steamuser, check if there is another steamid64
                    if register['rowcount']==0:
                        logmsg(logfile,'debug','checking if discorduser is known with another steamuser')
                        query="SELECT id FROM register WHERE NOT steamusers_id = %s AND discordusers_id = %s LIMIT 1"
                        values=[]
                        values.append(steamusers_id)
                        values.append(discordusers_id)
                        register=dbquery(query,values)

                        # if discorduser is not registered with a different steamid64, add new entry in register 
                        if register['rowcount']==0:
                            logmsg(logfile,'debug','not entry found in register db')
                            query="INSERT INTO register (steamusers_id,discordusers_id) VALUES (%s,%s)"
                            values=[]
                            values.append(steamusers_id)
                            values.append(discordusers_id)
                            dbquery(query,values)
                            logmsg(logfile,'info','registered steamid64 '+str(steamid64)+' with discordid ('+str(discordid)+')')
                            response='registered steamid64 ('+str(steamid64)+') with discordid ('+str(discordid)+')'
                        else:
                            # discorduser is registered with a different steamid64
                            register_id=data['rows'][0][0]
                            logmsg(logfile,'warn','entry found in register db discordusers_id ('+str(discordusers_id)+') with id ('+str(register_id)+'), but with a different steamid64')
                            response='already registered discordusers_id ('+str(discordusers_id)+') as id ('+str(register_id)+'), but with a different steamid64'
                    else:
                        # discorduser is already registered with given steamid64
                        register_id=data['rows'][0][0]
                        logmsg(logfile,'warn','entry found in register db for steamusers_id ('+str(steamusers_id)+') and discordusers_id ('+str(discordusers_id)+') with id ('+str(register_id)+')')
                        response='already registered steamusers_id ('+str(steamusers_id)+') with discordusers_id ('+str(discordusers_id)+') as id ('+str(register_id)+')'
                else:
                    # missing parameters
                    logmsg(logfile,'warn','missing parameter')
                    response='missing parameter - use !help for more info'

            case '!unregister':
                if paramsgiven:
                    user_message_split=user_message.split(' ',2)
                    db_param=user_message_split[1]
                    steamid64=db_param
                    discordid=message.author.id
                    logmsg(logfile,'debug','deleting entry in register for discorduser')

                    # get discorduser id
                    query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                    values=[]
                    values.append(discordid)
                    discordusers=dbquery(query,values)

                    if discordusers['rowcount']==0:
                        # actually delete
                        discordusers_id=discordusers['rows'][0][0]
                        query="DELETE FROM register WHERE discordusers_id = %s LIMIT 1"
                        values=[]
                        values.append(discordusers_id)
                        register=dbquery(query,values)
                        logmsg(logfile,'info','deleted entry in register for given discorduser: '+str(discordid)+')')
                        response='deleted entry in register for given discorduser: '+str(discordid)+')'
                    else:
                        # could not find discorduser with given discordid
                        logmsg(logfile,'warn','could not find discorduser in discordusers db')
                        response='could not find discorduser in discordusers db'
                else:
                    # missing parameters
                    logmsg(logfile,'warn','missing parameter')
                    response='missing parameter - use !help for more info'

            case '!getstats':
                discordid=str(message.author.id)

                # get id from discordusers db
                query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                values=[]
                values.append(discordid)
                discordusers=dbquery(query,values)
                if discordusers['rowcount']==0:
                    # discorduser does not exist
                    logmsg(logfile,'warn','discordid not registered')
                    response='discordid not registered - use !help for more info'
                else:
                    # discorduser exists
                    discordusers_id=discordusers['rows'][0][0]

                    # get id for steamuser from register db
                    query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
                    values=[]
                    values.append(discordusers_id)
                    register=dbquery(query,values)
                    steamusers_id=register['rows'][0][0]

                    # get global averages for steamuser from stats db
                    query="SELECT kills,deaths,average,score,ping"
                    query+=",AVG(kills) as avg_kills,AVG(deaths) as avg_deaths,AVG(average) as avg_average,AVG(score) as avg_score,AVG(ping) as avg_ping"
                    query+=",MIN(kills) as min_kills,MIN(deaths) as min_deaths,MIN(average) as min_average,MIN(score) as min_score,MIN(ping) as min_ping"
                    query+=",MAX(kills) as max_kills,MAX(deaths) as max_deaths,MAX(average) as max_average,MAX(score) as max_score,MAX(ping) as max_ping"
                    query+=" FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                    #query+="AND matchended IS TRUE AND playercount>9 "
                    query+="ORDER BY timestamp ASC"
                    values=[]
                    values.append(steamusers_id)
                    stats=dbquery(query,values)
                    logmsg(logfile,'debug','stats: '+str(stats))

                    query="SELECT id FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                    #query+="AND matchended IS TRUE AND playercount>9 "
                    query+="ORDER BY timestamp ASC"
                    values=[]
                    values.append(steamusers_id)
                    all_stats=dbquery(query,values)

                    limit_stats=2
                    if all_stats['rowcount']<limit_stats:
                        # not enough stats
                        logmsg(logfile,'info','not enough data to generate stats ('+str(all_stats['rowcount'])+')')
                        response='not enough data to generate stats ('+str(all_stats['rowcount'])+')'
                    else:
                        parts=[
                            user_message+': successful\n'
                            '',
                            'VERY MUCH WIP',
                            '',
                            'avg_score: '+str(stats['rows'][0][8]),
                            'avg_average: '+str(stats['rows'][0][7]),
                            'avg_kills: '+str(stats['rows'][0][5]),
                            'avg_deaths: '+str(stats['rows'][0][6]),
                            'avg_ping: '+str(stats['rows'][0][9]),
                            'min_score: '+str(stats['rows'][0][13]),
                            'min_average: '+str(stats['rows'][0][12]),
                            'min_kills: '+str(stats['rows'][0][10]),
                            'min_deaths: '+str(stats['rows'][0][11]),
                            'min_ping: '+str(stats['rows'][0][14]),
                            'max_score: '+str(stats['rows'][0][18]),
                            'max_average: '+str(stats['rows'][0][17]),
                            'max_kills: '+str(stats['rows'][0][15]),
                            'max_deaths: '+str(stats['rows'][0][16]),
                            'max_ping: '+str(stats['rows'][0][19])]
                        response=''
                        for part in parts:
                            response=response+'\n'+part

            case '!getrank':
                discordid=str(message.author.id)

                # get id from discordusers db
                query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
                values=[]
                values.append(discordid)
                discordusers=dbquery(query,values)
                if discordusers['rowcount']==0:
                    # discorduser does not exist
                    logmsg(logfile,'warn','discordid not registered')
                    response='discordid not registered - use !help for more info'
                else:
                    # discorduser exists
                    discordusers_id=discordusers['rows'][0][0]

                    # get id for steamuser from register db
                    query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
                    values=[]
                    values.append(discordusers_id)
                    register=dbquery(query,values)
                    steamusers_id=register['rows'][0][0]

                    # get stats for steamuser from stats db
                    query="SELECT kills,deaths,average,score,ping"
                    query+=",AVG(kills) as avg_kills,AVG(deaths) as avg_deaths,AVG(average) as avg_average,AVG(score) as avg_score,AVG(ping) as avg_ping"
                    query+=",MIN(kills) as min_kills,MIN(deaths) as min_deaths,MIN(average) as min_average,MIN(score) as min_score,MIN(ping) as min_ping"
                    query+=",MAX(kills) as max_kills,MAX(deaths) as max_deaths,MAX(average) as max_average,MAX(score) as max_score,MAX(ping) as max_ping"
                    query+=" FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                    #query+="AND matchended IS TRUE AND playercount>9 "
                    query+="ORDER BY timestamp ASC"
                    values=[]
                    values.append(steamusers_id)
                    player_stats=dbquery(query,values)
                    logmsg(logfile,'debug','player_stats: '+str(player_stats))

                    query="SELECT id FROM stats WHERE gamemode='SND' AND steamusers_id=%s "
                    #query+="AND matchended IS TRUE AND playercount>9 "
                    query+="ORDER BY timestamp ASC"
                    values=[]
                    values.append(steamusers_id)
                    player_all_stats=dbquery(query,values)

                    limit_stats=2
                    if player_all_stats['rowcount']<limit_stats:
                        # not enough stats
                        logmsg(logfile,'info','not enough data to generate stats ('+str(player_all_stats['rowcount'])+')')
                        response='not enough data to generate stats ('+str(player_all_stats['rowcount'])+')'
                    else:
                        # get stats for all users from stats db
                        query="SELECT kills,deaths,average,score,ping"
                        query+=",AVG(kills) as avg_kills,AVG(deaths) as avg_deaths,AVG(average) as avg_average,AVG(score) as avg_score,AVG(ping) as avg_ping"
                        query+=",MIN(kills) as min_kills,MIN(deaths) as min_deaths,MIN(average) as min_average,MIN(score) as min_score,MIN(ping) as min_ping"
                        query+=",MAX(kills) as max_kills,MAX(deaths) as max_deaths,MAX(average) as max_average,MAX(score) as max_score,MAX(ping) as max_ping"
                        query+=" FROM stats WHERE gamemode='SND' "
                        #query+="AND matchended IS TRUE AND playercount>9 "
                        query+="ORDER BY timestamp ASC"
                        values=[]
                        all_stats=dbquery(query,values)
                        logmsg(logfile,'debug','all_stats: '+str(all_stats))

                        player_avg_score=player_stats['rows'][0][8]
                        player_avg_average=player_stats['rows'][0][7]
                        player_avg_kills=player_stats['rows'][0][5]
                        player_avg_deaths=player_stats['rows'][0][6]
                        player_avg_ping=player_stats['rows'][0][9]

                        player_min_score=player_stats['rows'][0][13]
                        player_min_average=player_stats['rows'][0][12]
                        player_min_kills=player_stats['rows'][0][10]
                        player_min_deaths=player_stats['rows'][0][11]
                        player_min_ping=player_stats['rows'][0][14]

                        player_max_score=player_stats['rows'][0][18]
                        player_max_average=player_stats['rows'][0][17]
                        player_max_kills=player_stats['rows'][0][15]
                        player_max_deaths=player_stats['rows'][0][16]
                        player_max_ping=player_stats['rows'][0][19]

                        all_avg_score=all_stats['rows'][0][8]
                        all_avg_average=all_stats['rows'][0][7]
                        all_avg_kills=all_stats['rows'][0][5]
                        all_avg_deaths=all_stats['rows'][0][6]
                        all_avg_ping=all_stats['rows'][0][9]

                        all_min_score=all_stats['rows'][0][13]
                        all_min_average=all_stats['rows'][0][12]
                        all_min_kills=all_stats['rows'][0][10]
                        all_min_deaths=all_stats['rows'][0][11]
                        all_min_ping=all_stats['rows'][0][14]

                        all_max_score=all_stats['rows'][0][18]
                        all_max_average=all_stats['rows'][0][17]
                        all_max_kills=all_stats['rows'][0][15]
                        all_max_deaths=all_stats['rows'][0][16]
                        all_max_ping=all_stats['rows'][0][19]

                        if all_max_score<1:
                            all_max_score=1
                        if all_max_average<1:
                            all_max_average=1
                        if all_max_kills<1:
                            all_max_kills=1
                        if all_max_deaths<1:
                            all_max_deaths=1
                        if all_max_ping<1:
                            all_max_ping=1

                        relative_score=10*player_max_score/all_max_score
                        relative_average=10*player_max_average/all_max_average
                        relative_kills=10*player_max_kills/all_max_kills
                        relative_deaths=10*player_max_deaths/all_max_deaths
                        relative_ping=10*player_max_ping/all_max_ping

                        score_rank=int(relative_score)
                        if score_rank<4:
                            score_rank_title='Bronze'
                        elif score_rank<7:
                            score_rank_title='Silver'
                        elif score_rank<10:
                            score_rank_title='Gold'
                        else:
                            score_rank_title='Platinum'

                        average_rank=int(relative_average)
                        if average_rank<4:
                            average_rank_title='Bronze'
                        elif average_rank<7:
                            average_rank_title='Silver'
                        elif average_rank<10:
                            average_rank_title='Gold'
                        else:
                            average_rank_title='Platinum'

                        parts=[
                            user_message+': successful\n',
                            '',
                            'VERY MUCH WIP',
                            '',
                            'rank based on score: '+str(score_rank)+' ('+score_rank_title+')',
                            'rank based on average: '+str(score_rank)+' ('+score_rank_title+')']

                        response=''
                        for part in parts:
                            response=response+'\n'+part

    else: # access denied
        logmsg(logfile,'warn','missing access rights for command: '+str(command))
        response='missing access rights for command: '+str(command)+' - use !help for more info'
    return response