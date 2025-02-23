# present-ai-elevenlabs

Frontend:
https://github.com/liezl200/frontend-present-ai


## Deploy firebase storage rules
`cd functions`
`firebase deploy --only storage`


## Deploy firebase functions
`cd functions && python3.10 -m venv venv && source venv/bin/activate && python3.10 -m pip install -r requirements.txt`
`firebase deploy --only functions`


Build logs: https://gist.github.com/liezl200/aa72c3196014a13534bed2facd1c3cae