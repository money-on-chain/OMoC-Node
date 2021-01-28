### Usage 

* This has to be done from the root project

* Build: 
    * docker build -t omoc-node-img -f Docker/Dockerfile .

* Run: 
    * docker run -it --restart always --network=host --name omoc-node -v /home/ubuntu/OMoC-Node/monitor:/monitor omoc-node-img
