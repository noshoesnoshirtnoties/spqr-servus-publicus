import json
import mysql.connector

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

    # get all events
    query="SELECT * FROM events ORDER BY id ASC"
    values=[]
    events=dbquery(query,values)
    print('[DEBUG] events: '+str(events))
    #...