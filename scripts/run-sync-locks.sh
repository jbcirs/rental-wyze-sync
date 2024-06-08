export HOSPITABLE_EMAIL=""
export HOSPITABLE_PASSWORD=""
export WYZE_EMAIL=""
export WYZE_PASSWORD=""
export WYZE_KEY_ID=""
export WYZE_API_KEY=""
export SLACK_TOKEN="xoxb-1234"
export SLACK_CHANNEL="#notifications"
export DELETE_ALL_GUEST_CODES=False
export CHECK_IN_OFFSET_HOURS=-1
export CHECK_OUT_OFFSET_HOURS=1
export NON_PROD=True
export TEST_PROPERTY_NAME=""
export LOCAL_DEVELOPMENT=True
export WYZE_API_DELAY_SECONDS=5
export VAULT_URL=""
export STORAGE_ACCOUNT_NAME=""
export STORAGE_ACCOUNT_KEY=""




cd ..
cd src/

pip3 install -r requirements.txt --upgrade --force-reinstall

python3 ./lock_sync.py