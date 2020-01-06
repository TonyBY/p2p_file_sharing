# P2P File Sharing Project

## Requirements
macOS 10.15.1
python 3.6
pip3==19.1

os
sys
time
copy
random
socket
pickle
threading
subprocess
socketserver

## step 1: Start file owner
cd fileowner
python fileowner_dev.py
input port number: 8000

## step 2: Start peer1
open a new cmd window/tab
cd peer1
python peer_dev1.py
input port number of upload neighbor: 8050
input port number of download neighbor: 8010
(connect and log into the file owner: )
connect localhost 8000
login peer1 111
get test.pdf

## step 3-6: Start peer2-peer6 one by one

## step 7: Start p2p file sharing
press enter in each peer's cmd window

## exit precess by pressing "ctrl + c"
