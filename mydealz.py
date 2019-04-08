#!/usr/bin/python3
# -*- coding: utf-8 -*-
# created by Alwin Ebermann (alwin@alwin.net.au)

import configparser
from datetime import datetime
from db import Base
from db import Keywords
from db import User
import feedparser
import re
import html
from sqlalchemy import create_engine, exists
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram.error import ChatMigrated
from telegram.error import TimedOut
from telegram.error import Unauthorized

config = configparser.ConfigParser()
config.read('config.ini')

engine = create_engine('sqlite:///mydealz.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
s = DBSession()
keywords = s.query(Keywords).all()

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])


def send(chat_id, message, alertid, s, tryy=0):
    tryy+=1
    button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                    InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(alertid)),
                    InlineKeyboardButton("💣 Diese Benachrichtigung löschen",
                                         callback_data="4$" + str(alertid) + "$0")]]
    reply_markup = InlineKeyboardMarkup(button_list)
    try:
        bot.sendMessage(chat_id=chat_id, text=message, parse_mode=telegram.ParseMode.HTML, reply_markup=reply_markup)
    except Unauthorized:
        user = s.query(User).filter(User.id == chat_id).first()
        user.notifications = False
        s.commit()
        return True
    except TimedOut:
        if tryy < 10:
            return send(chat_id, message, alertid, s)
    except ChatMigrated as e:
        user = s.query(User).filter(User.id == chat_id).first()
        newuserexists = s.query(exists().where(User.id == e.new_chat_id)).scalar()
        if not newuserexists:
            user.id = e.new_chat_id
        else:
            user.delete()
        userkeywords = s.query(Keywords).filter(Keywords.user_id == chat_id)
        for keyword in userkeywords:
            keyword.user_id = e.new_chat_id
        s.commit()
        return True


f = open("lastentry.txt", "r+")
lastentry = datetime.fromtimestamp(float(f.read()))

d = feedparser.parse("https://www.mydealz.de/rss/alle")

counter = 0
while len(d.entries) > counter and lastentry < datetime.strptime(d.entries[counter].published[:-6], '%a, %d %b %Y %X'):
    print(d.entries[counter].title)
    try:
        raw_price = d.entries[counter].pepper_merchant["price"]
        price = raw_price.replace(".", "")
        price_string = " [" + raw_price + "]"
        price = float(price.replace(",", ".")[:-1])
    except (KeyError, AttributeError):
        price = 0
        try:
            price_string = " [-" + d.entries[counter].pepper_merchant["discount"] + "]"
        except (KeyError, AttributeError):
            price_string = ""
    try:
        category = d.entries[counter].category
    except AttributeError:
        category = "Alle"
    for keywordentry in keywords:
        for keyword in keywordentry.keywords.split(","):
            if (re.search(keyword, d.entries[counter].title, re.IGNORECASE) or (
                    keywordentry.scope == 1 and re.search(keyword, d.entries[counter].description, re.IGNORECASE))) \
                    and (keywordentry.category == category or keywordentry.category == "Alle") and (
                    keywordentry.maxprice == 0 or keywordentry.maxprice > price):
                # Match found
                message = "Neuer Deal: <a href='" + d.entries[counter].link + "'>" + html.escape(d.entries[counter].title) + "</a>" + price_string + "\n"
                send(keywordentry.user_id, message, keywordentry.id, s)
                break  # notify only once if multiple keywords of the same entry match
    counter += 1
f.seek(0, 0)
if len(d.entries) > 0:
    f.write(datetime.strptime(d.entries[0].published[:-6], '%a, %d %b %Y %X').strftime("%s"))
    print("Updated lastentry")
f.close()
