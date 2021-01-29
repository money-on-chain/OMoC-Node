### Usage 

* This has to be done from the root project

* Build: 
    * docker build -t omoc-node-img -f Docker/Dockerfile .

* Run: 
    * docker run -it --restart always --network=host --name omoc-node -v /home/ubuntu/OMoC-Node/monitor:/monitor omoc-node-img
    * Set oracle configuration
    * Exit the container (Ctrl+c)
    * Register your oracle... 

* Logs: 
    * docker exec -it omoc-node pm2 log oracle
    * check container status: 
        * docker exec -it omoc-node /bin/bash 


