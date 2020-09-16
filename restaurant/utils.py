import re
from django.utils import timezone, dateformat
import pytz


def check_email(email: str) -> bool:
    return re.match(r'[^@]+@[^@]+\.[^@]+', email)


# Transform timezone time to given format
# frequently used format: Y-m-d H:i:s, Y-m-d
# for more format: https://docs.djangoproject.com/en/2.1/ref/templates/builtins/#date
def timezone_to_string(timezone_fmt_time, fmt='Y-m-d') -> str:
    return dateformat.format(
        timezone.localtime(timezone_fmt_time, pytz.timezone('Asia/Taipei')),
        fmt
    )
