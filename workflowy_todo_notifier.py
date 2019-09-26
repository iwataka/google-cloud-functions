import os
import dropbox
import requests
import json
import re

# sensitive constants
webhook_url = os.getenv('WEBHOOK_URL')
dropbox_token = os.getenv('DROPBOX_TOKEN')
workflowy_file_path = os.getenv('DROPBOX_FILE_PATH')

head_title = ':straight_ruler: Here is your workflowy statistics!'

hashes = [
    ['#todo'],
    ['#todo', '#high'],
    ['#move'],
    ['#waiting'],
    ['#pending'],
    ['#need-organized'],
]

title2hashes = {
    ':sunny: Daily activities': ['#daily'],
    ':office: Things to do in the office': ['#work'],
    ':walking: Things to do on the way back': ['#on-the-way-back-home'],
}

bullet_pattern = re.compile('^\s*[-*+]')

hash2re = {}

def lines_contains_hashes(lines, hashes):
    lines = [l.strip() for l in lines]
    patterns = [create_hash_pattern(h) for h in hashes]
    return [bullet_pattern.sub('', l) for l in lines if bullet_pattern.search(l) and all(p.search(l) for p in patterns)]


def remove_hashes(line, hashes):
    patterns = [create_hash_pattern(h) for h in hashes]
    for pat in patterns:
        line = pat.sub('', line)
    return line


def create_hash_pattern(hash_str):
    if hash_str not in hash2re:
        hash2re[hash_str] = re.compile('(\s|^)%s(\s|$)' % hash_str)
    return hash2re[hash_str]


def send_notification(workflowy_lines, hashes, title2hashes, webhook_url):
    counts = [len(lines_contains_hashes(workflowy_lines, h)) for h in hashes]
    hash_strs = [' '.join(hs) for hs in hashes]
    msg_lines = [head_title]
    for hs, c in zip(hash_strs, counts):
        msg_lines.append('- `%s`: %d' % (hs, c))
    msg = '\n'.join(msg_lines)

    attachments = []
    for title, hs in title2hashes.items():
        lines = lines_contains_hashes(workflowy_lines, hs)
        text_lines = ['%s (%s)' % (title, ','.join(['`%s`' % h for h in hs]))]
        text_lines.extend(['- %s' % remove_hashes(l, hs) for l in lines])
        att = {
            'text': '\n'.join(text_lines),
            'color': '#36a64f' if lines else '',
        }
        attachments.append(att)

    send_msg_to_slack(msg, attachments, webhook_url)


def send_msg_to_slack(msg, attachments, webhook_url):
    requests.post(webhook_url, data=json.dumps({
        'text': msg,
        'username': 'Workflowy',
        'icon_emoji': ':hash:',
        'link_names': 1,
        'mrkdwn': True,
        'attachments': attachments,
    }))


def download_workflowy_file_lines(dbx, file_path):
    _, wf_res = dbx.files_download(file_path)
    if not wf_res.ok:
        raise Exception('Failed to download file from Dropbox')
    wf_res.encoding = 'utf-8'
    lines = wf_res.text.split('\n')
    first_line = lines[0]
    # If all of words in the first line is a hash tag, ignore it.
    if all(w.startswith('#') for w in first_line.split()[1:]):
        return lines[1:]
    return lines


def notify(hashes = hashes, title2hashes = title2hashes):
    dbx = dropbox.Dropbox(dropbox_token)
    lines = download_workflowy_file_lines(dbx, workflowy_file_path)
    send_notification(lines, hashes, title2hashes, webhook_url)


def execute(req):
    body_json = req.get_json()
    hs = hashes
    t2hs = title2hashes
    if body_json and 'hashes' in body_json:
        hs = body_json['hashes']
    if body_json and 'title2hashes' in body_json:
        t2hs = body_json['title2hashes']
    notify(hs, t2hs)


if __name__ == '__main__':
    notify()
