import json
from grid import Grid

class Level:
    def __init__(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.name = data.get('name', 'Unnamed Level')
        self.description = data.get('description', '')
        self.width = data.get('width', 5)
        self.height = data.get('height', 5)
        
        if 'robots' in data:
            self.robots_config = data['robots']
        elif 'robot' in data:
            self.robots_config = [data['robot']]
        else:
            self.robots_config = [{"x": 0, "y": 0, "facing": "N"}]
            
        self.items = data.get('items', [])
        self.walls = data.get('walls', [])
        self.inboxes = data.get('inboxes', [])
        self.outboxes = data.get('outboxes', [])
        self.outbox_configs = self.outboxes
        self.conveyors = data.get('conveyors', [])
        self.buttons = data.get('buttons', [])
        self.doors = data.get('doors', [])
        self.portals = data.get('portals', [])
        self.expected_output = data.get('expected_output', [])
        
    def create_grid(self):
        grid = Grid(self.width, self.height)
        for item in self.items:
            grid.add_item(item['x'], item['y'], item.get('value', 0))
        for wall in self.walls:
            grid.walls.add((wall['x'], wall['y']))
        for inbox in self.inboxes:
            grid.inboxes[(inbox['x'], inbox['y'])] = list(inbox.get('queue', []))
        for outbox in self.outboxes:
            grid.outboxes[(outbox['x'], outbox['y'])] = []
        for conv in self.conveyors:
            grid.conveyors[(conv['x'], conv['y'])] = conv['dir']
        for btn in self.buttons:
            targets = [(t['x'], t['y']) for t in btn.get('targets', [])]
            grid.buttons[(btn['x'], btn['y'])] = targets
        for door in self.doors:
            grid.doors.add((door['x'], door['y']))
        for p in self.portals:
            grid.portals[(p['x'], p['y'])] = (p['target_x'], p['target_y'])
        return grid
        
    def check_win(self, vm, grid):
        if self.expected_output:
            if not grid.outboxes:
                return False, "No outbox found."
                
            outbox_key = list(grid.outboxes.keys())[0]
            actual = grid.outboxes[outbox_key]
            
            if len(actual) < len(self.expected_output):
                return False, f"Waiting for output... {actual}"
            elif len(actual) > len(self.expected_output):
                return False, f"Too much output. Expected {self.expected_output}, got {actual}"
            
            if actual == self.expected_output:
                return True, "Output matches."
            else:
                return False, f"Output mismatch. Expected {self.expected_output}, got {actual}"
        else:
            # Check all outbox configs
            all_match = True
            for ob in self.outbox_configs:
                if 'expected' not in ob: continue
                key = (ob['x'], ob['y'])
                actual = grid.outboxes.get(key, [])
                expected = ob['expected']
                if len(actual) < len(expected):
                    return False, f"Waiting for output at {key}..."
                elif len(actual) > len(expected):
                    return False, f"Too much output at {key}."
                if actual != expected:
                    return False, f"Mismatch at {key}. Expected {expected}, got {actual}"
                    
            if all_match:
                return True, "All outputs match perfectly!"
            return False, "Not all outputs matched."
