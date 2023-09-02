import bot
import json

if __name__ == '__main__':
    env='live'

    # read meta + config
    meta=json.loads(open('meta.json').read())
    config=json.loads(open('config.json').read())[env]

    # run
    bot.run_bot(meta,config)
