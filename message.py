import mimetypes
import logging
import os
from email import encoders
from email.message import EmailMessage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate, parseaddr
from email.headerregistry import Address


class MakeMessage:
    def __init__(self, msg_from, msg_to, subject=None, date=None, content=None, attachments=None, message_id=None):
        self.msg_from = msg_from
        self.msg_to = msg_to
        self.subject = subject
        self.date = date
        self.content = content
        self.attachments = attachments
        self.message_id = message_id

    def __call__(self):

        parsed_sender = parseaddr(self.msg_from)
        self.msg_from = Address(parsed_sender[0], parsed_sender[1].split('@')[0], parsed_sender[1].split('@')[1])

        parsed_rcpts = [parseaddr(rcpt) for rcpt in self.msg_to]
        self.msg_to = [Address(rcpt[0], rcpt[1].split('@')[0], rcpt[1].split('@')[1]) for rcpt in parsed_rcpts]

        if self.attachments:
            logging.debug("Generating MIME Multipart message, to: {0}".format(self.msg_to))
            msg = MIMEMultipart()
            if len(self.msg_to) > 1:
                str_msg_to = []
                for rcpt in self.msg_to:
                    str_msg_to.append(rcpt.display_name + ' <' + rcpt.addr_spec + '>')
                msg['To'] = ', '.join(str_msg_to)
                logging.debug('!!!!!!!!!!!!!!!!!!!!RCPT TO: {0}'.format(msg['To']))
            else:
                msg['To'] = self.msg_to[0].display_name + ' <' + self.msg_to[0].addr_spec + '>'
            msg['From'] = self.msg_from.display_name + '<' + self.msg_from.addr_spec + '>'
            msg['Subject'] = self.subject

            if self.date:
                msg['Date'] = formatdate(self.date.timestamp(), localtime=True)
                logging.debug("Message date: {0}".format(msg['Date']))
            else:
                msg['Date'] = formatdate(localtime=True)
                logging.debug("Date of the message isn't given, added current date/time: {0}".format(msg['Date']))

            if self.message_id:
                msg['Message-ID'] = self.message_id
            else:
                msg['Message-ID'] = make_msgid(domain=self.msg_from.domain)
                logging.debug("Generated Message-ID: {0}".format(msg['Message-ID']))

            if self.content:
                logging.debug("Attaching text content")
                txt = MIMEText(self.content)
                msg.attach(txt)

            for file_path in self.attachments:
                if not os.path.isfile(file_path):
                    logging.warning("Given path file {0} is not a file, skipping..".format(file_path))
                    continue
                # Guess the content type based on the file's extension.  Encoding
                # will be ignored, although we should check for simple things like
                # gzip'd or compressed files.
                ctype, encoding = mimetypes.guess_type(file_path)
                filename = file_path.split('/')[-1]
                logging.debug("Attaching file {0}".format(filename))
                if ctype is None or encoding is not None:
                    # No guess could be made, or the file is encoded (compressed), so
                    # use a generic bag-of-bits type.
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                logging.debug("Guessed file type {0} for {1}".format(ctype, filename))
                if maintype == 'text':
                    with open(file_path) as fp:
                        attachment = MIMEText(fp.read(), _subtype=subtype)
                elif maintype == 'image':
                    with open(file_path, 'rb') as fp:
                        attachment = MIMEImage(fp.read(), _subtype=subtype)
                elif maintype == 'audio':
                    with open(file_path, 'rb') as fp:
                        attachment = MIMEAudio(fp.read(), _subtype=subtype)
                else:
                    with open(file_path, 'rb') as fp:
                        attachment = MIMEBase(maintype, subtype)
                        attachment.set_payload(fp.read())
                    # Encode the payload using Base64
                    encoders.encode_base64(attachment)
                # Set the filename parameter
                attachment.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(attachment)
                logging.debug("File {0} attached to the message".format(filename))
            logging.debug("Message {0} created and ready to send".format(msg['Message-ID']))
            return msg.as_bytes()

        else:
            logging.debug("Generating MIME NonMultipart message, to: {0}".format(self.msg_to))
            msg = EmailMessage()
            msg['To'] = self.msg_to
            msg['From'] = self.msg_from
            msg['Subject'] = self.subject

            if self.date:
                msg['Date'] = formatdate(self.date.timestamp(), localtime=True)
                logging.debug("Message date: {0}".format(msg['Date']))
            else:
                msg['Date'] = formatdate(localtime=True)
                logging.debug("Date of the message isn't given, added current date/time: {0}".format(msg['Date']))

            if self.message_id:
                msg['Message-ID'] = self.message_id
            else:
                msg['Message-ID'] = make_msgid(domain=self.msg_from.domain)
                logging.debug("Generated Message-ID: {0}".format(msg['Message-ID']))

            if self.content:
                msg.set_content(self.content)
                logging.debug("Message {0} created and ready to send".format(msg['Message-ID']))
                return msg.as_bytes()
            else:
                logging.debug("Message {0} created and ready to send".format(msg['Message-ID']))
                return msg.as_bytes()

    def __str__(self):
        return "MakeMessage - To: {0}".format(self.msg_to)
