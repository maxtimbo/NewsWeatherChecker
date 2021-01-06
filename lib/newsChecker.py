#!/usr/bin/python3

import hashlib, configparser, sys, shutil, datetime, smtplib, os, subprocess
from ftplib import FTP
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.audio import MIMEAudio

# import configuration file, saved as .ini file
conf = configparser.ConfigParser()
conf.read(sys.argv[1])

today = datetime.datetime.today()
todayHrMin = today.strftime('%Y-%m-%d_%H%M')

message = ""

# Use shaSum("file.wav") to compare file hashs
def shaSum(filename, blocksize=65536):
    hasher = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(blocksize), b""):
            hasher.update(block)
    return hasher.hexdigest()

# FTP Function to Download list of files defined in .ini file
def downloadfiles():
    ftp = FTP(conf['FTP']['url'])
    ftp.login(user=conf['FTP']['username'], passwd=conf['FTP']['password'])
    ftp.cwd(conf['FTP']['directory'])
    files = conf['FTP']['files'].split()
    for x in files:
        dl_file = f"{conf['DIRS']['DownloadDir']}/{x}_dl"
        try:
            ftp.nlst(x)
            local_file = open(dl_file, 'wb')
            ftp.retrbinary('RETR ' + x, local_file.write, 1024)
        except Exception as e:
            if str(e) == '550 The system cannot find the file specified. ':
                print(e)

    ftp.quit()

# SendEmail with mp3 attachments
def sendMail(subject, sender, whoto, files=None):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(whoto)
    message_text = MIMEText(message, 'plain')
    msg.attach(message_text)

    for wav in files:
        attachment = open(wav, 'rb')
        file_name = os.path.basename(wav)
        part = MIMEAudio(attachment.read(), _subtype='mp3')
        part.add_header('Content-Disposition', 'attachment', filename=file_name)
        msg.attach(part)

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(conf['EMAIL']['username'], conf['EMAIL']['password'])
        server.sendmail(sender, whoto, msg.as_string())
        server.close()
    except Exception as e:
        print(str(e))

## ----- Compare new downloads with previously saved file
def analyzeDownloads():
    global message
    problemFiles = []
    for x in conf['FTP']['files'].split():
        dl = f"{conf['DIRS']['DownloadDir']}/{x}_dl"
        cr = f"{conf['DIRS']['DownloadDir']}/{x}"
        dst = f"{conf['DIRS']['ExportDir']}/{x}"
        if not shaSum(dl) == shaSum(cr):
            message = message + f"{x} has been updated\n"
        else:
            message = message + f"{x} has not been updated\n"
            problemFiles.append(x)
    
    # Finish the function by moving the new downloads into place
    # One copy is saved on the local machine
        shutil.copy(dl, dst)
    # One copy is moved to Automation System
        shutil.move(dl, cr)
    
    problemFiles = ", ".join(problemFiles)
    return problemFiles 

# This function saves a copy of the .wav as a .mp3 and returns a list for email attachments
def convertAndCleanup(directory):
    attachments = []
    files = os.listdir(directory)
    files.sort()
    for x in files: 
        if x.endswith('.mp3'):
            os.remove(f"{directory}/{x}")
        elif x.endswith('.wav'):
            mp3 = f"{os.path.splitext(x)[0]}.mp3"
            convert = subprocess.Popen(f"ffmpeg -y -i {directory}/{x} -acodec libmp3lame {directory}/{mp3}".split(), stderr=subprocess.DEVNULL)
            convert.wait()
            attachments.append(f"{directory}/{mp3}")
    return attachments

## ---------------- Driver Code ---------------- ##
if __name__ == "__main__":
    message = f"News and weather for {todayHrMin}\n\nNote: Attached files are compressed for Email\n"
    downloadfiles()
    problemFiles = analyzeDownloads()
    attachments = convertAndCleanup(conf['DIRS']['DownloadDir'])
    if not problemFiles:
        sendMail("All Good", "News and Weather Updated", conf['EMAIL']['recipients'].split(), attachments)
    else:
        sendMail(f"Files Not Updated: {problemFiles}", "WSAV NOT Updated", conf['EMAIL']['problem_receipt'].split(), attachments)
