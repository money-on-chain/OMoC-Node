### Usage 

* This has to be done from the root project

* Build: 
    * docker build -t omoc-node-img -f Docker/Dockerfile .

* Run: 
    * Set oracle configuration: 
        python3 scripts/setAddress.py [-e env file]

* Logs: 
    * check container status: 
        * docker exec -it omoc-node /bin/bash 


* docker run -it --restart always --name omoc-node --publish 5004:5004 --env-file=./Docker/.env_file omoc-node-img /bin/bash
* docker run --restart always --name omoc-node --publish 5004:5004 --env-file=./Docker/.env_file omoc-node-img 
