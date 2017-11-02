#!/usr/bin/env python3
from datetime import datetime, timedelta
from configparser import SafeConfigParser
import argparse
import logging
import random
import praw
import time
import sys

import strings
import argsfile
from pythonFunctions import *

logger = logging.getLogger("giveawaybot")
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)

parser = SafeConfigParser()
parser.read('resume.ini')

if parser.get('SETTINGS', 'url') != 'null':
    resumeSession = input('Resume data detected. Resume previous giveaway? [Y/n]: ') or 'y'

if resumeSession == 'y':
    argReddit = parser.get('SETTINGS', 'reddit')
    argSubmission = parser.get('SETTINGS', 'url')
    argWait = parser.get('SETTINGS', 'wait')
    argKeyword = parser.get('SETTINGS', 'keyword')
    argKeyfile parser.get('SETTINGS', 'keyfile')
    timePosted parser.get('SETTINGS', 'timePosted')

    argWait = argWait - (datetime.utcnow() - timePosted)

else:
    inputAddr = input("Please enter a subreddit or submission url [steam_giveaway]: ") or "steam_giveaway"
    if inputAddr[:5] == 'http:' or inputAddr[:6] == 'https:':
        argReddit = ''
        argSubmission = inputAddr
        argScrape = input("Scrape submission link for Giveaway Details? [y/N]: ") or 'no'
    else:
        argReddit = inputAddr
        argSubmission = ''
        argScrape = 'no'

    argWait = int(input("Please enter a time to wait (in minutes) [1004]: ") or "1004")
    argKeyword = input("Please enter a keyword to use: ")
    while(not argKeyword.strip()):
        argKeyword = input("Please enter a keyword to use: ")

    argKeyfile = input("Please enter a keyfile [keyfile.txt]") or "keyfile.txt"

argAge = argsfile.age
argPoll = argsfile.poll
argReply = argsfile.reply
argRandom = argsfile.random
argKarmaLink = argsfile.karmaLink
argKarmaComment = argsfile.karmaComment

if argScrape[0] == 'y':
  #ignore next imputs and scan for them inside the submission text body
  logger.warn('Scraping Submission Link for Reusable Data')


if argReddit == 'pcmasterrace':
  logger.warn('Using PCMasterRace Flairs')
  flair_open = argsfile.pcmr_flair_open
  flair_closed = argsfile.pcmr_flair_closed

elif argReddit == 'steam_giveaway':
  logger.warn('Using Steam_Giveaway Flairs')
  flair_open = argsfile.sg_flair_open
  flair_closed = argsfile.sg_flair_closed

else:
  logger.warn('No Flairs Set')
  flair_open = ''
  flair_closed = ''

min_account_age = timedelta(days=argAge)
argKeyword = argKeyword.strip()

keys = []
try:
  with open(argKeyfile, 'r') as f:
    keys = f.readlines()
  f.close()
except IOError:
  logger.error("Could not open the key file {0}.".format(argKeyfile))
  sys.exit(1)

logger.info("Logging in...")
r = praw.Reddit('postaccount') #used for posting the giveaway
rmsg = praw.Reddit('msgaccount') #used to comment and send messages to users. Can be the same/different account

if argReddit and not argSubmission:
  try:
    logger.info("Creating submission...")
    body = strings.submission_body

    if argKeyword:  # Alert users that they need a keyword
      body += "\n\n" + strings.keyword_message.format(keyword=argKeyword)

    if argRandom:  # Alert users that prizes are random
      utc_wait = (datetime.utcnow() + timedelta(minutes=argWait)).strftime("%H:%M:%S UTC")
      body += "\n\n" + strings.random_rule.format(wait=argWait, utc=utc_wait)
    else:  # Alert users that prizes
      body += "\n\n" + strings.timestamp_rule

    body += "\n\n" + strings.what_is_this
    rsub = r.subreddit(argReddit).submit(strings.submission_title.format(keys=len(keys)), selftext=body)
    argSubmission = rsub.shortlink
    logger.warning("Submission can be found at https://reddit.com" + str(rsub.permalink))
    if flair_open:
        rsub.flair.select(flair_open)
        logger.warn('Flair set to flair_open')
    rsub.disable_inbox_replies()
  except praw.exceptions.APIException as err:
    logger.error("Error with submission: " + str(err))


parser.set('SETTINGS', 'reddit', argReddit)
parser.set('SETTINGS', 'url', argSubmission)
parser.set('SETTINGS', 'wait', argWait)
parser.set('SETTINGS', 'timePosted', datetime.utcnow())
parser.set('SETTINGS', 'keyword', argKeyword)
parser.set('SETTINGS', 'keyfile', argKeyfile)

with open('resume.ini', 'w') as configfile:
        parser.write(configfile)

authors = set()
bannedUsers = set(line.strip() for line in open('banned.list'))
checked_comment_ids = set()

rsub = r.submission(url=argSubmission) #creates submission object
msgsub = rmsg.submission(url=argSubmission) #creates separate submission object for message user

if argRandom:
  logger.info("Sleeping for {0} minutes while users comment...".format(argWait))
  time.sleep(argWait * 60)

while len(keys) > 0:
  awarded = len(keys)
  logger.info("Checking comments...")

  msgsub.comments.replace_more(limit=None)
  comments = msgsub.comments.list()

  if argRandom:
    random.shuffle(comments)
  else:
    comments.sort(key=lambda c: c.created_utc)

  for comment in comments:
    if len(keys) == 0:
      break

    author = comment.author
    # Have we seen this comment before?
    if (author is not None and author.name not in authors and
        comment.id not in checked_comment_ids):
      checked_comment_ids.add(comment.id)
      # Ensure keyword is present if required
      if argKeyword and argKeyword not in comment.body:
        continue

      if (author.name in bannedUsers):
        logger.warn("Author {0} is on the banned users list".format(author.name))
        continue

      # Check account age
      created_date = datetime.fromtimestamp(int(author.created_utc))
      authors.add(author.name)
      if (datetime.now() - min_account_age) < created_date:
        logger.warn("Author {0} is less then {1} days old.".format(author.name, (datetime.now() - min_account_age)))
        continue

      # We aren't using author karma, just a one month age. Why? Simple. I was a lurker for almost a year. 
      # I had no karma but I wasn't a spam account. I think a karma limit (even small) would limit more legit users then fake account.
      # but the code block is below just in case I want to implement it...

      if ((author.link_karma < argKarmaLink) or (author.comment_karma < argKarmaComment)):
        logger.warn("Author {0} does not have enough Karma. Post Karma: {1}, Comment Karma: {2}".format(author.name, author.link_karma, author.comment_karma))
        continue

      try:
        delPrize = str(keys[0])
        message = strings.prize_reply_message.format(prize=keys.pop(0).strip(),
          url=argSubmission)
        if argReply == "inline":
          comment.reply(message)
        else:
          rmsg.redditor(author.name).message(strings.reply_title, message)
          comment.reply(strings.generic_reply_message)
          deleteLine(argKeyfile, delPrize)
      except AttributeError as err:
        logging.error("Missing value in strings file: {0}".format(err))
        sys.exit(1)

  if len(keys) < awarded:
    logger.info("Awarded {0} new prizes!".format(awarded - len(keys)))
  if len(keys) > 0:
    time.sleep(argPoll)

try:
  if rsub.selftext:
    rsub.edit(rsub.selftext + "\n\n**EDIT:** " + strings.end_message)
  else:
    rsub.edit(strings.end_message)
  if flair_closed:
    rsub.flair.select(flair_closed)
    logger.warn('Flair set to flair_closed')
except praw.exceptions.APIException:
  logger.warning("Unable to edit original post to warn that giveaway "
    "is over. Recommend manually editing the post.")

logger.info("Prizes are all distributed, erasing resume.ini.")

parser.set('SETTINGS', 'reddit', 'null')
parser.set('SETTINGS', 'url', 'null')
parser.set('SETTINGS', 'wait', 'null')
parser.set('SETTINGS', 'timePosted', 'null')
parser.set('SETTINGS', 'keyword', 'null')
parser.set('SETTINGS', 'keyfile', 'null')

with open('resume.ini', 'w') as configfile:
            parser.write(configfile)

logger.info("Resume.ini erased. Exiting.")
