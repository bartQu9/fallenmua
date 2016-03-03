from urllib.error import URLError, HTTPError
from xml.dom import minidom
import urllib.request
import logging


def get_mx_from_ispdb(domain):
    """
    Search for MX servers in Mozilla ISPDB.
    :param domain: a str FQDN
    :return: List of tuples consists of mx server and listening port
    """
    try:
        logging.debug("Connecting to the Mozilla ISPDB")
        xml_config = urllib.request.urlopen("https://autoconfig.thunderbird.net/autoconfig/v1.1/{0}".
                                            format(domain), timeout=2).read()
        logging.debug("Fetched autoconfigure XML file from Mozilla ISPDB")
    except HTTPError:
        logging.info("No data for domain {0} in the Mozilla ISPDB".format(domain))
        return None
    except URLError as err:
        logging.warning("Unable to connect with the Mozilla ISPDB, reason: {0}".format(err))
        return None

    dom_tree = minidom.parseString(xml_config)
    c_nodes = dom_tree.childNodes

    mx_servers = []
    for i in c_nodes[0].getElementsByTagName("outgoingServer"):
        mx_servers.append([i.getElementsByTagName("hostname")[0].childNodes[0].toxml(),
                           list([int(i.getElementsByTagName("port")[0].childNodes[0].toxml())])])

    logging.debug("MX servers from Mozilla ISPDB: {0}".format(mx_servers))

    if not mx_servers:
        return None
    else:
        return mx_servers


def get_mx_from_isp(domain):
    try:
        logging.debug("Connecting to the ISP autoconfig")
        xml_config = urllib.request.urlopen("http://autoconfig.{0}/mail/config-v1.1.xml".format(domain),
                                            timeout=4).read()
        logging.debug("Fetched autoconfigure XML file from autoconfig.{0}/mail/config-v1.1.xml".format(domain))
    except (HTTPError, URLError):
        logging.info("No data on autoconfig.{0}".format(domain))
        return None

    dom_tree = minidom.parseString(xml_config)
    c_nodes = dom_tree.childNodes

    mx_servers = []
    for i in c_nodes[0].getElementsByTagName("outgoingServer"):
        mx_servers.append([i.getElementsByTagName("hostname")[0].childNodes[0].toxml(),
                           list([int(i.getElementsByTagName("port")[0].childNodes[0].toxml())])])

    logging.debug("MX servers from autoconfig.{0}: {1}".format(domain, mx_servers))

    if not mx_servers:
        logging.debug("Cannot read properly XML data from autoconfig")
        return None
    else:
        return mx_servers
