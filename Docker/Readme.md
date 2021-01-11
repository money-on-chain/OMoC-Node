### Usage 

* This has to be done from the root project

* Build: 
    * docker build -t omoc-node-img -f Docker/Dockerfile . 

* Run: 
    * docker run -it --name omoc-node -p 5556:5556 omoc-node-img
    * (Interatctive with the container): docker run -it --name omoc-node -p 5556:5556 omoc-node-img /bin/bash

