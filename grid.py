class Grid:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.items = {} # (x, y) -> value (int)
        self.walls = set() # (x, y) tuples
        self.inboxes = {} # (x, y) -> list of values (queue)
        self.outboxes = {} # (x, y) -> list of values (queue)
        self.conveyors = {} # (x, y) -> direction ('N', 'E', 'S', 'W')
        self.buttons = {} # (x, y) -> list of (tx, ty) target doors
        self.doors = set() # (x, y) tuples
        self.open_doors = set() # (x, y) tuples
        self.portals = {} # (x, y) -> (target_x, target_y)

    def is_wall(self, x, y):
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return True
        if (x, y) in self.walls:
            return True
        if (x, y) in self.doors and (x, y) not in self.open_doors:
            return True
        return False

    def get_portal_destination(self, x, y):
        if (x, y) in self.portals:
            return self.portals[(x, y)]
        return x, y

    def tick(self, robots=None):
        moves = []
        for (x, y), val in list(self.items.items()):
            if (x, y) in self.conveyors:
                d = self.conveyors[(x, y)]
                nx, ny = x, y
                if d == 'N': ny -= 1
                elif d == 'S': ny += 1
                elif d == 'E': nx += 1
                elif d == 'W': nx -= 1
                
                if not self.is_wall(nx, ny):
                    nx, ny = self.get_portal_destination(nx, ny)
                    moves.append(((x, y), (nx, ny), val))
                    
        for (src, dst, val) in moves:
            if src in self.items:
                del self.items[src]
                
        for (src, (nx, ny), val) in moves:
            self.drop_item(nx, ny, val)
            
        self.open_doors.clear()
        robot_coords = set((r.x, r.y) for r in robots) if robots else set()
        for (bx, by), targets in self.buttons.items():
            if self.has_item(bx, by) or (bx, by) in robot_coords:
                for tx, ty in targets:
                    self.open_doors.add((tx, ty))

    def add_item(self, x, y, val):
        self.items[(x, y)] = val

    def remove_item(self, x, y):
        if (x, y) in self.items:
            val = self.items.pop((x, y))
            return True, val
        elif (x, y) in self.inboxes and self.inboxes[(x, y)]:
            val = self.inboxes[(x, y)].pop(0)
            return True, val
        return False, None

    def has_item(self, x, y):
        return (x, y) in self.items or ((x, y) in self.inboxes and len(self.inboxes[(x, y)]) > 0)
        
    def drop_item(self, x, y, val):
        if (x, y) in self.outboxes:
            self.outboxes[(x, y)].append(val)
            return True
        else:
            self.items[(x, y)] = val
            return True
