import logging
from datetime import datetime

import requests
from nameparser import HumanName
from BeautifulSoup import BeautifulSoup


logger = logging.getLogger('TDCJ')

BASE_URL = "https://offender.tdcj.texas.gov"
SEARCH_PATH = "/OffenderSearch/search.action"


def query_by_name(first, last):
    """
    Query the TDCJ database with an inmate name.
    """
    logger.debug("Querying with name %s, %s", last, first)
    return _query_helper(firstName=first, lastName=last)


def query_by_inmate_id(inmate_id):
    """
    Query the TDCJ database with an inmate id.
    """

    try:
        inmate_id = '{:08d}'.format(int(inmate_id))
    except ValueError:
        msg = "{} is not a valid Texas inmate number".format(inmate_id)
        raise ValueError(msg)

    logger.debug("Querying with ID %s", inmate_id)
    matches = _query_helper(tdcj=inmate_id)
    if not matches:
        return None

    assert len(matches) == 1, "Unexpectedly got multiple matches on ID"
    return matches[0]


def format_inmate_id(inmate_id):
    """
    Helper for formatting TDCJ inmate IDs.
    """
    return '{:08d}'.format(int(inmate_id))


def _query_helper(**kwargs):
    """
    Private helper for querying TDCJ.
    """

    params = {
        'btnSearch': 'Search',
        'gender':    'ALL',
        'page':      'index',
        'race':      'ALL',
        'tdcj':      '',
        'sid':       '',
        'lastName':  '',
        'firstName': ''
    }
    params.update(kwargs)

    with requests.Session() as session:
        url = BASE_URL + SEARCH_PATH
        response = session.post(url, params=params)
        soup = BeautifulSoup(response.text)

    if soup.html.head.title.text != "Offender Search List":
        return []

    table = soup.find('table', {'class': 'ws'})
    rows = table.findAll('tr')
    keys = [ele.text.strip() for ele in rows[0].findAll('th')]

    def row_to_entry(row):
        values = [ele.text.strip() for ele in row.findAll('td')]
        entry = dict(zip(keys, values))
        entry['href'] = row.find('a').get('href')
        return entry

    entries = map(row_to_entry, rows[1:])
    inmates = map(_entry_to_inmate, entries)

    if not inmates:
        logger.debug("No results returned")

    return inmates


def _entry_to_inmate(entry):
    inmate = dict()

    inmate['id'] = entry['TDCJ Number']
    inmate['jurisdiction'] = 'Texas'

    name = HumanName(entry.get('Name', ''))
    inmate['first_name'] = name.first
    inmate['last_name'] = name.last

    inmate['unit'] = entry['Unit of Assignment']

    inmate['race'] = entry.get('Race', None)
    inmate['sex'] = entry.get('Gender', None)
    inmate['url'] = BASE_URL + entry['href'] if 'href' in entry else None

    release_string = entry['Projected Release Date']
    try:
        release = datetime.strptime(release_string, "%Y-%m-%d").date()
    except ValueError:
        release = release_string
        logger.debug("Failed to convert release date to date: %s", release)
    finally:
        inmate['release'] = release

    inmate['datetime_fetched'] = datetime.now()

    logger.debug(
        "%s, %s #%s: MATCHES",
        inmate['last_name'], inmate['first_name'], inmate['id']
    )

    return inmate