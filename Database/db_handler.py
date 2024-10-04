from flask import Flask, request
import litedb
import json

app = Flask("__init__")

channels = litedb.get_conn("channels")
user_access = litedb.get_conn("user_access")

conn_table = {"channels": channels, "user_access": user_access}

@app.get("/get")
def get_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return conn_table[table].get(key)


@app.get("/set")
def set_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    print(table,value,key)
    conn_table[table].set(key, value)

@app.get("/delete")
def delete_api():
    table = request.args.get("table")
    key = request.args.get("key")
    return conn_table[table].delete(key)


@app.get("/get_all")
def get_all_api():
    table = request.args.get("table")
    count = request.args.get("count")
    return conn_table[table].get_all()


@app.get("/insert")
def insert_api():
    table = request.args.get("table")
    key = request.args.get("key")
    value = request.args.get("value")
    data = conn_table[table].get(key)
    conn_table[table].set(key, data.append(value))
    
app.run("127.0.0.1", 3000)