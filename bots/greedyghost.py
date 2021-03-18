#!/usr/bin/env python3

from discord.ext import commands
import random, sys, configparser, web, traceback, MySQLdb, discord
import support.vtm_res as vtm_res
import support.ghostDB as ghostDB
import support.utils as utils

if len(sys.argv) == 1:
    print("Specifica un file di configurazione!")
    sys.exit()

config = configparser.ConfigParser()
config.read(sys.argv[1])

TOKEN = config['Discord']['token']


SOMMA_CMD = ["somma", "s", "lapse"]
DIFF_CMD = ["diff", "d"]
MULTI_CMD = ["multi", "m"]
DANNI_CMD = ["danni", "dmg"]
PROGRESSI_CMD = ["progressi", "p"]
SPLIT_CMD = ["split"]

SOAK_CMD = ["soak", "assorbi"]
INIZIATIVA_CMD = ["iniziativa", "iniz"]
RIFLESSI_CMD = ["riflessi", "r"]

RollCat = utils.enum("DICE", "INITIATIVE", "REFLEXES", "SOAK") # macro categoria che divide le azioni di tiro
RollArg = utils.enum("DIFF", "MULTI", "SPLIT", "ADD", "ROLLTYPE") # argomenti del tiro
RollType = utils.enum("NORMALE", "SOMMA", "DANNI", "PROGRESSI") # sottotipo dell'argomento RollType

INFINITY = float("inf")

max_dice = 100
max_faces = 100


die_emoji = {
    2: ":two:",
    3: ":three:",
    4: ":four:",
    5: ":five:",
    6: ":six:",
    7: ":seven:",
    8: ":eight:",
    9: ":nine:",
    10: ":keycap_ten:"
    }

def prettyRoll(roll, diff, cancel):
    for i in range(0, len(roll)-cancel):
        die = roll[i]
        if die == 1:
            roll[i] = '**1**'
        elif die >= diff:
            roll[i] = die_emoji[die]
        else:
            roll[i] = str(die)
    for i in range(len(roll)-cancel, len(roll)):
        roll[i] = f"**~~{roll[i]}~~**"
    random.shuffle(roll)
    return "["+", ".join(roll)+"]"

def rollStatusDMG(n):
    if n == 1:
        return f':green_square: **{1} Danno**'
    elif n > 1:
        return f':green_square: **{n} Danni**'
    else:
        return f':red_square: **Nessun danno**'

def rollStatusProgress(n):
    if n == 1:
        return f':green_square: **{1} Ora**'
    elif n > 1:
        return f':green_square: **{n} Ore**'
    else:
        return f':red_square: **Il soffitto è estremamente interessante**'

def rollStatusNormal(n):
    if n == 1:
        return f':green_square: **{1} Successo**'
    elif n > 1:
        return f':green_square: **{n} Successi**'
    elif n == 0:
        return f':yellow_square: **Fallimento**'
    elif n == -2:
        return f':orange_square: **Fallimento drammatico**'
    else:
        return f':sos: **Fallimento critico**'

def rollStatusReflexes(n):
    if n >= 1:
        return f':green_square: ** Successo!**'
    else:
        return f':yellow_square: **Fallimento!**'

def rollStatusSoak(n):
    if n == 1:
        return f':green_square: **{1} Danno assorbito**'
    elif n > 1:
        return f':green_square: **{n} Danni assorbiti**'
    else:
        return f':red_square: **Nessun danno assorbito**'

def rollAndFormatVTM(ndice, nfaces, diff, statusFunc = rollStatusNormal, extra_succ = 0, cancel = True, spec = False):
    successi, tiro, cancel = vtm_res.roller(ndice, nfaces, diff, cancel, spec)
    pretty = prettyRoll(tiro, diff, cancel)
    successi += extra_succ
    status = statusFunc(successi)
    response = status + f' (diff {diff}): {pretty}'
    if extra_succ:
        response += f' **+{extra_succ}**'
    return response

def atSend(ctx, msg):
    return ctx.send(f'{ctx.message.author.mention} {msg}')

def findSplit(idx, splits):
    for si in range(len(splits)):
        if idx == splits[si][0]:
            return splits[si][1:]
    return []

def validateTraitName(traitid):
    forbidden_chars = [" ", "+"]
    return sum(map(lambda x: traitid.count(x), forbidden_chars)) == 0

class BotException(Exception): # use this for 'known' error situations
    def __init__(self, msg):
        super(BotException, self).__init__(msg)
    
dbm = ghostDB.DBManager(config['Database'])

botcmd_prefixes = ['.']
bot = commands.Bot(botcmd_prefixes)

#executed once on bot boot
@bot.event
async def on_ready():
    for guild in bot.guilds:
        print(
            f'{bot.user} is connected to the following guild:\n'
            f'{guild.name} (id: {guild.id})'
        )
    #members = '\n - '.join([member.name for member in guild.members])
    #print(f'Guild Members:\n - {members}')
    #await bot.get_channel(int(config['DISCORD_DEBUG_CHANNEL'])).send("bot is online")

@bot.event
async def on_command_error(ctx, error):
    ftb = traceback.format_exc()
    #logging.warning(traceback.format_exc()) #logs the error
    #ignored = (commands.CommandNotFound, )
    error = getattr(error, 'original', error)
    #if isinstance(error, ignored):
    #    print(error)
    if isinstance(error, commands.CommandNotFound):
        try:
            msgsplit = ctx.message.content.split(" ")
            msgsplit[0] = msgsplit[0][1:] # toglie prefisso
            charid = msgsplit[0]
            ic, character = dbm.isValidCharacter(charid)
            if ic:
                await pgmanage(ctx, *msgsplit)
        except MySQLdb.OperationalError as e:
            if e.args[0] == 2006:
                dbm.reconnect()
                await atSend(ctx, f'Ho dovuto ripristinare al connessione Database, per favore riprova')
            else:
                await atSend(ctx, f'Congratulazioni! Hai trovato un modo per rompere il comando!')
                debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
                await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}\n\n{ftb}')
        except BotException as e:
            await atSend(ctx, f'{e}')
        except ghostDB.DBException as e:
            await atSend(ctx, f'{e}')   
    elif isinstance(error, BotException):
        await atSend(ctx, f'{error}')
    elif isinstance(error, ghostDB.DBException):
        await atSend(ctx, f'{error}')
    else:
        if isinstance(error, MySQLdb.OperationalError) and error.args[0] == 2006:
            dbm.reconnect()
            await atSend(ctx, f'Ho dovuto ripristinare al connessione Database, per favore riprova')
        else:
            await atSend(ctx, f'Congratulazioni! Hai trovato un modo per rompere il comando!')
        #print("debug user:", int(config['Discord']['debuguser']))
        debug_user = await bot.fetch_user(int(config['Discord']['debuguser']))
        await debug_user.send(f'Il messaggio:\n\n{ctx.message.content}\n\n ha causato l\'errore di tipo {type(error)}:\n\n{error}\n\n{ftb}')


@bot.command(name='coin', help = 'Testa o Croce.')
async def coin(ctx):
    moneta=['Testa' , 'Croce']
    await atSend(ctx, f'{random.choice(moneta)}')

roll_longdescription = """
.roll <cosa> <come>

.roll 10d10 - Tiro senza difficoltà
.roll 10d10 somma - Somma il numero dei tiri
.roll 10d10 diff 6 - Tiro con difficoltà specifica
.roll 10d10 danni - Tiro danni
.roll 10d10 +5 danni - Tiro danni con modificatore
.roll 10d10 progressi - Tiro per i progressi del giocatore
.roll 10d10 lapse - Tiro per i progressi in timelapse del giocatore
.roll 10d10 multi 3 diff 6 - Tiro multiplo
.roll 10d10 split 6 7 - Split a difficoltà separate [6, 7]
.roll 10d10 diff 6 multi 3 split 2 6 7  - Multipla [3] con split [al 2° tiro] a difficoltà separate [6,7]
.roll 10d10 multi 3 split 2 6 7 split 3 4 5 - Multipla [3] con split al 2° e 3° tiro

Si può sosrtituire XdY con una combinazione di tratti (forza, destrezza+schivare...) e se c'è una sessione aperta verranno prese le statistiche del pg rilevante

Scorciatoie:

.roll iniziativa: equivale a .roll 1d10 +(destrezza+prontezza+velocità)
.roll riflessi: equivale a .roll volontà diff (10-prontezza)
.roll assorbi: equivale a .roll costituzione+robustezza diff 6 danni
"""

# input: l'espressione <what> in .roll <what> [<args>]
# output: tipo di tiro, numero di dadi, numero di facce
def parseRollWhat(ctx, what):
    n = -1
    faces = -1

    # tiri custom 
    if what in INIZIATIVA_CMD:
        return RollCat.INITIATIVE, 1, 10
    if what in RIFLESSI_CMD:
        return RollCat.REFLEXES, 1, 10
    if what in SOAK_CMD:
        return RollCat.SOAK, 1, 10

    # combinazione di tratti
    singletrait, _ = dbm.isValidTrait(what)
    if what.count("+") or singletrait:
        character = dbm.getActiveChar(ctx)
        split = what.split("+")
        faces = 10
        n = 0
        for trait in split:
            n += dbm.getTrait(character['id'], trait)['cur_value']
        return RollCat.DICE, n, faces

    # espressione xdy
    split = what.split("d")
    if len(split) > 2:
        raise BotException("Troppe 'd' b0ss")
    if len(split) == 1:
        raise BotException(f'"{split[0]}" cosa')
    if split[0] == "":
        split[0] = "1"
    if not split[0].isdigit():
        raise BotException(f'"{split[0]}" non è un numero intero positivo')
    if split[1] == "":
        split[1] = "10"
    if not split[1].isdigit():
        raise BotException(f'"{split[1]}" non è un numero intero positivo')
    n = int(split[0])
    faces = int(split[1])
    if n == 0:
        raise BotException(f'{n} non è > 0')
    if  faces == 0:
        raise BotException(f'{faces} non è > 0')
    if n > max_dice:
        raise BotException(f'{n} dadi sono troppi b0ss')
    if faces > max_faces:
        raise BotException(f'{faces} facce sono un po\' tante')
    return RollCat.DICE, n, faces

def validateNumber(args, i, err_msg = 'un intero positivo'):
    if not args[i].isdigit():
        raise ValueError(f'"{args[i]}" non è {err_msg}')
    return i, int(args[i])

def validateBoundedNumber(args, i, min_bound, max_bound = INFINITY, err_msg = "un numero nell'intervallo accettato"):
    _, num = validateNumber(args, i)
    if num > max_bound or num < min_bound:
        raise ValueError(f'{num} non è {err_msg}')
    return i, num

def validateIntegerGreatZero(args, i):
    return validateBoundedNumber(args, i, 1, err_msg = "un intero maggiore di zero")

def validateDifficulty(args, i):
    return validateBoundedNumber(args, i, 2, 10, "una difficoltà valida")

# input: sequenza di argomenti per .roll
# output: dizionario popolato con gli argomenti validati
def parseRollArgs(args, n):
    parsed = {
        RollArg.ROLLTYPE: RollType.NORMALE # default
        }
    # leggo gli argomenti scorrendo args
    i = 0
    while i < len(args):
        if args[i] in SOMMA_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.SOMMA
        elif args[i] in DIFF_CMD:
            if RollArg.DIFF in parsed:
                raise ValueError(f'mi hai già dato una difficoltà')
            if len(args) == i+1:
                raise ValueError(f'diff cosa')
            i, diff = validateDifficulty(args, i+1)
            parsed[RollArg.DIFF] = diff
        elif args[i] in MULTI_CMD:
            if RollArg.SPLIT in parsed:
                raise ValueError(f'multi va specificato prima di split')
            if RollArg.MULTI in parsed:
                raise ValueError(f'Stai tentando di innestare 2 multiple?')
            if len(args) == i+1:
                raise ValueError(f'multi cosa')
            max_moves = (n+1)/2
            i, multi = validateBoundedNumber(args, i+1, 2, max_moves, f"un numero di mosse valido per il tuo dice pool (da 2 a {int(max_moves)})")
            parsed[RollArg.MULTI] = multi
        elif args[i] in DANNI_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.DANNI
        elif args[i] in PROGRESSI_CMD:
            parsed[RollArg.ROLLTYPE] = RollType.PROGRESSI
        elif args[i] in SPLIT_CMD:
            roll_index = 0
            split = []
            if RollArg.SPLIT in parsed: # fetch previous splits
                split = parsed[RollArg.SPLIT]
            if RollArg.MULTI in parsed:
                if len(args) < i+4:
                    raise ValueError(f'split prende almeno 3 parametri con multi!')
                i, temp = validateIntegerGreatZero(args, i+1)
                roll_index = temp-1
                if roll_index >= parsed[RollArg.MULTI]:
                    raise ValueError(f'"Non puoi splittare il tiro {args[i+1]} con multi {multi}')
                if sum(filter(lambda x: x[0] == roll_index, split)): # cerco se ho giò splittato questo tiro
                    raise ValueError(f'Stai già splittando il tiro {roll_index+1}')
            else: # not an elif because reasons
                if len(args) < i+3:
                    raise ValueError(f'split prende almeno 2 parametri!')
            i, d1 = validateIntegerGreatZero(args, i+1)
            i, d2 = validateIntegerGreatZero(args, i+1)
            split.append( [roll_index] + list(map(int, [d1, d2])))
            parsed[RollArg.SPLIT] = split # save the new split
        elif args[i].startswith("+"):
            raw = args[i][1:]
            if raw == "":
                if len(args) == i+1:
                    raise ValueError(f'+ cosa')
                raw = args[i+1] # support for space
                i += 1
            if not raw.isdigit() or raw == "0":
                raise ValueError(f'"{raw}" non è un intero positivo')
            add = int(raw)
            parsed[RollArg.ADD] = add
        else:
            width = 3
            ht = " ".join(list(args[max(0, i-width):i]) + ['**'+args[i]+'**'] + list(args[min(len(args), i+1):min(len(args), i+width)]))
            raise ValueError(f"L'argomento '{args[i]}' in '{ht}' non mi è particolarmente chiaro")
        i += 1
    return parsed

@bot.command(name='roll', aliases=['r', 'tira', 'lancia'], brief = 'Tira dadi', description = roll_longdescription) 
async def roll(ctx, *args):
    if len(args) == 0:
        raise BotException("roll cosa diomadonna")
    # capisco quanti dadi tirare
    what = args[0].lower()
    action, ndice, nfaces = parseRollWhat(ctx, what)
    # leggo e imposto le varie opzioni
    parsed = None
    try:
        parsed = parseRollArgs(args[1:], ndice)
    except ValueError as e:
        await atSend(ctx, str(e))
        return

    # decido cosa fare
    if len(args) == 1 and action == RollCat.DICE : #simple roll
        raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
        await atSend(ctx, repr(raw_roll))
        return

    response = ''
    if parsed[RollArg.ROLLTYPE] == RollType.NORMALE and not RollArg.DIFF in parsed and RollArg.ADD in parsed: #se non c'è difficoltà tramuta un tiro in un tiro somma instile dnd
        parsed[RollArg.ROLLTYPE] = RollType.SOMMA
    add = parsed[RollArg.ADD] if RollArg.ADD in parsed else 0
    if action == RollCat.INITIATIVE:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
            raise BotException("Combinazione di parametri non valida!")
        raw_roll = random.randint(1, nfaces)
        bonuses_log = []
        bonus = add
        if add:
            bonuses_log.append( f'bonus: {add}' )
        try:
            character = dbm.getActiveChar(ctx)
            for traitid in ['prontezza', 'destrezza', 'velocità']:
                try:
                    val = dbm.getTrait(character['id'], traitid)['cur_value']
                    bonus += val
                    bonuses_log.append( f'{traitid}: {val}' )
                except BotException:
                    pass
        except BotException:
            response += 'Nessun personaggio !\n'
        if len(bonuses_log):
            response += (", ".join(bonuses_log)) + "\n"
        final_val = raw_roll+bonus
        response += f'Iniziativa: **{final_val}**, tiro: [{raw_roll}]' + (f'+{bonus}' if bonus else '')
    elif action == RollCat.REFLEXES:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE or RollArg.DIFF in parsed:
            raise BotException("Combinazione di parametri non valida!")
        character = dbm.getActiveChar(ctx)
        volonta = dbm.getTrait(character['id'], 'volonta')['cur_value']
        prontezza = dbm.getTrait(character['id'], 'prontezza')['cur_value']
        diff = 10 - prontezza
        response = f'Volontà corrente: {volonta}, Prontezza: {prontezza} -> {volonta}d{nfaces} diff ({nfaces}-{prontezza})\n'
        response += rollAndFormatVTM(volonta, nfaces, diff, rollStatusReflexes, add)
    elif action == RollCat.SOAK:
        if RollArg.MULTI in parsed or RollArg.SPLIT in parsed or RollArg.ADD in parsed or parsed[RollArg.ROLLTYPE] != RollType.NORMALE:
            raise BotException("Combinazione di parametri non valida!")
        diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
        character = dbm.getActiveChar(ctx)
        pool = dbm.getTrait(character['id'], 'costituzione')['cur_value']
        try:
            pool += dbm.getTrait(character['id'], 'robustezza')['cur_value']
        except BotException:
            pass
        response = rollAndFormatVTM(pool, nfaces, diff, rollStatusSoak, 0)
    elif RollArg.MULTI in parsed:
        multi = parsed[RollArg.MULTI]
        split = []
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
        if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
            response = ""
            if not RollArg.DIFF in parsed:
                raise BotException(f'Si ma mi devi dare una difficoltà')
            for i in range(multi):
                parziale = ''
                ndadi = ndice-i-multi
                split_diffs = findSplit(i, split)
                if len(split_diffs):
                    pools = [(ndadi-ndadi//2), ndadi//2]
                    for j in range(len(pools)):
                        parziale += f'\nTiro {j+1}: '+ rollAndFormatVTM(pools[j], nfaces, split_diffs[j])
                else:
                    parziale = rollAndFormatVTM(ndadi, nfaces, parsed[RollArg.DIFF])
                response += f'\nAzione {i+1}: '+parziale # line break all'inizio tanto c'è il @mention
        else:
            raise BotException(f'Combinazione di parametri non supportata')
    else: # 1 tiro solo 
        if RollArg.SPLIT in parsed:
            split = parsed[RollArg.SPLIT]
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE:
                pools = [(ndice-ndice//2), ndice//2]
                response = ''
                for i in range(len(pools)):
                    parziale = rollAndFormatVTM(pools[i], nfaces, split[0][i+1])
                    response += f'\nTiro {i+1}: '+parziale
            else:
                raise BotException(f'Combinazione di parametri non supportata')
        else:
            if parsed[RollArg.ROLLTYPE] == RollType.NORMALE: # tiro normale
                if not RollArg.DIFF in parsed:
                    raise BotException(f'Si ma mi devi dare una difficoltà')
                response = rollAndFormatVTM(ndice, nfaces, parsed[RollArg.DIFF], rollStatusNormal, add)
            elif parsed[RollArg.ROLLTYPE] == RollType.SOMMA:
                raw_roll = list(map(lambda x: random.randint(1, nfaces), range(ndice)))
                somma = sum(raw_roll)+add
                response = f'somma: **{somma}**, tiro: {raw_roll}' + (f'+{add}' if add else '')
            elif parsed[RollArg.ROLLTYPE] == RollType.DANNI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(ndice, nfaces, diff, rollStatusDMG, add, False)
            elif parsed[RollArg.ROLLTYPE] == RollType.PROGRESSI:
                diff = parsed[RollArg.DIFF] if RollArg.DIFF in parsed else 6
                response = rollAndFormatVTM(ndice, nfaces, diff, rollStatusProgress, add, False, True)
            else:
                raise BotException(f'Tipo di tiro sconosciuto: {rolltype}')
    await atSend(ctx, response)
    
        
@bot.command(brief='Lascia che il Greedy Ghost ti saluti.')
async def salut(ctx):
    await atSend(ctx, 'Shalom!')

@bot.command(brief='Pay respect.')
async def respect(ctx):
	await atSend(ctx, ':regional_indicator_f:')

@bot.command(brief='Fa sapere il ping del Bot')
async def ping(ctx):
    await atSend(ctx, f' Ping: {round(bot.latency * 1000)}ms')

@bot.command(aliases=['divinazione' , 'div'] , brief='Presagire il futuro con una domanda' , help = 'Inserire comando + domanda')
async def divina(ctx, *, question):
    responses=['Certamente.',
	 	'Sicuramente.' ,
 		'Probabilmente si.' ,
	 	'Forse.' ,
	  	'Mi sa di no.' ,
		'Probabilmente no.' ,
	 	'Sicuramente no.',
		'Per come la vedo io, si.',
		'Non è scontato.',
		'Meglio chiedere a Rossellini.',
		'Le prospettive sono buone.',
		'Ci puoi contare.',
		'Difficile dare una risposta.',
		'Sarebbe meglio non risponderti adesso.',
		'Sarebbe uno spoiler troppo grosso.',
		'Non ci contare.',
		'I miei contatti mi dicono di no.'
		]
    await atSend(ctx, f'Domanda: {question}\nRisposta: {random.choice(responses)}')

@bot.command(aliases=['Paradiso' , 'Torta'] , brief='Ricorda a Sam il vero Vietnam' , help = 'Il regno del colesterolo')
async def paradise(ctx):
	replies=['https://funnelcakesparadise.com/wp-content/uploads/2020/06/FUNNEL-CAKE-PARADISE-MENU-4.png' ,
		 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT_U_TC2RrY1HupVVnqaYbh8icE5fQ5RtZaEA&usqp=CAU' ,
		 ':motorized_wheelchair: :cake: :baby_bottle: :drop_of_blood:' ,
		 'https://funnelcakesparadise.com/wp-content/uploads/2017/12/Catering-Menu-2.png' ]
	await atSend(ctx, f'{random.choice(replies)}')	
		
	
@bot.command(brief='Testa il database rispondendo con la lista degli amministratori')
async def dbtest(ctx):
    admins = []    
    response = ''
    try:
        admins = dbm.db.select('BotAdmin')
        response = "Database test, listing bot admins..."
        for admin in admins:
            user = await bot.fetch_user(admin['userid'])
            response += f'\n{user}'
    except Exception as e:
        response = f'C\'è stato un problema: {e}'
    await atSend(ctx, response)


@bot.command(brief = "Tira 1d100 per l'inizio giocata", description = "Tira 1d100 per l'inizio giocata")
async def start(ctx, *args):
    await atSend(ctx, f'{random.randint(1, 100)}')


@bot.group(brief='Controlla le sessioni di gioco', description = "Le sessioni sono basate sui canali: un canale può ospitare una sessione alla volta, ma la stessa cronaca può avere sessioni attive in più canali.")
async def session(ctx):
    if ctx.invoked_subcommand is None:
        sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
        if len(sessions):
            chronicle = dbm.db.select('Chronicle', where='id=$chronicle', vars=dict(chronicle=sessions[0]['chronicle']))
            cn = chronicle[0]['name']
            await atSend(ctx, f"Sessione attiva: {cn}")
        else:
            await atSend(ctx, "Nessuna sessione attiva in questo canale!")
        

@session.command(brief = 'Inizia una sessione', description = '.session start <nomecronaca>: inizia una sessione per <nomecronaca> (richiede essere admin o storyteller della cronaca da iniziare) (richiede essere admin o storyteller della cronaca da iniziare)')
async def start(ctx, *args):
    issuer = str(ctx.message.author.id)
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    chronicleid = args[0].lower()
    st, _ = dbm.isChronicleStoryteller(issuer, chronicleid)
    ba, _ = dbm.isBotAdmin(issuer)
    can_do = st or ba
    #can_do = len(dbm.db.select('BotAdmin',  where='userid = $userid', vars=dict(userid=ctx.message.author.id))) + len(dbm.db.select('StoryTellerChronicleRel', where='storyteller = $userid and chronicle=$chronicle' , vars=dict(userid=ctx.message.author.id, chronicle = chronicle)))
    if len(sessions):
        response = "C'è già una sessione in corso in questo canale"
    elif can_do:
        dbm.db.insert('GameSession', chronicle=chronicleid, channel=ctx.channel.id)
        chronicle = dbm.db.select('Chronicle', where='id=$chronicleid', vars=dict(chronicleid=chronicleid))[0]
        response = f"Sessione iniziata per la cronaca {chronicle['name']}"
        # todo lista dei pg?
    else:
        response = "Non hai il ruolo di Storyteller per la questa cronaca"
    await atSend(ctx, response)

@session.command(name = 'list', brief = 'Elenca le sessioni aperte', description = 'Elenca le sessioni aperte. richiede di essere admin o storyteller')
async def session_list(ctx):
    issuer = ctx.message.author.id
    st, _ = dbm.isStoryteller(issuer)
    ba, _ = dbm.isBotAdmin(issuer)
    if not (st or ba):
        raise BotException("no.")
    
    sessions = dbm.db.select('GameSession').list()
    channels = []
    for s in sessions:
        ch = await bot.fetch_channel(int(s['channel']))
        channels.append(ch)
    lines = []
    #pvt = 0
    for session, channel in zip(sessions, channels):
        if isinstance(channel, discord.abc.GuildChannel):
            lines.append(f"{channel.category}/{channel.name}: {session['chronicle']}")
        #elif isinstance(channel, discord.abc.PrivateChannel):
        #    pvt += 1
    if not len(lines):
        lines.append("Nessuna!")
    response = "Sessioni attive:\n" + ("\n".join(lines))
    await atSend(ctx, response)
    

@session.command(brief = 'Termina la sessione corrente', description = 'Termina la sessione corrente. Richiede di essere admin o storyteller della sessione in corso.')
async def end(ctx):
    response = ''
    issuer = str(ctx.message.author.id)
    sessions = dbm.db.select('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
    if len(sessions):
        ba, _ = dbm.isBotAdmin(issuer)
        st = dbm.db.query('select sc.chronicle from StoryTellerChronicleRel sc join GameSession gs on (sc.chronicle = gs.chronicle) where gs.channel=$channel and sc.storyteller = $st', vars=dict(channel=ctx.channel.id, st=ctx.message.author.id))
        can_do = ba or bool(len(st))
        if can_do:
            n = dbm.db.delete('GameSession', where='channel=$channel', vars=dict(channel=ctx.channel.id))
            if n:
                response = f'sessione terminata'
            else: # non dovrebbe mai accadere
                response = f'la cronaca non ha una sessione aperta in questo canale'
        else:
            response = "Non hai il ruolo di Storyteller per la questa cronaca"
    else:
        response = "Nessuna sessione attiva in questo canale!"
    await atSend(ctx, response)

damage_types = ["a", "l", "c"]

def defaultTraitFormatter(trait):
    return f"Oh no! devo usare il formatter di default!\n{trait['name']}: {trait['cur_value']}/{trait['max_value']}/{trait['pimp_max']}, text: {trait['text_value']}"

def prettyDotTrait(trait):
    pretty = f"{trait['name']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += ":red_circle:"*min(trait['cur_value'], trait['max_value'])
    if trait['cur_value']<trait['max_value']:
        pretty += ":orange_circle:"*(trait['max_value']-trait['cur_value'])
    if trait['cur_value']>trait['max_value']:
        pretty += ":green_circle:"*(trait['cur_value']-trait['max_value'])
    max_dots = max(trait['pimp_max'], 5)
    if trait['cur_value'] < max_dots:
        pretty += ":white_circle:"*(max_dots-max(trait['max_value'], trait['cur_value']))
    return pretty

healthToEmoji = {
    'c': '<:hl_bashing:815338465368604682>',
    'l': '<:hl_lethal:815338465176715325>',
    'a': '<:hl_aggravated:815338465365458994>',
    #
    ' ': '<:hl_free:815338465348026388>',
    'B': '<:hl_blocked:815338465260077077>'
    }


hurt_levels = [
    "Illeso",
    "Contuso",
    "Graffiato (-1)",
    "Leso (-1)",
    "Ferito (-2)",
    "Straziato (-2)",
    "Menomato (-5)",
    "Incapacitato"
]

def prettyHealth(trait, levels = 7):
    if trait['max_value'] <= 0:
        return 'Non hai ancora inizializzato la tua salute!'
    hs = trait['text_value']
    hs = hs + (" "*(trait['max_value']-len(hs)))
    columns = len(hs) // levels 
    extra = len(hs) % levels
    width = columns + (extra > 0)
    prettytext = 'Salute:'
    cursor = 0
    hurt_level = 0
    for i in range(levels):
        if hs[cursor] != " ":
            hurt_level = i+1
        if i < extra:
            prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+width])))
            cursor += width
        else:
            prettytext += '\n'+ " ".join(list(map(lambda x: healthToEmoji[x], hs[cursor:cursor+columns]+"B"*(extra > 0))))
            cursor += columns
    return hurt_levels[hurt_level] +"\n"+ prettytext

def prettyFDV(trait):
    return defaultTraitFormatter(trait)

blood_emojis = [":drop_of_blood:", ":droplet:"]
will_emojis = [":white_square_button:", ":white_large_square:"]

def prettyMaxPointTracker(trait, emojis, separator = ""):
    pretty = f"{trait['name']}: {trait['cur_value']}/{trait['max_value']}\n"
    pretty += separator.join([emojis[0]]*trait['cur_value'])
    pretty += separator
    pretty += separator.join([emojis[1]]*(trait['max_value']-trait['cur_value']))
    return pretty

def prettyPointAccumulator(trait):
    return f"{trait['name']}: {trait['cur_value']}"

def prettyTextTrait(trait):
    return f"{trait['name']}: {trait['text_value']}"

def prettyGeneration(trait):
    return f"{13 - trait['cur_value']}a generazione\n{prettyDotTrait(trait)}"

def trackerFormatter(trait):
    # formattatori specifici
    if trait['id'] == 'generazione':
        return prettyGeneration
    # formattatori generici
    if trait['textbased']:
        return prettyTextTrait
    elif trait['trackertype']==0:
        return prettyDotTrait
    elif trait['trackertype']==1:
        if trait['id'] == 'sangue':
            return lambda x: prettyMaxPointTracker(x, blood_emojis)
        else:
            return lambda x: prettyMaxPointTracker(x, will_emojis, " ")
    elif trait['trackertype']==2:
        return prettyHealth
    elif trait['trackertype']==3:
        return prettyPointAccumulator
    else:
        return defaultTraitFormatter

async def pc_interact(pc, can_edit, *args):
    response = ''
    if len(args) == 0:
        return f"Stai interpretando {pc['fullname']}"

    trait_id = args[0].lower()
    if len(args) == 1:
        if trait_id.count("+"):
            count = 0
            for tid in trait_id.split("+"):
                count += dbm.getTrait(pc['id'], tid)['cur_value']
            return f"{args[0]}: {count}"
        else:
            trait = dbm.getTrait(pc['id'], trait_id)
            prettyFormatter = trackerFormatter(trait)
            return prettyFormatter(trait)

    # qui siamo sicuri che c'è un'operazione (o spazzatura)
    if not can_edit:
        return f'A sessione spenta puoi solo consultare le tue statistiche'

    param = "".join(args[1:]) # squish
    operazione = param[0]
    if not operazione in ["+", "-", "="]:
        return "Stai usando il comando in modo improprio"
 
    trait = dbm.getTrait(pc['id'], trait_id)
    prettyFormatter = trackerFormatter(trait)
    if trait['pimp_max']==0 and trait['trackertype']==0:
        raise BotException(f"Non puoi modificare il valore corrente di {trait['name']}")
    if trait['trackertype'] != 2:
        n = param[1:]
        if not (n.isdigit() and n != "0"):
            return f'"{n}" non è un intero positivo'
        
        if operazione == "=":
            n = int(param[1:]) - trait['cur_value'] # tricks
        else:
            n = int(param)
        new_val = trait['cur_value'] + n
        max_val = max(trait['max_value'], trait['pimp_max']) 
        if new_val<0:
            raise BotException(f'Non hai abbastanza {trait_id}!')
        elif new_val > max_val and trait['trackertype'] != 3:
            raise BotException(f"Non puoi avere {new_val} {trait['name'].lower()}. Valore massimo: {max_val}")
        #
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), cur_value = trait['cur_value'] + n)
        if u == 1:
            trait = dbm.getTrait(pc['id'], trait_id)
            return prettyFormatter(trait)
        else:
            return f'Qualcosa è andato storto, righe aggiornate: {u}'

    # salute
    response = ''
    n = param[1:-1]
    if n == '':
        n = 1
    elif n.isdigit():
        n = int(n)
    elif operazione == "=":
        pass
    else:
        raise BotException(f'"{n}" non è un parametro valido!')
    dmgtype = param[-1].lower()
    new_health = trait['text_value']
    if not dmgtype in damage_types:
        raise BotException(f'"{dmgtype}" non è un tipo di danno valido')
    if operazione == "+":
        rip = False
        for i in range(n): # applico i danni uno alla volta perchè sono un nabbo
            if dmgtype == "c" and new_health.endswith("c"): # non rischio di cambiare la lunghezza
                new_health = new_health[:-1]+"l"
            else:
                if len(new_health) < trait['max_value']: # non ho già raggiunto il massimo
                    if dmgtype == "c":                                        
                        new_health += "c"
                    elif dmgtype == "a":
                        new_health = "a"+new_health
                    else:
                        la = new_health.rfind("a")+1
                        new_health = new_health[:la] + "l" + new_health[la:]
                else:  # oh no
                    convert = False
                    if dmgtype == "c":
                        if trait['cur_value'] > 0: # trick per salvarsi mezzo aggravato
                            trait['cur_value'] = 0
                        else:
                            convert = True
                            trait['cur_value'] = 1
                    elif dmgtype == 'l':
                        convert = True
                    else:
                        rip = True

                    if convert:
                        fl = new_health.find('l')
                        if fl >= 0:
                            new_health = new_health[:fl] + 'a' + new_health[fl+1:]
                        else:
                            rip = True
                    if rip:
                        break
        if new_health.count("a") == trait['max_value']:
            rip = True
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        if u != 1 and not rip:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)
        if rip:
            response += "\n\n RIP"
    elif operazione == "-":
        if dmgtype == "a":
            if new_health.count(dmgtype) < n:
                raise BotException("Non hai tutti quei danni aggravati")
            else:
                new_health = new_health[n:]
        elif dmgtype == "l":
            if new_health.count(dmgtype) < n:
                raise BotException("Non hai tutti quei danni letali")
            else:
                fl = new_health.find(dmgtype)
                new_health = new_health[:fl]+new_health[fl+n:]
        else: # dio can
            for i in range(n):
                if trait['cur_value'] == 0:
                    trait['cur_value'] = 1 # togli il mezzo aggravato
                else:
                    if new_health[-1] == 'c':
                        new_health = new_health[:-1]
                    elif new_health[-1] == 'l':
                        new_health = new_health[:-1]+'c'
                    else:
                        raise BotException("Non hai tutti quei danni contundenti")
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = trait['cur_value'])
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)
    else: # =
        full = param[1:]
        counts = list(map(lambda x: full.count(x), damage_types))
        if sum(counts) !=  len(full):
            raise BotException(f'"{full}" non è un parametro valido!')
        new_health = "".join(list(map(lambda x: x[0]*x[1], zip(damage_types, counts)))) # siamo generosi e riordiniamo l'input
        
        u = dbm.db.update('CharacterTrait', where='trait = $trait and playerchar = $pc', vars=dict(trait=trait_id, pc=pc['id']), text_value = new_health, cur_value = 1)
        if u != 1:
            raise BotException(f'Qualcosa è andato storto, righe aggiornate: {u}')
        trait = dbm.getTrait(pc['id'], trait_id)
        response = prettyFormatter(trait)

    return response

me_description = """.me <NomeTratto> [<Operazione>]

<Nometratto>: Nome del tratto (o somma di tratti)
<Operazione>: +/-/= n (se assente viene invece visualizzato il valore corrente)

-Richiede sessione attiva
-Basato sul valore corrente del Tratto'
"""

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = me_description)
async def me(ctx, *args):
    pc = dbm.getActiveChar(ctx)
    response = await pc_interact(pc, True, *args)
    await atSend(ctx, response)

@bot.command(brief='Permette ai giocatori di interagire col proprio personaggio durante le sessioni' , help = "come '.me', ma si può usare in 2 modi:\n\n1) .<nomepg> [argomenti di .me]\n2) .pgmanage <nomepg> [argomenti di .me]")
async def pgmanage(ctx, *args):
    if len(args)==0:
        raise BotException('Specifica un pg!')

    charid = args[0].lower()
    isChar, character = dbm.isValidCharacter(charid)
    if not isChar:
        raise BotException(f"Il personaggio {charid} non esiste!")

    # permission checks
    issuer = str(ctx.message.author.id)
    playerid = character['player']
    co = playerid == issuer
    
    st, _ = dbm.isStoryteller(issuer) # della cronaca?
    ba, _ = dbm.isBotAdmin(issuer)    
    ce = st or ba # can edit
    if co and (not ce):
        #1: unlinked
        ce = ce or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
        #2 active session
        ce = ce or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
    if not (st or ba or co):
        return # non vogliamo che .rossellini faccia cose
        #raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")
    
    response = await pc_interact(character, ce, *args[1:])
    await atSend(ctx, response)

async def pgmod_create(ctx, args):
    helptext = "Argomenti: nome breve (senza spazi), menzione al proprietario, nome completo del personaggio"
    if len(args) < 3:
        return helptext
    else:
        chid = args[0].lower()
        owner = args[1]
        if not (owner.startswith("<@!") and owner.endswith(">")):
            raise BotException("Menziona il proprietario del personaggio con @nome")
        owner = owner[3:-1]
        fullname = " ".join(list(args[2:]))

        # permission checks
        issuer = str(ctx.message.author.id)
        if issuer != owner: # chiunque può crearsi un pg, ma per crearlo a qualcun'altro serve essere ST/admin
            st, _ = dbm.isStoryteller(issuer)
            ba, _ = dbm.isBotAdmin(issuer)
            if not (st or ba):
                raise BotException("Per creare un pg ad un altra persona è necessario essere Admin o Storyteller")
        
        t = dbm.db.transaction()
        try:
            if not len(dbm.db.select('People', where='userid=$userid', vars=dict(userid=owner))):
                user = await bot.fetch_user(owner)
                dbm.db.insert('People', userid=owner, name=user.name)
            dbm.db.insert('PlayerCharacter', id=chid, owner=owner, player=owner, fullname=fullname)
            dbm.db.query("""
insert into CharacterTrait
    select t.id as trait, 
    pc.id as playerchar, 
    0 as cur_value, 
    0 as max_value, 
    "" as text_value,
    case 
    WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
    else 0
    end
    as pimp_max
    from Trait t, PlayerCharacter pc
    where t.standard = true
    and pc.id = $pcid;
""", vars = dict(pcid=chid))
        except:
            t.rollback()
            raise
        else:
            t.commit()
            return f'Il personaggio {fullname} è stato inserito!'

async def pgmod_chronicleAdd(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve della cronaca"
    if len(args) != 2:
        return helptext
    else:
        charid = args[0].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")
        chronid = args[1].lower()
        chronicles = dbm.db.select('Chronicle', where='id=$id', vars=dict(id=chronid))
        if not len(chronicles):
            raise BotException(f"La cronaca {chronid} non esiste!")
        chronicle = chronicles[0]

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = dbm.isChronicleStoryteller(issuer, chronicle['id'])
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per associare un pg ad una cronaca necessario essere Admin o Storyteller di quella cronaca")
        
        # todo check link esistente
        dbm.db.insert("ChronicleCharacterRel", chronicle=chronid, playerchar=charid)
        return f"{character['fullname']} ora gioca a {chronicle['name']}"


async def pgmod_traitAdd(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        traitid = args[1].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        ownerid = character['owner']
        
        st, _ = dbm.isStoryteller(issuer) # della cronaca?
        ba, _ = dbm.isBotAdmin(issuer)
        co = False
        if ownerid == issuer and not (st or ba):
            #1: unlinked
            co = co or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
            #2 active session
            co = co or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
        if not (st or ba or co):
            raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")

        istrait, trait = dbm.isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if len(ptraits):
            raise BotException(f"{character['fullname']} ha già il tratto {trait['name']} ")
        
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = 0, max_value = 0, text_value = textval, pimp_max = 0)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            pimp = 6 if trait['traittype'] in ['fisico', 'sociale', 'mentale'] else 0
            dbm.db.insert("CharacterTrait", trait=traitid, playerchar=charid, cur_value = args[2], max_value = args[2], text_value = "", pimp_max = pimp)
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

async def pgmod_traitMod(ctx, args):
    helptext = "Argomenti: nome breve del pg, nome breve del tratto, nuovo valore"
    if len(args) < 3:
        return helptext
    else:
        charid = args[0].lower()
        isChar, character = dbm.isValidCharacter(charid)
        if not isChar:
            raise BotException(f"Il personaggio {charid} non esiste!")

        # permission checks
        issuer = str(ctx.message.author.id)
        ownerid = character['owner']
        
        st, _ = dbm.isStoryteller(issuer) # della cronaca?
        ba, _ = dbm.isBotAdmin(issuer)
        co = False
        if ownerid == issuer and not (st or ba):
            #1: unlinked
            co = co or not len(dbm.db.select('ChronicleCharacterRel', where='playerchar=$id', vars=dict(id=charid)))
            #2 active session
            co = co or len(dbm.db.query("""
SELECT cc.playerchar
FROM GameSession gs
join ChronicleCharacterRel cc on (gs.chronicle = cc.chronicle)
where gs.channel = $channel and cc.playerchar = $charid
""", vars=dict(channel=ctx.channel.id, charid=charid)))
        if not (st or ba or co):
            raise BotException("Per modificare un personaggio è necessario esserne proprietari e avere una sessione aperta, oppure essere Admin o Storyteller")

        traitid = args[1].lower()
        istrait, trait = dbm.isValidTrait(traitid)
        if not istrait:
            raise BotException(f"Il tratto {traitid} non esiste!")
        
        ptraits = dbm.db.select("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']))
        if not len(ptraits):
            raise BotException(f"{character['fullname']} non ha il tratto {trait['name']} ")
        ttype = dbm.db.select('TraitType', where='id=$id', vars=dict(id=trait['traittype']))[0]
        if ttype['textbased']:
            textval = " ".join(args[2:])
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), text_value = textval)
            return f"{character['fullname']} ora ha {trait['name']} {textval}"
        else:
            dbm.db.update("CharacterTrait", where='trait = $trait and playerchar = $pc', vars=dict(trait=trait['id'], pc=character['id']), cur_value = args[2], max_value = args[2])
            return f"{character['fullname']} ora ha {trait['name']} {args[2]}"

pgmod_subcommands = {
    "create": [pgmod_create, "Crea un personaggio"],
    "link": [pgmod_chronicleAdd, "Aggiunge un personaggio ad una cronaca"],
    "addt": [pgmod_traitAdd, "Aggiunge tratto ad un personaggio"],
    "modt": [pgmod_traitMod, "Modifica un tratto di un personaggio"]
    }

async def gmadm_listChronicles(ctx, args):
    # voglio anche gli ST collegati
    return "non implementato"


async def gmadm_newChronicle(ctx, args):
    helptext = "Argomenti: <id> <nome completo> \n\nId non ammette spazi."
    if len(args) < 2:
        return helptext
    else:
        shortname = args[0].lower()
        fullname = " ".join(list(args[1:])) # squish

        # permission checks
        issuer = str(ctx.message.author.id)
        st, _ = dbm.isStoryteller(issuer) # della cronaca?
        # no botadmin perchè non è necessariente anche uno storyteller e dovrei faren check in più e non ho voglia
        if not (st):
            raise BotException("Per creare una cronaca è necessario essere Storyteller")

        # todo existence
        t = dbm.db.transaction()
        try:
            dbm.db.insert("Chronicle", id=shortname, name = fullname)
            dbm.db.insert("StoryTellerChronicleRel", storyteller=issuer, chronicle=shortname)
        except:
            t.rollback()
            raise
        else:
            t.commit()
            issuer_user = await bot.fetch_user(issuer)
            return f"Cronaca {fullname} inserita ed associata a {issuer_user}"

query_addTraitToPCs = """
    insert into CharacterTrait
        select t.id as trait, 
        pc.id as playerchar, 
        0 as cur_value, 
        0 as max_value, 
        "" as text_value,
        case 
        WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
        else 0
        end
        as pimp_max
        from Trait t, PlayerCharacter pc
        where t.standard = true
        and t.id = $traitid;
    """

query_addTraitToPCs_safe = """
    insert into CharacterTrait
        select t.id as trait, 
        pc.id as playerchar, 
        0 as cur_value, 
        0 as max_value, 
        "" as text_value,
        case 
        WHEN t.trackertype = 0 and (t.traittype ='fisico' or t.traittype = 'sociale' or t.traittype='mentale') THEN 6
        else 0
        end
        as pimp_max
        from Trait t, PlayerCharacter pc
        where t.standard = true
        and t.id = $traitid
        and not exists (
            select trait
            from CharacterTrait ct
            where ct.trait = $traitid and ct.playerchar = pc.id
        );
    """

async def gmadm_newTrait(ctx, args):
    if len(args) < 5:
        helptext = "Argomenti: <id> <tipo> <tracker> <standard> <nome completo>\n\n"
        helptext += "Gli id non ammettono spazi.\n\n"
        helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
        ttypes = dbm.db.select('TraitType', what = "id, name")
        ttypesl = ttypes.list()
        helptext += "Tipi di tratto: \n"
        helptext += "\n".join(list(map(lambda x : f"\t**{x['id']}**: {x['name']}", ttypesl)))
        #helptext += "\n".join(list(map(lambda x : ", ".join(list(map(lambda y: y+": "+str(x[y]), x.keys()))), ttypesl)))
        helptext += """\n\nTipi di tracker:
    **0**: Nessun tracker (Elementi normali di scheda)
    **1**: Punti con massimo (Volontà, Sangue...)
    **2**: Danni (salute...)
    **3**: Punti senza massimo (esperienza...)
"""
        return helptext
    else:
        # permission checks
        issuer = ctx.message.author.id
        st, _ = dbm.isStoryteller(issuer)
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per creare un tratto è necessario essere Admin o Storyteller")
        
        traitid = args[0].lower()
        istrait, trait = dbm.isValidTrait(traitid)
        if istrait:
            raise BotException(f"Il tratto {traitid} esiste già!")

        if not validateTraitName(traitid):
            raise BotException(f"'{traitid}' non è un id valido!")

        traittypeid = args[1].lower()
        istraittype, traittype = dbm.isValidTraitType(traittypeid)
        if not istraittype:
            raise BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[2].isdigit():
            raise BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[2])
        if not tracktype in [0, 1, 2, 3]: # todo dehardcode
            raise BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[3].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise BotException(f"{stdarg} non è un'opzione valida")
        
        traitname = " ".join(args[4:])
        dbm.db.insert("Trait", id = traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)

        response = f'Il tratto {traitname} è stato inserito'
        # todo: se std, aggiungilo a tutti i pg
        if std:
            t = dbm.db.transaction()
            try:
                dbm.db.query(query_addTraitToPCs, vars = dict(traitid=traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'

        return response

async def gmadm_updateTrait(ctx, args):
    if len(args) < 6:
        helptext = "Argomenti: <vecchio_id> <nuovo_id> <tipo> <tracker> <standard> <nome completo>\n\n"
        helptext += "Gli id non ammettono spazi.\n\n"
        helptext += "<standard> ammette [y, s, 1] per Sì e [n, 0] per No\n\n"
        ttypes = dbm.db.select('TraitType', what = "id, name")
        ttypesl = ttypes.list()
        helptext += "Tipi di tratto: \n"
        helptext += "\n".join(list(map(lambda x : f"\t**{x['id']}**: {x['name']}", ttypesl)))
        #helptext += "\n".join(list(map(lambda x : ", ".join(list(map(lambda y: y+": "+str(x[y]), x.keys()))), ttypesl)))
        helptext += """\n\nTipi di tracker:
    **0**: Nessun tracker (Elementi normali di scheda)
    **1**: Punti con massimo (Volontà, Sangue...)
    **2**: Danni (salute...)
    **3**: Punti senza massimo (esperienza...)
"""
        return helptext
    else:
        # permission checks
        issuer = ctx.message.author.id
        st, _ = dbm.isStoryteller(issuer)
        ba, _ = dbm.isBotAdmin(issuer)
        if not (st or ba):
            raise BotException("Per modificare un tratto è necessario essere Admin o Storyteller")

        old_traitid = args[0].lower()
        istrait, old_trait = dbm.isValidTrait(old_traitid)
        if not istrait:
            raise BotException(f"Il tratto {old_traitid} non esiste!")
        
        new_traitid = args[1].lower()
        istrait, new_trait = dbm.isValidTrait(new_traitid)
        if istrait and (old_traitid!=new_traitid):
            raise BotException(f"Il tratto {new_traitid} esiste già!")

        if not validateTraitName(new_traitid):
            raise BotException(f"'{new_traitid}' non è un id valido!")

        traittypeid = args[2].lower()
        istraittype, traittype = dbm.isValidTraitType(traittypeid)
        if not istraittype:
            raise BotException(f"Il tipo di tratto {traittypeid} non esiste!")

        if not args[3].isdigit():
            raise BotException(f"{args[2]} non è un intero >= 0!")
        tracktype = int(args[3])
        if not tracktype in [0, 1, 2, 3]: # todo dehardcode
            raise BotException(f"{tracktype} non è tracker valido!")

        stdarg = args[4].lower()
        std = stdarg in ['y', 's', '1']
        if not std and not stdarg in ['n', '0']:
            raise BotException(f"{stdarg} non è un'opzione valida")

        traitname = " ".join(args[5:])
        dbm.db.update("Trait", where= 'id = $oldid' , vars=dict(oldid = old_traitid), id = new_traitid, name = traitname, traittype = traittypeid, trackertype = tracktype, standard = std, ordering = 1.0)

        response = f'Il tratto {traitname} è stato inserito'
        # todo: se std, aggiungilo a tutti i pg
        if std and not old_trait['standard']:
            t = dbm.db.transaction()
            try:
                dbm.db.query(query_addTraitToPCs_safe, vars = dict(traitid=new_traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl nuovo talento standard {traitname} è stato assegnato ai personaggi!'
        elif not std and old_trait['standard']:
            t = dbm.db.transaction()
            try:
                dbm.db.query("""
    delete from CharacterTrait
    where trait = $traitid and max_value = 0 and cur_value = 0 and text_value = '';
    """, vars = dict(traitid=new_traitid))
            except:
                t.rollback()
                raise
            else:
                t.commit()
                response +=  f'\nIl talento {traitname} è stato rimosso dai personaggi che non avevano pallini'

        return response

async def gmadm_deleteTrait(ctx, args):
    return "non implementato"

async def gmadm_searchTrait(ctx, args):
    if len(args) == 0:
        helptext = "Argomenti: parte del nome breve o nome completo del tratto"
        return helptext
    else:
        searchstring = "%" + (" ".join(args)) + "%"
        lower_version = searchstring.lower()
        traits = dbm.db.select("Trait", where="id like $search_lower or name like $search_string", vars=dict(search_lower=lower_version, search_string = searchstring))
        if not len(traits):
            return 'Nessun match!'
        response = 'Tratti trovati:\n'
        for trait in traits:
            response += f"\n{trait['id']}: {trait['name']}"
        return response

gameAdmin_subcommands = {
    "listChronicles": [gmadm_listChronicles, "Elenca le cronache"],
    "newChronicle": [gmadm_newChronicle, "Crea una nuova cronaca associata allo ST che invoca il comando"],
    "newTrait": [gmadm_newTrait, "Crea nuovo tratto"],
    "updt": [gmadm_updateTrait, "Modifica un tratto"],
    "delet": [gmadm_deleteTrait, "Cancella un tratto"],
    "searcht": [gmadm_searchTrait, "Cerca un tratto"]
    # todo: nomina storyteller, associa storyteller a cronaca
    # todo: dissociazioni varie
    }

def generateNestedCmd(cmd_name, cmd_brief, cmd_dict):
    longdescription = "\n".join(list(map(lambda x: botcmd_prefixes[0]+cmd_name+" "+x+" [arg1, ...]: "+cmd_dict[x][1], cmd_dict.keys())))  + "\n\nInvoca un sottocomando senza argomenti per avere ulteriori informazioni sugli argomenti"

    @bot.command(name=cmd_name, brief=cmd_brief, description = longdescription)
    async def generatedCommand(ctx, *args):
        response = 'Azioni disponibili (invoca una azione senza argomenti per conoscere il funzionamento):\n'
        if len(args) == 0:
            response += longdescription
        else:
            subcmd = args[0]
            if subcmd in cmd_dict:
                response = await cmd_dict[subcmd][0](ctx, args[1:])
            else:
                response = f'"{subcmd}" non è un sottocomando valido!\n'+longdescription
            
        await atSend(ctx, response)
    #return generatedCommand

gmadm = generateNestedCmd('gmadm', "Gestione dell'ambiente di gioco", gameAdmin_subcommands)
pgmod = generateNestedCmd('pgmod', "Gestione prsonaggi", pgmod_subcommands)


bot.run(TOKEN)
