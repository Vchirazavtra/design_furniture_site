# db.py
import pymysql

def connect_db():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="dreddred",
        database="design_furniture_catalog",  # имя БД из SQL-скрипта
        port=3306,
        cursorclass=pymysql.cursors.DictCursor
    )
