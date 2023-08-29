import os
import json
import random
import discord
import logging
import asyncio
import mysql.connector
from pathlib import Path
from pavlov import PavlovRCON
from datetime import datetime,timezone

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

async def dbquery(config,logfile,query,values):
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
    i=0
    data['values']={}
    for value in cursor:
      logmsg(logfile,'debug','value: '+str(value))
      data['values'][0]=format(value)
      i+=1
  else:
    data['rows']=False
    data['values']=False
  logmsg(logfile,'debug','data: '+str(data))
  cursor.close()
  conn.close()
  logmsg(logfile,'debug','conn and conn closed')
  return data

async def rcon(config,logfile,rconcmd,rconparams):
  logmsg(logfile,'debug','rcon called')
  logmsg(logfile,'debug','rconcmd: '+str(rconcmd))
  logmsg(logfile,'debug','rconparams: '+str(rconparams))
  conn=PavlovRCON(config['rconip'],config['rconport'],config['rconpass'])
  for rconparam in rconparams:
    rconcmd+=' '+str(rconparam)
  data=await conn.send(rconcmd)
  data_json=json.dumps(data)
  data=json.loads(data_json)
  logmsg(logfile,'debug','data: '+str(data))
  await conn.send('Disconnect')
  return data

def get_rconparams(user_message):
  maxnumparams=3
  numsplitparts=maxnumparams+1
  user_message_split=user_message.split(' ',numsplitparts)
  rconparams={}
  i=0
  while i<(len(user_message_split)-1):
    pos=i+1
    rconparams[i]=user_message_split[pos]
    i+=1
  return rconparams

async def get_response(config,logfile,client,message,user_message,is_private):
  response=''
  logmsg(logfile,'debug','client: '+str(client))
  logmsg(logfile,'info','message: '+str(message))
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
  logmsg(logfile,'info','user_message: '+str(user_message))
  logmsg(logfile,'debug','is_private: '+str(is_private))

  paramsgiven=False
  user_message_split=user_message.split(' ',2)
  command=user_message_split[0]
  logmsg(logfile,'info','command: '+str(command))
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
      if is_praefectus!=True:
        logmsg(logfile,'warn','missing access rights for command: '+str(command))
        access_granted=False
  for senatecmd in config['senate-cmds']:
    if senatecmd==command:
      logmsg(logfile,'info','senate-cmd found')
      if is_senate!=True:
        logmsg(logfile,'warn','missing access rights for command: '+str(command))
        access_granted=False
  for architecticmd in config['architecti-cmds']:
    if architecticmd==command:
      logmsg(logfile,'info','architecti-cmd found')
      if is_architecti!=True:
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
        data=await rcon(config,logfile,'ServerInfo',{})
        if data['Successful']==True:
          response=user_message+' response: rcon: success: '+str(data)
        else:
          response=user_message+' response: rcon: something went wrong'
      case '!maplist':
        data=await rcon(config,logfile,'MapList',{})
        if data['Successful']==True:
          response=user_message+' response: rcon: success: '+str(data)
        else:
          response=user_message+' response: rcon: something went wrong'
      case '!resetsnd':
        data=await rcon(config,logfile,'ResetSND',{})
        if data['Successful']==True:
          response=user_message+' response: rcon: success'
        else:
          response=user_message+' response: rcon: something went wrong'
      case '!rotatemap':
        data=await rcon(config,logfile,'RotateMap',{})
        if data['Successful']==True:
          response=user_message+' response: rcon: success'
        else:
          response=user_message+' response: rcon: something went wrong'
      case '!setmap':
        rconparams={}
        rconparams=get_rconparams(user_message)
        if (len(rconparams))<1:
          response='SwitchMap is missing parameters'
        else:
          data=await rcon(config,logfile,'SwitchMap',rconparams)
          if data['Successful']==True:
            response=user_message+' response: rcon: success'
          else:
            response=user_message+' response: rcon: something went wrong'
      case '!setrandommap':
        maplist_data=await rcon(config,logfile,'MapList',{})
        maplist=maplist_data['MapList']
        poolofrandommaps={}
        i=0
        for mapentry in maplist:
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
        data=await rcon(config,logfile,rconcmd,rconparams)
        if data['Successful']==True:
          response=user_message+' response: rcon: success'
        else:
          response=user_message+' response: rcon: something went wrong'
      case '!kick':
        rconparams={}
        rconparams=get_rconparams(user_message)
        if (len(rconparams))<1:
          response='Kick is missing parameters'
        else:
          data=await rcon(config,logfile,'Kick',{rconparams[0]})
          if data['Successful']==True:
            response=user_message+' response: rcon: success'
          else:
            response=user_message+' response: rcon: something went wrong'
      case '!ban':
        rconparams={}
        rconparams=get_rconparams(user_message)
        if (len(rconparams))<1:
          response='Ban is missing parameters'
        else:
          data=await rcon(config,logfile,'Ban',{rconparams[0]})
          if data['Successful']==True:
            response=user_message+' response: rcon: success'
          else:
            response=user_message+' response: rcon: something went wrong'
      case '!unban':
        rconparams={}
        rconparams=get_rconparams(user_message)
        if (len(rconparams))<1:
          response='Unban is missing parameters'
        else:
          data=await rcon(config,logfile,'Unban',{rconparams[0]})
          if data['Successful']==True:
            response=user_message+' response: rcon: success'
          else:
            response=user_message+' response: rcon: something went wrong'
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
        if len(user_message_split)>3: # requires 2 params
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

          query="SELECT id FROM steamusers WHERE steamid64 = %s LIMIT 1"
          values=[]
          values.append(steamid64)
          data=await dbquery(config,logfile,query,values)

          logmsg(logfile,'debug','checking if steamid64 exists in steamuser db')
          if data['rowcount']==0:
            logmsg(logfile,'debug','steamid64 not found in steamusers db')
            query="INSERT INTO steamusers (steamid64) VALUES (%s)"
            values=[]
            values.append(steamid64)
            data=await dbquery(config,logfile,query,values)
            logmsg(logfile,'info','created entry in steamusers db for steamid64 '+str(steamid64))
          else:
            logmsg(logfile,'debug','steamid64 already exists in steamusers db')
          query="SELECT id FROM steamusers WHERE steamid64=%s LIMIT 1"
          values=[]
          values.append(steamid64)
          data=await dbquery(config,logfile,query,values)
          steamusers_id=data['rows'][0][0]
            
          query="SELECT id FROM discordusers WHERE discordid = %s LIMIT 1"
          values=[]
          values.append(discordid)
          data=await dbquery(config,logfile,query,values)

          logmsg(logfile,'debug','checking if discordid exists in discordusers db')
          if data['rowcount']==0:
            logmsg(logfile,'debug','discordid not found in discordusers db')
            query="INSERT INTO discordusers (discordid) VALUES (%s)"
            values=[]
            values.append(discordid)
            data=await dbquery(config,logfile,query,values)
            logmsg(logfile,'info','created entry in discordusers db for discordid '+str(discordid))
          else:
            logmsg(logfile,'debug','discordid already exists in discordusers db')

          query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
          values=[]
          values.append(discordid)
          data=await dbquery(config,logfile,query,values)
          discordusers_id=data['rows'][0][0]

          query="SELECT id FROM register WHERE steamusers_id = %s AND discordusers_id = %s LIMIT 1"
          values=[]
          values.append(steamusers_id)
          values.append(discordusers_id)
          data=await dbquery(config,logfile,query,values)

          logmsg(logfile,'debug','checking if entry in register db exists')
          if data['rowcount']==0:
            logmsg(logfile,'debug','not entry found in register db')
            query="INSERT INTO register (steamusers_id,discordusers_id) VALUES (%s,%s)"
            values=[]
            values.append(steamusers_id)
            values.append(discordusers_id)
            data=await dbquery(config,logfile,query,values)
            logmsg(logfile,'info','registered steamid64 '+str(steamid64)+' with discordid ('+str(discordid)+')')
            response='registered steamid64 ('+str(steamid64)+') with discordid ('+str(discordid)+')'
          else:
            register_id=data['rows'][0][0]
            logmsg(logfile,'debug','entry found in register db for steamusers_id ('+str(steamusers_id)+') and discordusers_id ('+str(discordusers_id)+') with id ('+str(register_id)+')')
            response='already registered steamusers_id ('+str(steamusers_id)+') with discordusers_id ('+str(discordusers_id)+') as id ('+str(register_id)+')'
        else:
          logmsg(logfile,'warn','missing parameters')
          response='missing parameters - use !help for more info'
      case '!unregister':
        response='https://cdn.discordapp.com/attachments/1122295345930571837/1122664710379159663/iu.png' # WIP
      case '!getstats':
        discordid=str(message.author.id)
        query="SELECT id FROM discordusers WHERE discordid=%s LIMIT 1"
        values=[]
        values.append(discordid)
        data=await dbquery(config,logfile,query,values)
        if data['rowcount']==0:
          logmsg(logfile,'warn','discordid not registered')
          response='discordid not registered - use !help for more info'
        else:
          discordusers_id=data['rows'][0][0]
          query="SELECT steamusers_id FROM register WHERE discordusers_id=%s LIMIT 1"
          values=[]
          values.append(discordusers_id)
          data=await dbquery(config,logfile,query,values)
          steamusers_id=data['rows'][0][0]
          query="SELECT kills,deaths,average,score FROM stats "
          query+="WHERE matchended IS TRUE AND (gamemode='SND' OR gamemode='snd') AND playercount>9 AND steamusers_id=%s "
          query+="ORDER BY timestamp ASC"
          values=[]
          values.append(steamusers_id)
          data=await dbquery(config,logfile,query,values)
          logmsg(logfile,'debug','stats data: '+str(data))
          response=str(data)
      case '!getrank':
        response='https://cdn.discordapp.com/attachments/1122295345930571837/1122664710379159663/iu.png' # WIP
  else: # access denied
    logmsg(logfile,'warn','missing access rights for command: '+str(command))
    response='missing access rights for command: '+str(command)+' - use !help for more info'
  return response