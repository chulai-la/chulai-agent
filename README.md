Chulai Agent
============
Runs on every chulai hosts


## how to deploy
cretae configurations, check permissions
```
./manager.py bootstrap
```

start agent
```
supervisorctl update
```

check if the agent status
```
./manager.py check
```
