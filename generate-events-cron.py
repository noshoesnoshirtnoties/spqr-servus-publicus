import json
import mysql.connector
import discord
import datetime
import time

if __name__ == '__main__':
    env='live'

    # read config
    config = json.loads(open('config.json').read())[env]

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
        else:
            data['rows']=False
        cursor.close()
        conn.close()
        return data

    # get all currently planned events
    query="SELECT * FROM events ORDER BY id ASC"
    values=[]
    events=dbquery(query,values)
    
    # init discord
    intents=discord.Intents.default()
    intents.message_content=True
    client=discord.Client(intents=intents)

    @client.event
    async def on_ready():
        channelid=config['bot-channel-ids']['g-matches']

        # delete old messages
        async for msg in client.logs_from(channelid):
            await client.delete_message(msg)

        # add new messages
        if events['rowcount']>0:
            for row in events['rows']:
                channel=client.get_channel(int(channelid))
                response=row['text']
                try:
                    await channel.send(response)
                except Exception as e:
                    print('[ERROR] '+str(e))
        await client.close()

    client.run(config['bot_token'])

    # delete all currently planned events
    query="DELETE FROM events"
    values=[]
    dbquery(query,values)
    
    # add new events for upcoming week
    current=datetime.datetime.utcnow().replace(hour=0,minute=0,second=0,microsecond=0)
    unix=time.mktime(current.timetuple())

    mon=unix + (1 * 86400) + (18 * 3600)
    tue=unix + (2 * 86400) + (19 * 3600)
    wed=unix + (3 * 86400) + (18 * 3600)
    thu=unix + (4 * 86400) + (19 * 3600)
    sat=unix + (6 * 86400) + (18 * 3600)

    new_events=[
        '<t:'+str(int(mon))+':F>, <t:'+str(int(mon))+':R>',
        '<t:'+str(int(tue))+':F>, <t:'+str(int(tue))+':R>',
        '<t:'+str(int(wed))+':F>, <t:'+str(int(wed))+':R>',
        '<t:'+str(int(thu))+':F>, <t:'+str(int(thu))+':R>',
        '<t:'+str(int(sat))+':F>, <t:'+str(int(sat))+':R>'
    ]

    for new_event in new_events:
        query="INSERT INTO events (text) VALUES (%s)"
        values=[]
        values.append(new_event)
        dbquery(query,values)

    exit()