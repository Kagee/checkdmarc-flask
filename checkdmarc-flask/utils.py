import checkdmarc
from collections import OrderedDict


# We want to skip tls check (port 25 etc traffic) by default when running on Heroku
def full_check(domain, skip_tls=True):
    res = checkdmarc.check_domains([domain], skip_tls=skip_tls)

    output = OrderedDict()
    output['about'] = "For questions: mailto:hildenae+dmarc@gmail.com. Data produced "\
                      "using https://domainaware.github.io/checkdmarc/index.html"
    # We do this to make sure "about" is put first in the merged ordered dict
    output.update(res)

    return output
