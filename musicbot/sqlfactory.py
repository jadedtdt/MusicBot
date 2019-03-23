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

    def get_con(self):
        return MySQLdb.connect(host=self.host, user=self.user, passwd=self.passwd, db=self.db, init_command='SET NAMES utf8mb4;', charset="utf8mb4")

    def list_to_str(self, input_list):
        if not input_list:
            return None

        output_str = str(input_list).replace('[', '', 1).replace(']', '', 1)
        if '[' in output_str or ']' in output_str:
            raise ValueException('Cannot have list within list if you want to convert to string')
            return None
        return output_str.replace('\'', '')

    def load_config(self):

        config = configparser.ConfigParser(interpolation=None)
        config.read('config/database_auth.ini', encoding='utf-8')

        self.host = config.get('database_auth', 'host')
        self.user = config.get('database_auth', 'user')
        self.passwd = config.get('database_auth', 'passwd')
        self.db = config.get('database_auth', 'db')

    async def email_create(self, ID, SUBJECT, CONTENTS, CRET_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (ID, SUBJECT, CONTENTS, CRET_DT_TM) VALUES (%s, %s, %s, %s)'.format(table='EMAIL')
            log.debug('[SQL] [EMAIL] {query}'.format(query=query))
            values = (ID, SUBJECT, CONTENTS, CRET_DT_TM,)
            log.debug('[VALUES] [EMAIL] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def email_read(self, ID):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE ID = %s'.format(table='EMAIL')
            log.debug('[SQL] [EMAIL] {query}'.format(query=query))
            values = (ID,)
            log.debug('[VALUES] [EMAIL] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            rows = cur.fetchall()
            if rows_affected == 1 and rows:
                result = [ each_row for each_row in rows[0] ]
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return result

    async def email_update(self, ID, SUBJECT, CONTENTS, CRET_DT_TM, OLD_ID):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET ID = %s, SUBJECT = %s, CONTENTS = %s, CRET_DT_TM = %s WHERE ID = %s'.format(table='EMAIL')
            log.debug('[SQL] [EMAIL] {query}'.format(query=query))
            values = (ID, SUBJECT, CONTENTS, CRET_DT_TM, OLD_ID,)
            log.debug('[VALUES] [EMAIL] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def email_delete(self, ID):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE ID = %s'.format(table='EMAIL')
            log.debug('[SQL] [EMAIL] {query}'.format(query=query))
            values = (ID,)
            log.debug('[VALUES] [EMAIL] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def user_song_create(self, ID, URL, PLAY_COUNT, LAST_PLAYED_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (ID, URL, PLAY_COUNT, LAST_PLAYED_DT_TM) VALUES (%s, %s, %s, %s)'.format(table='USER_SONG')
            log.debug('[SQL] [USER_SONG] {query}'.format(query=query))
            values = (ID, URL, PLAY_COUNT, LAST_PLAYED_DT_TM,)
            log.debug('[VALUES] [USER_SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def user_song_read(self, ID, URL):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE ID = %s AND URL = %s'.format(table='USER_SONG')
            log.debug('[SQL] [USER_SONG] {query}'.format(query=query))
            values = (ID, URL,)
            log.debug('[VALUES] [USER_SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            rows = cur.fetchall()
            if rows_affected == 1 and rows:
                result = [ each_row for each_row in rows[0] ]
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return result

    async def user_song_update(self, ID, URL, PLAY_COUNT, LAST_PLAYED_DT_TM, OLD_ID, OLD_URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET ID = %s, URL = %s, PLAY_COUNT = %s, LAST_PLAYED_DT_TM = %s WHERE ID = %s AND URL = %s'.format(table='USER_SONG')
            log.debug('[SQL] [USER_SONG] {query}'.format(query=query))
            values = (ID, URL, PLAY_COUNT, LAST_PLAYED_DT_TM, OLD_ID, OLD_URL,)
            log.debug('[VALUES] [USER_SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected and rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def user_song_delete(self, ID, URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE ID = %s AND URL = %s'.format(table='USER_SONG')
            log.debug('[SQL] [USER_SONG] {query}'.format(query=query))
            values = (ID, URL,)
            log.debug('[VALUES] [USER_SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status


