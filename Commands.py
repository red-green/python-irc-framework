# coding=utf8
import sys, os, time, math, random
import Irc, Transactions, Blocknotify, Logger, Global, Hooks, Config

ri = lambda a,b: str(random.randint(a,b))

commands = {}

def ping(req, _):
	"""%ping - Pong"""
	req.reply("Pong")
commands["ping"] = ping

def balance(req, _):
	"""%balance - Displays your confirmed and unconfirmed balance"""
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	confirmed = Transactions.balance(acct)
	pending = Transactions.balance_unconfirmed(acct)
	if pending:
		req.reply("Your balance is Ɖ%i (+Ɖ%i unconfirmed)" % (confirmed, pending))
	else:
		req.reply("Your balance is Ɖ%i" % (confirmed))
commands["balance"] = balance

def deposit(req, _):
	"""%deposit - Displays your deposit address"""
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	req.reply_private("To deposit, send coins to %s (transactions will be credited after %d confirmations)" % (Transactions.deposit_address(acct), Config.config["confirmations"]))
commands["deposit"] = deposit

def withdraw(req, arg):
	"""%withdraw <address> [amount] - Sends 'amount' coins to the specified dogecoin address. If no amount specified, sends the whole balance"""
	if len(arg) == 0:
		return req.reply(gethelp("withdraw"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if Transactions.lock(acct):
		return req.reply_private("Your account is currently locked")
	if len(arg) == 1:
		amount = max(Transactions.balance(acct) - 1, 1)
	else:
		if arg[1] == "all":
			arg[1] = str(max(Transactions.balance(acct) - 1, 1))
		try:
			amount = float(arg[1])
			if math.isnan(amount):
				raise ValueError
		except ValueError as e:
			return req.reply_private(repr(arg[1]) + " - invalid amount")
		if amount > 1e12:
			return req.reply_private(repr(arg[1]) + " - invalid amount (value too large)")
		if amount <= 0:
			return req.reply_private(repr(arg[1]) + " - invalid amount (should be 1 or more)")
		if not int(amount) == amount:
			return req.reply_private(repr(arg[1]) + " - invalid amount (should be integer)")
		amount = int(amount)
	to = arg[0]
	if not Transactions.verify_address(to):
		return req.reply_private(to + " doesn't seem to be a valid dogecoin address")
	with Logger.token() as token:
		try:
			tx = Transactions.withdraw(token, acct, to, amount)
			req.reply("Coins have been sent, see http://dogechain.info/tx/%s [%s]" % (tx, token.id))
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to withdraw Ɖ%i (+Ɖ1 TX fee) but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
		except Transactions.InsufficientFunds:
			req.reply("Something went wrong, report this to mniip [%s]" % (token.id))
			Logger.irclog("InsufficientFunds while executing '%s' from '%s'" % (req.text, req.nick))
commands["withdraw"] = withdraw

def tip(req, arg):
	"""%tip <target> <amount> - Sends 'amount' coins to the specified nickname"""
	if len(arg) < 2:
		return req.reply(gethelp("tip"))
	to = arg[0]
	acct, toacct = Irc.account_names([req.nick, to])
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if Transactions.lock(acct):
		return req.reply_private("Your account is currently locked")
	if not toacct:
		if toacct == None:
			return req.reply_private(to + " is not online")
		else:
			return req.reply_private(to + " is not identified with freenode services")
	arg[1] = {
		'all':str(Transactions.balance(acct)),
		'dogecar':'98',
		'joshwise':'98',
		'hack':'1337',
		'leet':'1337',
		'elite':'1337',
		'blazeit':'420',
		'flip':ri(1,2),
		'roll':ri(1,10),
		'megaroll':ri(1,100),
		'gigaroll':ri(1,1000),
		'200m','200000000'
		}.get(arg[1].lower(),arg[1])
	try:
		amount = float(arg[1])
		if math.isnan(amount):
			raise ValueError
	except ValueError as e:
		return req.reply_private(repr(arg[1]) + " - invalid amount")
	if amount > 1e12:
		return req.reply_private(repr(arg[1]) + " - invalid amount (value too large)")
	if amount < 1:
		return req.reply_private(repr(arg[1]) + " - invalid amount (should be 1 or more)")
	if not int(amount) == amount:
		return req.reply_private(repr(arg[1]) + " - invalid amount (should be integer)")
	amount = int(amount)
	with Logger.token() as token:
		try:
			Transactions.tip(token, acct, toacct, amount)
			if Irc.equal_nicks(req.nick, req.target):
				req.reply("Done [%s]" % (token.id))
			else:
				req.say("Such %s tipped much Ɖ%i to %s! (to claim /msg Doger help) [%s]" % (req.nick, amount, to, token.id))
			req.privmsg(to, "Such %s has tipped you Ɖ%i (to claim /msg Doger help) [%s]" % (req.nick, amount, token.id), priority = 10)
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
commands["tip"] = tip

def mtip(req, arg):
	"""%mtip <targ1> <amt1> [<targ2> <amt2> ...] - Send multiple tips at once"""
	if not len(arg) or len(arg) % 2:
		return req.reply(gethelp("mtip"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if Transactions.lock(acct):
		return req.reply_private("Your account is currently locked")
	for i in range(0, len(arg), 2):
		if arg[i + 1] == "all":
			arg[i + 1] = str(Transactions.balance(acct))
		try:
			amount = float(arg[i + 1])
			if math.isnan(amount):
				raise ValueError
		except ValueError as e:
			return req.reply_private(repr(arg[i + 1]) + " - invalid amount")
		if amount > 1e12:
			return req.reply_private(repr(arg[i + 1]) + " - invalid amount (value too large)")
		if amount < 1:
			return req.reply_private(repr(arg[i + 1]) + " - invalid amount (should be 1 or more)")
		if not int(amount) == amount:
			return req.reply_private(repr(arg[i + 1]) + " - invalid amount (should be integer)")
	targets = []
	amounts = []
	total = 0
	for i in range(0, len(arg), 2):
		target = arg[i]
		amount = int(float(arg[i + 1]))
		found = False
		for i in range(len(targets)):
			if Irc.equal_nicks(targets[i], target):
				amounts[i] += amount
				total += amount
				found = True
				break
		if not found:
			targets.append(target)
			amounts.append(amount)
			total += amount
	balance = Transactions.balance(acct)
	if total > balance:
		return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (total, balance))
	accounts = Irc.account_names(targets)
	totip = {}
	failed = ""
	tipped = ""
	for i in range(len(targets)):
		if accounts[i]:
			totip[accounts[i]] = amounts[i]
			tipped += " %s %d" % (targets[i], amounts[i])
		elif accounts[i] == None:
			failed += " %s (offline)" % (targets[i])
		else:
			failed += " %s (unidentified)" % (targets[i])
	with Logger.token() as token:
		try:
			Transactions.tip_multiple(token, acct, totip)
			tipped += " [%s]" % (token.id)
		except Transactions.NotEnoughMoney:
			return req.reply_private("You tried to tip Ɖ%i but you only have Ɖ%i" % (total, Transactions.balance(acct)))
	output = "Tipped:" + tipped
	if len(failed):
		output += "  Failed:" + failed
	req.reply(output)
commands["mtip"] = mtip

def donate(req, arg):
	"""%donate <amount> - Donate 'amount' coins to the developers of this bot (mniip)"""
	if len(arg) < 1:
		return req.reply(gethelp("donate"))
	acct = Irc.account_names([req.nick])[0]
	if not acct:
		return req.reply_private("You are not identified with freenode services (see /msg NickServ help)")
	if Transactions.lock(acct):
		return req.reply_private("Your account is currently locked")
	toacct = "mniip"
	if arg[0] == "all":
		arg[0] = str(Transactions.balance(acct))
	try:
		amount = float(arg[0])
		if math.isnan(amount):
			raise ValueError
	except ValueError as e:
		return req.reply_private(repr(arg[0]) + " - invalid amount")
	if amount > 1e12:
		return req.reply_private(repr(arg[0]) + " - invalid amount (value too large)")
	if amount < 1:
		return req.reply_private(repr(arg[0]) + " - invalid amount (should be 1 or more)")
	if not int(amount) == amount:
		return req.reply_private(repr(arg[0]) + " - invalid amount (should be integer)")
	amount = int(amount)
	with Logger.token() as token:
		try:
			Transactions.tip(token, acct, toacct, amount)
			req.reply("Done [%s]" % (token.id))
			req.privmsg(toacct, "Such %s donated Ɖ%i [%s]" % (req.nick, amount, token.id), priority = 10)
		except Transactions.NotEnoughMoney:
			req.reply_private("You tried to donate Ɖ%i but you only have Ɖ%i" % (amount, Transactions.balance(acct)))
commands["donate"] = donate

def gethelp(name):
	if name[0] == Config.config["prefix"]:
		name = name[1:]
	cmd = commands.get(name, None)
	if cmd and cmd.__doc__:
		return cmd.__doc__.split("\n")[0].replace("%", Config.config["prefix"])

def _help(req, arg):
	"""%help - list of commands; %help <command> - help for specific command"""
	if len(arg):
		h = gethelp(arg[0])
		if h:
			req.reply(h)
	else:
		if not Irc.equal_nicks(req.target, req.nick):
			return req.reply("I'm Doger, an IRC dogecoin tipbot written by mniip. For more info do /msg Doger help")
		acct = Irc.account_names([req.nick])[0]
		if acct:
			ident = "you're identified as \2" + acct + "\2"
		else:
			ident = "you're not identified"
		req.say("I'm Doger, I'm an IRC dogecoin tipbot written by mniip. To get help about a specific command, say \2%help <command>\2  Commands: %tip %balance %withdraw %deposit %mtip %donate %help".replace("%", Config.config["prefix"]))
		req.say("Note that to receive or send tips you should be identified with freenode services (%s). For any support questions, including those related to lost coins, join ##doger" % (ident))
commands["help"] = _help

def admin(req, arg):
	"""
	admin"""
	if len(arg):
		command = arg[0]
		arg = arg[1:]
		if command == "reload":
			for mod in arg:
				reload(sys.modules[mod])
			req.reply("Reloaded")
#		elif command == "exec":
#			exec(" ".join(arg).replace("$", "\n"))
		elif command == "ignore":
			Irc.ignore(arg[0], int(arg[1]))
			req.reply("Ignored")
		elif command == "die":
			for instance in Global.instances:
				Global.manager_queue.put(("Disconnect", instance))
			Global.manager_queue.join()
			Blocknotify.stop()
			Global.manager_queue.put(("Die",))
		elif command == "restart":
			for instance in Global.instances:
				Global.manager_queue.put(("Disconnect", instance))
			Global.manager_queue.join()
			Blocknotify.stop()
			os.execv(sys.executable, [sys.executable] + sys.argv)
		elif command == "manager":
			for cmd in arg:
				Global.manager_queue.put(cmd.split("$"))
			req.reply("Sent")
		elif command == "raw":
			Irc.instance_send(req.instance, eval(" ".join(arg)))
		elif command == "join":
			Irc.instance_send(req.instance, ("JOIN", arg[0]), priority = 0.1)
		elif command == "part":
			Irc.instance_send(req.instance, ("PART", arg[0]), priority = 0.1)
		elif command == "caches":
			acsize = 0
			accached = 0
			with Global.account_lock:
				for channel in Global.account_cache:
					for user in Global.account_cache[channel]:
						acsize += 1
						if Global.account_cache[channel][user] != None:
							accached += 1
			acchannels = len(Global.account_cache)
			whois = " OK"
			whoisok = True
			for instance in Global.instances:
				tasks = Global.instances[instance].whois_queue.unfinished_tasks
				if tasks:
					if whoisok:
						whois = ""
						whoisok = False
					whois += " %s:%d!" % (instance, tasks)
			req.reply("Account caches: %d user-channels (%d cached) in %d channels; Whois queues:%s" % (acsize, accached, acchannels, whois))
		elif command == "channels":
			inss = ""
			for instance in Global.instances:
				chans = []
				with Global.account_lock:
					for channel in Global.account_cache:
						if instance in Global.account_cache[channel]:
							chans.append(channel)
				inss += " %s:%s" % (instance, ",".join(chans))
			req.reply("Instances:" + inss)
		elif command == "balances":
			database, dogecoind = Transactions.balances()
			req.reply("Dogecoind: %.8f; Database: %.8f" % (dogecoind, database))
		elif command == "lock":
			if len(arg) > 1:
				if arg[1] == "on":
					Transactions.lock(arg[0], True)
				elif arg[1] == "off":
					Transactions.lock(arg[0], False)
				req.reply("Done")
			elif len(arg):
				req.reply("locked" if Transactions.lock(arg[0]) else "not locked")

commands["admin"] = admin

def _as(req, arg):
	"""
	admin"""
	_, target, text = req.text.split(" ", 2)
	if target[0] == '@':
		Global.account_cache[""] = {"@": target[1:]}
		target = "@"
	if text.find(" ") == -1:
		command = text
		args = []
	else:
		command, args = text.split(" ", 1)
		args = [a for a in args.split(" ") if len(a) > 0]
	if command[0] != '_':
		cmd = commands.get(command.lower(), None)
		if not cmd.__doc__ or cmd.__doc__.find("admin") == -1 or Irc.is_admin(source):
			if cmd:
				req = Hooks.FakeRequest(req, target, text)
				Hooks.run_command(cmd, req, args)
	if Global.account_cache.get("", None):
		del Global.account_cache[""]
commands["as"] = _as
