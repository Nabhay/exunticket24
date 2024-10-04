import sqlite3, traceback, json, uuid, os

class Connection:
    def __init__(self, collection) -> None:
        self.collection = collection
    
    def set(self, key, value):
        set(self.collection, key, json.dumps(value))

    def insert(self, key=None, record=None):
        if record==None:
            record=key
            key=None
        record=json.dumps(record)
        if key==None:
            set(self.collection, uuid.uuid4().__str__(), record)
        else:
            set(self.collection, key, record)

    def delete(self, key):
        try:
            delete(self.collection, key)
        except Exception as e:
            traceback.print_exc()
    
    def search(self, search_function, debug=True):
        try:
            cursor = self.collection.cursor()
            cursor.execute("SELECT * FROM main")
            while True:
                records = cursor.fetchmany(100)
                if not records:
                    break
                for record in records:
                    id, record=record
                    record=json.loads(record)
                    try:
                        if search_function(id, record):
                            yield {"key":id, "val":record}
                    except:
                        if debug:
                            traceback.print_exc()
        except Exception as e:
            traceback.print_exc()

    def get(self, key):
        return get(self, key)
    
    def get_all(self):
        return get_all(self.collection)

def get_conn(name):
    path=f"databases"
    try:
        os.makedirs(path)
    except:
        pass
    conn = sqlite3.connect(path+f"/{name}", check_same_thread=False)
    cursor = conn.cursor()
    query1 = "CREATE TABLE IF NOT EXISTS main(x TEXT PRIMARY KEY, y TEXT)"
    cursor.execute(query1)
    conn.commit()
    return Connection(conn)

def set(conn, key, val, iterations=0):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM main WHERE x = ?", (key,))
        if len(cursor.fetchall()) == 0:
            query2 = "INSERT INTO main VALUES (?, ?)"
            cursor.execute(query2, (key, val))
            conn.commit()
        else:
            cursor.execute("UPDATE main SET y = ? WHERE x = ?", (val, key))
            conn.commit()
    except Exception as e:
        if iterations > 4:
            traceback.print_exc()
            raise e
        set(conn, key, val, iterations + 1)

def get(conn, key, iterations=0):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM main WHERE x = ?", (key,))
        data = cursor.fetchall()
        if len(data) == 0:
            return None
        return list(data[0])[1]
    except Exception as e:
        if iterations > 4:
            traceback.print_exc()
            raise e
        return get(conn, key, iterations + 1)

def get_all(conn, iterations=0):
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM main")
        data = cursor.fetchall()
        return data
    except Exception as e:
        if iterations > 4:
            traceback.print_exc()
            raise e
        return get_all(conn, iterations + 1)

def delete(conn, key, iterations=0):
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM main WHERE x = ?", (key,))
        conn.commit()
    except Exception as e:
        if iterations > 4:
            traceback.print_exc()
            raise e
        delete(conn, key, iterations + 1)