import litedb

conn = litedb.get_conn('test')
conn.set('help', 'me')