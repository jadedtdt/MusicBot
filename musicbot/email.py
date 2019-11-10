import configparser
import logging
import os
import smtplib
import string

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
log = logging.getLogger(__name__)

class Email:

    def __init__(self, url_song_dict=None, users_list=None):

        self.HOST = ''
        self.SUBJECT = ''
        self.TO = ''
        self.FROM = ''
        self.TEXT = ''

        self.load_config()

    def contains_non_ascii_characters(self, str):
        return not all(ord(c) < 128 for c in str)

    def add_header(self, message, header_name, header_value):
        if self.contains_non_ascii_characters(header_value):
            h = Header(header_value, 'utf-8')
            message[header_name] = h
        else:
            message[header_name] = header_value
        return message

    def send_exception(self, user_name, song_obj, exception):

        self.TEXT = "Exception was caught for {user} on {song}. Exception: {exception}".format(
            user=user_name if user_name else 'NoUserSpecified', song=str(song_obj) if song_obj else 'NoSongSpecified', exception=exception if exception else 'NoExceptionFound')

        msg = MIMEMultipart('alternative')
        msg = self.add_header(msg, 'Subject', self.SUBJECT)
        msg = self.add_header(msg, 'From', self.FROM)
        msg = self.add_header(msg, 'To', self.TO)

        if(self.contains_non_ascii_characters(self.TEXT)):
            plain_text = MIMEText(self.TEXT.encode('utf-8'),'plain','utf-8')
        else:
            plain_text = MIMEText(self.TEXT,'plain')

        msg.attach(plain_text)

        server = smtplib.SMTP(self.HOST, 587)
        server.ehlo()
        server.starttls()
        server.login(self.username, self.password)
        server.sendmail(self.FROM, self.TO, msg.as_string())
        server.quit()

    def load_config(self):

        config = configparser.ConfigParser(interpolation=None)
        config.read('config/email.ini', encoding='utf-8')

        self.HOST = config.get('email', 'HOST')
        self.SUBJECT = config.get('email', 'SUBJECT')
        self.TO = config.get('email', 'TO')
        self.FROM = config.get('email', 'FROM')
        self.TEXT = config.get('email', 'TEXT')

        self.username = os.environ['EMAIL_USERNAME']
        self.password = os.environ['EMAIL_PASSWORD']
