import requests
import urllib3

# Global Patch: Disable SSL certificate verification to handle SSL-intercepting municipal firewalls
original_request = requests.Session.request
def patched_request(self, *args, **kwargs):
    kwargs['verify'] = False
    return original_request(self, *args, **kwargs)
requests.Session.request = patched_request

# Silence InsecureRequestWarning messages in logs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from cfr_dispatch.orchestration import run_dispatch_system

if __name__ == "__main__":
    run_dispatch_system()