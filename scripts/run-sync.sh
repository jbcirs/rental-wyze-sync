export HOSPITABLE_EMAIL=""
export HOSPITABLE_PASSWORD=""
export HOSPITABLE_TOKEN=""
export WYZE_EMAIL=""
export WYZE_PASSWORD=""
export WYZE_KEY_ID=""
export WYZE_API_KEY=""
export SLACK_TOKEN=""
export SLACK_CHANNEL="#notifications"
export CHECK_IN_OFFSET_HOURS=-1
export CHECK_OUT_OFFSET_HOURS=1
export NON_PROD=True
export TEST_PROPERTY_NAME=""
export LOCAL_DEVELOPMENT=True
export WYZE_API_DELAY_SECONDS=5
export VAULT_URL=""
export STORAGE_ACCOUNT_NAME=""
export STORAGE_CONNECTION_STRING=""
export TIMEZONE="America/Chicago"
export ALWAYS_SEND_SLACK_SUMMARY=True
export SLACK_SIGNING_SECRET=""
export SMARTTHINGS_TOKEN=""




cd ..
cd src/

#pip3 install -r requirements.txt --upgrade --force-reinstall

python3 ./sync.py
cd brands/smartthings/
#python3 ./smartthings.py