import litedb

db=litedb.get_conn("test")

def search(id, record):
    if record["age"]<1:
        return True

for x in db.search(search):
    print(x)