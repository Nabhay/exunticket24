from flask import Flask, request
import litedb
import json

app = Flask('__init__')

channels = litedb.get_conn('channels')
user_access = litedb.get_conn('user_access')

conn_table = {'channels': channels, 'user_access': user_access}

@app.get('/get')
def get_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return json.loads(litedb.get(table,key))

@app.get('/set')
def set_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    litedb.set(conn_table[table], key, value)

@app.get('/delete')
def delete_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return json.loads(litedb.delete(conn_table[table], key))

@app.get('/get_all')
def get_all_api():
    table = request.args.get('table')
    return json.loads(litedb.get_all(conn_table[table]))

@app.get('/insert')
def insert_api():
    table = request.args.get('table')
    key = request.args.get('key')
    value = request.args.get('value')
    data = json.dumps(litedb.get(conn_table[table], key))
    litedb.set(conn_table[table], key, data.append(value))