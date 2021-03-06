import smtplib
import logging
from _socket import timeout
from resolvers import get_mx_from_ispdb, get_mx_from_isp, get_mx_from_dns
from socket import getdefaulttimeout

smtp_ports = {'all': (587, 465, 25),
              'starttls': (587, 25),
              'ssl': (465,),
              'plain': (587, 25)}


class SMTPHandler:
    def __init__(self, domain):
        self.domain = domain
        self.mx_servers = []
        self.session = None
        self.connected_mx_server = {'hostname': None, 'port': None}
        self.skip_autoconfig = False
        logging.debug("Initializing a SMTPHandler object")

    def resolve_mx(self):

        if not self.skip_autoconfig:
            logging.debug("Searching MX servers in the Mozilla ISPDB")
            _mx_from_ispdb = get_mx_from_ispdb(self.domain)

            if _mx_from_ispdb:
                self.mx_servers = _mx_from_ispdb
                return self.mx_servers
            else:
                logging.debug("Searching MX servers in the domain autoconfig")
                _mx_from_isp = get_mx_from_isp(self.domain)
                if _mx_from_isp:
                    self.mx_servers = _mx_from_isp
                    return self.mx_servers
                else:
                    logging.debug("Searching MX servers in DNS zone")
                    self.mx_servers = get_mx_from_dns(self.domain)
                    return self.mx_servers

    def connect(self, tlsmethod='all'):

        """
        Establish connection to the first reachable mx server with the best possible encryption method
        :param tlsmethod: is a str param which tells the favorite encryption method, by default 'all', also available:
        'starttls','ssl', 'none'.
        :return If connection with required encryption is established properly returned will be a smtplib.SMTP object,
        otherwise None object will be returned.
        """

        _timeout = 1

        # TODO resolver.query() returning GOOGLE MX's when querying domain hasn't such MX records LOL
        if not self.mx_servers:
            logging.debug("No MX servers, it seems that the mx query hasn't been executing yet")
            if not self.resolve_mx():
                logging.error("No such MX server to connect")
                return False

        for mx_server in self.mx_servers:
            if mx_server['port'] in smtp_ports[tlsmethod]:
                try:
                    if mx_server['port'] in smtp_ports['ssl']:
                        logging.debug(
                            "Trying to connect {0} on {1}".format(mx_server['hostname'], mx_server['port']))
                        self.session = smtplib.SMTP_SSL(mx_server['hostname'], mx_server['port'], timeout=_timeout)
                    else:
                        logging.debug(
                            "Trying to connect {0} on {1}".format(mx_server['hostname'], mx_server['port']))
                        self.session = smtplib.SMTP(mx_server['hostname'], mx_server['port'], timeout=_timeout)
                except (ConnectionRefusedError, smtplib.SMTPServerDisconnected, timeout) as err:
                    logging.debug("Unable to connect to the server {0}, on port {1}, reason: {2}"
                                  .format(mx_server['hostname'], mx_server['port'], err))
                    continue

                logging.info("Connection with {0} on {1} established successful".format(mx_server['hostname'],
                                                                                        mx_server['port']))
                self.connected_mx_server = mx_server
                self.session.sock.settimeout(getdefaulttimeout())
                logging.debug("Connection timeout changed to default")
                break

        if not self.session:
            logging.error("Unable to connect to any MX server on ports: {0}".format(smtp_ports[tlsmethod]))
            return None

        # if session should be encrypted, do it now
        if tlsmethod != 'none':
            if self.connected_mx_server['port'] in smtp_ports['starttls']:
                self.session.ehlo(
                    '[' + self.session.sock.getsockname()[0] + ']')  # with '[]' spamassassin sees as hostname
                if 'starttls' in self.session.esmtp_features:
                    self.session.starttls()
                    logging.info("Connection with {0} is encrypted now".format(self.connected_mx_server['hostname']))
                    return self.session
                else:
                    logging.error(
                        "Server {0} on {1} doesnt doesn't support STARTTLS command".format(
                            self.connected_mx_server['hostname'],
                            self.connected_mx_server['port']))
                    self.session.quit()
                    return None
            else:
                logging.debug("Connection with {0} already encrypted".format(self.connected_mx_server['hostname']))
                return self.session
        else:
            logging.debug("Unencrypted connection with {0}".format(self.connected_mx_server['hostname']))
            return self.session

    def authorize(self, user, password):
        """
        Authorizes user on the SMTP server, it automatically check whether appending the at separated FQDN is a MUA's
        job.
        :param user: string, only username without at separated domain.
        :param password: string represents the user's password in the clear form.
        :return: True if authorization successful or False if error(s) occurred.
        """
        if not self.session:
            logging.debug("Cannot authorize user, when connection isn't established")
            return False

        self.session.ehlo('[' + self.session.sock.getsockname()[0] + ']')
        if 'auth' in self.session.esmtp_features:
            if self.connected_mx_server['username_type'] == '%EMAILLOCALPART%':
                try:
                    self.session.login(user, password)
                    logging.info("Authentication successful")
                    return True
                except smtplib.SMTPAuthenticationError:
                    logging.error("Unable to authorize user")
                    self.session = None
                    return False
            elif self.connected_mx_server['username_type'] == '%EMAILADDRESS%':
                try:
                    self.session.login(user + '@' + self.domain, password)
                    logging.info("Authentication successful")
                    return True
                except smtplib.SMTPAuthenticationError:
                    logging.error("Unable to authorize user")
                    self.session = None
                    return False
            else:
                logging.debug("Unsupported or unknown username type, trying '%EMAILLOCALPART%")
                try:
                    self.session.login(user, password)
                    logging.info("Authentication successful")
                    return True
                except smtplib.SMTPAuthenticationError:
                    try:
                        logging.debug("Authentication error, now trying with @FQDN")
                        self.session.login(user + '@' + self.domain, password)
                        logging.info("Authentication successful")
                        return True
                    except smtplib.SMTPAuthenticationError:
                        logging.error("Unable to authorize user")
                        self.session = None
                        return False
        else:
            logging.error("Server {0} on {1}, doesn't support AUTH command".
                          format(self.connected_mx_server['hostname'], self.connected_mx_server['port']))
            return False

    def send_mail(self, env_from, env_to, message):
        """
        :param message: previously prepared MIME message as bytes
        :param env_from: e-mail address which will be a SMTP MAIL FROM parameter
        :param env_to: list of e-mail addresses which will be a SMTP RCPT TO parameter
        :return: True if message sent successfully, False if the response is not 250 "OK"
        """
        if not self.session:
            logging.debug("Cannot send mail, when connection isn't established")
            return False

        try:
            logging.debug("Sending cmd MAIL FROM: {0}".format(env_from))
            _mail_from_response = self.session.mail(env_from)
            logging.debug("MAIL FROM response: {0}".format(_mail_from_response))

            if _mail_from_response[0] != 250:
                logging.error('Remote server replied "{0}" in response to "MAIL FROM" '
                              'command'.format(_mail_from_response))
                return False

            for rcpt in env_to:
                logging.debug("Sending cmd RCPT TO: {0}".format(rcpt))
                _rcpt_to_response = self.session.rcpt(rcpt)
                logging.debug("RCPT To response: {0}".format(_rcpt_to_response))

                if _rcpt_to_response[0] != 250:
                    logging.error('Remote server replied "{0}" in response to "RCPT TO" '
                                  'command'.format(_rcpt_to_response))
                    return False

            logging.info("Sending message, size: {0:.2f}MiB".format(len(message) / 1024 / 1024))
            _data_response = self.session.data(message)
            logging.debug("DATA response: {0}".format(_data_response))

            if _data_response[0] != 250:
                logging.error('Remote server replied "{0}" in response to "DATA" '
                              'command'.format(_data_response))
                return False
        except smtplib.SMTPServerDisconnected:
            logging.error("Unexpectedly lost connection with the SMTP server")
            self.session = None
            return False

        logging.info("Mail sent successful")
        return True

    def close(self):

        if self.session:
            logging.debug("Sending cmd QUIT")
            _quit_response = self.session.quit()
            logging.debug("QUIT response {0}".format(_quit_response))
            logging.info("Session with {0} closed".format(self.connected_mx_server['hostname']))
            self.session = None
            self.connected_mx_server = {'hostname': None, 'port': None}
            return
        else:
            logging.debug("Cannot close session which doesn't exist")
            return
