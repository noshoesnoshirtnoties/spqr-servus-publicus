import json
import discord
import os
import random
from pathlib import Path

if __name__ == '__main__':
    env='live'

    # read config
    config = json.loads(open('config.json').read())[env]

    # init discord
    intents=discord.Intents.default()
    intents.message_content=True
    client=discord.Client(intents=intents)

    @client.event
    async def on_ready():
        channelid=config['bot-channel-ids']['news']
        channel=client.get_channel(int(channelid))

        # get random quote
        randomquote=random.choice(os.listdir('txt/suntzu'))
        quotepath="txt/suntzu/"+randomquote
        quote=Path(str(quotepath)).read_text()

        gladiator=config['role-ids']['gladiator']
        tiro=config['role-ids']['tiro']
        gmatches=config['bot-channel-ids']['g-matches']
        response='<@&'+str(gladiator)+'> <@&'+str(tiro)+'> **automated reminder**\n\n:crossed_swords:  come play <#'+str(gmatches)+'>\n\n'+quote+'\n-SunTzu'

        try:
            await channel.send(response)
        except Exception as e:
            print('[ERROR] '+str(e))
        await client.close()

    client.run(config['bot_token'])
    exit()