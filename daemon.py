#!/usr/bin/python3
# -*- coding: utf-8 -*-
# created by Alwin Ebermann (alwin@alwin.net.au)
import configparser
import copy
from db import Base
from db import Keywords
from db import User
import logging
import time
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater
from telegram.error import ChatMigrated
from telegram.error import NetworkError
from telegram.error import TimedOut
from telegram.error import Unauthorized

config = configparser.ConfigParser()
config.read('config.ini')

engine = create_engine('sqlite:///mydealz.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def send_or_edit(bot, update, text, reply_markup=None):
    try:
        message_id = update.callback_query.message.message_id
        chat_id = update.callback_query.message.chat.id
        try:
            bot.editMessageText(text=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup,
                                parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)
        except Unauthorized:
            session = DBSession()
            user = session.query(User).filter(User.id == chat_id).first()
            session.delete(user)
            session.commit()
            session.close()
        except TimedOut:
            time.sleep(20)
            return send_or_edit(bot, update, text, reply_markup)
        except ChatMigrated as e:
            session = DBSession()
            user = session.query(User).filter(User.id == chat_id).first()
            user.id = e.new_chat_id
            session.commit()
            session.close()
            return True
        except NetworkError:
            return False
    except AttributeError:
        bot.sendMessage(text=text, chat_id=update.message.chat.id, reply_markup=reply_markup,
                        parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True)


def CheckUser(bot, update):
    session = DBSession()
    try:
        chat = update.message.chat
        current_selection = "message"
    except AttributeError:
        chat = update.callback_query.message.chat
        current_selection = update.callback_query.data
    entry = session.query(User).filter(User.id == chat.id).first()
    if not entry:
        # Nutzer ist neu
        new_user = User(id=chat.id, first_name=chat.first_name, last_name=chat.last_name, username=chat.username,
                        title=chat.title, counter=0, current_selection="0")
        new_usr = copy.deepcopy(new_user)
        session.add(new_user)
        session.commit()
        message = "Mit diesem Bot kannst du dich benachrichtigen lassen, wenn bestimmte Deals auf MyDealz erstellt werden."
        bot.sendMessage(chat_id=chat.id, text=message, reply_markup=telegram.ReplyKeyboardRemove())
        session.close()
        return new_usr
    else:
        entry.counter += 1
        ent = copy.deepcopy(entry)
        entry.current_selection = current_selection if not current_selection == "message" else "0"
        session.commit()
        session.close()
        return ent


def ShowHome(bot, update, usr):
    # get all current keywords
    s = DBSession()
    keywords = s.query(Keywords).filter(Keywords.user_id == usr.id).all()
    if len(keywords) > 0:
        message = "Folgende Benachrichtigungen sind aktiv:\n"
        button_list = []
        for keyword in keywords:
            button_list.append([InlineKeyboardButton("📜 " + keyword.keywords, callback_data="1$" + str(keyword.id))])
        button_list.append([InlineKeyboardButton("📯 Neuen Benachrichtigung erstellen", callback_data="2")])
        send_or_edit(bot, update, message, InlineKeyboardMarkup(button_list))
    else:
        message = "Noch keine Benachrichtigungen erstellt. Leg gleich los:"
        button_list = [[InlineKeyboardButton("📯 Neuen Benachrichtigung erstellen", callback_data="2")]]
        send_or_edit(bot, update, message, InlineKeyboardMarkup(button_list))
    s.close()


def ShowAlert(bot, update, keyword):
    # show current information about Alert
    button_list = [[InlineKeyboardButton("💣 Benachrichtigung löschen", callback_data="4$" + str(keyword.id) + "$0"),
                    InlineKeyboardButton("💶 Maximalpreis bearbeiten", callback_data="3$" + str(keyword.id))],
                   [InlineKeyboardButton("🗃️ Kategorie ändern", callback_data="5$" + str(keyword.id)),
                    InlineKeyboardButton("🔍 Suchbegriffe bearbeiten", callback_data="2$" + str(keyword.id))],
                   [InlineKeyboardButton("🏷️ Reichweite ändern", callback_data="6$" + str(keyword.id)),
                    InlineKeyboardButton("🏠 Home", callback_data="0")]]
    message = "*Suchbegriffe:* " + keyword.keywords + "\n*Kategorie:* " + keyword.category + "\n*Maximalpreis:* "
    message += str(keyword.maxprice).replace(".", ",") + "€" if keyword.maxprice > 0 else "kein Maximalpreis gesetzt"
    message += "\n*Reichweite:* "
    message += "Nur Titel" if keyword.scope == 0 else "Titel & Beschreibung"
    send_or_edit(bot, update, message, InlineKeyboardMarkup(button_list))


def SetCategory(bot, update, keyword, value=None):
    categories = ["Alle", "Fashion & Accessoires", "Family & Kids", "Reisen", "Versicherung & Finanzen",
                  "Telefon- und Internet-Verträge", "Kultur & Freizeit", "Gaming", "Beauty & Gesundheit",
                  "Lebensmittel & Haushalt", "Home & Living", "Sport & Outdoor", "Auto & Motorrad",
                  "Dienstleistungen & Verträge", "Elektronik", "Alle"]
    button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
    if value is None:
        message = "Bitte neue Kategorie für die Benachrichtigung '" + keyword.keywords + "' auswählen:"
        counter = 0
        button_list = []
        while counter < len(categories):
            button_list.append([InlineKeyboardButton(categories[counter],
                                                     callback_data="5$" + str(keyword.id) + "$" + categories[counter]),
                                InlineKeyboardButton(categories[counter + 1],
                                                     callback_data="5$" + str(keyword.id) + "$" + categories[
                                                         counter + 1])])
            counter += 2
        send_or_edit(bot, update, message, InlineKeyboardMarkup(button_list))
    else:
        if value in categories:
            if not keyword:
                send_or_edit(bot, update, "Die Benachrichtigung kann nicht gefunden werden",
                             InlineKeyboardMarkup(button_list))
            else:
                keyword.category = value
                button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                                InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(keyword.id)),
                                InlineKeyboardButton("💶 Maximalpreis ändern", callback_data="3$" + str(keyword.id))]]
                send_or_edit(bot, update, "Kategorie aktualisiert.", InlineKeyboardMarkup(button_list))
        else:
            send_or_edit(bot, update, "Das ist keine valide Kategorie", InlineKeyboardMarkup(button_list))


def SetScope(bot, update, keyword, value=None):
    button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
    if value is None:
        message = "Bitte die neue Reichweite für die Benachrichtigung '" + keyword.keywords + "' auswählen:"
        button_list = [[InlineKeyboardButton("Nur Titel", callback_data="6$" + str(keyword.id) + "$0"),
                        InlineKeyboardButton("Titel & Beschreibung", callback_data="6$" + str(keyword.id) + "$1")]]
        send_or_edit(bot, update, message, InlineKeyboardMarkup(button_list))
    else:
        if value in ["0", "1"]:
            if not keyword:
                send_or_edit(bot, update, "Die Benachrichtigung kann nicht gefunden werden",
                             InlineKeyboardMarkup(button_list))
            else:
                keyword.scope = value
                button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                                InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(keyword.id))]]
                send_or_edit(bot, update, "Reichweite aktualisiert.", InlineKeyboardMarkup(button_list))

        else:
            send_or_edit(bot, update, "Das ist keine valide Kategorie", InlineKeyboardMarkup(button_list))


def SaveMaxPrice(bot, update, usr, alertid):
    # check format of Price
    if re.match(r"^[0-9]+(,[0-9]{0,2})?$", update.message.text) is not None and len(update.message.text) < 10:
        maxprice = float(update.message.text.replace(",", "."))
        s = DBSession()
        keyword = s.query(Keywords).filter(Keywords.id == alertid, Keywords.user_id == usr.id).first()
        if not keyword:
            send_or_edit(bot, update, "Die Benachrichtigung kann nicht gefunden werden",
                         InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="0")]]))
        else:
            keyword.maxprice = maxprice
            s.commit()
            button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                            InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(alertid)),
                            InlineKeyboardButton("🏷️ Reichweite ändern", callback_data="6$" + str(alertid))]]
            send_or_edit(bot, update, "Maximalpreis aktualisiert.", InlineKeyboardMarkup(button_list))
        s.close()
    else:
        send_or_edit(bot, update, "Bitte einen gültigen Preis als ganze Zahl oder mit zwei Nachkommastellen angeben.",
                     None)


def SaveKeywords(bot, update, usr, alertid=None):
    # split keywords and check
    if update.message.text is None:
        send_or_edit(bot, update, "Bitte mit einem Text antworten")
        return
    keywords = update.message.text.split(",")
    for keyw in keywords:
        keyw = keyw.strip()
        if re.search(r"^[a-zA-Z0-9äöüÄÖÜß .-]+$", keyw) is None:
            send_or_edit(bot, update,
                         "Der Ausdruck enthält ungültige Zeichen oder entspricht nicht der vorgeschriebenen Formatierung. Es sind nur Buchstaben und die Sonderzeichen .- erlaubt. Suchbegriffe oder Wortgruppen müssen durch ein Komma getrennt werden.")
            return
    if len(update.message.text) > 200:
        send_or_edit(bot, update, "Die Maximallänge ist auf 200 Zeichen beschränkt.")
        return
    s = DBSession()
    if alertid is not None:
        keyword = s.query(Keywords).filter(Keywords.id == alertid, Keywords.user_id == usr.id).first()
        if not keyword:
            button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
            send_or_edit(bot, update, "Die Benachrichtigung kann nicht gefunden werden",
                         InlineKeyboardMarkup(button_list))
        else:  # change keywords
            button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                            InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(alertid)),
                            InlineKeyboardButton("🗃️ Kategorie ändern", callback_data="5$" + str(alertid))]]
            keyword.keywords = update.message.text
            s.commit()
            send_or_edit(bot, update, "Die Suchbegriffe wurden gespeichert.", InlineKeyboardMarkup(button_list))
    else:  # create new alert
        new_alert = Keywords(user_id=usr.id, keywords=update.message.text, scope=0, maxprice=0, category="Alle")
        s.add(new_alert)
        s.commit()
        button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                        InlineKeyboardButton("📜 Übersicht", callback_data="1$" + str(new_alert.id)),
                        InlineKeyboardButton("🗃️ Kategorie ändern", callback_data="5$" + str(new_alert.id))]]
        send_or_edit(bot, update, "Die Suchbegriffe wurden gespeichert.", InlineKeyboardMarkup(button_list))
    s.close()


def DeleteAlert(bot, update, conf, keyword, s):
    if conf == "1":
        s.delete(keyword)
        send_or_edit(bot, update, "Der Suchauftrag '" + keyword.keywords + "' wurde erfolgreich gelöscht.",
                     InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="0")]]))
    else:
        button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0"),
                        InlineKeyboardButton("💣 Löschen", callback_data="4$" + str(keyword.id) + "$1")]]
        send_or_edit(bot, update, "Möchtest du den Suchauftrag '" + keyword.keywords + "' wirklich löschen?",
                     InlineKeyboardMarkup(button_list))


def Start(bot, update):
    usr = CheckUser(bot, update)
    ShowHome(bot, update, usr)


def AllInline(bot, update):
    args = update.callback_query.data.split("$")
    if len(args) > 1:  # check the alert here
        usr = CheckUser(bot, update)
        s = DBSession()
        keyword = s.query(Keywords).filter(Keywords.id == args[1], Keywords.user_id == usr.id).first()
        if not keyword:
            button_list = [[InlineKeyboardButton("🏠 Home", callback_data="0")]]
            send_or_edit(bot, update, "Die Benachrichtigung kann nicht gefunden werden",
                         InlineKeyboardMarkup(button_list))
        else:
            if args[0] == "1":  # show current information about Alert
                ShowAlert(bot, update, keyword)
            elif args[0] == "5":  # Kategorie ändern
                if len(args) > 2:  # Wert setzen
                    SetCategory(bot, update, keyword, args[2])
                else:  # Auswahl anzeigen
                    SetCategory(bot, update, keyword)
            elif args[0] == "6":  # Reichweite ändern
                if len(args) > 2:  # Wert setzen
                    SetScope(bot, update, keyword, args[2])
                else:  # Auswahl anzeigen
                    SetScope(bot, update, keyword)
            elif int(args[0]) == 3:  # Maxprice setzen
                usr = CheckUser(bot, update)
                send_or_edit(bot, update,
                             "Bitte neuen Maximalpreis angeben. \"0,00\" deaktiviert den Maximalpreisfilter.", None)
            elif int(args[0]) == 4 and len(args) > 2:  # Alert löschen
                DeleteAlert(bot, update, args[2], keyword, s)
            elif int(args[0]) == 2:
                send_or_edit(bot, update,
                             "Bitte gib eine Liste durch Komma getrennter Suchbegriffe oder Wortgruppen an. Der Alarm wird ausgelöst sobald ein Suchbegriff oder eine Wortgruppe gefunden wird. Die Groß-/ Kleinschreibung wird dabei nicht beachtet.",
                             None)
            else:
                update.callback_query.message.reply_text("Kommando nicht erkannt")
                bot.sendMessage(
                    text="Inlinekommando nicht erkannt.\n\nData: " + update.callback_query.data + "\n User: " + str(
                        update.callback_query.message.chat), chat_id=config['DEFAULT']['AdminId'])
        s.commit()
        s.close()
    elif int(args[0]) == 0:
        Start(bot, update)
    elif int(args[0]) == 2:  # neu oder keywords ändern
        usr = CheckUser(bot, update)
        send_or_edit(bot, update,
                     "Bitte gib eine Liste durch Komma getrennter Suchbegriffe oder Wortgruppen an. Der Alarm wird ausgelöst sobald ein Suchbegriff oder eine Wortgruppe gefunden wird. Die Groß-/ Kleinschreibung wird dabei nicht beachtet.",
                     None)
    else:
        update.callback_query.message.reply_text("Kommando nicht erkannt")
        bot.sendMessage(text="Inlinekommando nicht erkannt.\n\nData: " + update.callback_query.data + "\n User: " + str(
            update.callback_query.message.chat), chat_id=config['DEFAULT']['AdminId'])


def About(bot, update):
    usr = CheckUser(bot, update)
    send_or_edit(bot, update,
                 "Dieser Bot wurde erstellt von @Alwinius. Der Quellcode ist unter https://github.com/Alwinius/mydealzbot verfügbar.\nWeitere interessante Bots: \n - @tummoodlebot\n - @tummensabot")
    ShowHome(bot, update, usr)


def Msg(bot, update):
    usr = CheckUser(bot, update)
    args = usr.current_selection.split("$")
    if len(args) > 1 and int(args[0]) == 3:  # maxprice speichern
        SaveMaxPrice(bot, update, usr, args[1])
    elif int(args[0]) == 2:  # Keywords speichern
        if len(args) > 1:
            SaveKeywords(bot, update, usr, args[1])
        else:
            SaveKeywords(bot, update, usr)
    else:
        ShowHome(bot, update, usr)


start_handler = CommandHandler('start', Start)
dispatcher.add_handler(start_handler)
about_handler = CommandHandler('about', About)
dispatcher.add_handler(about_handler)

inlinehandler = CallbackQueryHandler(AllInline)
dispatcher.add_handler(inlinehandler)

msghandler = MessageHandler(Filters.all, Msg)
dispatcher.add_handler(msghandler)

updater.start_webhook(listen='localhost', port=8080, webhook_url=config['DEFAULT']['WebHookUrl'])
updater.idle()
updater.stop()
