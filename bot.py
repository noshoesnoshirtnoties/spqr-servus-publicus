import json
import discord
import logging
import responses

def run_bot(meta,config):
    # init logging
    if bool(config['debug'])==True:
        level=logging.DEBUG
    else:
        level=logging.INFO
    logging.basicConfig(
        filename='spqr-servus-publicus.log',
        filemode='a',
        format='%(asctime)s,%(msecs)d [%(levelname)s] srvmon: %(message)s',
        datefmt='%m/%d/%Y %H:%M:%S',
        level=level)
    logfile=logging.getLogger('logfile')

    # def funcs
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

    intents=discord.Intents.default()
    intents.message_content=True
    client=discord.Client(intents=intents)

    async def send_answer(client,message,user_message,is_private):
        response='' # empty response
        logmsg('debug','send_answer called')
        try:
            response=await responses.get_response(config,logfile,client,message,user_message,is_private)
            if str(response)=='None' or str(response)=='':
                logmsg('debug','nothing to do')
            else:
                logmsg('info','sending response')
                logmsg('info','response: '+str(response))
                try:
                    await message.author.send(response) if is_private else await message.channel.send(response)
                except Exception as e:
                    logmsg('debug',str(e))
        except Exception as e:
            logmsg('debug',str(e))

    @client.event
    async def on_ready():
        logmsg('info',str(meta['name'])+' '+str(meta['version'])+' is now running')

    @client.event
    async def on_message(message):
        if message.author==client.user:
            logmsg('debug','message.author == client.user -> dont get high on your own supply')
            return
        username=str(message.author)
        user_message=str(message.content)
        channel=str(message.channel)
        logmsg('debug',str(username)+' said: "'+str(user_message)+'" in channel: '+str(channel))
        logmsg('debug','type(user_message): "'+str(type(user_message)))

        if user_message[0]=='?':
            user_message=user_message[1:]
            is_private=True
        else:
            is_private=False
        await send_answer(client,message,user_message,is_private)

    client.run(config['bot_token'])



