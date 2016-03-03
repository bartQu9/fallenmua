import getpass

import dns

print("---Fallen Mail User Agent---")

mailAddr = input("Step 1: enter your e-mail address (user@FQDN)\n"
                 "example: user@domain.com\n"
                 "Address: ")

while mailAddr.find("@") <= 0:
    mailAddr = input("wrong e-mail address\n"
                     "enter address again (user@domain.com)\n"
                     "Address: ")

fqdn = mailAddr.partition("@")[2]

nameServers = dns.resolver.query(fqdn, "MX")

password = getpass.getpass("Step 2: enter your e-mail password (password will be hidden)\n"
                           "Password: ")

messageFrom = input('Step 3: Enter sender address, if blank the message will be send as {0}\n'
                    'Example: Mike Mclain <mike.mclain@yahoo.com>,\n'
                    'or:      <mike.mclain@yahoo.com>,\n'
                    'or:      mike.mclain@yahoo.com\n'
                    'From: '.format(mailAddr))

if not messageFrom:
    messageFrom = mailAddr.partition("@")[0]

rcpt = input("Step 4: Enter recipient address (user@domain.com)\n"
             "To: ")

subject = input("Step 5: Enter message subject, nothing to explain..\n"
                "Subject: ")

attachment = input("Step 6: Enter the attachment file path Example: /home/mike/doc.txt or leave blank if u won't send "
                   "attachments\n"
                   "Path: ")
if attachment:
    attachmentType = int(input("And chose type of the file\n"
                               "1: Text\n"
                               "2: Image\n"
                               "3: Audio\n"
                               "4: Application\n"
                               "Type: "))