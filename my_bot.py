# My WhatsApp Bot
# This bot has been built for two reasons:
# 1) log and save everything that passes through your phone. That's because I hated people who sent messages
#    and later deleted them. I wanted to log what they wrote or sent anyways. Saving and logging everything
#    is what I call "to bank" or "banking" everything. This was the only thing the very first version of the bot did.
#    If you want to do just this, the function you're looking for is bank()
# 2) mimic Telegram's SpacoBot, but in a more open, social way. With this bot you can pre-set the AI brain so it
#    responds to a series of commands and keywords you decide, just like SpacoBot.
#    But you also give chat users the ability to add content, actions and answers, so the limit it chat
#    people's fantasy. Have fun.
#
# Please feel free to use and contribute to the project
# This is the first time I use GitHub
#         the first time I use python
#         the first time I use Selenium
#         the first time I use webwhatsapi
# So please don't be too harsh on me :) and forgive my not-so-pythonic approach
#
# Things to do:
# TODO: adding a maintenance mode to allow editing of AI brain entries (changing captions, deleting some, etc.)
# TODO: enable logging via global var (safe_print_and_log and similar)

import os, sys, time, json, datetime, inspect
import urllib.request
from pathlib import Path
from random import randint, randrange
from ast import literal_eval
from webwhatsapi import WhatsAPIDriver
from webwhatsapi.objects.message import Message, MediaMessage

# Bot Logic Schema
# ==========
# In this case of use, you'll attach the bot to a phone number, that will be the "monitored_number"
# The bot will intercept every message sent to this phone and try to process it
# The bot has 3 user levels:
# - masters: full control and some special command
# - power users: almost full control and some reserved command
# - normal users
# Masters phone numbers are listed in "masters_numbers" list, as well as power users in "power_users".
# "masters_numnbers" cannot contain the "monitored_number".
# In my usage scenario I have these 2 use cases:
# 1) I can invoke the bot in any chat and have its answers there
# 2) I can set it to an "intercept keywords and auto-post" mode, but LIMITED TO A SPECIAL CHAT CALLED ZOO
# 3) I can invoke the bot in any chat and make it post its answer to the zoo

# Global Vars
# TODO: manage global vars in a settings.ini
bot_signature = '[MyBOT]'  # Prefix to bot's posts in chats
masters_numbers = ["393518314666"]  # Numbers include international prefix, without the leading "+"
power_users = ["393471134326","393391607733"]
monitored_number = "393471134326"
zoo_chat = "393356328484-1401008247@g.us"  # ZOO Chat ID
ai_brain_file = "ai_brain.json"
ai_error = "ERROR: check if you've written well..."
bot_trigger = "please my lovely bot "  # this is the BOT invocation trigger normal users have to type
bot_trigger_short = "pmlb "  # this is a short form available to all users, but it's kinda secret
bot_trigger_master = "bot "  # this is the invocation trigger reserved to power users and masters
triggers = False  # global var for the "intercept keywords and auto-post" mode
polemical = False  # global var for the "polemical" mode

# Usually, the bot AI works this way: you specify a request in the form of: "bot <verb> <subject> [num]"
# e.g. "bot mock john 3"
# The bot will search its AI brain for the verb "mock" and the subject "john" and post 3 random contents from there.
# When you set the "triggers" mode on, you have to pre-set a list of verbs the bot will try to auto-trigger.
# For instance, you set it on with "bot triggers on mock insult".
# From now on, for every post the bot receives IN THE ZOO CHAT, it will take each word in the post and try to find
# a matching record in "mock ..." and "insult ..." starting with the given word.
# For every match it finds, it wil fire the corresponding "mock ..." or "insult ..." as if someone had issued it by hand.
# For text content, there is the risk of auto-ignition of endless loops, so we track the last AI post to avoid that
# as much as possible

trigger_fakes_command = []  # will contain the list of verbs to use in "triggers" mode, e.g. "mock" and "insult"
last_ai_post = ""

# Global Vars
pinger = -1  # simple pinger to notify the masters_numbers we are alive
start_time = datetime.datetime.now()  # used to calc UPTIME
ai_brain = {}  # our AI


# Classes, Procs and Funcs
def is_int(s):
	try:
		int(s)
		return True
	except ValueError:
		return False


def load_ai():
	global ai_brain
	with open(ai_brain_file) as f:
		ai_brain=json.load(f)


def save_ai():
	with open(ai_brain_file, 'w') as f:
		json.dump(ai_brain, f, indent=2)


# Utility function
def check_or_make_folder(path):
	if not os.path.exists(path):
		os.makedirs(path)


# Used in our logging functions to give scope to the logged text.
# Instead of specifying the logging function by hand in the log text, we get the function's name this way
# Taken from techtonik on https://gist.github.com/techtonik/2151727
# Thanks techtonik
def caller_name(skip=2):
	"""Get a name of a caller in the format module.class.method

		`skip` specifies how many levels of stack to skip while getting caller
		name. skip=1 means "who calls me", skip=2 "who calls my caller" etc.

		An empty string is returned if skipped levels exceed stack height
	"""
	def stack_(frame):
		framelist = []
		while frame:
			framelist.append(frame)
			frame = frame.f_back
		return framelist

	stack = stack_(sys._getframe(1))
	start = 0 + skip
	if len(stack) < start + 1:
		return ''
	parentframe = stack[start]

	name = []
	module = inspect.getmodule(parentframe)
	# `modname` can be None when frame is executed directly in console
	# TODO(techtonik): consider using __main__
	if module:
		name.append(module.__name__)
	# detect classname
	if 'self' in parentframe.f_locals:
		# I don't know any way to detect call from the object method
		# XXX: there seems to be no way to detect static method call - it will
		#		be just a function call
		name.append(parentframe.f_locals['self'].__class__.__name__)
	codename = parentframe.f_code.co_name
	if codename != '<module>':	# top level usually
		name.append(codename)  # function or a method
	del parentframe
	return ".".join(name)


# This adds a new string to the AI brain JSON
def add_brain_string(verb, subj, author, content):
	global ai_brain

	safe_print_and_log(
		'Adding {"' + verb + '": {"' + subj + '": [{"author": "' + author + '","content": "' + content + '"}]}}')

	if verb not in ai_brain: ai_brain[verb] = {}
	if subj not in ai_brain[verb]: ai_brain[verb][subj] = []
	ai_brain[verb][subj].append(
		literal_eval('{"author": ' + json.dumps(author) + ',"content": ' + json.dumps(content) + '}'))


# The AI Brain is a mixture of text answers and pointers to multimedia files stored on disk.
# This function saves to disk in a directory structure that is
# script folder -> ai_media -> verb -> subject
# When you add a multimedia response to a command represented by "verb subject" from the chat command,
# this function takes care the multimedia file is saved on disk under the proper directory
def save_brain_media(verb, subj, author, message):
	mediapath = ".\\ai_media\\{vrb}\\{sbj}\\".format(vrb=verb, sbj=subj)  # TODO: improve generalizing it with Pathlib
	check_or_make_folder(mediapath)
	sourcefilename = Path(message.save_media(mediapath))
	destfilename = "{athr}_{oldname}".format(athr=author, oldname=sourcefilename.name)
	os.rename(mediapath+sourcefilename.name	,mediapath+destfilename)
	return mediapath+destfilename


# This builds the string to be stored in the AI brain in the case of a multimedia content
def add_brain_media(verb, subj, author, message):
	mediapath = save_brain_media(verb, subj, author, message)
	add_brain_string(verb, subj, author, "[Multimedia|Type:{typ}|Caption:|Name:{nm}]".format(typ=message.type, nm=mediapath))


# This processes the user request to add a content to a "verb subject" entry
# 'commandstring' is a command of the type:
#	add verb subject content
# e.g.:          "add mock john john is fat"
# in the array    [0] [1]  [2]  [3]  [4][5]
# When AI will process the command "mock john" it will post the content "john is fat"
def add_ai_content(message, commandstring, zoo):

	author = message.sender.get_safe_name()
	if zoo:  # if the "zoo" parameter is passed, the content must be posted to the ZOO chat
		chatid_str = zoo_chat
	else:
		chatid_str = message.chat_id["_serialized"]
	safe_print_and_log(chatid_str)
	commands = commandstring.split(" ")  # split the commandstring into the array
	safe_print_and_log(commands)
	if (len(commands) > 2):
		verb = commands[1]  # "mock"
		safe_print_and_log(verb)
		subj = commands[2]  # "john"
		safe_print_and_log(subj)
		commands.remove("add")
		commands.remove(verb)
		commands.remove(subj)
		if (message.type == "chat") and (len(commands)>0):  # this will cover simple text
			safe_print_and_log("Adding to AI text content")
			commandstring = " ".join(commands)
			safe_print_and_log("Remaining text: '{cmd}'".format(cmd=commandstring))
			add_brain_string(verb, subj, author, commandstring)
		elif (message.type == "chat") and (len(commands) == 0) and ('quotedMsg' in message._js_obj):  # this will cover replied-to messages and forwarded messages
			# In order to add someone else's text message as content to a command, simply reply-to that message (or forward
			# it to a secret chat) and put your "verb subject" in your message text.
			safe_print_and_log("Adding to AI quoted text message")
			quotedMsg = message._js_obj["quotedMsg"]
			if quotedMsg["type"]=="chat":
				commandstring = quotedMsg["body"]
				add_brain_string(verb, subj, author, commandstring)
				safe_print_and_log(ai_brain[verb][subj])
		elif message.type == 'image' or message.type == 'video' or message.type == 'document' or message.type == 'audio' or message.type == 'ptt':
			# This will cover multimedia content
			safe_print_and_log("Adding to AI multimedia content")
			# When the multimedia is big (or connection is poor) we wait media is loaded before we try to add and save it
			if message._js_obj["mediaData"]["mediaStage"] == "INIT":  # Media is loaded
				add_brain_media(verb, subj, author, message)
				safe_print_and_log(ai_brain[verb][subj])
		else:
			safe_print_and_log("Unprocessable AI message")
		safe_print_and_log(json.dumps(ai_brain, indent=2))  # Log resulting AI, for debug
		save_ai()
		safe_print_and_log("AI Saved")
	else:
		safe_print_and_log("Command too short, ignoring")


# This processes the user request for the bot to post something
def process_ai_content(zoo, private, message, commandstring):
	global ai_brain
	global power_users

	chatid_str = message.chat_id["_serialized"]
	safe_print_and_log(chatid_str)
	# As usual, commandstring is split in the words array
	# "mock john" becomes ['mock','john']
	commands = commandstring.split(" ")
	safe_print_and_log(commands)
	ai_response = ""
	if (len(commands) > 1):
		verb = commands[0]
		safe_print_and_log(verb)
		subj = commands[1]
		# AI Brain "verbs" reserved to power users and masters are identified by adding a "reserved_to_master"
		# virtual "subject". Suppose you have the verb "offend" reserved to masters, and you have an entry
		# for your friend "mark". You, the master, are allowed to ask the bot to "offend mark".
		# The following line takes care that in no event, a request "offend reserved_to_master" is executed.
		if subj == 'reserved_to_master':
			subj = ''  # Avoids considering the 'reserved_to_master' attribute as a valid subject to process in AI
		safe_print_and_log(subj)
		num_actions = 1  # you can ask the bot to execute the command <n> times "mock john 3"
		if (len(commands) >= 3):
			if is_int(commands[2]):
				num_actions = int(commands[2])
		# Strips the verb and subj and joins the remaining words again
		commands.remove(verb)
		commands.remove(subj)
		commandstring = " ".join(commands)
		safe_print_and_log(commandstring)
		if verb in ai_brain:
			if subj in ai_brain[verb]:
				ai_brain_subarray = ai_brain[verb][subj][:]  # Make a by-val copy, so that "del" doesn't empty our brain
				safe_print_and_log(ai_brain_subarray)
				# If you asked more than we have, and we're in polemical mode, we insult you
				if (len(ai_brain_subarray) < num_actions) and polemical:
					# TODO: Make the insult text a global var
					send_message_to_chat(zoo, private, message.chat_id, 'You dumbass, I dont have the {rich} you requested, I just have {num} possible {vrb} {sbj}, you could easily find out by asking "{trg} verbs" you lazy dumbass! I will post only {num}, you dickhead'.format(rich=num_actions, num=len(ai_brain_subarray), vrb=verb, sbj=subj, trg=bot_trigger))
				for ai_action in range (0, num_actions):
					if len(ai_brain_subarray) > 0:
						# As long as we have available content, post it and pop it form the array
						# to avoid posting the same twice
						ai_index = randint(0,len(ai_brain_subarray)-1)
						ai_content = ai_brain_subarray[ai_index]['content']
						ai_response += ai_content + '; '
						if ('reserved_to_master' not in ai_brain[verb]) or (message.sender.id['user'] in power_users):
							send_message_to_chat(zoo, private, message.chat_id, ai_content)
						del(ai_brain_subarray[ai_index])

				safe_print_and_log(ai_response)
			else:
				safe_print_and_log("Unknown AI command, ignoring")
		else:
			safe_print_and_log("Unknown AI command, ignoring")
	else:
		safe_print_and_log("AI Command too short, ignoring")
	return ai_response


# Sends a message to the masters (all of them)
def send_message_to_master(text):
	global masters_numbers
	global monitored_number

	for phone_safe in masters_numbers: # Phone number with country code
		phone_whatsapp = "{}@c.us".format(phone_safe) # WhatsApp Chat ID
		if phone_whatsapp != monitored_number:
			driver.send_message_to_id(phone_whatsapp,text)


# Sends a message to the chat, it manages both multimedia and text content
def send_message_to_chat(zoochat, privateflag, chat_id, text):
	global last_ai_post

	phone_whatsapp = chat_id["_serialized"] # WhatsApp Chat ID
	if text[:17] == "[Multimedia|Type:":  # Multimedia detected
		path_end = (text.split("|")[3].split(":")[1]).find("]")
		mediapath = (text.split("|")[3].split(":")[1])[:path_end]
		caption = bot_signature + ' ' + text.split("|")[2].split(":")[1]
		last_ai_post = caption  # Set our text to avoid auto-triggering
		if (not privateflag):
			if zoochat:
				driver.send_media(mediapath, zoo_chat, caption)
			else:
				driver.send_media(mediapath, phone_whatsapp, caption)
	else:
		last_ai_post = text  # Set our text to avoid auto-triggering
		if (not privateflag):
			if zoochat:
				driver.send_message_to_id(zoo_chat, bot_signature + ' ' + text)
			else:
				driver.send_message_to_id(phone_whatsapp, bot_signature + ' ' + text)


# Gets the text to be used as content from msg body (if type is text) or multimedia caption (if multimedia)
def get_command_from(message):
	if (message.type == "chat" and hasattr(message,'content')):
		return message.content
	elif ( message.type == "image" or message.type == "video" or message.type == "ptt" or message.type == "document" ) and hasattr(message,'caption'):
		return message.caption
	else:
		return ""


# Displays list of verbs and commands
def send_commands(zoochat, privateflag, message):
	global ai_brain
	global power_users

	msgtxt = "## MY BOT, AVAILABLE VERBS:\n"

	for verb in ai_brain:
		# Shows reserved_to_master commands only to power_users
		if ('reserved_to_master' not in ai_brain[verb]) or message.sender.id['user'] in power_users:
			for subj in ai_brain[verb]:
				msgtxt += "{verbo} {soggetto} [{num}]\n".format(verbo=verb, soggetto=subj, num=len(ai_brain[verb][subj]))
	send_message_to_chat(zoochat, privateflag, message.chat_id, msgtxt)


# Displays help
def send_help(zoochat, privateflag, message):
	msgtxt = "## MY BOT, USAGE GUIDE:\n"
	msgtxt += "Write '{invocation} [<command>|<verb> <subject> [<num>]]".format(invocation=bot_trigger)
	if message.sender.id['user'] in power_users:
		msgtxt += " [zoo]"  # Shows the ZOO modifier only to power users
	msgtxt += "'\n"
	msgtxt += " 1) command: hard-coded commands'\n"
	if message.sender.id['user'] in power_users:  # Place to put your reserved hard-coded commands
		msgtxt += "	 -'what about john': answers 'Well John is dumb, even stones know that'\n"
	msgtxt += "	 -laugh: writes 'Uauhauhauhaua'\n"
	msgtxt += "	 -bank: writes 'Banked'\n"
	msgtxt += "	 -add: adds a verb/subject to the AI. e.g.. 'add mock john john is fat'. To add images and videos, the text must be the caption\n"
	msgtxt += "	 -verbs: lists all possible verbs/subjects in AI\n"
	msgtxt += "	 -help: this message'\n"
	msgtxt += " 2) <verb> <subject> [<n>]: takes n (1 if n not specified) times from AI the content corresponding to 'verb subject'\n"
	if message.sender.id['user'] in power_users:  # Lists special commands for power users
		msgtxt += " 3) zoo: if specified, answers in the ZOO chat, otherwise answers in the current chat\n"
		msgtxt += " 4) muori: switches the BOT off\n"
		msgtxt += " 5) reload_ai: reloads AI brain\n"
		msgtxt += " 6) triggers: prints current 'triggers mode' setting\n"
		msgtxt += " 7) triggers on <verb> [verb verb ...]: activates the 'triggers mode' on the specified verbs\n"
		msgtxt += " 8) triggers off: switches 'triggers mode' off\n"
		msgtxt += " 9) polemical: prints current 'polemical mode' setting\n"
		msgtxt += "10) polemical on: switches 'polemical mode' on\n"
		msgtxt += "11) polemical off: switches 'polemical mode' off\n"
	send_message_to_chat(zoochat, privateflag, message.chat_id, msgtxt)


def process_chat_ai(message, command):
	global triggers
	global polemical
	global trigger_fakes_command

	command_words = command.casefold().split(" ")
	ai_output = ""
	private = False
	zoo = False
	for word in command_words:
		if word == 'private':
			private = True
			safe_print_and_log("Found: private")
		elif word == 'zoo':
			zoo = True
			safe_print_and_log("Found: zoo")
	if private:
		command_words.remove('private')
	if zoo:
		command_words.remove('zoo')
	command = ' '.join(command_words)
	safe_print_and_log("Remaining commands: " + command)

	if command.lower() == 'what about john':
		send_message_to_chat(zoo, private, message.chat_id, "Well John is dumb, even stones know that")
	elif command.lower().split(" ")[0] == 'laugh':
		send_message_to_chat(zoo, private, message.chat_id, "Uahuhauhauhauhauhauhauh")
	elif command.lower().split(" ")[0] == 'bank':
		send_message_to_chat(zoo, private, message.chat_id, "banked")
	elif command.lower().split(" ")[0] == "add":
		send_message_to_chat(zoo, private, message.chat_id, "Adding AI content: {cnt}".format(cnt=command.lower()))
		add_ai_content(message, command.lower(), zoo)
	elif command.lower().split(" ")[0] == "verbs":
		send_commands(zoo, private, message)
	elif command.lower().split(" ")[0] == "die":
		send_message_to_chat(zoo, private, message.chat_id, "Quitiing...")
		quit()
	elif command.lower().split(" ")[0] == "reload_ai":
		send_message_to_chat(zoo, private, message.chat_id, "Reloading AI")
		load_ai()
	elif command.lower().split(" ")[0] == "help":
		send_help(zoo, private, message)
	elif command.lower().split(" ")[0] == "triggers":
		if len(command.lower().split(" ")) == 1:
			send_message_to_chat(zoo, private, message.chat_id, "triggers are {trig} and fake {fake}".format(trig=triggers, fake=trigger_fakes_command))
		else:
			if command.lower().split(" ")[1] == "on":
				triggers = True
				trigger_fakes_command = command.lower().split(" ")[2:]
				send_message_to_chat(zoo, private, message.chat_id, "triggers on {fake}".format(fake=trigger_fakes_command))
			else:
				triggers = False
				trigger_fakes_command = []
				send_message_to_chat(zoo, private, message.chat_id, "triggers off")
	elif command.lower().split(" ")[0] == "polemical":
		if len(command.lower().split(" ")) == 1:
			send_message_to_chat(zoo, private, message.chat_id, "polemical mode is {pol}".format(pol=polemical))
		else:
			if command.lower().split(" ")[1] == "on":
				polemical = True
				send_message_to_chat(zoo, private, message.chat_id, "polemical mode on")
			else:
				polemical = False
				send_message_to_chat(zoo, private, message.chat_id, "polemical mode off")
	else:
		ai_output = process_ai_content(zoo, private, message, command.lower())
		send_message_to_master("[Chat autopost]: AI answer was: {answ}".format(answ=ai_output))
		if ai_output == ai_error:
			send_message_to_chat(False, private, message.chat_id, "{answ}".format(answ=ai_output))


def process_command(message, command):
	safe_print_and_log("Processing cmmand: {cmd}".format(cmd=command))
	if command.lower() == 'status':
		send_message_to_master(bot_signature + " Alive and kicking")
	elif command.lower() == 'ping':
		send_message_to_master(bot_signature + " Pinger at {ping}".format(ping=pinger))
	elif command.lower() == 'uptime':
		uptime = datetime.datetime.now() - start_time
		send_message_to_master(bot_signature + " Bot up since {start}, for a total uptime of {upt}".format(start=start_time,upt=uptime))
	elif command.lower() == 'thanks':
		send_message_to_master(bot_signature + " You're welcome")
	else:
		process_chat_ai(message, command)


def safe_print(label, object=None, safe_object=None):
	try:
		print(label) if object is None else print(label,object)
	except:
		try:
			send_message_to_master("[safe_print] found an unprintable object! Check!")
			print('[safe_print] exception trying to print an object. The safe_object is {safeobj}'.format(safeobj=safe_object))
		except:
			send_message_to_master("[safe_print] found an unprintable object! Check!")
			print('[safe_print] exception trying to print an object, and the object is not printable or no safe-object to show.')


def safe_writefile(filename, object, safe_object=None):
	try:
		f=open(filename, "a+", encoding="utf-8")
		f.write(object)
		f.close()
	except:
		try:
			send_message_to_master("[safe_writefile] found an unsavable object! Check!")
			f=open(filename, "a+", encoding="utf-8")
			f.write(safe_object)
			f.close()
		except:
			send_message_to_master("[safe_writefile] found an unsavable object! Check!")
			print('[safe_writefile] exception trying to save an object, and the object is not savable or no safe-object to save.')


def safe_log(object, safe_object=None):
	safe_writefile("generallog.log", object, safe_object)


def safe_chat_log(chat_id, object, safe_object=None):
	safe_writefile("chat_" + chat_id['_serialized'] + ".chat.log", object, safe_object)


def safe_safechat_log(chat_id, object, safe_object=None):
	safe_writefile("safechat_" + chat_id['_serialized'] + ".chat.log", object, safe_object)


def safe_print_and_log(text):
	caller = caller_name()
	safe_print("[{timestamp}|{functionName}]: {txt}\n".format(timestamp=datetime.datetime.now(),functionName=caller, txt=text))
	safe_log("[{timestamp}|{functionName}]: {txt}\n".format(timestamp=datetime.datetime.now(),functionName=caller, txt=text))


# This logs everything that passes through the monitored number
def bank_content(message):
	if message.type == 'chat':
		safe_print('-- Chat')
		safe_print('safe_content', message.safe_content)
		safe_print('content', message.content, message.safe_content)
		safe_chat_log(message.chat_id, "{timestamp};{sender};".format(sender=message.sender.get_safe_name(),
																	  timestamp=message.timestamp))
		safe_chat_log(message.chat_id, message.content, message.safe_content)
		safe_chat_log(message.chat_id, "\n")

		safe_safechat_log(message.chat_id,
						  "{timestamp};{sender};{content}\n".format(sender=message.sender.get_safe_name(),
																	timestamp=message.timestamp,
																	content=message.safe_content))
	elif message.type == 'image' or message.type == 'video' or message.type == 'document' or message.type == 'audio' or message.type == 'ptt':
		safe_print('-- Media')
		safe_print('filename', message.filename)
		safe_print('size', message.size)
		safe_print('mime', message.mime)
		msg_caption = ''
		if hasattr(message, 'caption'):
			msg_caption = message.caption
			safe_print('caption', message.caption)
		safe_print('client_url', message.client_url)
		safe_chat_log(message.chat_id,
					  "{timestamp};{sender};sent multimedia content chat_{id}\{filename} with caption '{caption}'\n".format(
						  sender=message.sender.get_safe_name(), timestamp=message.timestamp,
						  id=message.chat_id['_serialized'], filename=message.filename, caption=msg_caption))
		safe_safechat_log(message.chat_id,
						  "{timestamp};{sender};sent multimedia content chat_{id}\{filename} wiht caption '{caption}'\n".format(
							  sender=message.sender.get_safe_name(), timestamp=message.timestamp,
							  id=message.chat_id['_serialized'], filename=message.filename, caption=msg_caption))
		check_or_make_folder('chat_{id}'.format(id=message.chat_id['_serialized']))
		try:
			if message._js_obj["mediaData"]["mediaStage"] == "INIT":  # Save media only when fully loaded has finished.
				message.save_media('chat_{id}'.format(id=message.chat_id['_serialized']))
		except:
			send_message_to_master("Content not ssaved, exception in message.save_media\n")
			safe_print_and_log('Content not ssaved, exception in message.save_media. Message:\n')
			safe_print_and_log(json.dumps(message.get_js_obj(), indent=4))
	else:
		print('-- Other')


# This scans the post someone made, looking for subjects to auto-post
def process_triggers(command, message):
	global ai_brain
	global trigger_fakes_command
	global last_ai_post

	command_candidates = []

	if command != last_ai_post:  # Avoids auto-triggering
		words = command.lower().split(' ')
		for word in words:                         # Scan every word in the post...
			for trigger in trigger_fakes_command:  # ...then cycle through all verbs set for triggering...
				for subject in ai_brain[trigger]:  # ...and all the subjects in those verbs.
					if word.startswith(subject):   # If one word starts with one of the subjects...
						command_candidates.append('{fakecmd} {subj}'.format(fakecmd=trigger, subj=subject))  # ...add it to the candidate commands to fire
		if len(command_candidates)>0:  # If at least one candidate command has been found, fire a random one among them!
			process_ai_content(False, False, message, command_candidates[randrange(len(command_candidates))])


# Main
load_ai()
print("Loading AI content file")
safe_print_and_log(ai_brain) #debug

driver = WhatsAPIDriver()
print("Waiting for QR")

driver.wait_for_login()
print("Bot started")

try:

	while True:
		time.sleep(3)

		# Just a keep alive pinger in order to know everytinhg's still running
		pinger = pinger +1
		if ((pinger%600) == 0):  # Set this to what you want. Now this is 600 * 3sec = 1800 sec = 30 min. Every 30min a message to the master numbers will say everything's ok
			pinger=0
			send_message_to_master("Work work. Resetting counter to {pingcount}. Status is '{status}'".format(pingcount=pinger, status=driver.get_status()))
		safe_print('Checking messages. Status is {status}. Counter={pingcount}'.format(pingcount=pinger, status=driver.get_status()))
		for contact in driver.get_unread(include_me=True, include_notifications=True):
			for message in contact.messages:
				safe_print_and_log(json.dumps(message.get_js_obj(), indent = 4))
				# Log full JSON to general log
				safe_print_and_log("\n\n==========================================================================\nMessage received at {timestamp}\n".format(timestamp=str(datetime.datetime.now())))
				safe_print('class', message.__class__.__name__)
				safe_print('message', message)
				safe_print('id', message.id)
				safe_print('type', message.type)
				safe_print('timestamp', message.timestamp)
				safe_print('chat_id', message.chat_id)
				safe_print('sender', message.sender)
				
				# Notifications don't seem to have sender.id neither sender.getsafename()
				try:
					sender_id = message.sender.id
					notification = False
				except:
					sender_id = 'NONE'
					notification = True
				safe_print('sender.id', sender_id)
				try:
					sender_safe_name = message.sender.get_safe_name()
				except:
					sender_safe_name = 'NONE'
				safe_print('sender.safe_name', sender_safe_name)

				bank_content(message)  # bank everything

				command = get_command_from(message)	 # get cmd string from text (if chat) or caption (if media)

				if triggers and (message.chat_id["_serialized"] == zoo_chat):  # triggers only work in zoo chat
					process_triggers(command, message)

				if (not notification):
					if message.sender.id['user'] in masters_numbers:
						safe_print_and_log("Message from master: '{cmd}'. Obeying...".format(cmd=command))
						if message.sender.id['user'] != monitored_number:
							process_command(message, command)
					elif (command[:24].casefold()==bot_trigger) or \
							(command[:6].casefold()==bot_trigger_short) or \
							((message.sender.id['user'] in power_users) and (command[:4].casefold()==bot_trigger_master)):
						command = command.casefold().replace(bot_trigger,"")
						command = command.casefold().replace(bot_trigger_short,"")
						command = command.casefold().replace(bot_trigger_master,"")
						safe_print_and_log("Kind request from chat: '{cmd}'. Obeying...".format(cmd=command))
						process_chat_ai(message, command)
					elif (command[:4].casefold()==bot_trigger_master) and (message.sender.id['user'] not in power_users) \
							and polemical == True:
						send_message_to_chat(False, False, message.chat_id, 'You cant just write '
							+ bot_trigger_master
							+ ' you dumbass! Youre no power user! Youre a douche bag!'
							+ ' You must write "' + bot_trigger + '" like all other losers!')

except Exception as e:
	send_message_to_master("I am dying! HELP!\n")
	send_message_to_master("Exception: {exc}\n".format(exc=e))
	safe_print_and_log('EXCEPTION:')
	safe_print_and_log(e)
	raise