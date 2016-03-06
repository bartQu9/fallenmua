from urllib.error import URLError, HTTPError
from xml.dom import minidom
from dns import resolver
import urllib.request
import logging


def parse_thunderbird_autoconfig(xml_autoconfig):
    mx_servers = []

    dom_tree = minidom.parseString(xml_autoconfig)
    c_nodes = dom_tree.childNodes

    for i in c_nodes[0].getElementsByTagName("outgoingServer"):
        try:
            curr_hostname = i.getElementsByTagName("hostname")[0].childNodes[0].toxml().lower()
            curr_port = int(i.getElementsByTagName("port")[0].childNodes[0].toxml())
            curr_sock_type = i.getElementsByTagName("socketType")[0].childNodes[0].toxml().lower()
            curr_username_type = i.getElementsByTagName("username")[0].childNodes[0].toxml()
            curr_auth_method = i.getElementsByTagName("authentication")[0].childNodes[0].toxml().lower()
        except IndexError:
            logging.error("Bad autoconfiguration file in ISPDB")
            return None

        mx_servers.append({'hostname': curr_hostname, 'port': curr_port, 'sock_type': curr_sock_type,
                           'username_type': curr_username_type, 'auth_method': curr_auth_method})

    if mx_servers:
        return mx_servers
    else:
        return None


def get_mx_from_ispdb(domain, _timeout=2):
    """
    Search for MX servers in Mozilla ISPDB.
    :param _timeout: resource connection timeout
    :param domain: a str FQDN
    :return: List of tuples consists of mx server and listening port
    """
    try:
        logging.debug("Connecting to the Mozilla ISPDB")
        xml_config = urllib.request.urlopen("https://autoconfig.thunderbird.net/autoconfig/v1.1/{0}".
                                            format(domain), timeout=_timeout).read()
        logging.debug("Fetched autoconfigure XML file from Mozilla ISPDB")
    except HTTPError:
        logging.info("No data for domain {0} in the Mozilla ISPDB".format(domain))
        return None
    except URLError as err:
        logging.warning("Unable to connect with the Mozilla ISPDB, reason: {0}".format(err))
        return None

    mx_servers = parse_thunderbird_autoconfig(xml_config)
    hostnames = [mx['hostname'] for mx in mx_servers]

    logging.debug("MX servers from Mozilla ISPDB: {0}".format(hostnames))

    return mx_servers


def get_mx_from_isp(domain, _timeout=4):
    try:
        logging.debug("Connecting to the ISP autoconfig")
        xml_config = urllib.request.urlopen("http://autoconfig.{0}/mail/config-v1.1.xml".format(domain),
                                            timeout=_timeout).read()
        logging.debug("Fetched autoconfigure XML file from autoconfig.{0}/mail/config-v1.1.xml".format(domain))
    except (HTTPError, URLError):
        logging.info("No data on autoconfig.{0}".format(domain))
        return None

    mx_servers = parse_thunderbird_autoconfig(xml_config)
    hostnames = [mx['hostname'] for mx in mx_servers]

    logging.debug("MX servers from autoconfig.{0}: {1}".format(domain, hostnames))

    return mx_servers


def get_mx_from_dns(domain):
    mx_servers = []

    try:
        _tmp_mx = []
        for mx in resolver.query(domain, "MX"):
            _tmp_mx.append(mx.to_text().split(" "))
        logging.info("Found {0} MX servers in DNS zone".format(len(_tmp_mx)))
        _tmp_mx.sort()  # sort MX's by priority

    except resolver.NXDOMAIN:
        logging.error("Cannot resolve domain name ".format(domain))
        return None

    for mx in _tmp_mx:
        for port in (587, 465, 25):  # Adding commonly known SMTP ports
            mx_servers.append({'hostname': mx[1], 'port': port, 'sock_type': None, 'username_type': None,
                               'auth_method': None})

    return mx_servers
