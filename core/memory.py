from collections import defaultdict

# SESSION holds per-session arbitrary keys like last_location
SESSION = defaultdict(dict)

def get_mem(sid, key, default=None):
    return SESSION[sid].get(key, default)

def set_mem(sid, key, val):
    SESSION[sid][key] = val

