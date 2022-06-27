import websocket
import os, json
from base64 import b64decode

# Error Classes
class CraftError(Exception):
    pass

# Create a long-term connection for transactions

class Client:
    def __init__(self, token):
        self.nonce = "0"
        self.token = token.replace('http://', '')
        self.config = json.loads(b64decode(token.split('.')[1] + '===='))
        self.event = {}

        self.responseNonce = -1
        self.responseFunc = False

        self.queue = None
    
    def login(self):
        self.ws = websocket.WebSocketApp('ws://' + self.config['host'] + '/gateway',
            on_open=self.onOpen,
            on_message=self.onMessage,
            on_error=self.onError,
            on_close=self.onClose
        )
        
        self.ws.run_forever()

    # Private Send Function
    def _send(self, data):
        self.ws.send(json.dumps(data))
        self.nonce = str(int(self.nonce) + 1)

        self.queue = data

    # Resend Function
    def _resend(self, data):
        self.ws.send(json.dumps(data))

    # Disconnect Function
    def disconnect(self):
        self.ws.close()
        
    # Login function
    def onOpen(self, ws): # Send authetication request
        self._send(
            {
                "action": "authenticate",
                "token": self.token,
                "nonce": self.nonce
            }
        )    

    def onError(self, ws, error):
        print("ERROR:", error)
    
    def onClose(self, ws, close_status_code, close_msg):
        if 'close' in self.event:
            self.event['close'](self)
        
        print("REPLCRAFT CLOSED:", close_msg)
        print(close_status_code)

    # Event Wrapper
    def on(self, event):
        def decorator(func):
            self.event[event] = func
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return result
            return wrapper
        return decorator
        
    # Event Listener
    def onMessage(self, ws, message):
        msg = json.loads(message)

        print(msg)

        if msg.get('nonce', False) == self.responseNonce and self.responseFunc:
            self.responseFunc(msg)
            self.responseNonce = -1
            self.responseFunc = False
        
        # Check if error occured
        if msg.get('ok', False) and msg['ok'] == False:
            print("ERROR:", msg)
            if msg.get('error', False):
                if msg['error'] == 'out of fuel' and 'out of fuel' in self.event:
                    self._resend(self.queue)
                    self.event['out of fuel'](self, msg)
                elif 'error' in self.event: 
                    self.event['error'](self, msg['error'], msg)
        
        # Check if connection opened
        if msg.get('nonce', False) == '0': self.event['open'](self)  
        
        # Transaction Handling
        if 'transact' in self.event and msg.get('type', False) == 'transact': 

            # Accept and Deny functions
            def accept():
                self._send({
                    'action': 'respond',
                    'nonce': self.nonce,
                    'queryNonce': msg['queryNonce'],
                    'accept': True
                })
            def deny():
                self._send({
                    'action': 'respond',
                    'nonce': self.nonce,
                    'queryNonce': msg['queryNonce'],
                    'accept': False
                })

            msg['accept'] = accept
            msg['deny'] = deny
            # Split up message into arguments
            msg['query'] = msg['query'].split(' ')
                
            # Run event listener
            self.event['transact'](self, msg)

        # Block Update Handling
        elif 'block update' in self.event and msg.get('type', False) == 'block update':
            self.event['block update'](self, msg['cause'], msg['block'], msg['x'], msg['y'], msg['z'])

        # Events
        if msg.get('event', False) and 'event' in self.event['event']:
            self.event['event'](self, msg['event'], msg['cause'], msg['block'], msg['x'], msg['y'], msg['z'])

    #
    # Handle response messages
    #

    def _response(self, func):
        self.responseFunc = func
        self.responseNonce = self.nonce
        
    #
    # Tell & Pay Functions
    #

    # Send a message to a player inside a structure
    def tell(self, target, message):
        return self._send(
            {
                "action": "tell",
                "target": target,
                "message": message,
                "nonce": self.nonce
            }
        )
    
    # Send money to a player
    def pay(self, target, amount):
        return self._send(
            {
                "action": "tell",
                "target": target,
                "amount": amount,
                "nonce": self.nonce
            }
        )

    #
    # Block Functions
    # From bobbypin's ReplCraftPy library
    #

    # Retrieves a block at the given structure-local coordinates.
    def getBlock(self, responseFunc, x, y, z):
        self._response(responseFunc)
        
        return self._send(
            {
                "action":"get_block",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Retrieves the world coordinate location of the (0,0,0)
    def location(self, responseFunc, x, y, z):
        self._response(responseFunc)

        return self._send(
            {
                "action":"get_location",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )
        
    # Retrieves the inner size of the structure.
    def getSize(self, responseFunc, x, y, z):
        self._response(responseFunc)
        
        return self._send(
            {
                "action":"get_size",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Sets a block at the given structure-local coordinates. The block must be available
    # in the specified source chest or the structure inventory. Any block replaced by this call
    # is stored in the specified target chest or the structure inventory, or dropped in the
    # world if there's no space.
    #
    # :source_x, source_y, source_z: The container the block to set is in.
    # :target_x, target_y, target_z: The container the block replaced should go to.
    def setBlock(self, x, y, z, blockdata, 
                 source_x=None, source_y=None, source_z=None, 
                 target_x=None, target_y=None, target_z=None
            ):
        return self._send({
                "action":"set_block",
                "x": x,
                "y": y,
                "z": z,
                "blockData": blockdata,
                "source_x": source_x,
                "source_y": source_y,
                "source_z": source_z,
                "target_x": target_x,
                "target_y": target_y,
                "target_z": target_z,
                "nonce": self.nonce
            })

    # Retrieves the text of a sign at the given coordinates.
    def getSignText(self, responseFunc, x, y, z):
        self._response(responseFunc)
        
        return self._send(
            {
                "action":"get_sign_text",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Sets the text of a sign at the given coordinates.
    def setSignText(self, x, y, z, lines):
        return self._send(
            {
                "action":"set_sign_text",
                "x": x,
                "y": y,
                "z": z,
                "lines": lines,
                "nonce": self.nonce
            }
        )

    # Begins watching a block for updates.
    def watch(self, x, y, z):
        return self._send(
            {
                "action":"watch",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Stops watching a block for updates.
    def unwatch(self, x, y, z):
        return self._send(
            {
                "action":"unwatch",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Begins watching all blocks in the structure for updates.
    def watchAll(self):
        return self._send(
            {
                "action":"watch_all",
                "nonce": self.nonce
            }
        )

    # Stops watching all blocks for updates.
    def unwatchAll(self):
        return self._send(
            {
                "action":"unwatch_all",
                "nonce": self.nonce
            }
        )

    # Begins polling all blocks in the structure for updates.
    # Updates will be very slow!
    def pollAll(self):
        return self._send(
            {
                "action":"poll_all",
                "nonce": self.nonce
            }
        )

    # Stops polling all blocks in the structure.
    def unpollAll(self):
        return self._send(
            {
                "action":"unpoll_all",
                "nonce": self.nonce
            }
        )

    # Begins polling a block for updates.
    # Note that this catches all possible block updates, but only one block is polled per tick.
    # The more blocks you poll, the slower each individual block will be checked.
    # Additionally, if a block changes multiple times between polls, only the latest change
    # will be reported.
    def poll(self, x, y, z):
        return self._send(
            {
                "action":"poll",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Stops watching a block for updates.
    def unpoll(self, x, y, z):
        return self._send(
            {
                "action":"unpoll",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    # Gets all entities inside the region.
    def getEntities(self, responseFunc):
        self._response(responseFunc)
        
        return self._send({
                "action":"get_entities",
                "nonce": self.nonce
            })

    # Gets all items from a container such as a chest or hopper.
    def getInventory(self, responseFunc, x, y, z):
        self._response(responseFunc)

        return self._send({
                "action":"get_inventory",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            })

    # Moves an item between containers.
    def moveItem(self, index,
            source_x, source_y, source_z, 
            target_x, target_y, target_z,
            amount=None, target_index=None
        ):
        return self._send({
                "action":"move_item",
                "amount": amount,
                "index": index,
                "source_x": source_x,
                "source_y": source_y,
                "source_z": source_z,
                "target_index": target_index,
                "target_x": target_x,
                "target_y": target_y,
                "target_z": target_z,
                "nonce": self.nonce
            })

    # Gets a block's redstone power level.
    def getPowerLevel(self, responseFunc, x, y, z):
        self._response(responseFunc)

        return self._send({
                "action":"get_power_level",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            })

    # Crafts an item, which is then stored into the given container.
    def craft(self, x, y, z, recipe):
        return self._send({
                "action":"craft",
                "x": x,
                "y": y,
                "z": z,
                "ingredients": recipe,
                "nonce": self.nonce
            })

    # Fuel Info API
    def fuelInfo(self, responseFunc):
        self._response(responseFunc)

        return self._send(
            {
                "action": "fuelinfo",
                "nonce": self.nonce
            }
        )
        
    # Index of an item withing a container.
    #
    # :index: index of the slot the time is in within the container.
    # :x, y, z: the coordinates of the container.
    class ItemIndex:
        def __init__(self, index, x, y, z):
            self.index = index # The index of the chest slot the item is in.
            self.x = x
            self.y = y
            self.z = z
    
        def item(self):            
            return {
                    "index": self.index,
                    "x": self.x,
                    "y": self.y,
                    "z": self.z
                }
    
    # Recipe, matching it's vanilla definition
    #
    # :s1-s9: crafting table slots
    class Recipe:
        def __init__(self, 
            s1=None, 
            s2=None, 
            s3=None, 
            s4=None, 
            s5=None, 
            s6=None, 
            s7=None, 
            s8=None, 
            s9=None
        ):
            self.s1 = s1
            self.s2 = s2
            self.s3 = s3
            self.s4 = s4
            self.s5 = s5
            self.s6 = s6
            self.s7 = s7
            self.s8 = s8
            self.s9 = s9
    
        def table(self):
            return [
                    self.s1, self.s2, self.s3,
                    self.s4, self.s5, self.s6,
                    self.s7, self.s8, self.s9
                ]
