import sqlite3

conn = sqlite3.connect('data/demo_requests.db')
print(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='demo_requests'").fetchone())
print(conn.execute('SELECT COUNT(*) FROM demo_requests').fetchone())
conn.close()
