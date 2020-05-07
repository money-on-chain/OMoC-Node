from getpass import getpass
from pathlib import Path
from shutil import copyfile
import re

envMonitor = "monitor/backend/.env"
envServer = "servers/.env"

def comment(filePath, search):
	file = Path(filePath)
	content = re.sub(
			r'.*' + re.escape(search) + r'.*',
			"# " + search ,
			file.read_text())
	file.open('w').write(content)
def uncomment(filePath, search):
	file = Path(filePath)
	content = re.sub(
			re.escape("#") + r'.*' + re.escape(search) + r'.*',
			search ,
			file.read_text())
	file.open('w').write(content)
def addTo(filePath, search, replace):
	file = Path(filePath)
	content = re.sub(re.escape(search) + r'.*',search + replace,file.read_text())
	file.open('w').write(content)

def main():

	copyfile (envMonitor[:-4] + "Sample.env", envMonitor)
	copyfile (envServer[:-4] + "dotenv_example", envServer)


	# Address  and privateKey
	address = input("address:") 
	privKey = getpass("PrivateKey:") 

	answ = input("use the same addres for scheduler? (default: yes)").lower()
	if (answ in ["no","n"]):
		schedulerAddress = input("address:")
		schedulerPrivKey = getpass("PrivateKey:")
	else:
		schedulerAddress = address
		schedulerPrivKey = privKey

	addTo(envServer,"ORACLE_ADDR=",'"' + address + '"')
	addTo(envServer,"ORACLE_PRIVATE_KEY=",'"' + privKey + '"' )
	addTo(envServer,"SCHEDULER_SIGNING_ADDR = ",'"' + schedulerAddress  + '"')
	addTo(envServer,"SCHEDULER_SIGNING_KEY = ", '"' + schedulerPrivKey + '"')

	addTo(envMonitor,"ORACLE_SERVER_ADDRESS=",address)



	#EMAIL INFO
	answ = input("Do you want to configurate your mail (default: no)").lower()
	if answ in ["yes","y"]:
		addTo(envMonitor,"SMTP_HOST=", input("SMTP_HOST:"))
		addTo(envMonitor,"SMTP_PORT=", input("SMTP_PORT:"))
		addTo(envMonitor,"SMTP_From=", input("SMTP_From:"))
		answ = input("SMTP_SSL_TLS (default: yes)").lower()
		if answ in ["no","n"]:
			addTo(envMonitor,"SMTP_SSL_TLS=", "no")
		else:
			addTo(envMonitor,"SMTP_SSL_TLS=", "yes")
		addTo(envMonitor,"SMTP_USER=", input("SMTP_USER:"))
		addTo(envMonitor,"SMTP_PWD=", getpass("SMTP_PWD:"))
		addTo(envMonitor,"ALERT_EMAILS=", input("ALERT_EMAILS:"))
		addTo(envMonitor,"EMAIL_REPEAT_INTERVAL=", input("Email repeat interval in sec:"))



	#add and remove comments

	comment(envServer,'NETWORK_ID=12341234')
	comment(envServer,'NODE_URL = "http://localhost:8545"')
	
	uncomment(envServer,'NODE_URL = "https://public-node.testnet.rsk.co:443"')
	uncomment(envServer,'NETWORK_ID=31')
	uncomment(envServer,'CHAIN_ID=31')


	print("Perfecto, todo configurado ")


if __name__ =="__main__":
	#main()
	comment(envServer,'NETWORK_ID=12341234')
	comment(envServer,'NODE_URL = "http://localhost:8545"')
