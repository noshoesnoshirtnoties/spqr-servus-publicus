import json
import discord
import logging
import responses

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

async def send_answer(config,logfile,client,message,user_message,is_private):
  response='' # empty response
  logmsg(logfile,'debug','send_answer called')
  try:
    response=await responses.get_response(config,logfile,client,message,user_message,is_private)
    if str(response)=='None' or str(response)=='':
      logmsg(logfile,'debug','nothing to do')
    else:
      logmsg(logfile,'info','sending response')
      logmsg(logfile,'info','response: '+str(response))
      try:
        await message.author.send(response) if is_private else await message.channel.send(response)
      except Exception as e:
        logmsg(logfile,'debug',str(e))
  except Exception as e:
    logmsg(logfile,'debug',str(e))

def run_bot():
  env='live'
  meta=json.loads(open('meta.json').read())
  config=json.loads(open('config.json').read())[env]

  if bool(config['debug'])==True:
    level=logging.DEBUG
  else:
    level=logging.INFO
  logging.basicConfig(filename='spqr-servus-publicus.log',filemode='a',format='%(asctime)s,%(msecs)d [%(levelname)s] srvmon: %(message)s',datefmt='%m/%d/%Y %H:%M:%S',level=level)
  logfile=logging.getLogger('logfile')

  intents=discord.Intents.default()
  intents.message_content=True
  client=discord.Client(intents=intents)

  @client.event
  async def on_ready():
    logmsg(logfile,'info',str(meta['name'])+' '+str(meta['version'])+' is now running')

  @client.event
  async def on_message(message):
    if message.author==client.user:
      logmsg(logfile,'debug','message.author == client.user -> dont get high on your own supply')
      return
    username=str(message.author)
    user_message=str(message.content)
    channel=str(message.channel)
    logmsg(logfile,'debug',str(username)+' said: "'+str(user_message)+'" in channel: '+str(channel))

    if user_message[0]=='?':
      user_message=user_message[1:]
      is_private=True
    else:
      is_private=False
    await send_answer(config,logfile,client,message,user_message,is_private)

  client.run(config['bot_token'])