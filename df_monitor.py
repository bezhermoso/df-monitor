import subprocess
import re
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import time
import cli.app


def send_mail(full, threshold, raw_output, to, server_alias, sender):

    sendmail_location = '/usr/sbin/sendmail'

    msg_parts = []

    justify = 20

    msg_parts.append('The disk-space for the following partition(s) in %s went up to or above the %s%% threshold:' % (server_alias, threshold))
    msg_parts.append('');

    header = '%s%s%s' % ('Partition'.ljust(justify), 'Percent used'.ljust(justify), 'Mount'.ljust(justify))
    msg_parts.append(header)

    for f in full.values():

        msg_parts.append('%(partition)s%(percent_used)s%(mount)s' % {
            'partition': f['partition'].ljust(justify),
            'percent_used': f['percent_used'].ljust(justify),
            'mount': f['mount'].ljust(justify)
        })


    msg_parts.append('')
    msg_parts.append('')
    msg_parts.append('')

    msg_parts.append('(Raw output of df -h):')
    msg_parts.append('')
    msg_parts.append(raw_output)

    msg_parts.insert(0, '<html><body style="font-size: 12px;"><pre>')
    msg_parts.append('</pre></body></html>')

    body = MIMEText('\n'.join(msg_parts), 'html')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Disk-space monitor - Partition(s) in %s almost full.' % server_alias
    msg['From'] = sender
    msg['To'] = to
    msg.attach(body)

    p = subprocess.Popen([sendmail_location, "-t"], stdin=subprocess.PIPE)
    p.communicate(msg.as_string())

def should_notify(timestamp, interval):
    notify = True

    if not os.path.isfile('.df-monitor'):
        notify = True
    else:
        f = open('.df-monitor', 'r')
        str = f.read()
        data = json.loads(str.replace('\n', ''))
        notify = timestamp > data['last_notification'] + (60 * 60 * interval)
        f.close()

    return notify

def write_lock(timestamp):

    data = dict(last_notification=timestamp)
    f = open('.df-monitor', mode='w')
    str = json.dumps(data)
    f.write(str)
    f.close()


@cli.app.CommandLineApp
def check_diskspace(app):

    df = subprocess.Popen(['df', '-h'], stdout=subprocess.PIPE)
    stdout = df.communicate()[0]
    output = stdout.splitlines()
    output = output[1:]

    almost_full = dict()

    for line in output:

        parts = re.split('\s+', line)

        data = {
            'partition': parts[0],
            'size': parts[1],
            'used': parts[2],
            'available': parts[3],
            'percent_used': parts[4],
            'mount': parts[-1],
            'line': line
        }

        percent_number = re.match('^\d+', data['percent_used']).group(0)
        percent_number = int(percent_number)

        if percent_number >= app.params.threshold and app.params.mount_point == data['mount']:
            almost_full[data['partition']] = data

    timestamp = time.time()

    if len(almost_full) > 0 and should_notify(timestamp=timestamp, interval=app.params.threshold):

        if app.params.server_alias is None:
            hostname = subprocess.Popen(['hostname'], stdout=subprocess.PIPE)
            hostname = hostname.communicate()[0].replace('\n', '')
        else:
            hostname = app.params.server_alias

        send_mail(full=almost_full, raw_output=stdout, to=app.params.recipient, threshold=app.params.threshold, server_alias=hostname, sender=app.params.sender)
        write_lock(timestamp)


check_diskspace.add_param('recipient', help="The email address to notify.")
check_diskspace.add_param('mount_point', help="The mount point to monitor.", default='/')
check_diskspace.add_param('sender', help="The sender email address.")
check_diskspace.add_param('-t', '--threshold', help='The disk usage threshold.', default=95, type=float)
check_diskspace.add_param('-n', '--notification-interval', help='Interval of notifications (in hours)', default=3, type=float)
check_diskspace.add_param('-a', '--server-alias', help='Server alias used in the email notificaiton.', default=None)


'''

Main script execution

'''
if __name__ == '__main__':
    check_diskspace.run()



