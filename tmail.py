
import base64
import re
import os
import time
from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def get_messages(service, messages):
    messages_text = []
    for m in messages['messages']:
        message = service.users().messages().get(userId='me', id=m['id']).execute()
        msg = ''
        data = ''
        if message['payload'].get('parts'):
            for p in message['payload']['parts']:
                data += p['body']['data']
        else:
            data = message['payload']['body']['data']
        
        missing_padding = len(data) % 4
        data += '=' * (4 - missing_padding)
        msg += base64.urlsafe_b64decode(data).decode('utf-8')
        sender = [i['value'] for i in message['payload']['headers'] if i['name'] == 'From']
        messages_text.append({'id': m['id'], 'text': msg, 'from': sender})
    return messages_text


def remove_html_tags(text):
    return re.sub('<[^<]+?>', '', text)


def extract_email_info(messages_text):
    user_infos = []
    for msg in messages_text:
        text = msg['text']
        addr_pat = 'Address ?\d?: (.+)'
        email_pat = 'Email: (.+)'
        name_pat = 'Name: (.+)'
        addr_mat = re.search(addr_pat, text)
        if addr_mat:
            addr = addr_mat.group(1).strip()
            addr = remove_html_tags(addr)
        email_mat = re.search(email_pat, text)
        if email_mat:
            email = email_mat.group(1).strip()
            email = remove_html_tags(email)
        name_mat = re.search(name_pat, text)
        if name_mat:
            name = name_mat.group(1).strip()
            name = remove_html_tags(name)
        user_infos.append({'id': msg['id'], 'from': msg['from'], 'email': email, 'address': addr, 'name': name})
    return user_infos


def create_message(sender, to, subject, message_text):
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_string().encode("utf-8")).decode('ascii')}


def main():
    creds = None
    dir_path = os.path.dirname(os.path.realpath(__file__))
    token_file = os.path.join(dir_path, 'token.json')
    cred_file = os.path.join(dir_path, 'credentials.json')

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        template_path = os.path.join(dir_path, "template.txt")
        template_file = open(template_path, "r")
        template = template_file.read()

        service = build('gmail', 'v1', credentials=creds)
        profile = service.users().getProfile(userId='me').execute()
        messages = service.users().messages().list(userId='me', q='in:inbox label:unread').execute()
        messages_text = get_messages(service, messages)
        user_infos = extract_email_info(messages_text)

        sent = set()
        for info in user_infos:
            if info['email'] not in sent:
                sent.add(info['email'])
                print()
                print(info) # 'addLabelIds':['auto'], 
                template.replace('<name>', info['name'])
                # message = create_message(profile['emailAddress'], info['email'], info['address'], template)
                # resp = (service.users().messages().send(userId='me', body=message).execute())
                # print('sent email %s' % resp['id'])
                # service.users().messages().modify(userId='me', id=info['id'], body={'removeLabelIds': ['UNREAD', 'INBOX']}).execute()
                # print('marked read, archived\n')
                #time.sleep(50)


    except HttpError as error:
        print(f'\nAn error occurred: {error}\n')


if __name__ == '__main__':
    main()
