import checkdmarc
from collections import OrderedDict

import signal
import os
# for modifying datetime timezones
from datetime import timezone, timedelta


# We want to skip tls check (port 25 etc traffic) by default when running on Heroku
def full_check(domain, skip_tls=True, timeout=None):
    res = None
    nameservers=os.getenv('NAMESERVERS', None)
    if nameservers:
        nameservers = nameservers.split(",")
    if timeout:
        def raise_TimedOutExc(a, b):
            raise TimedOutExc(f"checkdmarc used more than predefined timeout ({timeout} seconds)")
        signal.signal(signal.SIGALRM, raise_TimedOutExc)
        signal.alarm(timeout)

        res = checkdmarc.check_domains([domain], skip_tls=skip_tls, nameservers=nameservers)
        signal.alarm(0)
    else:
        res = checkdmarc.check_domains([domain], skip_tls=skip_tls)
    output = OrderedDict()
    output['_about'] = "For questions: mailto:hildenae+dmarc@gmail.com. Data produced "\
                      "using https://domainaware.github.io/checkdmarc/index.html"
    # We do this to make sure "about" is put first in the merged ordered dict
    output.update(res)

    return output


def force_iso_tz(timestamp):
    if timestamp.tzinfo:
        return timestamp
    # Set a timezone offset of 0 to force printing timezone even if GMT
    return timestamp.replace(microsecond=0).replace(tzinfo=timezone(timedelta(0))).isoformat()

class TimedOutExc(Exception):
    pass

