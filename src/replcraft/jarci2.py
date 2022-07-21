import websocket
import json
from base64 import b64decode

class Client:
    """
    Replcraft Instance    
    """
    def __init__(self, token):
        # Extract token
        self.token = token.replace('http://', '')
        self.config = json.loads(b64decode(token.split('.')[1] + '===='))

        # Nonce
        self.nonce = "0"

        # Event manager
        self.events = {}

        # Out of Fuel Queue (unimplemented)
        self.queue = {}

    def login(self):
        """
        Create and start the websocket connection
        """
        self.ws = websocket.create_connection('ws://' + self.config['host'] + '/gateway')

        self._open()
        self._recv()
        
        # Run open event
        self._event('open')(self)  
        
        while True:
            msg = self._recv()
            
            # Check if error occured
            if msg.get('ok', False) and msg['ok'] == False:
                if msg.get('error', False):
                    if msg['error'] == 'out of fuel' and 'out of fuel' in self.events:
                        self._event('out of fuel')(self, msg)
                    elif 'error' in self.events: 
                        self._event('error')(self, msg['error'], msg)
            
            # Transaction Handling
            if 'transact' in self.events and msg.get('type', False) == 'transact': 
    
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
                self._event('transact')(self, msg)
    
            # Block Update Handling
            elif 'block update' in self.events and msg.get('type', False) == 'block update':
                self._event('block update')(self, msg['cause'], msg['block'], msg['x'], msg['y'], msg['z'])
    
            # Events
            if msg.get('event', False) and 'event' in self.events['event']:
                self._event('event')(self, msg['event'], msg['cause'], msg['block'], msg['x'], msg['y'], msg['z'])

    # Events
    def on(self, event: str):
        """
        Add function to event 
                Parameters:
                    event (str): Event manager
                Returns:
                    decorator
        """
        def decorator(func):
            self.events[event] = func
            def wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                return result
            return wrapper
        return decorator
    
    def _event(self, event: str):
        return self.events.get(event, False)

    def _open(self):
        self._send(
            {
                "action": "authenticate",
                "token": self.token,
                "nonce": self.nonce
            }
        )    

    # Private Send Function
    def _send(self, data):
        self.ws.send(json.dumps(data))
        self.nonce = str(int(self.nonce) + 1)

        self.queue = data
        
    # Private Recieve Function
    def _recv(self):
        msg = self.ws.recv()

        if msg: # Check if message is an empty string, JSON cannot handle empty strings
            msg = json.loads(msg)
        else:
            return

        if msg.get('error') == 'out of fuel':
            self._send(self.queue)

        return msg

    #
    # Tell & Pay Functions
    #

    def tell(self, target: str, message: str) -> dict:
        """
        Send a message to a player inside a structure
                Parameters:
                    target (str): Player Name or UUID
                    message (str): Message to send to player
                Returns:
                    dict
        """
        return self._send(
            {
                "action": "tell",
                "target": target,
                "message": message,
                "nonce": self.nonce
            }
        )
    
    def pay(self, target: str, amount: str) -> dict:
        """
        Send money to a player.
                Parameters:
                    target (str): Player Name or UUID
                    amount (str): Amount of money to send to player
                Returns:
                    None
        """
        self._send(
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

    def getBlock(self, x, y, z):
        """
        Retrieves a block at the given structure-local coordinates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                Returns:
                    dict
        """
        self._send(
            {
                "action":"get_block",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

        return self._recv()

    def location(self, x, y, z):
        """
        Retrieves a block at the given structure-local coordinates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                Returns:
                    dict
        """
        self._send(
            {
                "action":"get_location",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

        return self._recv()
        
    def getSize(self):
        """
        Retrieves the inner size of the structure.
                Returns:
                    dict
        """
        self._send(
            {
                "action":"get_size",
                "nonce": self.nonce
            }
        )

        return self._recv()

    def setBlock(self, x, y, z, blockdata, 
                 source_x=None, source_y=None, source_z=None, 
                 target_x=None, target_y=None, target_z=None
            ):
        """
        Sets a block at the given structure-local coordinates. 
        The block must be available in the specified source chest or the structure inventory. 
        Any block replaced by this call is stored in the specified target chest or the structure inventory, or dropped in the world if there's no space.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                    x (str): Blockdata       
                    **source_x (int): The X coordinate of the container the block to set is in.
                    **source_y (int): The Y coordinate of the container the block to set is in.
                    **source_z (int): The Z coordinate of the container the block to set is in.
                    **target_x (int): The X coordinate of the container the block replaced should go to.
                    **target_y (int): The Y coordinate of the container the block replaced should go to.
                    **target_z (int): The Z coordinate of the container the block replaced should go to.
                Returns:
                    None
        """
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

    def getSignText(self, x, y, z):      
        """
        Retrieves the text of a sign at the given coordinates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                Returns:
                    dict
        """
        self._send(
            {
                "action":"get_sign_text",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )
        
        return self._recv()

    def setSignText(self, x, y, z, lines):
        """
        Sets the text of a sign at the given coordinates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                    lines (list): Lines to set
                Returns:
                    dict
        """
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

    def watch(self, x, y, z):
        """
        Begins watching a block for updates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                Returns:
                    dict
        """
        return self._send(
            {
                "action":"watch",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
            }
        )

    def unwatch(self, x, y, z):
        """
        Stops watching a block for updates.
                Parameters:
                    x (int): X coordinate
                    y (int): Y coordinate
                    z (int): Z coordinate
                Returns:
                    dict
        """

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
    def getEntities(self):
        self._send({
                "action":"get_entities",
                "nonce": self.nonce
        })
        
        return self._recv()

    # Gets all items from a container such as a chest or hopper.
    def getInventory(self, x, y, z):
        self._send({
                "action":"get_inventory",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
        })

        return self._recv()

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
    def getPowerLevel(self, x, y, z):
        self._send({
                "action":"get_power_level",
                "x": x,
                "y": y,
                "z": z,
                "nonce": self.nonce
        })

        return self._recv()

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
    def fuelInfo(self):
        self._send(
            {
                "action": "fuelinfo",
                "nonce": self.nonce
            }
        )

        return self._recv()
        
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
