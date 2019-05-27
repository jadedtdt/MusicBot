import asyncio
import configparser
import logging
import MySQLdb
import os

from datetime import datetime

from musicbot.config import Config, ConfigDefaults
from musicbot.email import Email
from musicbot.song import Song
from musicbot.user import User
log = logging.getLogger(__name__)

class SqlFactory:

    def __init__(self):
        self.load_config()

    def get_con(self):
        return MySQLdb.connect(host=self.host, user=self.user, passwd=self.passwd, db=self.db, init_command='SET NAMES utf8mb4;', charset="utf8mb4")

    def list_to_str(self, input_list):
        if not input_list:
            return None

        output_str = str(input_list).replace('[', '', 1).replace(']', '', 1)
        if '[' in output_str or ']' in output_str:
            log.error('Cannot have list within list if you want to convert to string')
            return None
        return output_str.replace('\'', '')

    def load_config(self):
        self.db = os.environ['DATABASE_DB']
        self.host = os.environ['DATABASE_HOST']
        self.passwd = os.environ['DATABASE_PASSWD']
        self.user = os.environ['DATABASE_USER']

    async def execute(self, query, list_values=[]):
        return self._execute(query, list_values)

    def _execute(self, query, list_values=[]):
        if query.count('%s') != len(list_values):
            log.error('Malformed sql passed in. Must have same number of params as values')
            log.error('Param count: {}, Arg count: {}'.format(query.count('%s'), len(list_values)))
            return False, None

        if query.count('%s') == len(list_values) == 0:
            log.warn('Raw SQL passed in, please add parameters to it.')
            log.warn('Lazy option: \'SELECT * FROM TABLE WHERE 1 = %s\', \'1\'')
            return False, None

        log.info('Using adhoc execute, logging for auditing purposes')
        log.info('Query: {}, Params: {}'.format(query, str(list_values)))

        con = self.get_con()
        cur = con.cursor()
        result = None
        try:
            log.debug('[SQL] [EXECUTE] {query}'.format(query=query))
            log.debug('[VALUES] [EXECUTE] {values}'.format(values=str(list_values)))
            rows_affected = cur.execute(query, list_values)            
            rows = cur.fetchall()
            if rows_affected > 0 and rows:
                if ',)' in str(rows[0]):
                    #log.warning('BEFORE: ' + str(rows[0]))
                    rows = [ (str(each_row).split(',)')[0] + ')').replace('(','').replace(')','').split(',') for each_row in rows ]
                    #log.warning('AFTER: ' + str(rows[0]))
                else:
                    result = rows
                result = [ each_row for each_row in rows ]
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=str(list_values)))
            log.error(e)
            return False, None
        finally:
            con.close()
            return True, result

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
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def mood_create(self, TAG, UPDT_DT_TM, CRET_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (TAG, UPDT_DT_TM, CRET_DT_TM) VALUES (%s, %s, %s)'.format(table='MOOD')
            log.debug('[SQL] [MOOD] {query}'.format(query=query))
            values = (TAG, UPDT_DT_TM, CRET_DT_TM,)
            log.debug('[VALUES] [MOOD] {values}'.format(values=values))
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

    async def mood_read(self, TAG):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE TAG = %s'.format(table='MOOD')
            log.debug('[SQL] [MOOD] {query}'.format(query=query))
            values = (TAG,)
            log.debug('[VALUES] [MOOD] {values}'.format(values=values))
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

    async def mood_update(self, TAG, UPDT_DT_TM, CRET_DT_TM, OLD_TAG):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET TAG = %s, UPDT_DT_TM = %s, CRET_DT_TM = %s WHERE TAG = %s'.format(table='MOOD')
            log.debug('[SQL] [MOOD] {query}'.format(query=query))
            values = (TAG, UPDT_DT_TM, CRET_DT_TM, OLD_TAG,)
            log.debug('[VALUES] [MOOD] {values}'.format(values=values))
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

    async def mood_delete(self, TAG):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE TAG = %s'.format(table='MOOD')
            log.debug('[SQL] [MOOD] {query}'.format(query=query))
            values = (TAG,)
            log.debug('[VALUES] [MOOD] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def mood_song_create(self, TAG, URL, LAST_PLAYED_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (TAG, URL, LAST_PLAYED_DT_TM) VALUES (%s, %s, %s)'.format(table='MOOD_SONG')
            log.debug('[SQL] [MOOD_SONG] {query}'.format(query=query))
            values = (TAG, URL, LAST_PLAYED_DT_TM,)
            log.debug('[VALUES] [MOOD_SONG] {values}'.format(values=values))
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

    async def mood_song_read(self, TAG, URL):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE TAG = %s AND URL = %s'.format(table='MOOD_SONG')
            log.debug('[SQL] [MOOD_SONG] {query}'.format(query=query))
            values = (TAG, URL,)
            log.debug('[VALUES] [MOOD_SONG] {values}'.format(values=values))
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

    async def mood_song_update(self, TAG, URL, LAST_PLAYED_DT_TM, OLD_TAG, OLD_URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET TAG = %s, URL = %s, LAST_PLAYED_DT_TM = %s WHERE TAG = %s AND URL = %s'.format(table='MOOD_SONG')
            log.debug('[SQL] [MOOD_SONG] {query}'.format(query=query))
            values = (TAG, URL, LAST_PLAYED_DT_TM, OLD_TAG, OLD_URL,)
            log.debug('[VALUES] [MOOD_SONG] {values}'.format(values=values))
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

    async def mood_song_delete(self, TAG, URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE TAG = %s AND URL = %s'.format(table='MOOD_SONG')
            log.debug('[SQL] [MOOD_SONG] {query}'.format(query=query))
            values = (TAG, URL,)
            log.debug('[VALUES] [MOOD_SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status
            
    async def song_create(self, URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM):
        return self._song_create(URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM)

    def _song_create(self, URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM) VALUES (%s, %s, %s, %s, %s, %s)'.format(table='SONG')
            log.debug('[SQL] [SONG] {query}'.format(query=query))
            values = (URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM,)
            log.debug('[VALUES] [SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def song_read(self, URL):
        return self._song_read(URL)

    def _song_read(self, URL):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE URL = %s'.format(table='SONG')
            log.debug('[SQL] [SONG] {query}'.format(query=query))
            values = (URL,)
            log.debug('[VALUES] [SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            rows = cur.fetchall()
            if rows_affected == 1 and rows:
                result = [ each_row for each_row in rows ]
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return result

    async def song_update(self, URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM, OLD_URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET URL = %s, TITLE = %s, PLAY_COUNT = %s, VOLUME = %s, UPDT_DT_TM = %s, CRET_DT_TM = %s WHERE URL = %s'.format(table='SONG')
            log.debug('[SQL] [SONG] {query}'.format(query=query))
            values = (URL, TITLE, PLAY_COUNT, VOLUME, UPDT_DT_TM, CRET_DT_TM, OLD_URL,)
            log.debug('[VALUES] [SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def song_delete(self, URL):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE URL = %s'.format(table='SONG')
            log.debug('[SQL] [SONG] {query}'.format(query=query))
            values = (URL,)
            log.debug('[VALUES] [SONG] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def user_create(self, ID, NAME, TAG, YTI_URL, UPDT_DT_TM, CRET_DT_TM):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'INSERT INTO {table} (ID, NAME, TAG, YTI_URL, UPDT_DT_TM, CRET_DT_TM) VALUES (%s, %s, %s, %s, %s, %s)'.format(table='USER')
            log.debug('[SQL] [USER] {query}'.format(query=query))
            values = (ID, NAME, TAG, YTI_URL, UPDT_DT_TM, CRET_DT_TM,)
            log.debug('[VALUES] [USER] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status

    async def user_read(self, ID):
        result = None
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'SELECT * FROM {table} WHERE ID = %s'.format(table='USER')
            log.debug('[SQL] [USER] {query}'.format(query=query))
            values = (ID,)
            log.debug('[VALUES] [USER] {values}'.format(values=values))
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

    async def user_update(self, ID, NAME, TAG, YTI_URL, UPDT_DT_TM, CRET_DT_TM, OLD_ID):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'UPDATE {table} SET ID = %s, NAME = %s, TAG = %s, YTI_URL = %s, UPDT_DT_TM = %s, CRET_DT_TM = %s WHERE ID = %s'.format(table='USER')
            log.debug('[SQL] [USER] {query}'.format(query=query))
            values = (ID, NAME, TAG, YTI_URL, UPDT_DT_TM, CRET_DT_TM, OLD_ID,)
            log.debug('[VALUES] [USER] {values}'.format(values=values))
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

    async def user_delete(self, ID):
        status = False
        con = self.get_con()
        cur = con.cursor()
        try:
            query = 'DELETE FROM {table} WHERE ID = %s'.format(table='USER')
            log.debug('[SQL] [USER] {query}'.format(query=query))
            values = (ID,)
            log.debug('[VALUES] [USER] {values}'.format(values=values))
            rows_affected = cur.execute(query, values)
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
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
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
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
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
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
            status = (rows_affected == 1)
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
            log.debug('[ROWS_AFFECTED] {rows_affected}'.format(rows_affected=rows_affected))
            status = (rows_affected == 1)
            if status:
                con.commit()
        except Exception as e:
            log.error('Error with SQL: {query}, Values: {values}'.format(query=query, values=values))
            log.error(e)
        finally:
            con.close()
            return status


