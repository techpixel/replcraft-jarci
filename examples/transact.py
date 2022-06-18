import os
from jarci import Client

replcraft = Client(os.environ['token'])

@replcraft.on('open')
def opener(manager):
    print("REPLCRAFT OPENED!")
    manager.setBlock(0, 0, 0, 'minecraft:air')

@replcraft.on('transact')
def handler(manager, transaction):    
    manager.tell(transaction['player_uuid'], "Transaction Payment Recieved for ", transaction['amount'])
    
    transaction['accept']()

replcraft.login()
