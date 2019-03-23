import configparser
import MySQLdb

def main():

    def list_to_str(input_list):
        if not input_list:
            return ''

        output_str = str(input_list).replace('[', '', 1).replace(']', '', 1)
        if '[' in output_str or ']' in output_str:
            raise ValueException('Cannot have list within list if you want to convert to string')
            return ''
        return output_str.replace('\'', '')

    def gen_set(columns):
        set_str = None

        if columns:
            set_str = 'SET {column0} = %s'.format(column0=columns[0])
            for i in range(1, len(columns)):
                set_str += ', {column} = %s'.format(column=columns[i])
        return set_str

    def gen_where(columns, boolean_operator):
        where_str = None
        if boolean_operator.upper() != 'AND' and boolean_operator.upper() != 'OR':
            print("Error: Only OR/AND operations allowed for gen_where() function")
            return where_str

        if columns:
            where_str = 'WHERE {column0} = %s'.format(column0=columns[0])
            for i in range(1, len(columns)):
                where_str += ' {boolean_operator} {column} = %s'.format(column=columns[i], boolean_operator=boolean_operator)
        return where_str

    def get_con():

        config = configparser.ConfigParser(interpolation=None)
        config.read('../config/database_auth.ini', encoding='utf-8')

        host = config.get('database_auth', 'host')
        user = config.get('database_auth', 'user')
        passwd = config.get('database_auth', 'passwd')
        db = config.get('database_auth', 'db')

        return MySQLdb.connect(host=host, user=user, passwd=passwd, db=db, init_command='SET NAMES utf8mb4;', charset="utf8mb4")

    def get_columns(table):
        rs = []
        con = get_con()
        cur = con.cursor()

        config = configparser.ConfigParser(interpolation=None)
        config.read('../config/database_auth.ini', encoding='utf-8')
        db = config.get('database_auth', 'db')

        try:
            query = 'SELECT `COLUMN_NAME` FROM `INFORMATION_SCHEMA`.`COLUMNS` WHERE `TABLE_SCHEMA` = %s AND `TABLE_NAME` = %s'
            values = (db, table)
            results = cur.execute(query, values)
            rows = cur.fetchmany(size=100)
            if rows:
                rs = [each_row[0] for each_row in rows]
        except Exception as e:
            print('Failed to get columns')
            print(str(e))
        finally:
            con.close()
            return rs

    def get_pks(table):
        rs = []
        con = get_con()
        cur = con.cursor()

        config = configparser.ConfigParser(interpolation=None)
        config.read('../config/database_auth.ini', encoding='utf-8')
        db = config.get('database_auth', 'db')

        try:
            query = 'SELECT `COLUMN_NAME` FROM `INFORMATION_SCHEMA`.`KEY_COLUMN_USAGE` WHERE `TABLE_SCHEMA` = %s AND `TABLE_NAME` = %s;'
            values = (db, table)
            results = cur.execute(query, values)
            rows = cur.fetchmany(size=100)
            if rows:
                rs = [each_row[0] for each_row in rows]
        except Exception as e:
            print('Failed to get pks')
            print(str(e))
        finally:
            con.close()
            return rs

    def get_tables():
        rs = []
        con = get_con()
        cur = con.cursor()

        config = configparser.ConfigParser(interpolation=None)
        config.read('../config/database_auth.ini', encoding='utf-8')
        db = config.get('database_auth', 'db')

        try:
            query = 'SELECT DISTINCT `TABLE_NAME` FROM `INFORMATION_SCHEMA`.`COLUMNS` WHERE `TABLE_SCHEMA` = %s'
            values = [(db)]
            results = cur.execute(query, values)
            rows = cur.fetchmany(size=100)
            if rows:
                rs = [each_row[0] for each_row in rows]
        except Exception as e:
            print('Failed to get tables')
            print(str(e))
        finally:
            con.close()
            return rs

    file_contents = ''

    # Begin Head
    head = 'import asyncio\n' \
    'import configparser\n' \
    'import logging\n' \
    'import MySQLdb\n' \
    '\n' \
    'from datetime import datetime\n' \
    '\n' \
    'from .config import Config, ConfigDefaults\n' \
    'from .email import Email\n' \
    'from .song import Music\n' \
    'from .user import User\n' \
    'log = logging.getLogger(__name__)\n' \
    '\n' \
    'class SqlFactory:\n' \
    '\n' \
    '\tdef __init__(self):\n' \
    '\n' \
    '\t\tconfig_file = ConfigDefaults.options_file\n' \
    '\t\tself.config = Config(config_file)\n' \
    '\n' \
    '\t\tself.load_config()\n' \
    '\n' \
    '\tdef get_con(self):\n' \
    '\t\treturn MySQLdb.connect(host=self.host, user=self.user, passwd=self.passwd, db=self.db, init_command=\'SET NAMES utf8mb4;\', charset="utf8mb4")\n' \
    '\n' \
    '\tdef list_to_str(self, input_list):\n' \
    '\t\tif not input_list:\n' \
    '\t\t\treturn None\n' \
    '\n' \
    '\t\toutput_str = str(input_list).replace(\'[\', \'\', 1).replace(\']\', \'\', 1)\n' \
    '\t\tif \'[\' in output_str or \']\' in output_str:\n' \
    '\t\t\traise ValueException(\'Cannot have list within list if you want to convert to string\')\n' \
    '\t\t\treturn None\n' \
    '\t\treturn output_str.replace(\'\\\'\', \'\')\n' \
    '\n' \
    '\tdef load_config(self):\n' \
    '\n' \
    '\t\tconfig = configparser.ConfigParser(interpolation=None)\n' \
    '\t\tconfig.read(\'config/database_auth.ini\', encoding=\'utf-8\')\n' \
    '\n' \
    '\t\tself.host = config.get(\'database_auth\', \'host\')\n' \
    '\t\tself.user = config.get(\'database_auth\', \'user\')\n' \
    '\t\tself.passwd = config.get(\'database_auth\', \'passwd\')\n' \
    '\t\tself.db = config.get(\'database_auth\', \'db\')\n' \
    '\n'

    # Begin Body
    body = ''
    blacklist_tables = ['MOOD', 'MOOD_SONG', 'SONG', 'USER']
    tables = get_tables()
    #tables = [ each_table for each_table in tables if each_table not in blacklist_tables ]
    tables = filter(lambda x : x not in blacklist_tables, tables)

    for each_table in tables:
        columns = get_columns(each_table)
        pks = get_pks(each_table)
        if columns:
            body += '\tasync def {table}_create(self, {columns_str}):\n'.format(table=each_table.lower(), columns_str=list_to_str(columns))
            body += '\t\tstatus = False\n'
            body += '\t\tcon = self.get_con()\n'
            body += '\t\tcur = con.cursor()\n'
            body += '\t\ttry:\n'
            body += '\t\t\tquery = \'INSERT INTO {{table}} ({columns_str}) VALUES ({values_list_qmarks})\'.format(table=\'{table}\')\n'.format(table=each_table, columns_str=list_to_str(columns), values_list_qmarks=list_to_str([ '%s' for i in range(0, len(columns)) ]))
            body += '\t\t\tlog.debug(\'[SQL] [{table}] {{query}}\'.format(query=query))\n'.format(table=each_table)
            body += '\t\t\tvalues = {columns_str}\n'.format(columns_str=str(columns).replace('\'', '').replace('[', '(', 1).replace(']', ',)', 1))
            body += '\t\t\tlog.debug(\'[VALUES] [{table}] {{values}}\'.format(values=values))\n'.format(table=each_table)
            body += '\t\t\trows_affected = cur.execute(query, values)\n'
            body += '\t\t\tstatus = (rows_affected == 1)\n'
            body += '\t\t\tif status:\n'
            body += '\t\t\t\tcon.commit()\n'
            body += '\t\texcept Exception as e:\n'
            body += '\t\t\tlog.error(\'Error with SQL: {query}, Values: {values}\'.format(query=query, values=values))\n'
            body += '\t\t\tlog.error(e)\n'
            body += '\t\tfinally:\n'
            body += '\t\t\tcon.close()\n'
            body += '\t\t\treturn status\n'
            body += '\n'
            body += '\tasync def {table}_read(self, {pks_str}):\n'.format(table=each_table.lower(), pks_str=list_to_str(pks))
            body += '\t\tresult = None\n'
            body += '\t\tcon = self.get_con()\n'
            body += '\t\tcur = con.cursor()\n'
            body += '\t\ttry:\n'
            body += '\t\t\tquery = \'SELECT * FROM {{table}} {where_clause}\'.format(table=\'{table}\')\n'.format(table=each_table, where_clause=gen_where(pks, 'AND'))
            body += '\t\t\tlog.debug(\'[SQL] [{table}] {{query}}\'.format(query=query))\n'.format(table=each_table)
            body += '\t\t\tvalues = {pks_str}\n'.format(pks_str=str(pks).replace('\'', '').replace('[', '(', 1).replace(']', ',)', 1))
            body += '\t\t\tlog.debug(\'[VALUES] [{table}] {{values}}\'.format(values=values))\n'.format(table=each_table)
            body += '\t\t\trows_affected = cur.execute(query, values)\n'
            body += '\t\t\trows = cur.fetchall()\n'
            body += '\t\t\tif rows_affected == 1 and rows:\n'
            body += '\t\t\t\tresult = [ each_row for each_row in rows[0] ]\n'
            body += '\t\texcept Exception as e:\n'
            body += '\t\t\tlog.error(\'Error with SQL: {query}, Values: {values}\'.format(query=query, values=values))\n'
            body += '\t\t\tlog.error(e)\n'
            body += '\t\tfinally:\n'
            body += '\t\t\tcon.close()\n'
            body += '\t\t\treturn result\n'
            body += '\n'
            body += '\tasync def {table}_update(self, {columns_str}, {old_pks_str}):\n'.format(table=each_table.lower(), columns_str=list_to_str(columns), old_pks_str=list_to_str(['OLD_' + each_pk for each_pk in pks]))
            body += '\t\tstatus = False\n'
            body += '\t\tcon = self.get_con()\n'
            body += '\t\tcur = con.cursor()\n'
            body += '\t\ttry:\n'
            body += '\t\t\tquery = \'UPDATE {{table}} {set_clause} {where_clause}\'.format(table=\'{table}\')\n'.format(table=each_table, set_clause=gen_set(columns), where_clause=gen_where(pks, 'AND'))
            body += '\t\t\tlog.debug(\'[SQL] [{table}] {{query}}\'.format(query=query))\n'.format(table=each_table)
            body += '\t\t\tvalues = {pks_str}\n'.format(pks_str=str(columns + ['OLD_' + each_pk for each_pk in pks]).replace('\'', '').replace('[', '(', 1).replace(']', ',)', 1))
            body += '\t\t\tlog.debug(\'[VALUES] [{table}] {{values}}\'.format(values=values))\n'.format(table=each_table)
            body += '\t\t\trows_affected = cur.execute(query, values)\n'
            body += '\t\t\tstatus = (rows_affected == 1)\n'
            body += '\t\t\tif status:\n'
            body += '\t\t\t\tcon.commit()\n'
            body += '\t\texcept Exception as e:\n'
            body += '\t\t\tlog.error(\'Error with SQL: {query}, Values: {values}\'.format(query=query, values=values))\n'
            body += '\t\t\tlog.error(e)\n'
            body += '\t\tfinally:\n'
            body += '\t\t\tcon.close()\n'
            body += '\t\t\treturn status\n'

            old_pks_str=list_to_str(['OLD_' + each_pk for each_pk in pks])
            body += '\n'
            body += '\tasync def {table}_delete(self, {pks_str}):\n'.format(table=each_table.lower(), pks_str=list_to_str(pks))
            body += '\t\tstatus = False\n'
            body += '\t\tcon = self.get_con()\n'
            body += '\t\tcur = con.cursor()\n'
            body += '\t\ttry:\n'
            body += '\t\t\tquery = \'DELETE FROM {{table}} {where_clause}\'.format(table=\'{table}\')\n'.format(table=each_table, where_clause=gen_where(pks, 'AND'))
            body += '\t\t\tlog.debug(\'[SQL] [{table}] {{query}}\'.format(query=query))\n'.format(table=each_table)
            body += '\t\t\tvalues = {pks_str}\n'.format(pks_str=str(pks).replace('\'', '').replace('[', '(', 1).replace(']', ',)', 1))
            body += '\t\t\tlog.debug(\'[VALUES] [{table}] {{values}}\'.format(values=values))\n'.format(table=each_table)
            body += '\t\t\trows_affected = cur.execute(query, values)\n'
            body += '\t\t\tstatus = (rows_affected == 1)\n'
            body += '\t\t\tif status:\n'
            body += '\t\t\t\tcon.commit()\n'
            body += '\t\texcept Exception as e:\n'
            body += '\t\t\tlog.error(\'Error with SQL: {query}, Values: {values}\'.format(query=query, values=values))\n'
            body += '\t\t\tlog.error(e)\n'
            body += '\t\tfinally:\n'
            body += '\t\t\tcon.close()\n'
            body += '\t\t\treturn status\n'
            body += '\n'

    # Begin Tail
    tail = '\n'

    file_contents += head
    file_contents += body
    file_contents += tail
    # tabs to 4 spaces so it's compatible with the rest of the musicbot programs
    file_contents = file_contents.replace('\t', '    ')

    with open('sqlfactory.py', 'w', encoding='utf8') as f:
        f.write(file_contents)

main()
