import asyncio
import configparser
import logging
import MySQLdb

from datetime import datetime

from .config import Config, ConfigDefaults
from .email import Email
from .song import Music
from .user import User
log = logging.getLogger(__name__)

class SqlFactory:

    def __init__(self):

        config_file = ConfigDefaults.options_file
        self.config = Config(config_file)

        self.load_config()

        self.con = MySQLdb.connect(host=self.host, user=self.user, passwd=self.passwd, db=self.db, init_command='SET NAMES utf8mb4;', charset="utf8mb4")

    def load_config(self):

        config = configparser.ConfigParser(interpolation=None)
        config.read('config/database_auth.ini', encoding='utf-8')

        self.host = config.get('database_auth', 'host')
        self.user = config.get('database_auth', 'user')
        self.passwd = config.get('database_auth', 'passwd')
        self.db = config.get('database_auth', 'db')

    async def email_insert(self, ID, SUBJECT, CONTENTS, CRET_DT_TM):
        self.cur = self.con.cursor(cursor_class=MySQLCursorPrepared)
        try:
            self.cur.execute('INSERT INTO {table} ({columns_str}) VALUES ({values_list_qmarks})'.format(table=each_table, columns_str=list_to_str(columns).replace('\'', ''), values_list_qmarks=list_to_str([ '?' for i in range(0, len(columns)) ])))
        except:
            print('error with sql')

    async def email_update(self, ID, SUBJECT, CONTENTS, CRET_DT_TM):
        self.cur = self.con.cursor(cursor_class=MySQLCursorPrepared)

    async def email_delete(self, PK):
        self.cur = self.con.cursor(cursor_class=MySQLCursorPrepared)


