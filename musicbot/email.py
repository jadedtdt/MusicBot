import configparser
import logging
import smtplib
import string
log = logging.getLogger(__name__)

class Email:

    def __init__(self, url_song_dict=None, users_list=None):


        self.HOST = ''
        self.SUBJECT = ''
        self.TO = ''
        self.FROM = ''
        self.TEXT = ''

        self.load_config()

    def send_exception(self, user_name, song_obj, exception):

        self.TEXT = "Exception was caught for {user} on {song}. Exception: {exception}".format(
            user=user_name if user_name else 'NoUserSpecified', song=song_obj if song_obj else 'NoSongSpecified', exception=exception if exception else 'NoExceptionFound')

        BODY = "\r\n".join([
                "From: %s" % self.FROM,
                "To: %s" % self.TO,
                "Subject: %s" % self.SUBJECT,
                "",
                self.TEXT
                ])

        server = smtplib.SMTP(self.HOST, 587)
        server.ehlo()
        server.starttls()
        server.login(self.username, self.password)
        server.sendmail(self.FROM, self.TO, BODY)
        server.quit()

    def send_corruption(self, user_name, song_obj, exception):

        self.TEXT = ""

        BODY = "\r\n".join((
                "From: %s" % FROM,
                "To: %s" % TO,
                "Subject: %s" % SUBJECT,
                "",
                TEXT
                ))
        server = smtplib.SMTP(HOST)
        server.ehlo()
        server.login(self.username, self.password)
        server.sendmail(FROM, [TO], BODY)
        server.quit()

    def load_config(self):

        config = configparser.ConfigParser(interpolation=None)
        config.read('config/email.ini', encoding='utf-8')

        self.HOST = config.get('email', 'HOST')
        self.SUBJECT = config.get('email', 'SUBJECT')
        self.TO = config.get('email', 'TO')
        self.FROM = config.get('email', 'FROM')
        self.TEXT = config.get('email', 'TEXT')

        config.read('config/email_auth.ini', encoding='utf-8')

        self.username = config.get('email_auth', 'USERNAME')
        self.password = config.get('email_auth', 'PASSWORD')