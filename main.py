#!/usr/bin/python3

import signal
import sys
import argparse
import getpass
import datetime
import logging
from workers import MsgWorker
from message import MakeMessage
from multiprocessing import Queue, JoinableQueue, cpu_count
from smtp import SMTPHandler


def terminate_workers(processes_list):
    for proc in processes_list:
        if proc.is_alive():
            logging.debug("Terminating process: {0}".format(proc.name))
            proc.terminate()
        else:
            logging.debug("Process {0} won't be killed, because is already dead ")


def main():

    def sigint_handler(signal, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, sigint_handler)  # SIGINT handler register

    argParser = argparse.ArgumentParser(description='Fallen MUA - a simple Mail User Agent', prog="fallenmua")
    argParser.epilog = 'NOTE: "-a" argument is almost always required to getting a relay access on the remote SMTP' \
                       ' server!'
    argParser.add_argument("from_", metavar="From", help="Sender (envelope from) e-mail address (user@example.com)")
    argParser.add_argument("to", metavar="To", help="Comma separated recipients list")
    argParser.add_argument("-a", "--auth", action="store_true",
                           help='Use ESMTP authorization feature (you will be asked for a password)')
    argParser.add_argument("-A", "--attach", help="Add attachment to the message")
    argParser.add_argument("-p", "--password", help="Enter the ESMTP authorization password in the visible way")
    argParser.add_argument("-s", "--subject", help="Subject of the e-mail message, by default, blank")
    argParser.add_argument("-d", "--date", help='Date and time of the message, by default, current date and time.')
    argParser.add_argument("-v", "--verbosity", action="count", default=0, help="increase output verbosity")
    argParser.add_argument("-c", "--content", help="Message content")
    argParser.add_argument("--bcc", action="store_true", help="blind carbon copy")

    args = argParser.parse_args()

    if args.verbosity == 1:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    elif args.verbosity >= 2:
        logging.basicConfig(format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s', datefmt='%H:%M:%S',
                            level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.WARNING)

    msg = {}
    smtp = {}
    env = {'to': args.to.replace(" ", "").split(","), 'from': args.from_}

    msg['msg_from'] = env['from']
    smtp['username'] = env['from'].split("@")[0]
    smtp['domain'] = env['from'].split("@")[1]

    if args.auth:
        if args.password:
            smtp['password'] = args.password
        else:
            smtp['password'] = getpass.getpass("Password: ")
    else:
        smtp['password'] = None

    if args.subject:
        msg['subject'] = args.subject
    else:
        msg['subject'] = None

    if args.date:
        try:
            msg['date'] = datetime.datetime.strptime(args.date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print('Wrong date/time format\n The correct example: "2016-2-4 10:30:12"')
            sys.exit(2)
    else:
        msg['date'] = None

    if args.attach:
        msg['attachments'] = [path.strip() for path in args.attach.split(',')]
    else:
        msg['attachments'] = None

    if args.content:
        msg['content'] = args.content.replace('\\n', '\n')
    else:
        msg['content'] = None

    tasks = JoinableQueue()
    messages_ready_to_send = Queue()

    if args.bcc:
        messages_num = len(env['to'])
        logging.info("Number of messages to prepare and send: {0}".format(messages_num))
        for curr_rcpt in env['to']:
            msg['msg_to'] = [curr_rcpt]
            tasks.put([env['from'], [curr_rcpt], MakeMessage(**msg)])
    else:
        messages_num = 1
        logging.info("Number of messages to prepare and send: {0}".format(messages_num))
        msg['msg_to'] = env['to']
        tasks.put([env['from'], env['to'], MakeMessage(**msg)])

    msg_workers_count = cpu_count()
    logging.debug("Creating {0} MsgWorkers".format(msg_workers_count))
    msg_workers = [MsgWorker(tasks, messages_ready_to_send) for _ in range(msg_workers_count)]

    for msg_worker in msg_workers:
        logging.debug("Startning {0}".format(msg_worker.name))
        msg_worker.start()

    # Add a poison pill for each MsgWorker
    for i in range(msg_workers_count):
        tasks.put(None)

    session = SMTPHandler(smtp['domain'])

    if not session.connect():
        logging.critical("Unable to connect any {0} MX server, exiting..".format(smtp['domain']))
        terminate_workers(msg_workers)
        sys.exit(2)

    if smtp['password']:
        if not session.authorize(smtp['username'], smtp['password']):
            logging.critical("Cannot authorize user, maybe wrong password?")
            session.close()
            terminate_workers(msg_workers)
            sys.exit(2)

    for msg in range(messages_num):
        msg_to_send = messages_ready_to_send.get()

        if not session.send_mail(msg_to_send[0], msg_to_send[1], msg_to_send[2]):
            logging.critical("Unable to send mail, increase output verbosity to see details")
            terminate_workers(msg_workers)
            sys.exit(1)

    logging.info("It seems that there are no more messages to send, closing connection with MX server")


if __name__ == "__main__":
    main()
