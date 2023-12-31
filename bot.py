import json
import logging
import discord
import responses

def run_bot(meta,config):

    intents=discord.Intents.default()
    intents.message_content=True
    client=discord.Client(intents=intents)

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

    async def send_answer(client,message,user_message,is_private):
        logmsg(logfile,'debug','send_answer called')
        resp=await responses.get_response(config,logfile,client,message,user_message,is_private)
        if int(len(resp))<1:
            logmsg(logfile,'debug','nothing to do - response was found empty')
        else:
            logmsg(logfile,'debug','sending response')
            logmsg(logfile,'debug','resp: '+str(resp))
            try:
                await message.author.send(resp) if is_private else await message.channel.send(resp)
            except Exception as e:
                logmsg(logfile,'debug',str(e))

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

        is_private=False
        if len(user_message)>0:
            if user_message[0]=='?':
                user_message=user_message[1:]
                is_private=True
            
        await send_answer(client,message,user_message,is_private)

    client.run(config['bot_token'])



