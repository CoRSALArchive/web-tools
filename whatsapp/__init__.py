from flask import Blueprint, request, send_file
import os
import csv
import unicodedata
import re

app = Blueprint('whatsapp', __name__,
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

#Pseudonym list can be uncommented with accompanying code block to anonymize message senders
#pseudonyms = ["Alex", "Beth", "Charlie", "Diane"]

csv_export = []

def w_con(infile):
    with open('export.csv','w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["Sender","Date","Time","Message","Media"])
        writer.writeheader()
        senders = {}
       #Messages in exported text can be delimited by date followed by comma
        messages = re.split(r'\n(?=[0-9][0-9]?/[0-9][0-9]?/[0-9][0-9],)', infile.read().decode('utf-8'))
        for m in messages:
           #Remove newline within message
            m = m.replace('\n',' ')
            datetime = re.match(r'^([0-9/]*),\s([0-9:]*\s(AM|PM))\s-\s', m)
            m = m.split(datetime.group(0))[1]
           #Messages sent by user include colon, chat events do not
            if ':' in m:
                sendertext = m.split(': ')
                sender, text = sendertext[0], sendertext[1]
               #Uncomment this code and list of pseudonyms to anonymize sender info automatically, also reassign sender to psender is csv_export.append()
               #if sender in senders.keys():
               #    p_sender = senders[sender]
               #else:
               #    senders[sender] = pseudonyms.pop()
               #    p_sender = senders[sender]
               #Check for information about file attachments
                if '(file attached)' in text:
                    file = re.match(r'(.*\..*)(?=\s\(file attached\))', text).group(1)
                    try: 
                        text = re.split(r'\(file attached\) ', text)[1]
                    except:
                        text = "(file attached)"
                else:
                    file = 'NA'
                csv_export.append({'Sender':sender, 'Date':datetime.group(1), 'Time':datetime.group(2), 'Message':text, 'Media':file})
        for item in csv_export:
            text = item['Message']
            item['Message'] = text
        writer.writerows(csv_export)
    return

@app.route('/', methods=['GET', 'POST'])
def whatsapp():
    if request.method == 'POST':
        fin = request.files['file']
        w_con(fin)
        return send_file('export.csv', as_attachment=True)
    return app.send_static_file('index.html')
