"""
scp.py: Written by Gnosis for Grapewhistle 2009, inherited by Glacon in 2011, even later inherited by Gordon in 2015 and expanded by GreenWolf.
v1.1 of basic in-channel data acquisition plugins for IRC channels of the SCP Foundation.
"""
from util import hook, http
import threading
from time import sleep
import sqlite3
import re
import os

class SCPThread(threading.Thread):
    def __init__(self, dbpath):
        threading.Thread.__init__(self, name="SCP")
        self.dbpath = dbpath
    def run(self):
        db = sqlite3.connect(self.dbpath)
        db.execute("create table if not exists scps(number varchar primary key, title varchar)")
        db.execute("create table if not exists tales(page varchar primary key, title varchar)")
        db.execute("create table if not exists gois(page varchar primary key, title varchar)")
        db.text_factory = str

        basescpurl = "http://www.scp-wiki.net"
        scpseriespages = ["/scp-series", "/scp-series-2", "/scp-series-3"]
        scpextrapages = ["/scp-ex", "/joke-scps", "/archived-scps"]
        scptalepages = ["/system%3Apage-tags/tag/tale"]
        scpgoipages = ["/system%3Apage-tags/tag/goi-format"]

        scpinterval = 60 * 15
        scpcounter = 0
        talecounter = 0
        goicounter = 0

	# Infinite query loop
        while True:
            try:
                c = db.cursor()
                c.execute("delete from scps")
                scpcounter = 0
                talecounter = 0
        	goicounter = 0

                # Regex fuckery to bypass wikidot api
                scp_re = re.compile(r'<a href="/scp-(.*)">SCP-\1</a> - (.*?)</li>', re.I)
                scpx_re = re.compile(r'<a href="/scp-(.*)">SCP-\1</a> - (.*?)</li>', re.I)
		# Grab main list entries from each page
                for scpseriespage in scpseriespages+scpextrapages:
                    page = http.to_utf8(http.get(basescpurl + scpseriespage))
                    scp_list = scp_re.findall(page)
                    #print scp_list

                    # Add entries to database
                    for (k, v) in scp_list:
                        #print k, v
                        c.execute(u"replace into scps(number, title) values (upper(?), ?)", (k, v))
                        scpcounter = scpcounter + 1
                    db.commit()
                    #print "scp.py - Updated SCP database from listing on", scpseriespage

                #print "scp.py: Grabbing tales from", (basescpurl+scptalepages[0])
                talepage = http.get_html(basescpurl + scptalepages[0])
                # This is so ugly, why two xpaths?
                talelinklist = talepage.xpath("//*[@class='title']/a/@href")
                talelist = talepage.xpath("//*[@class='title']/a/text()")
                # Grab list of tales from the 'tale' tag page
                for i in range(len(talelist)):
                    talelink = talelinklist[i]
                    taletitle = talelist[i]
                    #print talelink#, unicode(taletitle, "utf-8")
                    c.execute(u"replace into tales (page, title) values(?,?)",
                        (talelink, taletitle)
                    )
                    talecounter = talecounter + 1
                db.commit()

                # Shamelessly copy/pasted from tale code - GW
                goipage = http.get_html(basescpurl + scpgoipages[0])
                # This is so ugly, why two xpaths?
		# I don't know, gnosis. - GW
                goilinklist = goipage.xpath("//*[@class='title']/a/@href")
                goilist = goipage.xpath("//*[@class='title']/a/text()")
                # Grab list of goi formats from the 'goi-format' tag page
                for i in range(len(goilist)):
                    goilink = goilinklist[i]
                    goititle = goilist[i]
                    c.execute(u"replace into gois (page, title) values(?,?)",
                        (goilink, goititle)
                    )
                    goicounter = goicounter + 1
                db.commit()

                c.close()
                print "scp.py - SCP database update complete, %d total entries." % scpcounter
                print "scp.py - SCP tale database update complete, %d total entries." % talecounter
                print "scp.py - GOI format database update complete, %d total entries." % goicounter
            except Exception, e:
                print "ERROR ERROR ERROR, ", e
	    # Query every -5- -30- 15 minutes
	    sleep(scpinterval)

# Looks up SCP from cached database. Returns [ACCESS DENIED] if not in database.
def scp_lookup(number,  title=None):
    url = "http://www.scp-wiki.net/scp-%s" % number
    db = sqlite3.connect(scp_path)
    if not title:
        try: title = db.execute("select title from scps where number = ?", (number.upper(),)).fetchone()[0]
        except TypeError: title = "[ACCESS DENIED]"
    return "%s - %s" % (url, title)

def scp_init(dbpath):
    if all([thread.name != "SCP" for thread in threading.enumerate()]):
        scp_thread = SCPThread(scp_path)
        scp_thread.start()
        sleep(1)

@hook.regex(r'^SCP-((?:\w|-|J)+)$', re.I)
def scp(inp, bot=None, input=None):
    try: inp = inp.groups()[0]
    except AttributeError: pass

    dbpath = os.path.join(bot.persist_dir, "%s.%s.db" % (input.conn.nick, input.conn.server))

    return scp_lookup(inp)

# Query multiple SCPs at once with a comma-delimited list of !scp-xxxx tokens
@hook.event('PRIVMSG')
def multiscp(inp, bot=None, input=None):
    scps = re.compile('!SCP-((?:\w|-|J)+)', re.I).findall(inp[1])
    for scp in scps:
        input.reply(scp_lookup(scp))

# Fetches the rating from the HTML page of the target SCP.
@hook.command
def rating(inp):
    print ("Calling http.get() on http://www.scp-wiki.net/%s" % inp)
    page = http.get("http://www.scp-wiki.net/%s" % inp)
    rating = http.get_html("http://www.scp-wiki.net/%s" % inp).xpath("//*[@class='number prw54353']/text()")[0]
    return rating

# Searches cached database for keyword in SCP name/title.
@hook.command
def search(inp):
    inp = "%" + inp + "%"
    db = sqlite3.connect(scp_path)
    scps =  db.execute("SELECT NUMBER, TITLE FROM SCPS WHERE TITLE LIKE ?", (inp,)).fetchall()
    if len(scps) == 1:
        (number, title) = scps[0]
        return "SCP-%s - %s - http://www.scp-wiki.net/scp-%s" % (number, title, number)
    printed = scps[:5]
    output = ""
    for (number, title) in printed:
        output += "SCP-%s (%s), " % (number, title)
    if len(scps) > 5: output += " plus %d more" % (len(scps) - 5)
    else: output = output[:-2]
    if not output: return "No SCPs found."
    return output

# Look up function for tales. Wish there was a good way that didn't involve
# so much code duplication.
@hook.command
def tale(inp):
    #print "tale command called"
    inp = "%" + inp + "%"
    db = sqlite3.connect(scp_path)
    tales = db.execute("SELECT PAGE, TITLE FROM TALES WHERE TITLE LIKE ?", (inp,)).fetchall()
    if len(tales) == 1:
        (taleurl, title) = tales[0]
        return u"%s - http://www.scp-wiki.net%s" % (title, taleurl)
    printed = tales[:5]
    #output = "http://www.scp-wiki.net" + printed[0][0] + " "
    output = ""
    for (taleurl, title) in printed:
        output += title + ", "
    if len(tales) > 5:
        output += " plus %d more" % (len(tales) - 5)
    else:
        output = output[:-2]
    if not output:
        return u"No tales found."
    return output

# More code duplication for gois - GW
@hook.command
def goi(inp):
    inp = "%" + inp + "%"
    db = sqlite3.connect(scp_path)
    gois = db.execute("SELECT PAGE, TITLE FROM GOIS WHERE TITLE LIKE ?", (inp,)).fetchall()
    if len(gois) == 1:
        (goiurl, title) = gois[0]
        return u"%s - http://www.scp-wiki.net%s" % (title, goiurl)
    printed = gois[:5]
    #output = "http://www.scp-wiki.net" + printed[0][0] + " "
    output = ""
    for (goiurl, title) in printed:
        output += title + ", "
    if len(gois) > 5:
        output += " plus %d more" % (len(gois) - 5)
    else:
        output = output[:-2]
    if not output:
        return u"No GOI formats found."
    return output


# Returns a random SCP in cached database.
@hook.command
def random(inp):
    db = sqlite3.connect(scp_path)
    (number, title)  = db.execute("SELECT NUMBER, TITLE FROM SCPS ORDER BY RANDOM() LIMIT 1").fetchone()
    return "SCP-%s - %s - http://www.scp-wiki.net/scp-%s" % (number, title, number)

# Just returns the tag page for now.
# TODO Make it return a list of tagged pages. - GW
@hook.command
def tag(inp):
    return "http://www.scp-wiki.net/system:page-tags/tag/" + inp

mydir = dir()
scp_path = os.path.join(os.path.abspath('persist'), "scp.db")
scp_init(scp_path)
